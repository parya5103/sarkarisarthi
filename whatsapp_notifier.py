import logging
import os
import json
import asyncio
import requests

from storage import load_manifest
from job_schema import select_recent_jobs

# ✅ Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ Load from environment variables
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
WHATSAPP_RECIPIENT_ID = os.environ.get("WHATSAPP_RECIPIENT_ID", "") # Could be a group or phone number

def format_job_message(job):
    """
    Formats a single job dictionary into a WhatsApp-friendly message.
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

    message += f"🔗 *Apply Here:* {job.get('url', 'N/A')}\n"
    return message

async def send_whatsapp_message(message):
    """
    Sends a message via the Meta WhatsApp Graph API.
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID or not WHATSAPP_RECIPIENT_ID:
        logger.warning("⚠️ Missing WhatsApp credentials (WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, or WHATSAPP_RECIPIENT_ID). Skipping WhatsApp notification.")
        return False

    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_RECIPIENT_ID,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": message
        }
    }

    try:
        response = await asyncio.to_thread(requests.post, url, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"✅ WhatsApp message sent to {WHATSAPP_RECIPIENT_ID}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to send WhatsApp message: {e}")
        if response.text:
            logger.error(f"Response: {response.text}")
        return False

async def notify_new_jobs():
    logger.info("📢 Starting WhatsApp notification for new jobs...")

    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID or not WHATSAPP_RECIPIENT_ID:
        logger.info("ℹ️ WhatsApp credentials not configured. Skipping WhatsApp alerts.")
        return

    manifest = load_manifest()
    # Only jobs first recorded recently (see select_recent_jobs):
    # the full manifest must never be blasted on every run.
    jobs_to_notify = select_recent_jobs(manifest.get('jobs', []))

    if not jobs_to_notify:
        logger.info("ℹ️ No new jobs found to notify on WhatsApp.")
        return

    for job in jobs_to_notify:
        message = format_job_message(job)
        await send_whatsapp_message(message)
        # Add a small delay to avoid rate limits
        await asyncio.sleep(1)

    logger.info(f"📨 Notified about {len(jobs_to_notify)} jobs on WhatsApp.")

async def main():
    await notify_new_jobs()

if __name__ == "__main__":
    asyncio.run(main())
