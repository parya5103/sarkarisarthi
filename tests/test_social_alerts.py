from datetime import datetime, timezone, timedelta

import news_telegram_notifier as news


def test_news_selector_ignores_seen_unverified_and_stale_articles():
    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    articles = [
        {"id": "new", "title": "Fresh", "url": "https://example.com/new",
         "published_at": (now - timedelta(minutes=5)).isoformat(), "date_unverified": False},
        {"id": "seen", "title": "Seen", "url": "https://example.com/seen",
         "published_at": (now - timedelta(minutes=4)).isoformat(), "date_unverified": False},
        {"id": "unknown-date", "title": "Unknown date", "url": "https://example.com/unknown",
         "date_unverified": True},
        {"id": "old", "title": "Old", "url": "https://example.com/old",
         "published_at": (now - timedelta(days=2)).isoformat(), "date_unverified": False},
    ]
    selected = news.select_new_articles(articles, {"seen"}, now=now)
    assert [item["id"] for item in selected] == ["new"]


def test_news_selector_rejects_missing_urls_and_future_dates():
    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    articles = [
        {"id": "no-url", "title": "No URL", "published_at": now.isoformat()},
        {"id": "future", "title": "Future", "url": "https://example.com/future",
         "published_at": (now + timedelta(hours=1)).isoformat()},
    ]
    assert news.select_new_articles(articles, set(), now=now) == []


def test_news_message_escapes_untrusted_text_and_links_to_original():
    message = news.format_news_message({
        "title": "<script>alert(1)</script>",
        "source": "News & Co",
        "category": "technology",
        "url": "https://example.com/story",
        "summary": "A & B",
    })
    assert "<script>" not in message
    assert "&lt;script&gt;" in message
    assert "https://example.com/story" in message
    assert "News &amp; Co" in message


def test_job_alerts_only_include_active_officially_verified_jobs(monkeypatch):
    import telegram_notifier as notifier
    jobs = [
        {"id": "official", "status": "active", "verification_status": "official_verified",
         "scraped_at": "2026-11-21T10:00:00", "url": "https://ssc.gov.in/apply"},
        {"id": "secondary", "status": "active", "verification_status": "secondary_source_only",
         "scraped_at": "2026-11-21T10:00:00"},
        {"id": "review", "status": "active", "verification_status": "needs_review",
         "scraped_at": "2026-11-21T10:00:00"},
        {"id": "expired", "status": "expired", "verification_status": "official_verified",
         "scraped_at": "2026-11-21T10:00:00"},
    ]
    monkeypatch.setattr(notifier, "load_manifest", lambda: {"jobs": jobs})
    monkeypatch.setattr(notifier, "select_recent_jobs", lambda records: records)
    selected = notifier.get_notifiable_jobs()
    assert [job["id"] for job in selected] == ["official"]


def test_whatsapp_channel_urls_are_the_exact_user_supplied_links():
    from pathlib import Path
    html = Path(__file__).resolve().parents[1].joinpath("index.html").read_text(encoding="utf-8")
    assert 'https://whatsapp.com/channel/0029VbE1ulAAjPXQZiUbbu1Z' in html
    assert 'https://whatsapp.com/channel/0029Vb5zVwjICVfnQ95zT10F' in html
