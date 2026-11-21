"""Send newly published PikaNews headlines to the existing Telegram updates chat.

The workflow cache stores sent article IDs. The first run seeds the cache and
does not blast historical headlines. Only articles with a verified publication
timestamp and an original source URL are eligible.
"""
import html
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

logger = logging.getLogger("pikanews_telegram")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FEED_URL = "https://raw.githubusercontent.com/parya5103/PikaNews/main/news_json/latest.json"
STATE_PATH = Path("state/pikanews_notified_ids.json")
MAX_AGE_HOURS = 24
MAX_PER_RUN = 5


def parse_published_at(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def select_new_articles(articles, seen_ids, now=None, max_age_hours=MAX_AGE_HOURS):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=max_age_hours)
    selected = []
    for article in articles if isinstance(articles, list) else []:
        if not isinstance(article, dict):
            continue
        article_id = str(article.get("id") or "").strip()
        title = str(article.get("title") or "").strip()
        url = str(article.get("url") or "").strip()
        published = parse_published_at(article.get("published_at"))
        if (not article_id or article_id in seen_ids or not title or
                not url.startswith("https://") or article.get("date_unverified") is True or
                not published or published < cutoff or published > now.astimezone(timezone.utc)):
            continue
        selected.append(article)
    selected.sort(key=lambda item: parse_published_at(item.get("published_at")) or cutoff,
                  reverse=True)
    return selected


def format_news_message(article):
    title = html.escape(str(article.get("title") or "News update"))
    source = html.escape(str(article.get("source") or "PikaNews"))
    category = html.escape(str(article.get("category") or "News").title())
    summary = html.escape(str(article.get("summary") or "")[:350])
    url = html.escape(str(article.get("url") or ""), quote=True)
    lines = ["📰 <b>New PikaNews Update</b>", "", f"<b>{title}</b>",
             f"🗂️ {category} · {source}"]
    if summary:
        lines.extend(["", summary])
    lines.extend(["", f'<a href="{url}">Read original report</a>',
                  '<a href="https://gogocompany.in/pikanews/">Open PikaNews</a>'])
    return "\n".join(lines)


def load_seen_ids():
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return set(payload.get("ids", [])) if isinstance(payload, dict) else set()
    except (OSError, ValueError, TypeError):
        return set()


def save_seen_ids(ids):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"ids": list(ids)[-1000:]}, indent=2), encoding="utf-8")


def send_telegram_message(token, chat_id, message):
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML",
              "disable_web_page_preview": False},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError("Telegram API rejected the news message")
    return True


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Telegram bot credentials are missing from repository secrets")

    response = requests.get(FEED_URL, headers={"User-Agent": "GoGoCompany-NewsAlerts/1.0"},
                            timeout=30)
    response.raise_for_status()
    articles = response.json()
    seen = load_seen_ids()

    # First run is a quiet baseline: do not flood the public channel with
    # historical stories when the workflow is enabled for the first time.
    if not seen:
        baseline = [str(a.get("id")) for a in articles
                    if isinstance(a, dict) and a.get("id")]
        save_seen_ids(baseline)
        logger.info("Initialized news alert baseline with %d existing articles; no backfill sent.",
                    len(baseline))
        return

    candidates = select_new_articles(articles, seen)
    if not candidates:
        logger.info("No newly published eligible PikaNews articles.")
        return

    sent = []
    for article in candidates[:MAX_PER_RUN]:
        send_telegram_message(token, chat_id, format_news_message(article))
        sent.append(str(article["id"]))
    save_seen_ids(seen.union(sent))
    logger.info("Sent %d new PikaNews alerts.", len(sent))


if __name__ == "__main__":
    main()
