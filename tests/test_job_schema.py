"""Tests for the job schema: normalization, status, verification
labels, deduplication, cross-source merging, and the storage-level
status refresh.

Covers: missing and malformed dates, duplicate advertisements,
expired/cancelled handling, no fabrication of missing values,
verification status derivation, merge-only-fills-missing behaviour,
and the storage-level status backfill during refresh_job_statuses.

Run with: python -m pytest tests/test_job_schema.py -v
"""
from datetime import date, timedelta

import pytest

import storage
from job_schema import (
    NOT_SPECIFIED_TEXT, parse_date, compute_status, normalize_job,
    advertisement_key, is_duplicate_job, title_date_key, merge_job,
    compute_verification_status, validate_http_url, is_official_url,
)

TODAY = date(2026, 11, 3)


def base_job():
    return {
        'id': 'abc123',
        'title': 'SSC CGL 2026 Notification',
        'url': 'https://example.gov.in/job/1',
        'source': 'example.gov.in',
        'description': 'Official notification text',
        'important_dates': {'found_date': '09-11-2026'},
        'category': 'SSC',
        'skills': [],
        'scraped_at': '2026-10-20T02:02:03.926475',
        'links': [],
    }


def private_job():
    """A record that comes from a private job-information portal."""
    job = base_job()
    job['url'] = 'https://exampleportal.in/job/1'
    job['source'] = 'exampleportal.in'
    job['links'] = []
    return job


class TestParseDate:
    def test_common_indian_formats(self):
        assert parse_date('09-11-2026') == date(2026, 11, 9)
        assert parse_date('09/11/2026') == date(2026, 11, 9)
        assert parse_date('2026-11-09') == date(2026, 11, 9)
        assert parse_date('09 Nov 2026') == date(2026, 11, 9)
        assert parse_date('09 November 2026') == date(2026, 11, 9)

    def test_iso_timestamp(self):
        assert parse_date('2026-11-09T14:22:48') == date(2026, 11, 9)

    def test_invalid_and_missing(self):
        assert parse_date(None) is None
        assert parse_date('') is None
        assert parse_date('   ') is None
        assert parse_date('not a date') is None
        assert parse_date('32-13-2026') is None
        assert parse_date(20261109) is None


class TestComputeStatus:
    def test_expired_when_last_date_in_past(self):
        job = base_job()
        job['important_dates'] = {'last_date': '01-11-2026'}
        assert compute_status(job, TODAY) == 'expired'

    def test_active_when_last_date_today_or_future(self):
        job = base_job()
        job['important_dates'] = {'last_date': '03-11-2026'}
        assert compute_status(job, TODAY) == 'active'
        job['important_dates'] = {'last_date': '30-11-2026'}
        assert compute_status(job, TODAY) == 'active'

    def test_cancelled_wins(self):
        job = base_job()
        job['status'] = 'cancelled'
        job['important_dates'] = {'last_date': '30-11-2026'}
        assert compute_status(job, TODAY) == 'cancelled'

    def test_upcoming_when_start_date_in_future(self):
        job = base_job()
        job['important_dates'] = {'application_start_date': '10-11-2026'}
        assert compute_status(job, TODAY) == 'upcoming'

    def test_active_when_no_dates(self):
        # No fabricated dates: a job without dates stays active.
        assert compute_status(base_job(), TODAY) == 'active'

    def test_unparseable_last_date_keeps_active(self):
        job = base_job()
        job['important_dates'] = {'last_date': 'asap'}
        assert compute_status(job, TODAY) == 'active'

    def test_flat_last_date_also_recognised(self):
        job = base_job()
        del job['important_dates']
        job['last_date'] = '01-11-2026'
        assert compute_status(job, TODAY) == 'expired'


class TestUrlValidation:
    def test_http_https_accepted(self):
        assert validate_http_url('https://ssc.gov.in/notice.pdf') is True
        assert validate_http_url('http://example.in/x') is True

    def test_dangerous_schemes_rejected(self):
        assert validate_http_url('javascript:alert(1)') is False
        assert validate_http_url('data:text/html,x') is False
        assert validate_http_url('ftp://example.in/x') is False
        assert validate_http_url('') is False
        assert validate_http_url(None) is False
        assert validate_http_url(123) is False

    def test_official_domain_detection(self):
        assert is_official_url('https://ssc.gov.in/notice.pdf') is True
        assert is_official_url('https://www.ncs.gov.in/pages/govt-job-vacancies.aspx') is True
        assert is_official_url('https://example.in/notice.pdf') is False
        assert is_official_url('javascript:alert(1)') is False


class TestVerificationStatus:
    def test_official_link_means_verified(self):
        job = private_job()
        job['official_notification_url'] = 'https://ssc.gov.in/notice.pdf'
        assert compute_verification_status(job, TODAY) == 'official_verified'

    def test_official_source_means_verified(self):
        # Employment News style: data from employmentnews.gov.in itself.
        assert compute_verification_status(base_job(), TODAY) == 'official_verified'

    def test_private_only_is_secondary_source(self):
        assert compute_verification_status(private_job(), TODAY) == 'secondary_source_only'

    def test_gov_link_in_links_is_link_pending(self):
        job = private_job()
        job['links'] = ['https://www.mppsc.mp.gov.in/notice.pdf']
        assert compute_verification_status(job, TODAY) == 'official_link_pending'

    def test_invalid_official_url_needs_review(self):
        job = private_job()
        job['official_notification_url'] = 'javascript:alert(1)'
        assert compute_verification_status(job, TODAY) == 'needs_review'

    def test_stale_unknown_last_date_needs_review(self):
        job = private_job()
        job['scraped_at'] = '2026-09-01T00:00:00'
        job['last_verified'] = '2026-09-01T00:00:00'
        # No verified last date and not re-checked for > 30 days.
        assert compute_verification_status(job, TODAY) == 'needs_review'

    def test_fresh_unknown_last_date_is_not_flagged(self):
        job = private_job()
        job['scraped_at'] = '2026-11-01T00:00:00'
        job['last_verified'] = '2026-11-01T00:00:00'
        assert compute_verification_status(job, TODAY) == 'secondary_source_only'

    def test_lifecycle_states_win(self):
        job = private_job()
        job['official_notification_url'] = 'https://ssc.gov.in/n.pdf'
        job['status'] = 'expired'
        assert compute_verification_status(job, TODAY) == 'expired'
        job['status'] = 'cancelled'
        assert compute_verification_status(job, TODAY) == 'cancelled'


class TestNormalizeJob:
    def test_schema_fields_added_without_data_loss(self):
        job = base_job()
        out = normalize_job(job)
        for field in ('organization', 'department', 'location', 'vacancies',
                      'advertisement_no', 'qualification', 'age_limit',
                      'official_notification_url', 'official_application_url',
                      'published_date', 'last_verified', 'status',
                      'original_source_url', 'verification_status',
                      'state', 'district', 'salary', 'pay_scale',
                      'application_fee', 'selection_process'):
            assert field in out, field
        for key in job:
            assert key in out
        assert out['description'] == 'Official notification text'
        assert out['skills'] == []

    def test_missing_fields_are_none_not_fabricated(self):
        out = normalize_job(base_job())
        assert out['organization'] is None
        assert out['qualification'] is None
        assert out['state'] is None
        assert out['salary'] is None
        assert out['important_dates'].get('last_date') is None
        assert NOT_SPECIFIED_TEXT == 'Not specified in official notification'

    def test_last_verified_defaults_to_scraped_at(self):
        out = normalize_job(base_job())
        assert out['last_verified'] == '2026-10-20T02:02:03.926475'

    def test_last_verified_not_overwritten(self):
        job = base_job()
        job['last_verified'] = '2026-01-01T00:00:00'
        assert normalize_job(job)['last_verified'] == '2026-01-01T00:00:00'

    def test_flat_admin_last_date_backfilled_into_important_dates(self):
        job = base_job()
        del job['important_dates']
        job['last_date'] = (date.today() + timedelta(days=20)).strftime('%d-%m-%Y')
        out = normalize_job(job)
        assert out['important_dates']['last_date'] == job['last_date']
        assert out['status'] == 'active'

    def test_summary_becomes_description_when_missing(self):
        job = base_job()
        del job['description']
        job['summary'] = 'Manual summary'
        assert normalize_job(job)['description'] == 'Manual summary'

    def test_original_source_url_from_url(self):
        out = normalize_job(base_job())
        assert out['original_source_url'] == 'https://example.gov.in/job/1'

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError):
            normalize_job('not-a-dict')

    def test_existing_values_never_overwritten(self):
        job = base_job()
        job['organization'] = 'Staff Selection Commission'
        job['vacancies'] = '1200'
        out = normalize_job(job)
        assert out['organization'] == 'Staff Selection Commission'
        assert out['vacancies'] == '1200'


class TestDeduplication:
    def test_same_url_duplicate(self):
        urls = {'https://example.gov.in/job/1'}
        cand = {'url': 'https://example.gov.in/job/1', 'title': 'X'}
        assert is_duplicate_job(cand, urls, set()) == 'same-url'

    def test_same_advertisement_and_organization_duplicate(self):
        keys = {('adv/2026/01', 'staff selection commission')}
        cand = {
            'url': 'https://other.example.in/xyz',
            'title': 'X',
            'advertisement_no': 'ADV/2026/01',
            'organization': 'Staff Selection Commission',
        }
        assert is_duplicate_job(cand, set(), keys) == 'same-advertisement'

    def test_title_similarity_alone_is_not_duplicate(self):
        urls = {'https://example.gov.in/job/1'}
        cand = {
            'url': 'https://different.gov.in/job/2',
            'title': 'SSC CGL 2026 Notification',
        }
        assert is_duplicate_job(cand, urls, set()) is None

    def test_title_date_key_requires_both_parts(self):
        assert title_date_key({'title': 'SSC CGL 2026', 'important_dates': {}}) is None
        assert title_date_key({'title': '', 'important_dates': {'last_date': '30-11-2026'}}) is None
        key = title_date_key({
            'title': '  SSC   CGL 2026 Notification ',
            'important_dates': {'last_date': '30-11-2026'},
        })
        assert key == ('ssc cgl 2026 notification', '2026-11-30')

    def test_same_title_and_last_date_is_duplicate(self):
        td_keys = {('ssc cgl 2026 notification', '2026-11-30')}
        cand = {
            'url': 'https://portal-b.in/ssc-cgl',
            'title': 'SSC CGL 2026 Notification',
            'important_dates': {'last_date': '30-11-2026'},
        }
        assert is_duplicate_job(cand, set(), set(), td_keys) == 'same-title-date'

    def test_same_title_but_different_last_date_not_duplicate(self):
        td_keys = {('ssc cgl 2026 notification', '2026-11-30')}
        cand = {
            'url': 'https://portal-b.in/ssc-cgl',
            'title': 'SSC CGL 2026 Notification',
            'important_dates': {'last_date': '15-12-2026'},
        }
        assert is_duplicate_job(cand, set(), set(), td_keys) is None

    def test_partial_advertisement_key_is_none(self):
        assert advertisement_key({'advertisement_no': 'ADV/2026/01'}) is None
        assert advertisement_key({'organization': 'SSC'}) is None
        assert advertisement_key({}) is None

    def test_advertisement_key_normalizes_case_and_whitespace(self):
        key = advertisement_key({
            'advertisement_no': '  ADV/2026/01  ',
            'organization': 'staff   selection commission',
        })
        assert key == ('adv/2026/01', 'staff selection commission')

    def test_unique_job_returns_none(self):
        cand = {'url': 'https://example.gov.in/job/9', 'title': 'X'}
        assert is_duplicate_job(cand, set(), set()) is None


class TestMergeJob:
    def test_merge_fills_only_missing_fields(self):
        existing = normalize_job(private_job())
        existing['organization'] = 'Staff Selection Commission'
        existing['qualification'] = None
        incoming = {
            'source': 'portal-b.in',
            'url': 'https://portal-b.in/x',
            'organization': 'WRONG ORG',
            'qualification': 'Graduate',
            'important_dates': {'last_date': '30-11-2026'},
        }
        merged, filled = merge_job(existing, incoming, now='2026-11-03T00:00:00')
        assert merged['organization'] == 'Staff Selection Commission'
        assert merged['qualification'] == 'Graduate'
        assert merged['important_dates']['last_date'] == '30-11-2026'
        assert filled >= 2

    def test_merge_keeps_source_attribution(self):
        existing = normalize_job(private_job())
        incoming = {'source': 'portal-b.in', 'url': 'https://portal-b.in/x'}
        merged, filled = merge_job(existing, incoming)
        refs = merged.get('source_refs') or []
        assert {'source': 'portal-b.in', 'url': 'https://portal-b.in/x'} in refs

    def test_merge_does_not_duplicate_same_source_ref(self):
        existing = normalize_job(private_job())
        incoming = {'source': 'portal-b.in', 'url': 'https://portal-b.in/x'}
        merged, _ = merge_job(existing, incoming)
        merged, _ = merge_job(merged, incoming)
        refs = merged.get('source_refs') or []
        assert len(refs) == 1

    def test_deadline_extension_applies(self):
        job = normalize_job(private_job())
        job['important_dates'] = {'last_date': '10-11-2026'}
        incoming = {
            'source': 'portal-b.in',
            'url': 'https://portal-b.in/x',
            'important_dates': {'last_date': '05-12-2026'},
        }
        merged, filled = merge_job(job, incoming)
        assert merged['important_dates']['last_date'] == '05-12-2026'
        assert merged.get('deadline_extended') is True

    def test_earlier_deadline_does_not_shorten(self):
        job = normalize_job(private_job())
        job['important_dates'] = {'last_date': '30-12-2026'}
        incoming = {
            'source': 'portal-b.in',
            'url': 'https://portal-b.in/x',
            'important_dates': {'last_date': '30-11-2026'},
        }
        merged, _ = merge_job(job, incoming)
        assert merged['important_dates']['last_date'] == '30-12-2026'

    def test_merge_never_invents_data(self):
        existing = normalize_job(private_job())
        incoming = {'source': None, 'url': None}
        merged, filled = merge_job(existing, incoming)
        assert filled == 0
        assert merged['organization'] is None
        assert merged['vacancies'] is None


class TestStorageStatusRefresh:
    """refresh_job_statuses: expired records are KEPT for reference with
    status='expired', counters are recomputed from the actual statuses,
    and a job without a verified last date is never auto-expired."""

    def _use_tmp_job_dir(self, tmp_path, monkeypatch):
        job_dir = tmp_path / 'jobs'
        job_dir.mkdir()
        monkeypatch.setattr(storage, 'JOB_DIR', str(job_dir))
        monkeypatch.setattr(storage, 'MANIFEST_FILE', str(job_dir / 'job_manifest.json'))
        monkeypatch.setattr(storage, 'ARCHIVE_FILE', str(job_dir / 'expired_archive.json'))
        monkeypatch.setattr(storage, 'BACKUP_DIR', str(job_dir / 'backup'))
        return job_dir

    def test_expired_kept_with_status_counters_consistent(self, tmp_path, monkeypatch):
        job_dir = self._use_tmp_job_dir(tmp_path, monkeypatch)
        active = {
            'id': 'active_job_1',
            'title': 'Active Job',
            'url': 'https://example.gov.in/a',
            'important_dates': {
                'last_date': (date.today() + timedelta(days=20)).strftime('%d-%m-%Y')
            },
        }
        expired = {
            'id': 'expired_job_1',
            'title': 'Old Job',
            'url': 'https://example.gov.in/b',
            'important_dates': {
                'last_date': (date.today() - timedelta(days=30)).strftime('%d-%m-%Y')
            },
        }
        storage.save_jobs_to_files([active, expired])
        storage.save_manifest({'jobs': [active, expired]})

        storage.refresh_job_statuses()

        manifest = storage.load_manifest()
        by_id = {job['id']: job for job in manifest['jobs']}
        # History preserved: the expired record is still there.
        assert set(by_id) == {'active_job_1', 'expired_job_1'}
        assert by_id['active_job_1']['status'] == 'active'
        assert by_id['expired_job_1']['status'] == 'expired'
        assert by_id['active_job_1']['last_verified']
        assert by_id['active_job_1']['organization'] is None
        # Counters now match the actual record statuses.
        assert manifest['active_jobs'] == 1
        assert manifest['expired_jobs'] == 1
        assert manifest['total_jobs'] == 2
        assert (job_dir / 'active_job_1.json').exists()

    def test_unknown_last_date_never_expires(self, tmp_path, monkeypatch):
        job_dir = self._use_tmp_job_dir(tmp_path, monkeypatch)
        stale = {
            'id': 'stale_job_1',
            'title': 'Stale Job',
            'url': 'https://example.gov.in/c',
            'scraped_at': '2026-08-01T00:00:00',
            # NO last_date at all: must NOT be expired by any age rule.
        }
        storage.save_manifest({'jobs': [stale]})

        storage.refresh_job_statuses()

        manifest = storage.load_manifest()
        job = manifest['jobs'][0]
        assert job['status'] == 'active'
        assert manifest['active_jobs'] == 1
        assert manifest['expired_jobs'] == 0
        # Stale + unknown last date is flagged for review, not deleted.
        assert job['verification_status'] == 'needs_review'

    def test_expired_overflow_archived(self, tmp_path, monkeypatch):
        job_dir = self._use_tmp_job_dir(tmp_path, monkeypatch)
        monkeypatch.setattr(storage, 'MAX_EXPIRED_IN_MANIFEST', 1)
        jobs = [
            {
                'id': 'exp_%d' % i,
                'title': 'Old Job %d' % i,
                'url': 'https://example.gov.in/o%d' % i,
                'important_dates': {
                    'last_date': (date.today() - timedelta(days=30 + i)).strftime('%d-%m-%Y')
                },
                'scraped_at': '2026-10-%02dT00:00:00' % (i + 1),
            }
            for i in range(3)
        ]
        storage.save_manifest({'jobs': jobs})

        storage.refresh_job_statuses()

        manifest = storage.load_manifest()
        assert len(manifest['jobs']) == 1
        assert manifest['expired_jobs'] == 1
        archive = job_dir / 'expired_archive.json'
        assert archive.exists()
        import json
        archived = json.loads(archive.read_text(encoding='utf-8'))
        assert len(archived) == 2
        assert all(j.get('status') == 'expired' for j in archived)

    def test_backup_before_mutation(self, tmp_path, monkeypatch):
        job_dir = self._use_tmp_job_dir(tmp_path, monkeypatch)
        storage.save_manifest({'jobs': [{'id': 'j1', 'title': 'J1', 'url': 'u'}]})
        backup_path = storage.backup_manifest(now=date(2026, 11, 3))
        assert backup_path is not None
        assert (job_dir / 'backup' / 'manifest_backup_2026-11-03.json').exists()
        # Second backup same day overwrites, not duplicates.
        storage.backup_manifest(now=date(2026, 11, 3))
        backups = list((job_dir / 'backup').glob('manifest_backup_*.json'))
        assert len(backups) == 1
