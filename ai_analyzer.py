"""
AI-powered meeting analysis using GPT-5
"""

import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class MeetingAnalyzer:
    """Analyzes meeting transcripts using GPT-5"""

    DEFAULT_PROMPT = """You are an executive coach analyzing meeting effectiveness and productivity.

Focus on these key areas:
1. **Meeting Effectiveness** - Was this meeting necessary? Did it achieve its goals?
2. **Cost & Time** - Given the people involved, was this a good use of everyone's time?
3. **Strategic Thinking** - Evidence of long-term planning, risk assessment, and business impact
4. **Action Items** - Clear outcomes, decisions, and next steps
5. **Communication** - Clarity, influence, and stakeholder management
6. **Areas for Improvement** - Specific, actionable suggestions"""

    def __init__(self, api_key: str = None):
        """Initialize the analyzer with OpenAI API key"""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY in .env file")

        self.client = OpenAI(api_key=self.api_key)
        self.name = os.getenv('NAME', 'You')
        self.people = os.getenv('PEOPLE', '')
        self.custom_prompt = self._load_custom_prompt()

    def _load_custom_prompt(self) -> Optional[str]:
        """Load custom prompt from .prompt file if it exists"""
        # Use absolute path based on script location for cron compatibility
        script_dir = Path(__file__).parent.absolute()
        prompt_file = script_dir / '.prompt'
        if prompt_file.exists():
            try:
                return prompt_file.read_text().strip()
            except Exception as e:
                print(f"Warning: Could not load .prompt file: {e}")
        return None

    def analyze_meetings(self, meetings: List[Dict], previous_feedback: str = None) -> Dict:
        """Analyze multiple meetings and generate comprehensive feedback"""
        if not meetings:
            return {
                'summary': 'No meetings found in the specified date range.',
                'feedback': 'No meetings to analyze.',
                'date': datetime.now().strftime("%Y-%m-%d")
            }

        # Combine all meeting transcripts
        all_meetings_text = ""
        for meeting in meetings:
            title = meeting.get('title', 'Untitled Meeting')
            created_at = meeting.get('created_at', 'Unknown date')
            transcript_text = meeting.get('transcript_text', '')

            all_meetings_text += f"\n{'='*80}\n"
            all_meetings_text += f"Meeting: {title}\n"
            all_meetings_text += f"Date: {created_at}\n"
            all_meetings_text += f"{'='*80}\n"
            all_meetings_text += transcript_text + "\n\n"

        # Use custom prompt if available, otherwise use default
        base_prompt = self.custom_prompt if self.custom_prompt else self.DEFAULT_PROMPT

        # Build context
        context_parts = []

        if self.people:
            context_parts.append(f"People involved: {self.people}")

        if previous_feedback:
            context_parts.append(f"Previous feedback for context:\n{previous_feedback}")

        context = "\n\n".join(context_parts) if context_parts else ""

        # Generate analysis prompt
        prompt = f"""{base_prompt}

{context}

Analyze today's meetings and provide actionable feedback.

Guidelines:
- Exclude non-professional meetings (doctors appointments, personal calls, etc.)
- Skip meetings without useful data
- Be specific with examples
- Focus on actionable improvements
- Don't force insights if insufficient information

TODAY'S MEETINGS:
{all_meetings_text}

Provide comprehensive feedback with:
- STRENGTHS (what went well)
- AREAS FOR IMPROVEMENT (specific suggestions)
- ACTION ITEMS (what to do next)
- OVERALL ASSESSMENT (summary)"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-5",  # Using GPT-5 (released August 2025)
                messages=[
                    {"role": "system", "content": "You are an expert executive coach specializing in engineering leadership development."},
                    {"role": "user", "content": prompt}
                ],
            )

            feedback = response.choices[0].message.content

            return {
                'summary': f"Analyzed {len(meetings)} meetings from today",
                'feedback': feedback,
                'date': datetime.now().strftime("%Y-%m-%d"),
                'num_meetings': len(meetings)
            }

        except Exception as e:
            return {
                'summary': f"Failed to analyze {len(meetings)} meetings",
                'feedback': f'Analysis failed: {str(e)}',
                'date': datetime.now().strftime("%Y-%m-%d"),
                'num_meetings': len(meetings)
            }

    def format_report(self, analysis_result: Dict) -> str:
        """Format analysis results as a readable report"""
        report = []
        report.append("=" * 80)
        report.append(f"DAILY MEETING FEEDBACK - {analysis_result.get('date', 'N/A')}")
        report.append("=" * 80)
        report.append("")
        report.append(f"Summary: {analysis_result.get('summary', 'No summary')}")
        report.append("")
        report.append("=" * 80)
        report.append("")
        report.append(analysis_result.get('feedback', 'No feedback available'))
        report.append("")
        report.append("=" * 80)

        return "\n".join(report)
