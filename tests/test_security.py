"""Security tests: job-ID validation and path containment.

Covers valid IDs, invalid IDs, traversal attempts, encoded traversal
and path containment for every filesystem operation that uses a job
ID as a path component (save, status refresh, orphan sweep, temp PDF).
"""
import json
import os

import pytest

import storage
from storage import is_valid_job_id, job_file_path
from parser import process_job_content


def use_tmp_job_dir(tmp_path, monkeypatch):
    job_dir = tmp_path / 'jobs'
    job_dir.mkdir()
    monkeypatch.setattr(storage, 'JOB_DIR', str(job_dir))
    monkeypatch.setattr(storage, 'MANIFEST_FILE', str(job_dir / 'job_manifest.json'))
    return job_dir


VALID_IDS = [
    '5ccd399e8537b84c5a77d05981e8dc67',  # real md5-style scraped ID
    'manual_abc123',                     # admin manual-entry style
    'a' * 80,                            # maximum allowed length
    'RRB-NTPC-2026_01',
]

INVALID_IDS = [
    None,
    '',
    123,
    '../etc/passwd',                     # classic traversal
    '..',                               # parent directory
    'a/../b',                           # mid-path traversal
    '/absolute/path',                   # absolute path
    'a/b',                              # unexpected separator
    'a' + chr(92) + 'b',                # backslash separator
    'id with spaces',
    'id.json',                          # dot / extension injection
    '..%2F..%2Fetc%2Fpasswd',           # encoded traversal
    '%2e%2e%2f',                        # percent-encoded parent
    'a' * 81,                           # too long
    'café',                             # non-ASCII
]


@pytest.mark.parametrize('job_id', VALID_IDS)
def test_valid_job_ids_accepted(job_id):
    assert is_valid_job_id(job_id) is True
    path = job_file_path(job_id)
    assert os.path.basename(path) == job_id + '.json'


@pytest.mark.parametrize('job_id', INVALID_IDS)
def test_invalid_job_ids_rejected(job_id):
    assert is_valid_job_id(job_id) is False
    with pytest.raises(ValueError):
        job_file_path(job_id)


def test_job_file_path_stays_inside_jobs_dir(tmp_path, monkeypatch):
    job_dir = use_tmp_job_dir(tmp_path, monkeypatch)
    path = job_file_path('valid_id')
    assert os.path.realpath(path).startswith(os.path.realpath(str(job_dir)) + os.sep)


def test_job_file_path_rejects_symlink_escape(tmp_path, monkeypatch):
    job_dir = use_tmp_job_dir(tmp_path, monkeypatch)
    outside = tmp_path / 'outside.json'
    outside.write_text('secret')
    if not hasattr(os, 'symlink'):
        pytest.skip('symlinks not supported on this platform')
    try:
        os.symlink(str(outside), str(job_dir / 'linked.json'))
    except OSError:
        pytest.skip('symlinks not permitted')
    with pytest.raises(ValueError):
        job_file_path('linked')


def test_save_jobs_to_files_skips_unsafe_ids(tmp_path, monkeypatch):
    use_tmp_job_dir(tmp_path, monkeypatch)
    good_job = {'id': 'valid_id_1', 'title': 'Good Job', 'url': 'https://example.gov.in/j/1'}
    evil_job = {'id': '../../../evil', 'title': 'Evil Job', 'url': 'https://example.gov.in/j/2'}
    saved = storage.save_jobs_to_files([good_job, evil_job])
    assert saved == 1
    assert len(list(tmp_path.rglob('*.json'))) == 1


def test_refresh_job_statuses_never_escapes_jobs_dir(tmp_path, monkeypatch):
    """Status refresh must not turn a hostile job ID into a path.

    The old delete_expired_jobs() removed records; the new
    refresh_job_statuses() keeps expired history in the manifest and
    never derives any filesystem path from the job ID.
    """
    use_tmp_job_dir(tmp_path, monkeypatch)
    sentinel = tmp_path / 'sentinel.txt'
    sentinel.write_text('do not delete')
    manifest = {
        'last_updated': '2026-01-01T00:00:00',
        'total_jobs': 1,
        'active_jobs': 1,
        'expired_jobs': 0,
        'jobs': [
            {
                'id': '../sentinel',
                'title': 'Evil',
                'important_dates': {'last_date': '01-01-2020'},
            }
        ],
    }
    with open(storage.MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f)
    storage.refresh_job_statuses()
    with open(storage.MANIFEST_FILE, 'r', encoding='utf-8') as f:
        final = json.load(f)
    # Expired records are KEPT for reference, with status='expired'
    # and counters that match the actual statuses.
    assert len(final['jobs']) == 1
    assert final['jobs'][0]['status'] == 'expired'
    assert final['expired_jobs'] == 1
    assert final['active_jobs'] == 0
    # The unsafe ID never reached the filesystem.
    assert sentinel.exists()
    assert not (tmp_path / 'sentinel.json').exists()
    job_dir = tmp_path / 'jobs'
    assert sorted(p.name for p in job_dir.iterdir()) == ['job_manifest.json']


def test_remove_orphan_job_files_ignores_symlink_escape(tmp_path, monkeypatch):
    job_dir = use_tmp_job_dir(tmp_path, monkeypatch)
    (job_dir / 'orphan.json').write_text('{}')
    outside = tmp_path / 'outside-target.json'
    outside.write_text('keep me')
    if not hasattr(os, 'symlink'):
        pytest.skip('symlinks not supported on this platform')
    try:
        os.symlink(str(outside), str(job_dir / 'sneaky.json'))
    except OSError:
        pytest.skip('symlinks not permitted')
    storage._remove_orphan_job_files({'jobs': []})
    assert not (job_dir / 'orphan.json').exists()
    assert outside.exists()
    assert os.path.lexists(str(job_dir / 'sneaky.json'))


def test_process_job_content_skips_unsafe_pdf_download(tmp_path, monkeypatch):
    use_tmp_job_dir(tmp_path, monkeypatch)
    calls = []

    def fake_download(url, save_path, *args, **kwargs):
        calls.append(save_path)
        return True

    monkeypatch.setattr('parser.download_pdf', fake_download)
    job = {'id': '../evil', 'title': 'PDF Job', 'url': 'https://example.gov.in/x.pdf'}
    result = process_job_content(job)
    assert calls == []
    assert result.get('pdf_link') is None
    assert result['description'] == 'PDF Job'


def test_process_job_content_uses_safe_pdf_path(tmp_path, monkeypatch):
    use_tmp_job_dir(tmp_path, monkeypatch)
    seen = []

    def fake_download(url, save_path, *args, **kwargs):
        seen.append(save_path)
        with open(save_path, 'wb') as f:
            f.write(b'fake pdf bytes')
        return True

    monkeypatch.setattr('parser.download_pdf', fake_download)
    monkeypatch.setattr('parser.extract_text_from_pdf', lambda pdf_path: 'Last Date 30-11-2026')
    job = {'id': 'valid_pdf_id', 'title': 'PDF Job', 'url': 'https://example.gov.in/x.pdf'}
    result = process_job_content(job)
    assert len(seen) == 1
    assert os.path.basename(seen[0]) == 'temp_valid_pdf_id.pdf'
    assert not os.path.exists(seen[0])
    assert result['pdf_link'] == 'https://example.gov.in/x.pdf'
    assert result['important_dates'].get('last_date') == '30-11-2026'


def test_download_pdf_rejects_parent_directory_path(tmp_path):
    import parser as parser_module
    ok = parser_module.download_pdf(
        'https://example.gov.in/x.pdf',
        str(tmp_path) + '/../escape.pdf'
    )
    assert ok is False
