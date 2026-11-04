#!/usr/bin/env python3
"""
SarkariSarthi 2.0 - Job Fetcher (Fixed Version for GitHub Actions)
Job scraper for Indian government and public-sector jobs

Phase 1 (data quality):
- duplicate candidates are MERGED into existing records (missing
  fields filled, source attribution kept, deadline extensions apply)
  instead of being silently dropped;
- the manifest is backed up before every mutation (jobs/backup/);
- expiry is based ONLY on a verified last_date (no arbitrary age rule);
- per-source metrics are recorded and a readable daily source report
  is written to logs/source_report.{json,md};
- --dry-run runs the whole pipeline and reports what WOULD change
  without touching the manifest, job files or generated pages.
"""

import argparse
import logging
import os
import sys

from datetime import datetime

import concurrent.futures

# Import from refactored modules
from storage import (
    JOB_DIR, MANIFEST_FILE, load_manifest, save_manifest,
    save_jobs_to_files, refresh_job_statuses, update_seo_keywords,
    is_valid_job_id, backup_manifest, count_statuses
)
from scraper import JOB_PORTALS, fetch_page_content, scrape_generic_job_site, _scrape_single_portal, scrape_all_job_portals
from job_schema import normalize_job, is_duplicate_job, advertisement_key, title_date_key, merge_job
from official_sources import fetch_employment_news_jobs, SOURCE_NAME as OFFICIAL_SOURCE_NAME
from detail_pages import write_detail_pages
from source_metrics import SourceMetrics
from parser import (
    download_pdf, extract_text_from_pdf, summarize_job_description,
    extract_important_dates_and_links, auto_detect_job_category,
    extract_trending_skills, process_job_content
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main Execution ---

def _publish_detail_pages():
    """Regenerate static job detail pages + sitemap from the manifest.

    Non-fatal on purpose: a template failure must not block the data
    pipeline, but it is logged loudly in the workflow run.
    """
    try:
        manifest = load_manifest()
        write_detail_pages(manifest.get('jobs', []))
    except Exception as e:
        logger.error(f"❌ Failed to regenerate job detail pages: {e}")


def _index_existing_jobs(jobs):
    """Lookup indexes + duplicate key sets for the stored records."""
    by_url, by_adv, by_td = {}, {}, {}
    urls, adv_keys, td_keys = set(), set(), set()
    for idx, job in enumerate(jobs):
        url = job.get('url')
        if url:
            urls.add(url)
            by_url.setdefault(url, idx)
        adv = advertisement_key(job)
        if adv:
            adv_keys.add(adv)
            by_adv.setdefault(adv, idx)
        td = title_date_key(job)
        if td:
            td_keys.add(td)
            by_td.setdefault(td, idx)
    adv_keys.discard(None)
    td_keys.discard(None)
    return {
        'urls': urls, 'adv_keys': adv_keys, 'td_keys': td_keys,
        'by_url': by_url, 'by_adv': by_adv, 'by_td': by_td,
    }


def main(dry_run=False):
    """Main function to orchestrate job fetching process"""
    print("=" * 60)
    print("🚀 SarkariSarthi 2.0 Job Fetcher Started (for GitHub Actions)")
    if dry_run:
        print("🧪 DRY RUN: no files will be modified")
    print("=" * 60)

    os.makedirs(JOB_DIR, exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    logger.info(f"📁 Jobs data directory ready: {os.path.abspath(JOB_DIR)}")

    metrics = SourceMetrics()
    now = datetime.now().isoformat()

    manifest = load_manifest()
    manifest_jobs = manifest.get('jobs', [])
    existing = _index_existing_jobs(manifest_jobs)
    existing_job_urls = existing['urls']
    existing_adv_keys = existing['adv_keys']
    existing_td_keys = existing['td_keys']
    logger.info(f"📋 Existing jobs in manifest: {len(manifest_jobs)}")

    all_scraped_jobs = scrape_all_job_portals(metrics=metrics)

    # Official source: Employment News rows arrive already complete with
    # verified listing data. They must NOT be re-fetched through
    # process_job_content, so they are kept in a separate list.
    official_jobs = fetch_employment_news_jobs()
    metrics.record(
        OFFICIAL_SOURCE_NAME,
        status='ok' if official_jobs else 'no-jobs',
        permission='allowed',
        discovered=len(official_jobs),
        notes='official adapter; robots-checked, honest user-agent',
    )
    all_scraped_jobs.extend(official_jobs)

    metrics.note_pipeline_totals(raw_candidates=len(all_scraped_jobs))

    if not all_scraped_jobs:
        logger.warning("⚠️ WARNING: No jobs were scraped from any portal!")
        logger.warning("This might be due to: Network issues, website blocking, or structural changes.")
        metrics.note_pipeline_totals(new_jobs=0, duplicates=0, merged=0)
        if not dry_run:
            refresh_job_statuses()
            update_seo_keywords()
            _publish_detail_pages()
        metrics.write_report()
        print("\n" + "=" * 60)
        print("📈 FINAL SUMMARY (No new jobs scraped)")
        print("=" * 60)
        final_manifest = load_manifest()
        print(f"📊 Total active jobs in system: {final_manifest.get('active_jobs', 0)}")
        print(f"🕒 Last updated: {final_manifest.get('last_updated', 'Unknown')}")
        print("=" * 60)
        if not dry_run:
            # Honest failure (master plan Phase 7): zero jobs scraped from
            # every portal means the pipeline is broken. Fail the run
            # instead of silently pretending the site is up to date.
            sys.exit(1)
        return

    logger.info(f"\n🔍 Processing {len(all_scraped_jobs)} raw scraped jobs...")

    duplicate_count = 0
    merged_count = 0
    rejected_unsafe = 0
    merge_details = []
    jobs_to_process = []
    official_to_add = []

    for job_candidate in all_scraped_jobs:
        dup_reason = is_duplicate_job(job_candidate, existing_job_urls, existing_adv_keys, existing_td_keys)
        if dup_reason:
            duplicate_count += 1
            logger.info(f"Duplicate ({dup_reason}): {job_candidate.get('title', '')[:60]}")

            # Merge instead of dropping: fill only missing fields of the
            # stored record, keep source attribution, apply deadline
            # extensions (corrigendum rule).
            idx = None
            if dup_reason == 'same-url':
                idx = existing['by_url'].get(job_candidate.get('url'))
            elif dup_reason == 'same-advertisement':
                idx = existing['by_adv'].get(advertisement_key(job_candidate))
            elif dup_reason == 'same-title-date':
                idx = existing['by_td'].get(title_date_key(job_candidate))
            if idx is not None:
                merged_job, filled = merge_job(manifest_jobs[idx], job_candidate, now=now)
                if filled:
                    manifest_jobs[idx] = merged_job
                    merged_count += 1
                    merge_details.append({
                        'id': merged_job.get('id'),
                        'title': merged_job.get('title'),
                        'reason': dup_reason,
                        'fields_filled': filled,
                        'deadline_extended': bool(merged_job.get('deadline_extended')),
                    })
                    logger.info(f"  ↪ Merged {filled} missing field(s) into existing record")
            existing_job_urls.add(job_candidate.get('url'))
            continue
        # Security: drop any record whose ID would be unsafe as a
        # filesystem path component (jobs/<id>.json).
        if not is_valid_job_id(job_candidate.get('id')):
            logger.warning(f"⛔ Dropping scraped job with unsafe ID: {job_candidate.get('id')!r}")
            rejected_unsafe += 1
            continue
        if job_candidate.get('source') == OFFICIAL_SOURCE_NAME:
            # Official listing rows are already complete records.
            official_to_add.append(job_candidate)
        else:
            jobs_to_process.append(job_candidate)
        existing_job_urls.add(job_candidate['url'])
        adv_key = advertisement_key(job_candidate)
        if adv_key:
            existing_adv_keys.add(adv_key)
        td_key = title_date_key(job_candidate)
        if td_key:
            existing_td_keys.add(td_key)

    # Official records are normalized immediately (no per-job fetch).
    new_jobs_to_add = [normalize_job(j) for j in official_to_add]
    for j in official_to_add:
        metrics.record(j.get('source') or OFFICIAL_SOURCE_NAME, accepted=1)

    if jobs_to_process:
        logger.info(f"🔄 Concurrently processing {len(jobs_to_process)} unique jobs...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_job = {executor.submit(process_job_content, job): job for job in jobs_to_process}

            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    processed_job = future.result()
                    new_jobs_to_add.append(normalize_job(processed_job))
                    metrics.record(processed_job.get('source'), accepted=1)
                except Exception as exc:
                    metrics.record(job.get('source'), parser_errors=1)
                    logger.error(f"❌ Job processing generated an exception for {job['url']}: {exc}")

    logger.info(f"📊 Processing Summary:")
    logger.info(f"  New unique jobs to save: {len(new_jobs_to_add)}")
    logger.info(f"  Duplicates matched: {duplicate_count}")
    logger.info(f"  Merged into existing records: {merged_count}")

    manifest_dirty = merged_count > 0
    metrics.note_pipeline_totals(
        new_jobs=len(new_jobs_to_add),
        duplicates=duplicate_count,
        merged=merged_count,
        rejected_unsafe_ids=rejected_unsafe,
    )

    if dry_run:
        dry_report = {
            'run_at': now,
            'would_add': [
                {'id': j.get('id'), 'title': j.get('title'), 'source': j.get('source')}
                for j in new_jobs_to_add
            ],
            'would_merge': merge_details,
            'duplicates_skipped': duplicate_count,
            'rejected_unsafe_ids': rejected_unsafe,
            'current_counters': count_statuses(manifest_jobs),
        }
        report = metrics.write_report()
        report['dry_run'] = dry_report
        try:
            import json
            with open(os.path.join('logs', 'dry_run_report.json'), 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Failed to write dry-run report: {e}")
        print("\n" + "=" * 60)
        print("🧪 DRY RUN SUMMARY (no files were modified)")
        print("=" * 60)
        print(f"Would add: {len(new_jobs_to_add)} jobs")
        print(f"Would merge: {merged_count} duplicates into existing records")
        print(f"Duplicates matched: {duplicate_count}")
        print(f"Rejected unsafe IDs: {rejected_unsafe}")
        print(f"Full report: logs/dry_run_report.json")
        print("=" * 60)
        return

    # Backup BEFORE any mutation (bulk changes must be reversible).
    if new_jobs_to_add or manifest_dirty:
        backup_manifest()

    if new_jobs_to_add:
        saved_count = save_jobs_to_files(new_jobs_to_add)
        manifest['jobs'].extend(new_jobs_to_add)
        manifest['last_updated'] = now
        counters = count_statuses(manifest['jobs'])
        manifest['total_jobs'] = counters['total_jobs']
        manifest['active_jobs'] = counters['active_jobs']
        manifest['expired_jobs'] = counters['expired_jobs']
        save_manifest(manifest)

        logger.info(f"\n✅ Successfully added {saved_count} new jobs to the system!")
    elif manifest_dirty:
        # Merges changed existing records: persist them too.
        manifest['last_updated'] = now
        save_manifest(manifest)
        logger.info("\n♻️ No new jobs, but merged duplicate information into existing records.")
    else:
        logger.info("\n📋 No new unique jobs to add (all were duplicates or none found).")

    status_result = refresh_job_statuses()
    metrics.note_pipeline_totals(
        expired_now=status_result.get('expired', 0),
        archived_expired=status_result.get('archived', 0),
    )
    update_seo_keywords()
    _publish_detail_pages()
    metrics.write_report()

    final_manifest = load_manifest()
    print("\n" + "=" * 60)
    print("📈 FINAL SYSTEM SUMMARY")
    print("=" * 60)
    print(f"✅ SarkariSarthi 2.0 Job Fetcher completed successfully!")
    print(f"📊 Total active jobs currently in system: {final_manifest.get('active_jobs', 0)}")
    print(f"📁 Jobs directory: {os.path.abspath(JOB_DIR)}")
    print(f"📋 Manifest file: {os.path.abspath(MANIFEST_FILE)}")
    print(f"🕒 Last updated: {final_manifest.get('last_updated', 'Unknown')}")
    print("=" * 60)

def test_single_site():
    """Test function for debugging a single site."""
    test_url = "https://www.freejobalert.com"
    logger.info(f"🧪 Testing single site: {test_url}")

    os.makedirs(JOB_DIR, exist_ok=True)
    jobs = scrape_generic_job_site(test_url, "freejobalert_test")

    if jobs:
        logger.info(f"✅ Test successful! Found {len(jobs)} jobs (first 5 shown):")
        for i, job in enumerate(jobs[:5], 1):
            logger.info(f"  {i}. Title: {job['title'][:60]}... URL: {job['url']}")

        processed_test_jobs = [process_job_content(job) for job in jobs[:5]]
        save_jobs_to_files(processed_test_jobs)
        return True
    else:
        logger.warning("❌ Test failed - no jobs found from the test site.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SarkariSarthi job fetcher")
    parser.add_argument('--dry-run', action='store_true',
                        help='Report what would change without modifying any file')
    args = parser.parse_args()
    main(dry_run=args.dry_run)
