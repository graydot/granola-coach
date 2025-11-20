# Granola Meeting Analyzer

AI-powered meeting feedback using GPT-5. Analyzes your Granola meetings daily at 5 PM.

## Install

```bash
git clone https://github.com/yourusername/granola-processor.git
cd granola-processor
uv sync
cp .env.example .env
```

Edit `.env` with your keys:
```bash
OPENAI_API_KEY=sk-your-key
RESEND_API_KEY=re_your-key
FROM_EMAIL=onboarding@resend.dev
RECIPIENT_EMAIL=your@email.com
NAME=Your Name
PEOPLE=Alice is my manager, Bob is a colleague
```

Run installer:
```bash
./install.sh
```

Done! Runs daily at 5 PM.

## Manual Run

```bash
# Today
uv run python analyze_meetings.py

# Last 7 days
uv run python analyze_meetings.py --days 7

# No email
uv run python analyze_meetings.py --no-email
```

## Customize Analysis

Edit `.prompt` file to change what the AI focuses on:

```bash
nano .prompt
```

See `.prompt.example` for ideas.

## Tests

Run tests to verify everything works:

```bash
uv run pytest
```

## Uninstall

```bash
./uninstall.sh
```

Removes cron job. Keeps your data.

## Troubleshooting

**Cron not running?**
```bash
crontab -l | grep granola
tail -f logs/cron.log
```

**No meetings?**
- Check Granola app is logged in
- Try: `uv run python analyze_meetings.py --days 7`

**Email not sending?**
- Use `FROM_EMAIL=onboarding@resend.dev` for testing
- Check your Resend API key

**API errors?**
- Verify OpenAI key and credits
- Check GPT-5 access

## Files

- `feedback/current.txt` - Latest analysis
- `logs/cron.log` - Cron execution log
- `.prompt` - Your custom analysis prompt

## Requirements

- macOS with Granola app
- OpenAI API key (GPT-5)
- Resend account (free)
- uv package manager

## Cost

~$3-8/month for OpenAI (5-10 meetings/week). Resend is free.

## License

MIT
