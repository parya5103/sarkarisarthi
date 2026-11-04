"""Tests for official_sources: Employment News adapter + robots compliance.

All tests run offline against a fixture and injected fetch functions.
"""
import os

from job_schema import normalize_job
from storage import is_valid_job_id
from official_sources import (
    LISTING_URL, SOURCE_NAME, USER_AGENT,
    parse_employment_news_html, fetch_employment_news_jobs,
    robots_allows_from_text, robots_allows, _robots_url,
)

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'employmentnews_alljobs.html')

NEWLINE = chr(10)
DISALLOW_ALL = 'User-agent: *' + NEWLINE + 'Disallow: /'
ALLOW_ALL = 'User-agent: *' + NEWLINE + 'Disallow:'


def load_fixture_bytes():
    with open(FIXTURE, 'rb') as f:
        return f.read()


class TestEmploymentNewsParsing:
    def test_parses_valid_rows_and_skips_bad(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        # 7 data rows: 1 invalid (no parseable issued date) and
        # 2 identical rows collapse to 1, leaving 5 unique jobs.
        assert len(jobs) == 5

    def test_record_shape_matches_job_schema(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        for job in jobs:
            assert job['source'] == SOURCE_NAME
            assert job['url'].startswith('https://employmentnews.gov.in')
            assert job['organization']
            assert job['description']
            assert is_valid_job_id(job['id'])
            assert job['id'].startswith('en_')

    def test_dates_converted_to_house_format(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        by_post = {}
        for job in jobs:
            by_post[job['title'].split(' - ')[0]] = job
        tgt = by_post['TGT (COMPUTER SCIENCE) AND OTHERS']
        assert tgt['important_dates']['last_date'] == '21-11-2026'
        assert tgt['published_date'] == '02-11-2026'

    def test_unambiguous_day_first_issued_date(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        row = [j for j in jobs if j['title'].startswith('UNIVERSITY ASSISTANT')][0]
        assert row['published_date'] == '31-08-2026'
        assert row['important_dates']['last_date'] == '15-10-2026'

    def test_missing_last_date_never_invented(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        postal = [j for j in jobs if j['title'].startswith('POSTAL ASSISTANT')][0]
        assert 'last_date' not in postal['important_dates']
        assert 'Last date' not in postal['description']

    def test_row_link_becomes_absolute_url(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        ldc = [j for j in jobs if j['title'].startswith('LOWER DIVISION CLERK')][0]
        assert ldc['url'].startswith('https://employmentnews.gov.in/newemp/JobDetails.aspx')

    def test_all_urls_unique(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        urls = [job['url'] for job in jobs]
        assert len(set(urls)) == len(urls)

    def test_description_only_contains_verified_row_data(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        tgt = [j for j in jobs if 'TGT' in j['title']][0]
        assert 'SAINIK SCHOOL NAGROTA' in tgt['description']
        assert 'Recruitment' in tgt['description']
        assert '21-11-2026' in tgt['description']

    def test_normalize_job_completes_schema(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        out = normalize_job(jobs[0])
        for field in ('status', 'last_verified', 'advertisement_no',
                      'qualification', 'official_notification_url',
                      'official_application_url'):
            assert field in out
        assert out['status'] in ('active', 'expired', 'upcoming', 'cancelled')

    def test_duplicate_rows_collapse_by_content(self):
        jobs = parse_employment_news_html(load_fixture_bytes())
        ids = [job['id'] for job in jobs]
        assert len(set(ids)) == len(ids)


class TestRobotsCompliance:
    def test_disallow_all_blocks(self):
        assert robots_allows_from_text(DISALLOW_ALL, LISTING_URL, USER_AGENT) is False

    def test_empty_disallow_permits(self):
        assert robots_allows_from_text(ALLOW_ALL, LISTING_URL, USER_AGENT) is True

    def test_missing_robots_text_permits(self):
        assert robots_allows_from_text('', LISTING_URL, USER_AGENT) is True
        assert robots_allows_from_text(None, LISTING_URL, USER_AGENT) is True

    def test_robots_url_derivation(self):
        assert _robots_url(LISTING_URL) == 'https://employmentnews.gov.in/robots.txt'
        assert _robots_url('notaurl') is None

    def test_adapter_respects_robots_disallow(self):
        calls = []

        def fake_fetch(url, timeout):
            calls.append(url)
            if url.endswith('/robots.txt'):
                return DISALLOW_ALL
            return load_fixture_bytes()

        jobs = fetch_employment_news_jobs(fetch=fake_fetch)
        assert jobs == []
        assert calls == ['https://employmentnews.gov.in/robots.txt']

    def test_adapter_graceful_on_network_failure(self):
        def fake_fetch(url, timeout):
            raise RuntimeError('network down')

        assert fetch_employment_news_jobs(fetch=fake_fetch) == []

    def test_adapter_fetches_listing_when_robots_unreachable(self):
        calls = []

        def fake_fetch(url, timeout):
            calls.append(url)
            if url.endswith('/robots.txt'):
                raise RuntimeError('robots unreachable')
            return load_fixture_bytes()

        jobs = fetch_employment_news_jobs(fetch=fake_fetch)
        assert len(jobs) == 5
        assert len(calls) == 2

    def test_adapter_graceful_on_empty_html(self):
        def fake_fetch(url, timeout):
            if url.endswith('/robots.txt'):
                raise RuntimeError('no robots')
            return None

        assert fetch_employment_news_jobs(fetch=fake_fetch) == []
