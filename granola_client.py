"""
Granola API Client for fetching meeting transcriptions.
Uses reverse-engineered API endpoints.
"""

import json
import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class GranolaClient:
    """Client for interacting with Granola API"""

    CREDENTIALS_PATH = os.path.expanduser("~/Library/Application Support/Granola/supabase.json")
    API_BASE = "https://api.granola.ai"
    WORKOS_AUTH_URL = "https://api.workos.com/user_management/authenticate"

    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.client_id = None
        self._load_credentials()

    def _load_credentials(self):
        """Load credentials from Granola's local storage"""
        try:
            with open(self.CREDENTIALS_PATH, 'r') as f:
                creds = json.load(f)

                # Extract tokens from supabase.json structure
                # Try workos_tokens format (current Granola format)
                if 'workos_tokens' in creds:
                    workos_tokens = json.loads(creds['workos_tokens'])
                    self.access_token = workos_tokens.get('access_token')
                    self.refresh_token = workos_tokens.get('refresh_token')
                # Try currentSession format (older format)
                elif 'currentSession' in creds:
                    session = creds['currentSession']
                    self.access_token = session.get('access_token')
                    self.refresh_token = session.get('refresh_token')
                # Try direct format
                elif 'access_token' in creds:
                    self.access_token = creds.get('access_token')
                    self.refresh_token = creds.get('refresh_token')

                self.client_id = creds.get('client_id', 'client_01JARHTH2HQ6D64XDAEVXFNQ44')

        except FileNotFoundError:
            raise Exception(f"Granola credentials not found at {self.CREDENTIALS_PATH}. "
                          "Please make sure Granola app is installed and you're logged in.")
        except json.JSONDecodeError:
            raise Exception("Failed to parse Granola credentials file.")

    def _refresh_access_token(self):
        """Refresh the access token using WorkOS"""
        if not self.refresh_token:
            raise Exception("No refresh token available")

        payload = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        try:
            response = requests.post(self.WORKOS_AUTH_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            # Update tokens (refresh tokens are one-time use)
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']

            # Save updated refresh token for next time
            self._save_refresh_token()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to refresh access token: {e}")

    def _save_refresh_token(self):
        """Save updated refresh token back to credentials file"""
        try:
            with open(self.CREDENTIALS_PATH, 'r') as f:
                creds = json.load(f)

            # Save in the same format we found it
            if 'workos_tokens' in creds:
                workos_tokens = json.loads(creds['workos_tokens'])
                workos_tokens['access_token'] = self.access_token
                workos_tokens['refresh_token'] = self.refresh_token
                creds['workos_tokens'] = json.dumps(workos_tokens)
            elif 'currentSession' in creds:
                creds['currentSession']['access_token'] = self.access_token
                creds['currentSession']['refresh_token'] = self.refresh_token
            else:
                creds['access_token'] = self.access_token
                creds['refresh_token'] = self.refresh_token

            with open(self.CREDENTIALS_PATH, 'w') as f:
                json.dump(creds, f, indent=2)

        except Exception as e:
            print(f"Warning: Failed to save updated refresh token: {e}")

    def _make_request(self, endpoint: str, payload: dict, retry_auth: bool = True) -> dict:
        """Make authenticated request to Granola API"""
        url = f"{self.API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "Granola/5.354.0",
            "X-Client-Version": "5.354.0"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)

            # If unauthorized and we haven't retried yet, refresh token and retry
            if response.status_code == 401 and retry_auth:
                self._refresh_access_token()
                return self._make_request(endpoint, payload, retry_auth=False)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

    def get_documents(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Fetch documents from Granola"""
        payload = {
            "limit": limit,
            "offset": offset,
            "include_last_viewed_panel": True
        }

        response = self._make_request("/v2/get-documents", payload)
        return response.get('docs', [])

    def get_document_transcript(self, document_id: str) -> List[Dict]:
        """Fetch raw transcript for a specific document"""
        payload = {"document_id": document_id}

        response = self._make_request("/v1/get-document-transcript", payload)
        # API returns a list directly, not a dict with 'utterances'
        return response if isinstance(response, list) else []

    def get_meetings_in_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch all meetings within a date range"""
        from datetime import timezone

        # Make dates timezone-aware if they aren't already
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        all_meetings = []
        offset = 0
        limit = 100

        while True:
            documents = self.get_documents(limit=limit, offset=offset)

            if not documents:
                break

            for doc in documents:
                # Parse document creation date
                created_at = datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00'))

                # Filter by date range
                if start_date <= created_at <= end_date:
                    # Fetch transcript for this document
                    try:
                        transcript = self.get_document_transcript(doc['id'])
                        doc['transcript'] = transcript
                        all_meetings.append(doc)
                    except Exception as e:
                        print(f"Warning: Failed to fetch transcript for {doc.get('title', 'Unknown')}: {e}")
                        continue

            # If we got fewer documents than requested, we've reached the end
            if len(documents) < limit:
                break

            offset += limit

        return all_meetings

    def format_transcript_text(self, transcript: List[Dict]) -> str:
        """Convert transcript utterances to readable text"""
        if not transcript:
            return ""

        lines = []
        for utterance in transcript:
            speaker = utterance.get('source', 'Unknown')
            text = utterance.get('text', '')
            lines.append(f"{speaker}: {text}")

        return "\n".join(lines)
