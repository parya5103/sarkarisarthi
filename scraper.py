import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
from datetime import datetime
import time
import random
import concurrent.futures

# Honest identity + robots.txt checking are shared with the official
# adapters: generic portal scraping must follow the same rules.
from official_sources import robots_allows, USER_AGENT

logger = logging.getLogger(__name__)

# Source registry (Phase 1 documentation; adapters are added in later
# phases only after permission research):
# - allgovernmentjobs.in: robots default-allow, current primary source.
# - freejobalert.com / fresherslive.com: robots.txt allows generic
#   crawling (verified 2026-11-03); adapters are Phase 2 candidates.
# - freshersnow.com: robots.txt User-agent: * Allow: / (verified
#   2026-11-03; only /wp-admin/ disallowed) -> added to the list below.
# - sarkariresult.com: robots.txt itself returns 403 (CloudFront
#   anti-bot) -> discovery-only, do not scrape.
# - kirannewsagency.com: no robots.txt found; terms unverified ->
#   discovery-only until manually reviewed.
# - ssc.gov.in / ibps.in / esb.mp.gov.in / mppsc.mp.gov.in: anti-bot
#   walls -> manual admin import only (see official_sources.py).
# - employmentnews.gov.in is handled by the official adapter in
#   official_sources.py, so it is NOT in the generic list below.
JOB_PORTALS = {
    'government': [
        'https://www.freejobalert.com',
        'https://www.freshersnow.com',
        'https://www.sarkarinaukri.com',
        'https://www.mysarkarinaukri.com',
        'https://bharatsarkarijob.com',
        'https://allgovernmentjobs.in',
        'https://www.sarkariexam.com',
        'https://www.rojgarresult.com',
        'https://www.jobriya.com',
        'https://www.sarkari-naukri.info',
        'https://www.freshersworld.com/government-jobs'
    ],
    'private': [
        "https://www.sarkarinaukridaily.in/",
        "https://www.fresherslive.com/govt-jobs",
        "https://www.jobsarkari.com/",
        "https://www.naukrigulf.com/government-jobs",
        "https://www.latestgovtjobs.in/",
        "https://www.indiagovtjobs.in/",
        "https://sarkariprep.in/",
        "https://linkingsky.com/ "
    ]
}

def fetch_page_content(url, timeout=15, retries=3):
    headers = {
        # Honest identity: this is an automated job portal, not a
        # browser. Never spoof a browser User-Agent.
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-IN,en;q=0.9,hi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }

    for attempt in range(retries):
        try:
            time.sleep(random.uniform(2, 4))
            response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
            response.raise_for_status()
            logger.info(f"✅ Successfully fetched: {url} (Status: {response.status_code})")
            return response.content
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt == retries - 1:
                logger.error(f"❌ Failed to fetch {url} after {retries} attempts")
                return None
    return None

# Pre-allocate static sets/tuples to prevent re-allocation per inner loop iteration
VALID_JOB_KEYWORDS = (
    'job', 'recruitment', 'vacancy', 'notification', 'exam',
    'apply', 'bharti', 'posts', 'officer', 'clerk', 'assistant',
    'manager', 'engineer', 'teacher', 'constable', 'govt',
    'government', 'sarkari', 'admission form', 'eligibility',
    'syllabus', 'result', 'admit card', 'walk-in', 'interview', 'selection', 'merit list'
)
VALID_URL_KEYWORDS = ('job', 'recruitment', 'vacancy', 'notification', 'apply')
EXCLUDE_URL_WORDS = ('login', 'register', 'contact', 'about', 'privacy', 'terms')

def _is_valid_job_link(title, full_url):
    """Validate if a link is a genuine vacancy detail page, not a
    navigation/category/organization listing page of the source portal."""
    u_lower = full_url.lower()

    if any(exclude_word in u_lower for exclude_word in EXCLUDE_URL_WORDS):
        return False

    # Reject source-portal navigation pages: portal home pages,
    # "jobs-by-category" style listing pages, and generic
    # category/organization pages (e.g. "medical-jobs",
    # "iit-delhi-recruitment", "Bank Jobs"). Genuine vacancy
    # notifications almost always carry a year or post id in the URL
    # slug or the post title.
    parsed = urlparse(full_url)
    path = parsed.path.rstrip('/')
    last_segment = path.rsplit('/', 1)[-1] if path else ''
    if not last_segment:
        return False
    if 'jobs-by-' in path:
        return False
    title_has_digit = any(ch.isdigit() for ch in title)
    url_has_digit = any(ch.isdigit() for ch in last_segment)
    if not title_has_digit and not url_has_digit:
        return False

    if len(title) > 30:
        return True

    t_lower = title.lower()
    return (
        any(keyword in t_lower for keyword in VALID_JOB_KEYWORDS) or
        any(word in u_lower for word in VALID_URL_KEYWORDS)
    )

def _extract_jobs_from_selector(links, url, site_name, found_links_overall):
    """Extract job links from a list of BeautifulSoup elements."""
    extracted_jobs = []
    for link in links[:20]:
        try:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or not href or len(title) < 5:
                continue

            full_url = urljoin(url, href).split('#')[0]
            if not full_url.startswith('http') or full_url in found_links_overall:
                continue

            if _is_valid_job_link(title, full_url):
                job_id = hashlib.md5(full_url.encode()).hexdigest()
                extracted_jobs.append({
                    'id': job_id,
                    'title': title,
                    'url': full_url,
                    'source': site_name,
                    'description': '',
                    'pdf_link': None,
                    'important_dates': {},
                    'category': 'General',
                    'skills': [],
                    'scraped_at': datetime.now().isoformat()
                })
                found_links_overall.add(full_url)
        except Exception as e_link:
            continue
    return extracted_jobs

def scrape_generic_job_site(url, site_name, metrics=None):
    logger.info(f"\n🔍 Scraping {site_name}...")

    # robots.txt FIRST: a portal that disallows automated access is
    # skipped entirely (recorded as a permission refusal, not an error).
    try:
        allowed = robots_allows(url, USER_AGENT)
    except Exception as e_robots:
        logger.warning(f"robots.txt check failed for {site_name}: {e_robots}")
        allowed = False
    if not allowed:
        logger.warning(f"⛔ {site_name}: robots.txt disallows automated fetching; skipping source.")
        if metrics is not None:
            metrics.record(site_name, status='robots-disallowed',
                           permission='disallowed', discovered=0,
                           notes='robots.txt refuses this user-agent or path')
        return []

    started = datetime.now()
    html_content = fetch_page_content(url)
    jobs = []

    if not html_content:
        logger.warning(f"❌ No content fetched from {site_name}. Skipping.")
        if metrics is not None:
            metrics.record(site_name, status='fetch-failed', permission='allowed',
                           duration_s=round((datetime.now() - started).total_seconds(), 2),
                           discovered=0,
                           notes='listing page unreachable or blocked')
        return jobs

    try:
        soup = BeautifulSoup(html_content, 'lxml')
        job_selectors = [
            '.job-title a', '.vacancy-link', '.post-title a', '.job-link',
            'a[href*="jobs"]', 'a[href*="notification"]', 'a[href*="vacancy"]',
            'a[href*="recruitment"]', 'a[href*="bharti"]', 'a[href*="apply-online"]',
            'h3 a', 'h2 a', 'h1 a',
            'a[title*="job" i]', 'a[title*="recruitment" i]', 'a[class*="job" i]', 'a[id*="job" i]'
        ]

        logger.info(f"🔎 Trying {len(job_selectors)} different selectors for {site_name}...")
        found_links_overall = set()

        for i, selector in enumerate(job_selectors):
            try:
                links = soup.select(selector)
                current_selector_links = _extract_jobs_from_selector(links, url, site_name, found_links_overall)

                if current_selector_links:
                    jobs.extend(current_selector_links)
                    logger.info(f"  ✅ Found {len(current_selector_links)} potentially valid jobs with selector '{selector}'.")
            except Exception as e_selector:
                continue
    except Exception as e_soup:
        logger.error(f"❌ Error parsing HTML content for {site_name}: {e_soup}")
        if metrics is not None:
            metrics.record(site_name, status='parse-error', permission='allowed',
                           duration_s=round((datetime.now() - started).total_seconds(), 2),
                           discovered=0, parser_errors=1, notes=str(e_soup)[:120])
        return jobs

    duration = round((datetime.now() - started).total_seconds(), 2)
    if metrics is not None:
        metrics.record(
            site_name,
            status='ok' if jobs else 'no-jobs',
            permission='allowed',
            duration_s=duration,
            discovered=len(jobs),
            notes='' if jobs else 'listing fetched but no vacancy links parsed',
        )
    return jobs

def _scrape_single_portal(url, index, total, category_name, metrics=None):
    try:
        site_name = url.split('//')[1].split('/')[0]
        logger.info(f"\n[{index}/{total}] {category_name} Site: {site_name}")
        jobs = scrape_generic_job_site(url, site_name, metrics=metrics)
        return jobs
    except Exception as e:
        logger.error(f"❌ Unhandled error during scraping of {url}: {e}")
        if metrics is not None:
            metrics.record(url, status='error', discovered=0, notes=str(e)[:120])
        return []

def scrape_all_job_portals(metrics=None):
    all_jobs = []
    successful_sites = 0

    portals_to_scrape = []
    gov_portals = JOB_PORTALS['government']
    for i, url in enumerate(gov_portals, 1):
        portals_to_scrape.append((url, i, len(gov_portals), "Government"))

    priv_portals = JOB_PORTALS['private'][:3]
    for i, url in enumerate(priv_portals, 1):
        portals_to_scrape.append((url, i, len(priv_portals), "Private"))

    if not portals_to_scrape:
        return []

    max_workers = min(10, len(portals_to_scrape))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scrape_single_portal, url, index, total, category, metrics): url for url, index, total, category in portals_to_scrape}
        for future in concurrent.futures.as_completed(futures):
            try:
                jobs = future.result()
                if jobs:
                    all_jobs.extend(jobs)
                    successful_sites += 1
            except Exception as exc:
                pass
    return all_jobs
