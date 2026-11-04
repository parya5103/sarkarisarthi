"""Official government job sources (master plan Phase 3).

Only official recruitment listings are automated here. Every adapter:
- checks robots.txt FIRST and refuses to fetch when disallowed;
- identifies itself with an honest User-Agent (never spoofs a browser);
- makes a single polite request with a timeout (no retry storms);
- returns [] on any failure so the pipeline continues with other sources;
- builds records from VERIFIED row data only: no invented vacancies,
  qualifications, links or dates.

Automated now:
- Employment News (employmentnews.gov.in), the official Government of
  India weekly. Its AllJobs listing publishes, per row: issued date,
  organisation, post, method of appointment and last date. Both date
  columns actually carry DD/MM/YYYY values (the issued-date header
  says MM/DD/YYYY, but live rows like 31/08/2026 prove day-first).
  Those five verified values become the job record.

NOT automated (deliberately): SSC, UPSC, IBPS, MPESB. UPSC requires
JavaScript to render, and IBPS/MPESB/SSC sit behind anti-bot walls
(WAFs). Automated scraping there would be fragile and against the
project rules; those sources are served by the admin manual-import
form (full-schema Add Job modal in admin.html/admin.js), where the
admin pastes the official notification and application URLs.
"""

import hashlib
import logging
import urllib.robotparser
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LISTING_URL = 'https://employmentnews.gov.in/newemp/AllJobs.aspx?k=All'
SOURCE_NAME = 'employmentnews.gov.in'

# Honest identity: this is an automated job portal, not a browser.
USER_AGENT = 'SarkariSarthiJobPortal/2.0 (government job portal; https://gogocompany.in/sarkari-sarthi/)'
HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'}


def _default_fetch(url, timeout):
    """Single polite GET. Raises on HTTP errors; no retries by design."""
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.content


def _robots_url(url):
    """robots.txt URL for the origin of the given URL, or None."""
    scheme_end = url.find('://')
    if scheme_end < 0:
        return None
    rest = url[scheme_end + 3:]
    slash = rest.find('/')
    origin = rest if slash < 0 else rest[:slash]
    return url[:scheme_end + 3] + origin + '/robots.txt'


def robots_allows_from_text(text, url, user_agent):
    """Evaluate robots.txt rules (as text) against one URL."""
    rp = urllib.robotparser.RobotFileParser()
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'replace')
    rp.parse(text.splitlines() if text else [])
    return rp.can_fetch(user_agent, url)


def robots_allows(url, user_agent, fetch=None):
    """True when robots.txt permits fetching url with user_agent.

    A fetchable robots.txt that disallows -> hard stop (False).
    robots.txt missing/404 (raises) or unreachable -> allowed, but the
    caller still only makes one polite identified request.
    """
    fetch = fetch or _default_fetch
    robots_url = _robots_url(url)
    if not robots_url:
        return False
    try:
        text = fetch(robots_url, 10)
    except Exception as e:
        logger.warning('robots.txt unreachable at %s (%s); proceeding with a single polite request', robots_url, e)
        return True
    if not robots_allows_from_text(text, url, user_agent):
        logger.warning('robots.txt at %s disallows %s; source skipped', robots_url, url)
        return False
    return True


def _convert_issued_date(raw):
    """Parse an issued-date cell as DD/MM/YYYY (day-first).

    The listing column header claims MM/DD/YYYY, but the live values
    are day-first (verified: rows such as 31/08/2026 cannot be
    month-first). None when blank or unparseable.
    """
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), '%d/%m/%Y').strftime('%d-%m-%Y')
    except ValueError:
        return None


def _convert_date(raw, fmt):
    """Parse one listing date cell; None when blank or unparseable."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), fmt).strftime('%d-%m-%Y')
    except ValueError:
        return None


def parse_employment_news_html(html_bytes, now=None):
    """Parse the Employment News AllJobs table into job records.

    Defensive by design: works on any table whose rows carry
    [issued date, organisation, post, method, last date] cells, so an
    ASP.NET id/class change does not break it. Rows without a
    parseable issued date are skipped (headers, footers, junk).
    """
    now = now or datetime.now().isoformat()
    soup = BeautifulSoup(html_bytes, 'html.parser')
    jobs = []
    seen_ids = set()

    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 4:
            continue
        texts = [cell.get_text(separator=' ', strip=True) for cell in cells]
        issued = _convert_issued_date(texts[0])
        if not issued:
            continue
        org = texts[1]
        post = texts[2]
        method = texts[3]
        if not org or not post:
            continue
        last = _convert_date(texts[4], '%d/%m/%Y') if len(texts) >= 5 else None

        digest = hashlib.md5('|'.join([org, post, last or 'none']).encode('utf-8')).hexdigest()
        job_id = 'en_' + digest
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        link = row.find('a', href=True)
        if link:
            url = urljoin(LISTING_URL, link['href'].split('#')[0])
        else:
            url = LISTING_URL + '#en-' + digest

        important_dates = {'found_date': issued}
        if last:
            important_dates['last_date'] = last

        description = 'Employment News (Government of India) listing: ' + post + ' at ' + org + '.'
        if method:
            description = description + ' Method of appointment: ' + method + '.'
        description = description + ' Issued: ' + issued + '.'
        if last:
            description = description + ' Last date: ' + last + '.'

        jobs.append({
            'id': job_id,
            'title': post + ' - ' + org,
            'organization': org,
            'url': url,
            'source': SOURCE_NAME,
            'description': description,
            'pdf_link': None,
            'important_dates': important_dates,
            'published_date': issued,
            'category': 'General',
            'skills': [],
            'scraped_at': now,
            'links': [LISTING_URL],
        })

    return jobs


def fetch_employment_news_jobs(fetch=None, now=None):
    """Robots-checked, polite fetch of the Employment News listing.

    Returns a list of complete job records, or [] on any failure
    (robots disallow, network error, layout change). Never raises and
    never substitutes demo data.
    """
    fetch = fetch or _default_fetch
    if not robots_allows(LISTING_URL, USER_AGENT, fetch):
        return []
    try:
        html = fetch(LISTING_URL, 30)
    except Exception as e:
        logger.warning('Employment News listing fetch failed: %s', e)
        return []
    if not html:
        return []
    jobs = parse_employment_news_html(html, now=now)
    if jobs:
        logger.info('Employment News: %d rows parsed', len(jobs))
    else:
        logger.warning('Employment News listing yielded no parseable rows (layout change or empty listing)')
    return jobs
