"""Compliance tests for the generic portal scraper.

The scraper must:
- identify itself with the honest product User-Agent (never spoof
  a browser User-Agent like Mozilla/Chrome);
- check robots.txt BEFORE fetching a portal, and skip the source
  entirely (with a metric, not an error) when robots disallows it;
- parse a listing into structured job records when access is allowed;
- keep source failures independent.

Network access is fully mocked: no test here touches the internet.

Run with: python -m pytest tests/test_scraper_compliance.py -v
"""
from unittest.mock import MagicMock

import pytest

import scraper
from official_sources import USER_AGENT
from source_metrics import SourceMetrics

LISTING_HTML = b"""<html><body>
<h3><a href="/jobs/rrb-2026-1234">RRB Recruitment 2026 Apply Online 1234</a></h3>
<h3><a href="/about-us">About Us</a></h3>
</body></html>"""


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # fetch_page_content politely waits 2-4s between attempts; tests
    # must not actually sleep.
    monkeypatch.setattr(scraper.time, 'sleep', lambda *_: None)


class TestHonestUserAgent:
    def test_requests_use_product_user_agent(self, monkeypatch):
        captured = {}

        def fake_get(url, timeout=0, headers=None, allow_redirects=True):
            captured['url'] = url
            captured['headers'] = headers
            response = MagicMock()
            response.status_code = 200
            response.content = LISTING_HTML
            response.raise_for_status.return_value = None
            return response

        monkeypatch.setattr(scraper.requests, 'get', fake_get)
        monkeypatch.setattr(scraper, 'robots_allows', lambda *a, **k: True)

        jobs = scraper.scrape_generic_job_site('https://example.in', 'example.in')

        headers = captured['headers']
        assert headers['User-Agent'] == USER_AGENT
        assert 'SarkariSarthiJobPortal' in headers['User-Agent']
        # Never spoof a browser identity.
        assert 'Mozilla' not in headers['User-Agent']
        assert 'Chrome' not in headers['User-Agent']
        assert captured['url'] == 'https://example.in'
        assert len(jobs) == 1
        assert jobs[0]['url'] == 'https://example.in/jobs/rrb-2026-1234'
        assert jobs[0]['title'] == 'RRB Recruitment 2026 Apply Online 1234'
        assert jobs[0]['source'] == 'example.in'


class TestRobotsCompliance:
    def test_robots_disallowed_skips_fetch_entirely(self, monkeypatch):
        metrics = SourceMetrics()

        def robots_refuse(url, user_agent, fetch=None):
            return False

        def boom(*args, **kwargs):
            raise AssertionError('portal must not be fetched when robots disallows')

        monkeypatch.setattr(scraper, 'robots_allows', robots_refuse)
        monkeypatch.setattr(scraper, 'fetch_page_content', boom)

        jobs = scraper.scrape_generic_job_site('https://blocked.in', 'blocked.in', metrics=metrics)

        assert jobs == []
        entry = metrics.sources['blocked.in']
        assert entry['status'] == 'robots-disallowed'
        assert entry['permission'] == 'disallowed'
        assert entry['discovered'] == 0

    def test_robots_allowed_proceeds_and_parses(self, monkeypatch):
        metrics = SourceMetrics()
        monkeypatch.setattr(scraper, 'robots_allows', lambda *a, **k: True)
        monkeypatch.setattr(scraper, 'fetch_page_content', lambda url, timeout=15, retries=3: LISTING_HTML)

        jobs = scraper.scrape_generic_job_site('https://example.in', 'example.in', metrics=metrics)

        assert len(jobs) == 1
        entry = metrics.sources['example.in']
        assert entry['status'] == 'ok'
        assert entry['permission'] == 'allowed'
        assert entry['discovered'] == 1

    def test_no_metrics_still_works(self, monkeypatch):
        # metrics is optional: existing callers without metrics keep working.
        monkeypatch.setattr(scraper, 'robots_allows', lambda *a, **k: True)
        monkeypatch.setattr(scraper, 'fetch_page_content', lambda url, timeout=15, retries=3: LISTING_HTML)
        jobs = scraper.scrape_generic_job_site('https://example.in', 'example.in')
        assert len(jobs) == 1


class TestSourceIndependence:
    def test_fetch_failure_records_metric_and_returns_empty(self, monkeypatch):
        metrics = SourceMetrics()
        monkeypatch.setattr(scraper, 'robots_allows', lambda *a, **k: True)
        monkeypatch.setattr(scraper, 'fetch_page_content', lambda url, timeout=15, retries=3: None)

        jobs = scraper.scrape_generic_job_site('https://down.in', 'down.in', metrics=metrics)

        assert jobs == []
        entry = metrics.sources['down.in']
        assert entry['status'] == 'fetch-failed'
        assert entry['discovered'] == 0
        assert metrics.needs_attention(entry) is True

    def test_parse_failure_does_not_raise(self, monkeypatch):
        metrics = SourceMetrics()
        monkeypatch.setattr(scraper, 'robots_allows', lambda *a, **k: True)
        monkeypatch.setattr(scraper, 'fetch_page_content', lambda url, timeout=15, retries=3: b'\x00not-html')

        jobs = scraper.scrape_generic_job_site('https://broken.in', 'broken.in', metrics=metrics)
        # lxml is tolerant: worst case zero jobs, never a crash.
        assert isinstance(jobs, list)
        entry = metrics.sources['broken.in']
        assert entry['status'] in ('ok', 'no-jobs', 'parse-error')

    def test_one_failure_does_not_stop_other_portals(self, monkeypatch):
        metrics = SourceMetrics()
        by_portal = {
            'https://good.in': LISTING_HTML,
            'https://bad.in': None,
        }

        def fake_robots(url, user_agent, fetch=None):
            return 'bad.in' not in url

        monkeypatch.setattr(scraper, 'robots_allows', fake_robots)
        monkeypatch.setattr(
            scraper, 'fetch_page_content',
            lambda url, timeout=15, retries=3: by_portal.get(url),
        )

        good_jobs = scraper.scrape_generic_job_site('https://good.in', 'good.in', metrics=metrics)
        bad_jobs = scraper.scrape_generic_job_site('https://bad.in', 'bad.in', metrics=metrics)

        assert len(good_jobs) == 1
        assert bad_jobs == []
        assert metrics.sources['good.in']['status'] == 'ok'
        assert metrics.sources['bad.in']['status'] in ('fetch-failed', 'robots-disallowed')


class TestNoBlockedPortalsConfigured:
    def test_sarkariresult_not_in_active_portal_list(self):
        # sarkariresult.com sits behind an anti-bot wall (robots.txt
        # itself returns 403): it is a discovery-only source and must
        # not be fetched by the automated pipeline.
        all_portals = scraper.JOB_PORTALS['government'] + scraper.JOB_PORTALS['private']
        assert 'https://www.sarkariresult.com' not in all_portals
        assert not any('sarkariresult.com' in url for url in all_portals)

    def test_portal_list_is_not_empty(self):
        assert len(scraper.JOB_PORTALS['government']) >= 5
        assert len(scraper.JOB_PORTALS['private']) >= 3
