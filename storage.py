import logging
import os
import json
from datetime import datetime
import re

from job_schema import normalize_job

logger = logging.getLogger(__name__)

# Directory for storing job data and manifest
JOB_DIR = 'jobs'
MANIFEST_FILE = os.path.join(JOB_DIR, 'job_manifest.json')

# Pre-mutation manifest backups (jobs/backup/manifest_backup_YYYY-MM-DD.json)
BACKUP_DIR = os.path.join(JOB_DIR, 'backup')
BACKUP_KEEP = 7

# Expired records stay in the manifest for history, but only the most
# recent ones; older overflow moves to jobs/expired_archive.json.
MAX_EXPIRED_IN_MANIFEST = 300
MAX_ARCHIVED_EXPIRED = 2000
ARCHIVE_FILE = os.path.join(JOB_DIR, 'expired_archive.json')

# Security: strict allowlist for job IDs. Job IDs reach filesystem
# operations (jobs/<id>.json, temp_<id>.pdf) from scraped URLs and from
# manually entered admin records, so they are EXTERNAL INPUT and must
# never be trusted as path components.
JOB_ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,80}')


def is_valid_job_id(job_id):
    """True only for IDs matching the strict [A-Za-z0-9_-]{1,80} allowlist."""
    return (
        isinstance(job_id, str)
        and bool(job_id)
        and bool(JOB_ID_PATTERN.fullmatch(job_id))
    )


def job_file_path(job_id):
    """Return the validated jobs/<id>.json path for a job ID.

    Rejects traversal ('../'), encoded traversal, absolute paths,
    separators, over-long IDs and anything outside the allowlist.
    Also verifies the RESOLVED path stays inside the jobs directory
    (realpath containment, symlink-safe), so no write or delete can
    ever escape JOB_DIR.
    """
    if not is_valid_job_id(job_id):
        raise ValueError('Invalid job ID: %r' % (job_id,))
    job_dir_abs = os.path.abspath(JOB_DIR)
    path = os.path.join(JOB_DIR, job_id + '.json')
    resolved = os.path.realpath(path)
    if not resolved.startswith(job_dir_abs + os.sep):
        raise ValueError('Resolved job path escapes the jobs directory: %r' % (path,))
    return path

def load_manifest():
    """Load job manifest from file or create default structure if it doesn't exist or is invalid."""
    if not os.path.exists(MANIFEST_FILE):
        logger.info(f"Manifest file not found at {MANIFEST_FILE}. Creating a new one.")
        return {
            "last_updated": "",
            "total_jobs": 0,
            "active_jobs": 0,
            "expired_jobs": 0,
            "jobs": []
        }
    try:
        with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
            if not isinstance(manifest_data, dict) or "jobs" not in manifest_data:
                raise ValueError("Manifest file has an invalid structure.")
            return manifest_data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from manifest file {MANIFEST_FILE}: {e}. Recreating manifest.")
        return {
            "last_updated": "",
            "total_jobs": 0,
            "active_jobs": 0,
            "expired_jobs": 0,
            "jobs": []
        }
    except Exception as e:
        logger.error(f"Error loading manifest from {MANIFEST_FILE}: {e}. Recreating manifest.")
        return {
            "last_updated": "",
            "total_jobs": 0,
            "active_jobs": 0,
            "expired_jobs": 0,
            "jobs": []
        }

def save_manifest(manifest):
    """Save job manifest to file."""
    try:
        os.makedirs(os.path.dirname(MANIFEST_FILE), exist_ok=True)
        with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Manifest saved: {MANIFEST_FILE}")
    except Exception as e:
        logger.error(f"Error saving manifest to {MANIFEST_FILE}: {e}")

def backup_manifest(now=None):
    """Copy the current manifest into jobs/backup/ BEFORE any mutation.

    Bulk changes must always be reversible: the pipeline backs up the
    previous state first and keeps the last BACKUP_KEEP daily copies.
    Returns the backup path, or None when there was nothing to back up.
    """
    if not os.path.exists(MANIFEST_FILE):
        return None
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = (now or datetime.now()).strftime('%Y-%m-%d')
        backup_path = os.path.join(BACKUP_DIR, 'manifest_backup_%s.json' % stamp)
        with open(MANIFEST_FILE, 'r', encoding='utf-8') as src:
            data = src.read()
        with open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(data)
        backups = sorted(
            name for name in os.listdir(BACKUP_DIR)
            if name.startswith('manifest_backup_') and name.endswith('.json')
        )
        for old_name in backups[:-BACKUP_KEEP] if len(backups) > BACKUP_KEEP else []:
            try:
                os.remove(os.path.join(BACKUP_DIR, old_name))
            except OSError as e:
                logger.warning(f"Could not remove old backup {old_name}: {e}")
        logger.info(f"📦 Manifest backup saved: {backup_path}")
        return backup_path
    except OSError as e:
        logger.error(f"Manifest backup failed: {e}")
        return None

def save_jobs_to_files(jobs):
    """Save jobs to individual JSON files."""
    saved_count = 0
    if not jobs:
        logger.info("No new jobs to save to individual files.")
        return 0

    logger.info(f"\n💾 Saving {len(jobs)} new jobs to individual files in '{JOB_DIR}'...")
    os.makedirs(JOB_DIR, exist_ok=True)

    for i, job in enumerate(jobs, 1):
        try:
            safe_path = job_file_path(job.get('id'))
        except ValueError as e:
            logger.error(f"  [{i}/{len(jobs)}] ⛔ Skipping job with unsafe ID: {e}")
            continue
        try:
            with open(safe_path, 'w', encoding='utf-8') as f:
                json.dump(job, f, indent=2, ensure_ascii=False)
            logger.info(f"  [{i}/{len(jobs)}] ✅ Saved: {job['title'][:60]}... to {os.path.basename(safe_path)}")
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving job file for ID {job.get('id', 'unknown')} at {safe_path}: {e}")

    logger.info(f"\n📁 Successfully saved {saved_count}/{len(jobs)} job files to '{JOB_DIR}' directory.")
    return saved_count

def _remove_orphan_job_files(manifest):
    """Delete individual job JSON files that are no longer referenced by
    the manifest (e.g. records removed by a manifest cleanup or link
    filter). Keeps the jobs/ directory in sync with the manifest."""
    if not os.path.isdir(JOB_DIR):
        return
    active_ids = {job_entry.get('id') for job_entry in manifest.get('jobs', [])}
    protected = {
        os.path.basename(MANIFEST_FILE),
        # The expired archive lives inside JOB_DIR: the orphan sweep
        # must never treat it as a stale per-job file and delete it.
        os.path.basename(ARCHIVE_FILE),
    }
    removed = 0
    for file_name in os.listdir(JOB_DIR):
        if not file_name.endswith('.json') or file_name in protected:
            continue
        file_id = file_name[:-len('.json')]
        if file_id in active_ids:
            continue
        file_path = os.path.join(JOB_DIR, file_name)
        job_dir_abs = os.path.abspath(JOB_DIR)
        resolved = os.path.realpath(file_path)
        if not resolved.startswith(job_dir_abs + os.sep):
            logger.warning(f"Skipping suspicious job file outside jobs dir: {file_name}")
            continue
        try:
            os.remove(file_path)
            removed += 1
        except OSError as e:
            logger.error(f"Error removing orphaned job file {file_path}: {e}")
    if removed:
        logger.info(f"\U0001f5d1\ufe0f Removed {removed} orphaned job file(s) not present in the manifest.")

def _archive_expired_jobs(overflow):
    """Move overflow expired records to jobs/expired_archive.json.

    History is preserved on disk, but the live manifest stays bounded
    so mobile clients do not download unbounded JSON.
    """
    archived = 0
    try:
        existing = []
        if os.path.exists(ARCHIVE_FILE):
            with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    existing = data
        existing.extend(overflow)
        existing = existing[-MAX_ARCHIVED_EXPIRED:]
        with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        archived = len(overflow)
        logger.info(f"🗄️ Archived {archived} older expired record(s) to {ARCHIVE_FILE}.")
    except Exception as e:
        logger.error(f"Failed to archive expired jobs: {e}")
    return archived

def count_statuses(jobs):
    """Consistent counters derived from the actual job statuses."""
    active = 0
    expired = 0
    for job in jobs or []:
        status = str(job.get('status') or '').lower()
        if status == 'expired':
            expired += 1
        elif status in ('active', 'upcoming'):
            active += 1
    return {'total_jobs': len(jobs or []), 'active_jobs': active, 'expired_jobs': expired}

def refresh_job_statuses():
    """Recompute every job status and the manifest counters.

    Expiry policy (master plan):
    - A job expires ONLY when its verified last_date is in the past.
    - A job without a verified last date is NEVER auto-expired by an
      arbitrary age rule (the old 15-day scraped_at deletion is gone);
      it stays active and is flagged needs_review by the schema when
      stale.
    - Expired records are KEPT for reference (status='expired'), the
      most recent MAX_EXPIRED_IN_MANIFEST of them in the manifest and
      older overflow in jobs/expired_archive.json. Cancelled records
      are also kept and never shown as active.
    - Counters are recomputed from the actual statuses, so
      active_jobs/expired_jobs always match the records.
    """
    logger.info("\n🧹 Refreshing job statuses (verified last_date only)...")
    manifest = load_manifest()
    jobs_in_manifest = manifest.get('jobs', [])

    if not jobs_in_manifest:
        manifest['total_jobs'] = 0
        manifest['active_jobs'] = 0
        manifest['expired_jobs'] = 0
        save_manifest(manifest)
        _remove_orphan_job_files(manifest)
        return {'expired': 0, 'archived': 0}

    active_jobs = []
    expired_jobs = []
    for job_entry in jobs_in_manifest:
        normalized = normalize_job(job_entry)
        if normalized.get('status') == 'expired':
            expired_jobs.append(normalized)
        else:
            active_jobs.append(normalized)

    # Keep the freshest expired records in the manifest; archive the rest.
    expired_jobs.sort(
        key=lambda j: str(j.get('last_verified') or j.get('scraped_at') or ''),
        reverse=True,
    )
    keep_expired = expired_jobs[:MAX_EXPIRED_IN_MANIFEST]
    overflow = expired_jobs[MAX_EXPIRED_IN_MANIFEST:]
    archived = _archive_expired_jobs(overflow) if overflow else 0

    final_jobs = active_jobs + keep_expired
    counters = count_statuses(final_jobs)
    manifest['jobs'] = final_jobs
    manifest['total_jobs'] = counters['total_jobs']
    manifest['active_jobs'] = counters['active_jobs']
    manifest['expired_jobs'] = counters['expired_jobs']
    save_manifest(manifest)
    _remove_orphan_job_files(manifest)
    logger.info(
        f"✅ Status refresh complete: {counters['active_jobs']} active, "
        f"{counters['expired_jobs']} expired kept, {archived} archived."
    )
    return {'expired': len(expired_jobs), 'archived': archived}

SEO_STOPWORDS = {'recruitment', 'apply', 'online', 'post', 'posts', 'vacancies', 'notification', 'various', 'department', 'board', 'commission', 'service', '2023', '2024', '2025', '2026', 'india', 'state', 'vacancy', 'examination', 'exam'}

def update_seo_keywords():
    """Extract keywords from jobs and update index.html."""
    logger.info("\n🔍 Updating SEO keywords based on active jobs...")
    try:
        manifest = load_manifest()
    except Exception as e:
        logger.error(f"Failed to load manifest for SEO update: {e}")
        return

    jobs = manifest.get('jobs', [])
    if not jobs:
        logger.info("No jobs found to extract keywords.")
        return

    words = []
    base_keywords = ['sarkari job', 'government jobs', 'sarkari naukri', 'indian government jobs', 'job portal']

    for job in jobs:
        title = job.get('title', '')
        category = job.get('category', '')

        t_lower = title.lower()
        tokens = re.findall(r'\b[a-zA-Z]{4,}\b', t_lower)
        filtered_tokens = [t for t in tokens if t not in SEO_STOPWORDS]

        words.extend(filtered_tokens)
        if category:
            words.append(category.lower())

    from collections import Counter
    word_counts = Counter(words)
    top_words = [word for word, count in word_counts.most_common(15)]

    all_keywords = list(dict.fromkeys(base_keywords + top_words))
    keywords_str = ", ".join(all_keywords)

    html_path = 'index.html'
    try:
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            pattern = r'<meta name="keywords" content="[^"]*">'
            replacement = f'<meta name="keywords" content="{keywords_str}">'

            if re.search(pattern, html_content):
                new_html = re.sub(pattern, replacement, html_content)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(new_html)
                logger.info(f"✅ Successfully updated index.html with {len(all_keywords)} SEO keywords.")
            else:
                logger.warning("Could not find keywords meta tag in index.html to update.")
    except Exception as e:
        logger.error(f"Failed to update index.html for SEO: {e}")
