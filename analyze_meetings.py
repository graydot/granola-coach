#!/usr/bin/env python3
"""
Granola Meeting Analyzer

Automatically fetches meeting transcriptions from Granola,
analyzes them using OpenAI GPT-4 for Sr. Staff level performance,
and sends a daily email summary.
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

from granola_client import GranolaClient
from ai_analyzer import MeetingAnalyzer
from email_sender import EmailSender


# Get absolute paths based on script location for cron compatibility
SCRIPT_DIR = Path(__file__).parent.absolute()
STATE_FILE = str(SCRIPT_DIR / ".analysis_state.json")
LOGS_DIR = str(SCRIPT_DIR / "logs")
FEEDBACK_DIR = str(SCRIPT_DIR / "feedback")
CURRENT_FEEDBACK_FILE = str(SCRIPT_DIR / "feedback" / "current.txt")


class MeetingAnalysisRunner:
    """Main orchestrator for the meeting analysis workflow"""

    def __init__(self):
        self.granola_client = GranolaClient()
        self.analyzer = MeetingAnalyzer()
        self.email_sender = EmailSender()
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load analysis state from file"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load state file: {e}")
                return {"processed_documents": []}
        return {"processed_documents": []}

    def _save_state(self):
        """Save analysis state to file"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save state file: {e}")

    def _mark_as_processed(self, document_id: str):
        """Mark a document as processed"""
        if document_id not in self.state["processed_documents"]:
            self.state["processed_documents"].append(document_id)
            self._save_state()

    def _is_processed(self, document_id: str) -> bool:
        """Check if a document has been processed"""
        return document_id in self.state.get("processed_documents", [])

    def fetch_meetings(self, start_date: datetime, end_date: datetime, new_only: bool = False) -> List[Dict]:
        """Fetch meetings from Granola API"""
        print(f"Fetching meetings from {start_date.date()} to {end_date.date()}...")

        meetings = self.granola_client.get_meetings_in_date_range(start_date, end_date)

        # Filter out already processed meetings if new_only flag is set
        if new_only:
            original_count = len(meetings)
            meetings = [m for m in meetings if not self._is_processed(m['id'])]
            filtered_count = original_count - len(meetings)
            if filtered_count > 0:
                print(f"Filtered out {filtered_count} already-processed meetings")

        print(f"Found {len(meetings)} meetings to analyze")
        return meetings

    def prepare_meetings_for_analysis(self, meetings: List[Dict]) -> List[Dict]:
        """Prepare meetings by formatting transcripts"""
        prepared = []
        for meeting in meetings:
            transcript_text = self.granola_client.format_transcript_text(
                meeting.get('transcript', [])
            )
            meeting['transcript_text'] = transcript_text
            prepared.append(meeting)
        return prepared

    def _load_previous_feedback(self) -> Optional[str]:
        """Load previous week's feedback for context"""
        try:
            # Get all feedback files from the past 7 days
            feedback_files = []
            if Path(FEEDBACK_DIR).exists():
                for f in Path(FEEDBACK_DIR).glob("feedback_*.txt"):
                    # Extract date from filename (format: feedback_YYYYMMDD.txt)
                    try:
                        date_str = f.stem.split('_')[1]
                        file_date = datetime.strptime(date_str, "%Y%m%d")
                        days_ago = (datetime.now() - file_date).days
                        if 1 <= days_ago <= 7:  # Past week, excluding today
                            feedback_files.append((file_date, f))
                    except:
                        continue

            if not feedback_files:
                return None

            # Sort by date and get recent feedback
            feedback_files.sort(reverse=True)
            combined_feedback = "\n\n".join([
                f"[{date.strftime('%Y-%m-%d')}]\n{open(file).read()}"
                for date, file in feedback_files[:3]  # Last 3 days of feedback
            ])

            return combined_feedback if combined_feedback else None

        except Exception as e:
            print(f"Warning: Could not load previous feedback: {e}")
            return None

    def _save_feedback(self, feedback_text: str):
        """Save feedback with versioning"""
        Path(FEEDBACK_DIR).mkdir(exist_ok=True)

        # Create dated feedback file
        today = datetime.now().strftime("%Y%m%d")
        feedback_file = f"{FEEDBACK_DIR}/feedback_{today}.txt"

        # If file exists, back it up
        if Path(feedback_file).exists():
            backup_file = f"{FEEDBACK_DIR}/feedback_{today}_backup_{datetime.now().strftime('%H%M%S')}.txt"
            Path(feedback_file).rename(backup_file)
            print(f"✓ Previous feedback backed up to: {backup_file}")

        # Save new feedback
        with open(feedback_file, 'w') as f:
            f.write(feedback_text)

        # Also save as "current" for easy access
        with open(CURRENT_FEEDBACK_FILE, 'w') as f:
            f.write(feedback_text)

        print(f"✓ Feedback saved to: {feedback_file}")

    def analyze_and_report(self, meetings: List[Dict], date_range_str: str, send_email: bool = True) -> str:
        """Analyze meetings and generate report"""
        if not meetings:
            print("No meetings to analyze")
            return "No meetings found in the specified date range."

        # Load previous week's feedback for context
        previous_feedback = self._load_previous_feedback()
        if previous_feedback:
            print("✓ Loaded previous week's feedback for context")

        print(f"Analyzing {len(meetings)} meetings with GPT-4o...")
        analysis_result = self.analyzer.analyze_meetings(meetings, previous_feedback=previous_feedback)

        # Format report
        report = self.analyzer.format_report(analysis_result)

        # Save to feedback directory
        self._save_feedback(analysis_result.get('feedback', ''))

        # Save to logs directory
        self._save_report_to_log(report, date_range_str, analysis_result)

        # Print to console
        print("\n" + report)

        # Send email if requested
        if send_email:
            print("\nSending email report...")
            success = self.email_sender.send_analysis_report(report, date_range_str)
            if success:
                print("Email sent successfully!")
            else:
                print("Failed to send email. Report saved to feedback and logs directory.")

        # Mark all meetings as processed
        for meeting in meetings:
            self._mark_as_processed(meeting['id'])

        return report

    def _save_report_to_log(self, report_text: str, date_range_str: str, analysis_result: Dict):
        """Save analysis report to logs directory"""
        # Create logs directory if it doesn't exist
        Path(LOGS_DIR).mkdir(exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_date_range = date_range_str.replace(" ", "_").replace("/", "-")

        # Save text report
        text_filename = f"{LOGS_DIR}/analysis_{timestamp}_{safe_date_range}.txt"
        with open(text_filename, 'w') as f:
            f.write(report_text)

        # Save JSON data for potential later processing
        json_filename = f"{LOGS_DIR}/analysis_{timestamp}_{safe_date_range}.json"
        with open(json_filename, 'w') as f:
            json.dump(analysis_result, f, indent=2)

        print(f"\n✓ Report saved to: {text_filename}")
        print(f"✓ JSON data saved to: {json_filename}")

    def run(self, args):
        """Main execution flow"""
        # Calculate date range
        if args.start and args.end:
            start_date = datetime.strptime(args.start, "%Y-%m-%d")
            end_date = datetime.strptime(args.end, "%Y-%m-%d")
            date_range_str = f"{args.start} to {args.end}"
        elif args.days:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)
            date_range_str = f"Last {args.days} day(s)"
        else:
            # Default to today only
            end_date = datetime.now()
            start_date = end_date.replace(hour=0, minute=0, second=0)
            date_range_str = f"Today ({datetime.now().strftime('%Y-%m-%d')})"

        # Ensure end_date includes the full day
        end_date = end_date.replace(hour=23, minute=59, second=59)

        print(f"Analyzing meetings for: {date_range_str}")
        print("-" * 80)

        try:
            # Fetch meetings
            meetings = self.fetch_meetings(start_date, end_date, new_only=args.new_only)

            if not meetings:
                print("No meetings found. Nothing to analyze.")
                return

            # Prepare meetings
            prepared_meetings = self.prepare_meetings_for_analysis(meetings)

            # Analyze and report
            self.analyze_and_report(
                prepared_meetings,
                date_range_str,
                send_email=not args.no_email
            )

        except Exception as e:
            print(f"Error during analysis: {e}")
            import traceback
            traceback.print_exc()
            return


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Granola meeting transcriptions for Sr. Staff level performance"
    )

    # Date range options (mutually exclusive)
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        "--days",
        type=int,
        help="Analyze meetings from the last N days (e.g., --days 7)"
    )
    date_group.add_argument(
        "--start",
        type=str,
        help="Start date in YYYY-MM-DD format (requires --end)"
    )

    parser.add_argument(
        "--end",
        type=str,
        help="End date in YYYY-MM-DD format (requires --start)"
    )

    # Processing options
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Only analyze meetings that haven't been processed before"
    )

    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Don't send email, just print to console"
    )

    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Send a test email to verify configuration"
    )

    args = parser.parse_args()

    # Validate date arguments
    if args.start and not args.end:
        parser.error("--start requires --end")
    if args.end and not args.start:
        parser.error("--end requires --start")

    # Handle test email mode
    if args.test_email:
        print("Sending test email...")
        try:
            sender = EmailSender()
            success = sender.send_test_email()
            if success:
                print("Test email sent successfully! Check your inbox.")
            else:
                print("Failed to send test email. Check your configuration.")
        except Exception as e:
            print(f"Error: {e}")
        return

    # Run analysis
    runner = MeetingAnalysisRunner()
    runner.run(args)


if __name__ == "__main__":
    main()
