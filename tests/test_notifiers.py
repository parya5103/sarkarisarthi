"""Tests for notification helpers (recent-job selection + formatting)."""
from datetime import date, datetime

import telegram_notifier
import whatsapp_notifier
from job_schema import NOTIFICATION_CAP, select_recent_jobs


class TestSelectRecentJobs:
    def test_window_filter(self):
        now = date(2026, 11, 3)
        fresh = {'id': 'a', 'scraped_at': datetime(2026, 11, 3, 8, 0, 0).isoformat()}
        old = {'id': 'b', 'scraped_at': datetime(2026, 10, 30, 8, 0, 0).isoformat()}
        unknown = {'id': 'c'}
        found = {'id': 'd', 'important_dates': {'found_date': '02-11-2026'}}
        result = select_recent_jobs([fresh, old, unknown, found], now=now)
        assert [j['id'] for j in result] == ['a', 'd']

    def test_cap(self):
        now = date(2026, 11, 3)
        jobs = [{'id': 'j%d' % i, 'scraped_at': '2026-11-03'} for i in range(40)]
        assert len(select_recent_jobs(jobs, now=now)) == NOTIFICATION_CAP

    def test_last_verified_fallback(self):
        now = date(2026, 11, 3)
        job = {'id': 'lv', 'last_verified': '2026-11-02'}
        assert select_recent_jobs([job], now=now) == [job]


class TestMessageFormatting:
    def test_telegram_organization_preferred(self):
        msg = telegram_notifier.format_job_message({
            'title': 'SSC CGL 2026',
            'organization': 'Staff Selection Commission',
            'source': 'employmentnews.gov.in',
            'url': 'https://ssc.gov.in/',
        })
        assert 'Staff Selection Commission' in msg
        assert 'employmentnews.gov.in' not in msg

    def test_telegram_fallback_to_source(self):
        msg = telegram_notifier.format_job_message({
            'title': 'Job X',
            'source': 'employmentnews.gov.in',
        })
        assert 'employmentnews.gov.in' in msg

    def test_whatsapp_organization_preferred(self):
        msg = whatsapp_notifier.format_job_message({
            'title': 'SSC CGL 2026',
            'organization': 'Staff Selection Commission',
            'source': 'employmentnews.gov.in',
        })
        assert 'Staff Selection Commission' in msg
