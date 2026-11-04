import logging
import os
import json
from telegram import Bot
from telegram.error import TelegramError
import asyncio

from storage import load_manifest
from job_schema import select_recent_jobs

# ✅ Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ Load from GitHub Secrets via environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_CHAT_ID = os.environ.get("TELEGRAM_GROUP_CHAT_ID")

def format_job_message(job):
    """
    Formats a single job dictionary into a human-readable message.
    """
    message = "✨ *New Sarkari Job Alert!* ✨\n\n"
    message += f"📌 *{job.get('title', 'N/A')}*\n"
    org = job.get('organization') or job.get('department') or job.get('source') or 'N/A'
    message += f"🏢 *Organization:* {org}\n"
    message += f"🏷️ *Category:* {job.get('category', 'General')}\n\n"

    desc = job.get('description', 'N/A')
    if len(desc) > 200:
        desc = desc[:197] + "..."
    message += f"📝 *Details:* {desc}\n\n"

    if job.get('important_dates'):
        message += "📅 *Important Dates:*\n"
        for key, value in job['important_dates'].items():
            message += f"  🔹 {key.replace('_', ' ').title()}: {value}\n"
        message += "\n"

    if job.get('skills'):
        message += f"🎓 *Skills:* {', '.join(job['skills'])}\n\n"

    message += f"🔗 *Apply Here:* [Click Here to Apply]({job.get('url', 'N/A')})\n"
    return message

async def send_telegram_message(chat_id, message):
    """
    Sends a message to the specified Telegram chat ID.
    """
    if not BOT_TOKEN or not chat_id:
        logger.error("Missing BOT_TOKEN or CHAT_ID environment variables.")
        return

    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
        logger.info(f"✅ Message sent to chat ID {chat_id}")
    except TelegramError as e:
        logger.error(f"❌ Failed to send message to {chat_id}: {e}")

async def notify_new_jobs():
    logger.info("📢 Starting Telegram notification for new jobs...")
    manifest = load_manifest()
    # Only jobs first recorded recently (see select_recent_jobs):
    # the full manifest must never be blasted on every run.
    jobs_to_notify = select_recent_jobs(manifest.get('jobs', []))

    if not jobs_to_notify:
        logger.info("ℹ️ No new jobs found to notify.")
        return

    tasks = []
    for job in jobs_to_notify:
        message = format_job_message(job)
        tasks.append(send_telegram_message(TELEGRAM_GROUP_CHAT_ID, message))

    await asyncio.gather(*tasks)

    logger.info(f"📨 Notified about {len(jobs_to_notify)} jobs.")

async def main():
    await notify_new_jobs()

if __name__ == "__main__":
    asyncio.run(main())
