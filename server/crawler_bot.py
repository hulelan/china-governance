#!/usr/bin/env python3
"""
Telegram bot that generates Chinese gov crawlers on demand.

Send a URL like "crawl https://www.fujian.gov.cn/zwgk/" and the bot will:
1. Use Claude CLI to analyze the site and generate a crawler
2. Test it with --list-only
3. Push to a GitHub branch
4. Report back with results

Runs on Singapore droplet (can reach Chinese gov sites).

Usage:
    TELEGRAM_BOT_TOKEN=... python3 server/crawler_bot.py
"""

import asyncio
import json
import logging
import os
import subprocess
import re
import tempfile
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# Only respond to this user (your Telegram user ID)
ALLOWED_USER_ID = int(os.environ.get("TELEGRAM_USER_ID", "0"))
REPO_DIR = Path("/root/china-governance")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


def run_cmd(cmd: str, cwd: str = None, timeout: int = 300) -> tuple[int, str]:
    """Run a shell command and return (returncode, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=cwd or str(REPO_DIR), timeout=timeout,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "Command timed out"


def extract_url(text: str) -> str | None:
    """Extract a URL from the message text."""
    m = re.search(r'https?://[^\s]+', text)
    if m:
        return m.group(0)
    # Try without scheme
    m = re.search(r'([\w.-]+\.gov\.cn[^\s]*)', text)
    if m:
        return "https://" + m.group(1)
    return None


def extract_site_key(url: str) -> str:
    """Generate a site_key from a URL."""
    m = re.search(r'(?:www\.)?(\w+)\.gov\.cn', url)
    if m:
        return m.group(1)
    return "unknown"


def build_claude_prompt(url: str, site_key: str) -> str:
    """Build the prompt for Claude to generate a crawler."""
    return f"""You are working in /root/china-governance. This project crawls Chinese government documents.

I need you to create a crawler for: {url}

STEPS:
1. Read crawlers/beijing.py and crawlers/shanghai.py as templates — understand the pattern
2. Read crawlers/base.py to understand store_document(), fetch(), init_db()
3. Fetch {url} and analyze:
   - How are document listings structured (HTML pattern)?
   - How does pagination work?
   - What are the section URLs?
   - Where is body text on detail pages?
4. Create crawlers/{site_key}.py following the exact same pattern as beijing.py:
   - SITE_KEY, SITE_CFG, SECTIONS dict
   - _section_url(), _get_total_pages(), _parse_listing()
   - _extract_body(), _extract_meta(), _parse_date()
   - crawl_section(), crawl_all(), main() with argparse
   - Include --section, --stats, --list-only, --db flags
5. Test with: python3 -m crawlers.{site_key} --list-only --db /tmp/test.db
6. Report: how many docs were found, which sections work

IMPORTANT:
- Use the EXACT same pattern as beijing.py / shanghai.py
- date_written must be Unix timestamp at midnight CST (UTC+8)
- Use crawlers.base.fetch() for HTTP requests (has retry + delay built in)
- If the site uses a pattern you haven't seen, check if it's similar to jpage (jiangsu.py) or gkmlpt
- DO NOT modify any existing files except to create the new crawler

IMPORTANT CONSTRAINTS:
- Do NOT use the Agent tool or spawn subagents — work directly yourself
- Do NOT spend more than 5 minutes on recon — if the site structure isn't clear after 3 fetches, make your best guess and note it in the docstring
- If a section returns 0 results, move on — don't debug endlessly

After creating and testing, report back with:
- Number of documents found per section
- Any sections that failed and why
- The command to run the crawler
"""


def _format_transcript(data: dict, site_key: str) -> str:
    """Format Claude CLI JSON output into a readable transcript."""
    lines = [f"=== Crawler Generation Transcript: {site_key} ==="]
    lines.append(f"Timestamp: {datetime.utcnow().isoformat()}")
    lines.append("")

    # Handle different JSON output structures
    messages = data.get("messages", [])
    if not messages and "result" in data:
        # Simple format — just result text
        lines.append("--- Result ---")
        lines.append(data["result"])
        return "\n".join(lines)

    for msg in messages:
        role = msg.get("role", "unknown")
        if role == "user":
            lines.append(f"--- User ---")
            content = msg.get("content", "")
            if isinstance(content, str):
                lines.append(content[:500] + ("..." if len(content) > 500 else ""))
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block["text"]
                        lines.append(text[:500] + ("..." if len(text) > 500 else ""))
        elif role == "assistant":
            lines.append(f"--- Assistant ---")
            content = msg.get("content", "")
            if isinstance(content, str):
                lines.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            lines.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tool = block.get("name", "unknown")
                            inp = json.dumps(block.get("input", {}), ensure_ascii=False)
                            if len(inp) > 200:
                                inp = inp[:200] + "..."
                            lines.append(f"  [Tool: {tool}] {inp}")
        elif role == "tool":
            lines.append(f"--- Tool Result ---")
            content = msg.get("content", "")
            if isinstance(content, str):
                if len(content) > 500:
                    lines.append(content[:500] + "...")
                else:
                    lines.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block["text"]
                        if len(text) > 500:
                            lines.append(text[:500] + "...")
                        else:
                            lines.append(text)
        lines.append("")

    # Add final result
    if "result" in data:
        lines.append("--- Final Result ---")
        lines.append(data["result"])

    return "\n".join(lines)


async def _send_transcript(update: Update, transcript_path: Path):
    """Send transcript as a document attachment."""
    try:
        if transcript_path.exists() and transcript_path.stat().st_size > 0:
            with open(transcript_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=transcript_path.name,
                    caption="Full Claude conversation transcript",
                )
    except Exception as e:
        log.warning(f"Failed to send transcript: {e}")


async def handle_crawl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a crawl request."""
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("Unauthorized.")
        return

    text = update.message.text or ""
    url = extract_url(text)
    if not url:
        await update.message.reply_text(
            "Send a URL to crawl.\n"
            "Example: /crawl https://www.fujian.gov.cn/zwgk/"
        )
        return

    site_key = extract_site_key(url)
    await update.message.reply_text(
        f"Starting crawler generation for {site_key}...\n"
        f"URL: {url}\n"
        f"This may take 2-5 minutes."
    )

    # Pull latest code
    run_cmd("git pull", cwd=str(REPO_DIR))

    # Run Claude to generate the crawler
    prompt = build_claude_prompt(url, site_key)
    log.info(f"Running Claude for {site_key}...")

    # Use --output-format json to capture full transcript
    claude_cmd = (
        f"claude -p {repr(prompt)} "
        f"--allowedTools 'Read,Write,Edit,Bash,Glob,Grep,WebFetch' "
        f"--model sonnet "
        f"--max-turns 30 "
        f"--output-format json"
    )
    code, raw_output = run_cmd(claude_cmd, timeout=1200)

    # Parse JSON output — extract the final text result and full transcript
    output = raw_output
    transcript_text = ""
    try:
        data = json.loads(raw_output)
        # The JSON output has a "result" field with the final text
        output = data.get("result", raw_output)
        # Build a readable transcript from the messages
        transcript_text = _format_transcript(data, site_key)
    except (json.JSONDecodeError, KeyError):
        # Fall back to raw output if not valid JSON
        transcript_text = raw_output

    # Save transcript to file
    transcript_dir = REPO_DIR / "logs" / "bot-transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    transcript_path = transcript_dir / f"{site_key}-{timestamp}.txt"
    transcript_path.write_text(transcript_text or output, encoding="utf-8")

    # Check if crawler was created
    crawler_path = REPO_DIR / "crawlers" / f"{site_key}.py"
    if not crawler_path.exists():
        await update.message.reply_text(
            f"Failed to generate crawler for {site_key}.\n\n"
            f"Output (last 500 chars):\n{output[-500:]}"
        )
        # Still send transcript
        await _send_transcript(update, transcript_path)
        return

    # Try to push to a branch
    branch = f"crawler/{site_key}"
    run_cmd(f"git checkout -b {branch} 2>/dev/null || git checkout {branch}")
    run_cmd(f"git add crawlers/{site_key}.py")
    run_cmd(f'git commit -m "Add {site_key} crawler (auto-generated)"')
    push_code, push_out = run_cmd(f"git push origin {branch} 2>&1")
    run_cmd("git checkout main")

    # Summarize results
    lines = output.split("\n")
    result_lines = [l for l in lines if any(kw in l for kw in ["docs", "Found", "documents", "items", "stored"])]

    summary = f"Crawler generated: crawlers/{site_key}.py\n"
    if push_code == 0:
        summary += f"Pushed to branch: {branch}\n\n"
    else:
        summary += f"Push failed (may need git auth setup)\n\n"

    if result_lines:
        summary += "Results:\n" + "\n".join(result_lines[-10:]) + "\n\n"

    summary += f"Test locally:\n"
    summary += f"  git fetch && git checkout {branch}\n"
    summary += f"  python3 -m crawlers.{site_key} --list-only\n"

    if len(summary) > 4000:
        summary = summary[:4000] + "..."

    await update.message.reply_text(summary)

    # Send transcript as a document
    await _send_transcript(update, transcript_path)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages."""
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return

    text = (update.message.text or "").strip()
    url = extract_url(text)
    if url and ".gov.cn" in text:
        # Treat as a crawl request
        await handle_crawl(update, context)
    else:
        await update.message.reply_text(
            "Send a Chinese gov URL to generate a crawler.\n"
            "Example: https://www.fujian.gov.cn/zwgk/\n\n"
            "Or use /crawl <url>"
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "China Governance Crawler Bot\n\n"
        "Send me a Chinese government website URL and I'll generate a crawler for it.\n\n"
        "Example: /crawl https://www.fujian.gov.cn/zwgk/"
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN env var")
        return
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("crawl", handle_crawl))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
