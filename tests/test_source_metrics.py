"""Tests for per-source fetch metrics and the daily source report.

Covers: stat accumulation across multiple record calls, failure states
(robots-disallowed, fetch-failed, no-jobs), the needs_attention logic
(zero jobs is a flag even when HTTP succeeded), and report writing to
JSON + markdown without raising.

Run with: python -m pytest tests/test_source_metrics.py -v
"""
import json
import os

from source_metrics import SourceMetrics


class TestRecording:
    def test_record_creates_entry_with_last_fetch(self):
        m = SourceMetrics()
        m.record('example.in', status='ok', discovered=5, accepted=3)
        entry = m.sources['example.in']
        assert entry['source'] == 'example.in'
        assert entry['status'] == 'ok'
        assert entry['discovered'] == 5
        assert entry['accepted'] == 3
        assert entry['last_fetch']

    def test_counts_accumulate_across_calls(self):
        # One portal can be scraped in several passes; totals add up.
        m = SourceMetrics()
        m.record('example.in', discovered=5, accepted=3, duplicates=2)
        m.record('example.in', discovered=4, accepted=2, duplicates=2)
        entry = m.sources['example.in']
        assert entry['discovered'] == 9
        assert entry['accepted'] == 5
        assert entry['duplicates'] == 4
        assert len(m.sources) == 1

    def test_status_replaced_not_accumulated(self):
        m = SourceMetrics()
        m.record('example.in', status='ok')
        m.record('example.in', status='no-jobs')
        assert m.sources['example.in']['status'] == 'no-jobs'

    def test_none_values_ignored(self):
        m = SourceMetrics()
        m.record('example.in', status='ok', notes=None, parser_errors=None)
        entry = m.sources['example.in']
        assert 'notes' not in entry
        assert 'parser_errors' not in entry

    def test_empty_name_goes_to_unknown(self):
        m = SourceMetrics()
        m.record('', status='ok')
        m.record(None, status='ok')
        assert len(m.sources) == 1
        assert 'unknown' in m.sources

    def test_sources_are_independent(self):
        # One failing source must not affect another source's entry.
        m = SourceMetrics()
        m.record('good.in', status='ok', discovered=10, accepted=10)
        m.record('bad.in', status='fetch-failed', duration_s=30.5)
        assert m.sources['good.in']['status'] == 'ok'
        assert m.sources['bad.in']['status'] == 'fetch-failed'
        assert m.sources['good.in'].get('duration_s') is None


class TestNeedsAttention:
    def test_ok_with_jobs_is_fine(self):
        m = SourceMetrics()
        assert m.needs_attention({'status': 'ok', 'accepted': 5}) is False

    def test_zero_jobs_flagged_even_with_http_200(self):
        # HTTP success is not proof that extraction worked.
        m = SourceMetrics()
        assert m.needs_attention({'status': 'no-jobs'}) is True

    def test_failures_flagged(self):
        m = SourceMetrics()
        for status in ('fetch-failed', 'parse-error', 'robots-disallowed', 'error'):
            assert m.needs_attention({'status': status}) is True

    def test_parser_errors_flagged_even_if_ok(self):
        m = SourceMetrics()
        assert m.needs_attention({'status': 'ok', 'parser_errors': 2}) is True

    def test_missing_status_not_flagged(self):
        m = SourceMetrics()
        assert m.needs_attention({}) is False


class TestReportWriting:
    def test_json_and_markdown_written(self, tmp_path):
        m = SourceMetrics()
        m.record('portal-a.in', status='ok', discovered=10, accepted=8,
                 duplicates=2, duration_s=12.5)
        m.record('portal-b.in', status='no-jobs', duration_s=8.0,
                 notes='listing page returned no job entries')
        m.note_pipeline_totals(new_jobs=8, expired_jobs=3)
        json_path = tmp_path / 'source_report.json'
        md_path = tmp_path / 'source_report.md'
        report = m.write_report(json_path=str(json_path), md_path=str(md_path))

        data = json.loads(json_path.read_text(encoding='utf-8'))
        assert data['totals']['new_jobs'] == 8
        assert {s['source'] for s in data['sources']} == {'portal-a.in', 'portal-b.in'}
        assert report['totals']['new_jobs'] == 8

        md = md_path.read_text(encoding='utf-8')
        assert '| portal-a.in | ok |' in md
        assert 'portal-b.in' in md
        assert 'Needs attention' in md
        assert 'no-jobs' in md
        # The disclaimer about HTTP 200 vs extraction success is present.
        assert 'HTTP status alone' in md

    def test_markdown_skipped_when_md_path_none(self, tmp_path):
        m = SourceMetrics()
        m.record('portal-a.in', status='ok', accepted=1)
        json_path = tmp_path / 'source_report.json'
        m.write_report(json_path=str(json_path), md_path=None)
        assert json_path.exists()

    def test_all_good_sources_no_attention_section(self, tmp_path):
        m = SourceMetrics()
        m.record('portal-a.in', status='ok', discovered=5, accepted=5)
        json_path = tmp_path / 'r.json'
        md_path = tmp_path / 'r.md'
        m.write_report(json_path=str(json_path), md_path=str(md_path))
        md = md_path.read_text(encoding='utf-8')
        assert 'no attention flags' in md

    def test_bad_paths_do_not_raise(self):
        m = SourceMetrics()
        m.record('portal-a.in', status='ok')
        # Directory that cannot be created -> logged, not raised.
        report = m.write_report(json_path='/proc/definitely/not/ok/report.json',
                                md_path='/proc/definitely/not/ok/report.md')
        assert report['sources'][0]['source'] == 'portal-a.in'
