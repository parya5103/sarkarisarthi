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


def test_sarkari_portal_shows_only_its_own_whatsapp_channel_and_telegram_link():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("script.js").read_text(encoding="utf-8")
    assert html.count('https://whatsapp.com/channel/0029VbE1ulAAjPXQZiUbbu1Z') == 2
    assert 'https://whatsapp.com/channel/0029Vb5zVwjICVfnQ95zT10F' not in html
    assert 'https://t.me/sarkarisarthi' in script
    assert 'id="telegramBtn"' in html and 'id="footerTelegramBtn"' in html


def test_whatsapp_direct_alerts_only_include_active_official_jobs(monkeypatch):
    import whatsapp_notifier as notifier
    jobs = [
        {"id": "official", "status": "active", "verification_status": "official_verified",
         "url": "https://ssc.gov.in/apply", "scraped_at": "2026-11-21T10:00:00"},
        {"id": "secondary", "status": "active", "verification_status": "secondary_source_only",
         "url": "https://example.com/job", "scraped_at": "2026-11-21T10:00:00"},
        {"id": "expired", "status": "expired", "verification_status": "official_verified",
         "url": "https://ssc.gov.in/old", "scraped_at": "2026-11-21T10:00:00"},
    ]
    monkeypatch.setattr(notifier, "load_manifest", lambda: {"jobs": jobs})
    monkeypatch.setattr(notifier, "select_recent_jobs", lambda records: records)
    assert [job["id"] for job in notifier.get_notifiable_jobs()] == ["official"]


def test_workflow_keeps_public_telegram_free_of_github_diagnostics():
    from pathlib import Path
    workflow = Path(__file__).resolve().parents[1].joinpath(
        ".github/workflows/daily-job-fetch-deploy.yml"
    ).read_text(encoding="utf-8")
    assert "Send Telegram notification for new jobs" in workflow
    assert "Send deployment notification" not in workflow
    assert "Send failure notification" not in workflow
    assert "Send health check failure notification" not in workflow
    assert "Send WhatsApp direct-message notification for verified new jobs" in workflow
