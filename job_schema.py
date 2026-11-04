"""Consistent job record schema, status computation, verification
labels, deduplication and cross-source merging.

Every job saved to the manifest and to jobs/<id>.json passes through
normalize_job() so the whole system works with one structure:

    id, title, organization, department, recruitment_board, category,
    employment_type, location, state, district, vacancies,
    advertisement_no, qualification, minimum_qualification,
    age_limit, age_min, age_max, age_relaxation, salary, pay_scale,
    application_fee, selection_process, description,
    description_summary, important_dates (last_date,
    application_start_date, exam_date, ...), official_notification_url,
    official_application_url, official_website, original_source_url,
    url, source, source_refs, published_date, scraped_at,
    last_verified, status, verification_status.

Rules from the project master plan:
- Missing information is stored as None. It is NEVER fabricated here.
  The UI renders None values as NOT_SPECIFIED_TEXT.
- status is derived only from real parsed dates:
  cancelled > expired > upcoming > active.
- verification_status distinguishes official backing from
  private-source-only records:
      official_verified       official link present or official source
      official_link_pending  official domain referenced in links only
      secondary_source_only   private source, no official backing
      needs_review            stale record or invalid official URL
      expired / cancelled     lifecycle states
  A private-source-only job can never be labelled official_verified.
- Deduplication matches on the official URL, on a non-empty
  (advertisement_no, organization) pair, or on an exact normalized
  title + identical verified last date. Jobs are never merged just
  because their titles look similar.
- merge_job() fills ONLY missing fields of an existing record and
  records the duplicate's source as attribution. A later verified
  last date (deadline extension / corrigendum) updates the record.
"""

from datetime import date, datetime, timedelta
from urllib.parse import urlparse

NOT_SPECIFIED_TEXT = 'Not specified in official notification'

DATE_FORMATS = ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d %b %Y', '%d %B %Y')

# Indian government domains: data from these sources is official.
OFFICIAL_DOMAIN_SUFFIXES = ('.gov.in', '.nic.in')

OPTIONAL_TEXT_FIELDS = (
    'organization', 'department', 'recruitment_board', 'location',
    'state', 'district', 'vacancies', 'advertisement_no',
    'qualification', 'minimum_qualification', 'age_limit',
    'age_min', 'age_max', 'age_relaxation', 'salary', 'pay_scale',
    'application_fee', 'selection_process', 'employment_type',
    'official_notification_url', 'official_application_url',
    'official_website', 'description_summary', 'published_date',
)

# Fields a merged-in duplicate candidate may fill when missing.
MERGEABLE_FIELDS = OPTIONAL_TEXT_FIELDS + ('description',)


def parse_date(value):
    """Parse a job date string to datetime.date, or None.

    Understands the common Indian job-notification formats and ISO
    timestamps. Returns None for anything unparseable: callers must
    treat None as 'not available', never guess a date.
    """
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        return None


def compute_status(job, today=None):
    """Derive job status without inventing information.

    cancelled: previously stored status says so (admin-controlled).
    expired:   parsed last_date is strictly before today.
    upcoming:  parsed application_start_date is strictly after today.
    active:    otherwise (including jobs with no parseable dates).
    """
    today = today or date.today()
    if str(job.get('status') or '').lower() == 'cancelled':
        return 'cancelled'
    dates = job.get('important_dates') or {}
    last_date = parse_date(dates.get('last_date') or job.get('last_date'))
    if last_date and last_date < today:
        return 'expired'
    start_date = parse_date(
        dates.get('application_start_date') or job.get('application_start_date')
    )
    if start_date and start_date > today:
        return 'upcoming'
    return 'active'


def _host_of(url):
    """Lowercased hostname of a URL, or '' when unparseable."""
    if not isinstance(url, str) or not url.strip():
        return ''
    candidate = url.strip()
    if '://' not in candidate:
        candidate = 'http://' + candidate
    try:
        return (urlparse(candidate).netloc or '').lower()
    except ValueError:
        return ''


def is_official_url(url):
    """True when the URL is http(s) AND points to an official domain."""
    if not validate_http_url(url):
        return False
    host = _host_of(url)
    return bool(host) and host.endswith(OFFICIAL_DOMAIN_SUFFIXES)


def validate_http_url(url):
    """Only http/https URLs are valid clickable external links.

    Blocks javascript:, data: and every other scheme. Never lets a
    malformed or non-string value pass.
    """
    if not isinstance(url, str):
        return False
    cleaned = url.strip()
    return cleaned.lower().startswith('http://') or cleaned.lower().startswith('https://')


def _source_is_official(job):
    """True when the record itself comes from an official domain."""
    for field in ('source', 'url', 'original_source_url'):
        value = job.get(field)
        if not isinstance(value, str):
            continue
        host = _host_of(value) if '://' in value else value.strip().lower()
        if host and host.endswith(OFFICIAL_DOMAIN_SUFFIXES):
            return True
    return False


def _any_official_link(job):
    for link in job.get('links') or []:
        if is_official_url(link):
            return True
    return False


# A record without a verified last date that has not been re-checked
# for this many days is flagged for review (it is NEVER auto-expired).
STALE_AFTER_DAYS = 30


def compute_verification_status(job, today=None):
    """Derive the verification label without inventing information."""
    status = str(job.get('status') or '').lower()
    if status == 'cancelled':
        return 'cancelled'
    if status == 'expired':
        return 'expired'

    # An official link field that is present but not a valid http(s)
    # URL means the record carries unusable data: flag for review.
    for field in ('official_notification_url', 'official_application_url'):
        value = job.get(field)
        if value and not validate_http_url(value):
            return 'needs_review'

    # Stale record: no verified last date and not checked recently.
    dates = job.get('important_dates') or {}
    if not parse_date(dates.get('last_date') or job.get('last_date')):
        checked = parse_date(job.get('last_verified')) or parse_date(job.get('scraped_at'))
        today = today or date.today()
        if checked and (today - checked).days > STALE_AFTER_DAYS:
            return 'needs_review'

    # Official backing: a verified official link or an official source.
    if validate_http_url(job.get('official_notification_url')) or \
       validate_http_url(job.get('official_application_url')):
        return 'official_verified'
    if _source_is_official(job):
        return 'official_verified'
    # An official domain referenced in scraped links: the record
    # references the official notice but no direct link was captured.
    if _any_official_link(job):
        return 'official_link_pending'
    return 'secondary_source_only'


def normalize_job(job, now=None):
    """Return a copy of job upgraded to the full schema.

    - Preserves every existing key (no data is dropped or overwritten).
    - Backfills important_dates from flat admin fields (last_date,
      application_start_date) when the nested value is missing.
    - Sets missing optional fields to None (meaning: not available in
      the official notification; the UI shows NOT_SPECIFIED_TEXT).
    - last_verified defaults to scraped_at, else to now.
    - status is (re)computed from the real dates.
    - verification_status is (re)computed from official backing.
    """
    if not isinstance(job, dict):
        raise ValueError('normalize_job expects a dict job record')
    now = now or datetime.now().isoformat()

    normalized = dict(job)
    dates = dict(normalized.get('important_dates') or {})
    if not dates.get('last_date') and normalized.get('last_date'):
        dates['last_date'] = normalized['last_date']
    if not dates.get('application_start_date') and normalized.get('application_start_date'):
        dates['application_start_date'] = normalized['application_start_date']
    normalized['important_dates'] = dates

    for field in OPTIONAL_TEXT_FIELDS:
        if normalized.get(field) in (None, ''):
            normalized[field] = None

    if not normalized.get('description') and normalized.get('summary'):
        normalized['description'] = normalized['summary']
    if not normalized.get('original_source_url') and normalized.get('url'):
        normalized['original_source_url'] = normalized['url']
    if not normalized.get('last_verified'):
        normalized['last_verified'] = normalized.get('scraped_at') or now
    normalized['status'] = compute_status(normalized)
    normalized['verification_status'] = compute_verification_status(normalized)
    return normalized


def _clean_text(value):
    """Lowercase, whitespace-collapsed text for comparisons, or None."""
    if not isinstance(value, str):
        return None
    collapsed = ' '.join(value.split()).strip().lower()
    return collapsed or None


def advertisement_key(job):
    """(advertisement_no, organization) comparison key, or None.

    Only non-empty pairs count: deduplicating on a partial key would
    merge unrelated advertisements.
    """
    adv = _clean_text(job.get('advertisement_no'))
    org = _clean_text(job.get('organization'))
    if adv and org:
        return (adv, org)
    return None


def title_date_key(job):
    """(normalized title, verified last date) key, or None.

    Medium-confidence duplicate signal: the same vacancy republished
    by several portals usually keeps its exact title and last date.
    Only counts when BOTH are present, so it can never merge two
    merely similar-looking titles.
    """
    title = _clean_text(job.get('title'))
    dates = job.get('important_dates') or {}
    last = parse_date(dates.get('last_date') or job.get('last_date'))
    if title and last:
        return (title, last.isoformat())
    return None


def is_duplicate_job(candidate, existing_urls, existing_adv_keys,
                     existing_title_date_keys=None):
    """Return a duplicate reason string, or None if the job is unique.

    Duplicate when the official URL was already stored, when the same
    (advertisement_no, organization) was already stored, or when an
    exact normalized title plus the same verified last date was
    already stored. Titles alone NEVER deduplicate.
    """
    url = candidate.get('url')
    if url and url in existing_urls:
        return 'same-url'
    key = advertisement_key(candidate)
    if key and key in existing_adv_keys:
        return 'same-advertisement'
    if existing_title_date_keys is not None:
        td_key = title_date_key(candidate)
        if td_key and td_key in existing_title_date_keys:
            return 'same-title-date'
    return None


def merge_job(existing, incoming, now=None):
    """Merge a duplicate candidate into an existing record.

    - Fills ONLY fields that are missing (None or '') on the existing
      record. Existing values are never overwritten.
    - Keeps source attribution: the duplicate's (source, url) is
      appended to source_refs when new.
    - A verified last date STRICTLY LATER than the stored one updates
      the record (deadline extension / corrigendum).
    - Recomputes status and verification_status after the merge.

    Returns (merged_job, filled_field_count).
    """
    now = now or datetime.now().isoformat()
    merged = dict(existing)
    filled = 0

    for field in MERGEABLE_FIELDS:
        if merged.get(field) in (None, '') and incoming.get(field) not in (None, ''):
            merged[field] = incoming[field]
            filled += 1

    dates = dict(merged.get('important_dates') or {})
    incoming_dates = incoming.get('important_dates') or {}
    for key, value in incoming_dates.items():
        if value and not dates.get(key):
            dates[key] = value
            filled += 1
    merged['important_dates'] = dates

    # Corrigendum rule: a later verified last date extends the deadline.
    old_last = parse_date(dates.get('last_date') or merged.get('last_date'))
    new_last = parse_date(
        (incoming.get('important_dates') or {}).get('last_date')
        or incoming.get('last_date')
    )
    if new_last and (not old_last or new_last > old_last):
        if dates.get('last_date') != (incoming.get('important_dates') or {}).get('last_date'):
            dates['last_date'] = (incoming_dates.get('last_date')
                                  or incoming.get('last_date'))
            merged['important_dates'] = dates
            merged['deadline_extended'] = True
            filled += 1

    refs = list(merged.get('source_refs') or [])
    ref = {
        'source': incoming.get('source') or None,
        'url': incoming.get('url') or None,
    }
    if ref['source'] or ref['url']:
        already = any(
            r.get('url') == ref['url'] and r.get('source') == ref['source']
            for r in refs if isinstance(r, dict)
        )
        if not already:
            refs.append(ref)
            merged['source_refs'] = refs
            filled += 1

    if filled:
        merged['last_verified'] = now
    merged = normalize_job(merged)
    return merged, filled


NOTIFICATION_WINDOW_HOURS = 36
NOTIFICATION_CAP = 25


def select_recent_jobs(jobs, now=None, hours=NOTIFICATION_WINDOW_HOURS, cap=NOTIFICATION_CAP):
    """Return jobs first recorded within the notification window, capped.

    Notification channels must not blast the full manifest every run:
    only jobs whose scraped_at (or found_date / last_verified
    fallback) falls inside the window are selected, at most `cap` of
    them. Jobs without any usable timestamp are skipped rather
    than guessed.
    """
    now = now or date.today()
    window_start = now - timedelta(hours=hours)
    selected = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        stamp = (job.get('scraped_at')
                 or (job.get('important_dates') or {}).get('found_date')
                 or job.get('last_verified'))
        parsed = parse_date(stamp) if stamp else None
        if parsed and parsed >= window_start:
            selected.append(job)
    return selected[:cap]
