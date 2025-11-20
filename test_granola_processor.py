"""
Tests for Granola Meeting Analyzer

Focuses on critical functionality and regression tests for bugs we encountered.
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import tempfile
import os

from granola_client import GranolaClient
from ai_analyzer import MeetingAnalyzer
from analyze_meetings import MeetingAnalysisRunner


class TestGranolaClient:
    """Test credential loading and API response parsing - these had real bugs"""

    def test_credentials_parsing_nested_json(self):
        """Regression test: credentials are stored as nested JSON string"""
        # This was a real bug - workos_tokens is a JSON string, not a dict
        mock_credentials = {
            "workos_tokens": json.dumps({
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token"
            })
        }

        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_credentials))):
                client = GranolaClient()
                assert client.access_token == "test_access_token"
                assert client.refresh_token == "test_refresh_token"

    def test_api_response_uses_docs_key(self):
        """Regression test: API returns 'docs' not 'documents'"""
        # This was a real bug - we used wrong key initially
        client = GranolaClient()

        mock_response = {
            "docs": [
                {"id": "1", "title": "Meeting 1"},
                {"id": "2", "title": "Meeting 2"}
            ]
        }

        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.get_documents()
            assert len(result) == 2
            assert result[0]["title"] == "Meeting 1"

    def test_transcript_returns_list_directly(self):
        """Regression test: transcript API returns list, not dict with 'utterances'"""
        # This was a real bug - we tried to access .get('utterances')
        client = GranolaClient()

        mock_transcript = [
            {"source": "Alice", "text": "Hello"},
            {"source": "Bob", "text": "Hi"}
        ]

        with patch.object(client, '_make_request', return_value=mock_transcript):
            result = client.get_document_transcript("test_id")
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["source"] == "Alice"

    def test_date_filtering_timezone_aware(self):
        """Regression test: timezone-aware datetime comparison"""
        # This was a real bug - comparing naive and aware datetimes
        client = GranolaClient()

        # Use consistent time reference
        base_time = datetime.now(timezone.utc)
        yesterday = base_time - timedelta(days=1)

        mock_docs = [
            {"id": "1", "created_at": base_time.isoformat(), "title": "Meeting 1"},
            {"id": "2", "created_at": yesterday.isoformat(), "title": "Meeting 2"}
        ]

        mock_transcript = [{"source": "Test", "text": "Test"}]

        with patch.object(client, 'get_documents', return_value=mock_docs):
            with patch.object(client, 'get_document_transcript', return_value=mock_transcript):
                # Should not raise timezone comparison error
                # Use slightly wider range to account for timing
                start = base_time - timedelta(days=2)
                end = base_time + timedelta(hours=1)
                result = client.get_meetings_in_date_range(start, end)
                assert len(result) == 2

    def test_transcript_formatting(self):
        """Test transcript text formatting works correctly"""
        client = GranolaClient()

        transcript = [
            {"source": "Alice", "text": "First line"},
            {"source": "Bob", "text": "Second line"},
            {"source": "Alice", "text": "Third line"}
        ]

        formatted = client.format_transcript_text(transcript)

        assert "Alice: First line" in formatted
        assert "Bob: Second line" in formatted
        assert "Alice: Third line" in formatted


class TestMeetingAnalyzer:
    """Test AI analyzer functionality"""

    def test_custom_prompt_loading(self):
        """Test that custom .prompt file overrides default"""
        custom_prompt = "You are a custom coach analyzing meetings."

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / '.prompt'
            prompt_file.write_text(custom_prompt)

            # Mock the script directory to point to our temp dir
            with patch('ai_analyzer.Path') as mock_path:
                mock_path.return_value.parent.absolute.return_value = Path(tmpdir)
                mock_path.return_value.__truediv__ = lambda self, other: Path(tmpdir) / other
                (Path(tmpdir) / '.prompt').write_text(custom_prompt)

                with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
                    analyzer = MeetingAnalyzer()
                    # The custom prompt should be loaded
                    assert custom_prompt in str(analyzer.custom_prompt or '')

    def test_no_meetings_returns_empty_feedback(self):
        """Test handling of empty meeting list"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            analyzer = MeetingAnalyzer()
            result = analyzer.analyze_meetings([])

            assert 'No meetings' in result['summary']
            assert result['feedback'] == 'No meetings to analyze.'


class TestMeetingAnalysisRunner:
    """Test the main orchestration logic"""

    def test_state_management_tracks_processed_docs(self):
        """Test that processed documents are tracked and persisted"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / '.analysis_state.json'

            # Create initial state
            initial_state = {"processed_documents": ["doc1", "doc2"]}
            state_file.write_text(json.dumps(initial_state))

            # Mock the global STATE_FILE to use our temp file
            with patch('analyze_meetings.STATE_FILE', str(state_file)):
                runner = MeetingAnalysisRunner()

                # Should load existing state
                assert "doc1" in runner.state["processed_documents"]
                assert "doc2" in runner.state["processed_documents"]

                # Mark new document as processed
                runner._mark_as_processed("doc3")

                # Should be persisted
                saved_state = json.loads(state_file.read_text())
                assert "doc3" in saved_state["processed_documents"]

    def test_feedback_versioning_with_dated_files(self):
        """Test that feedback is saved with dates and current.txt"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_dir = Path(tmpdir) / 'feedback'
            feedback_dir.mkdir()

            with patch('analyze_meetings.FEEDBACK_DIR', str(feedback_dir)):
                with patch('analyze_meetings.CURRENT_FEEDBACK_FILE', str(feedback_dir / 'current.txt')):
                    runner = MeetingAnalysisRunner()

                    feedback_text = "This is test feedback"
                    runner._save_feedback(feedback_text)

                    # Check dated file exists
                    today = datetime.now().strftime("%Y%m%d")
                    dated_file = feedback_dir / f"feedback_{today}.txt"
                    assert dated_file.exists()
                    assert dated_file.read_text() == feedback_text

                    # Check current.txt exists
                    current_file = feedback_dir / 'current.txt'
                    assert current_file.exists()
                    assert current_file.read_text() == feedback_text

    def test_feedback_backup_on_multiple_runs(self):
        """Test that running multiple times in a day creates backups"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_dir = Path(tmpdir) / 'feedback'
            feedback_dir.mkdir()

            # Create initial feedback for today
            today = datetime.now().strftime("%Y%m%d")
            initial_file = feedback_dir / f"feedback_{today}.txt"
            initial_file.write_text("First run")

            with patch('analyze_meetings.FEEDBACK_DIR', str(feedback_dir)):
                with patch('analyze_meetings.CURRENT_FEEDBACK_FILE', str(feedback_dir / 'current.txt')):
                    runner = MeetingAnalysisRunner()

                    # Save new feedback
                    runner._save_feedback("Second run")

                    # Check backup was created
                    backup_files = list(feedback_dir.glob(f"feedback_{today}_backup_*.txt"))
                    assert len(backup_files) == 1
                    assert backup_files[0].read_text() == "First run"

                    # Check new file has new content
                    assert initial_file.read_text() == "Second run"

    def test_previous_feedback_loading(self):
        """Test that previous week's feedback is loaded for context"""
        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_dir = Path(tmpdir)

            # Create feedback files from different days
            today = datetime.now()
            for days_ago in [1, 2, 3, 8]:  # 8 days should be excluded
                date = today - timedelta(days=days_ago)
                date_str = date.strftime("%Y%m%d")
                feedback_file = feedback_dir / f"feedback_{date_str}.txt"
                feedback_file.write_text(f"Feedback from {days_ago} days ago")

            with patch('analyze_meetings.FEEDBACK_DIR', str(feedback_dir)):
                runner = MeetingAnalysisRunner()
                previous = runner._load_previous_feedback()

                # Should include 1, 2, 3 days ago (not 8)
                assert previous is not None
                assert "1 days ago" in previous
                assert "2 days ago" in previous
                assert "3 days ago" in previous
                assert "8 days ago" not in previous


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
