"""
Email sender using Resend API for daily meeting analysis reports.
"""

import os
from datetime import datetime
from typing import Optional
import resend
from dotenv import load_dotenv

load_dotenv()


class EmailSender:
    """Sends meeting analysis reports via Resend"""

    def __init__(self, api_key: str = None, from_email: str = None, recipient_email: str = None):
        """Initialize email sender with Resend API"""
        self.api_key = api_key or os.getenv('RESEND_API_KEY')
        if not self.api_key:
            raise ValueError("Resend API key not provided. Set RESEND_API_KEY in .env file")

        resend.api_key = self.api_key

        self.from_email = from_email or os.getenv('FROM_EMAIL')
        if not self.from_email:
            raise ValueError("FROM_EMAIL not provided. Set FROM_EMAIL in .env file")

        self.recipient_email = recipient_email or os.getenv('RECIPIENT_EMAIL')
        if not self.recipient_email:
            raise ValueError("RECIPIENT_EMAIL not provided. Set RECIPIENT_EMAIL in .env file")

    def send_analysis_report(self, report_text: str, date_range: str = None) -> bool:
        """Send meeting analysis report via email"""
        # Create subject line
        if date_range:
            subject = f"Sr. Staff Meeting Analysis - {date_range}"
        else:
            subject = f"Sr. Staff Meeting Analysis - {datetime.now().strftime('%Y-%m-%d')}"

        # Convert plain text report to HTML for better formatting
        html_content = self._format_html_email(report_text)

        try:
            params = {
                "from": self.from_email,
                "to": [self.recipient_email],
                "subject": subject,
                "html": html_content,
                "text": report_text  # Fallback plain text
            }

            email = resend.Emails.send(params)
            print(f"Email sent successfully! ID: {email.get('id', 'unknown')}")
            return True

        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

    def _format_html_email(self, report_text: str) -> str:
        """Convert plain text report to HTML with formatting"""
        # Escape HTML and preserve line breaks
        import html
        escaped_text = html.escape(report_text)

        # Convert to HTML with basic formatting
        html_lines = []
        in_section = False

        for line in escaped_text.split('\n'):
            if '=' * 40 in line:
                html_lines.append('<hr style="border: 2px solid #333; margin: 20px 0;">')
            elif '-' * 40 in line:
                html_lines.append('<hr style="border: 1px solid #666; margin: 15px 0;">')
            elif line.strip().startswith('TOP 3 STRENGTHS') or line.strip().startswith('TOP 3 AREAS') or line.strip().startswith('OVERALL ASSESSMENT'):
                html_lines.append(f'<h2 style="color: #2563eb; margin-top: 20px;">{line.strip()}</h2>')
            elif line.strip().startswith('Meeting: '):
                html_lines.append(f'<h3 style="color: #1e40af; margin-top: 15px;">{line.strip()}</h3>')
            elif line.strip().startswith('SR. STAFF LEVEL') or line.strip().startswith('INDIVIDUAL MEETING'):
                html_lines.append(f'<h1 style="color: #1e3a8a;">{line.strip()}</h1>')
            elif line.strip().startswith(('1.', '2.', '3.', '-')):
                html_lines.append(f'<p style="margin-left: 20px; line-height: 1.6;">{line.strip()}</p>')
            elif line.strip():
                html_lines.append(f'<p style="line-height: 1.6;">{line.strip()}</p>')
            else:
                html_lines.append('<br>')

        html_body = '\n'.join(html_lines)

        # Wrap in full HTML template
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meeting Analysis Report</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
             max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f9fafb; color: #111827;">
    <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        {html_body}
    </div>
    <div style="text-align: center; margin-top: 20px; color: #6b7280; font-size: 12px;">
        <p>This report was generated automatically by your Granola Meeting Analyzer</p>
    </div>
</body>
</html>
        """

        return html_template

    def send_test_email(self) -> bool:
        """Send a test email to verify configuration"""
        test_message = """
This is a test email from your Granola Meeting Analyzer.

If you received this email, your email configuration is working correctly!

You can now run the analyzer to receive daily meeting performance reports.
        """

        try:
            params = {
                "from": self.from_email,
                "to": [self.recipient_email],
                "subject": "Test Email - Granola Meeting Analyzer",
                "text": test_message
            }

            email = resend.Emails.send(params)
            print(f"Test email sent successfully! ID: {email.get('id', 'unknown')}")
            return True

        except Exception as e:
            print(f"Failed to send test email: {e}")
            return False
