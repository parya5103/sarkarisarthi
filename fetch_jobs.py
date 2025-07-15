import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dateparser

JOBS_DIR = "jobs"
PRIVATE_SOURCES = [
    "https://www.freejobalert.com/",
    "https://www.sarkarinaukridaily.in/",
    "https://www.sarkarinaukri.com/",
    "https://www.fresherslive.com/govt-jobs",
    "https://www.jobsarkari.com/",
    "https://www.naukrigulf.com/government-jobs",
    "https://rojgarresult.com/",
    "https://www.employmentnews.gov.in/",
    "https://www.latestgovtjobs.in/",
    "https://www.indiagovtjobs.in/"
    "https://www.kirannewsagency.com/"
    "https://www.mysarkarinaukri.com/"
    "https://sarkariprep.in/"
    "https://linkingsky.com/"
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def ensure_jobs_dir():
    if not os.path.exists(JOBS_DIR):
        os.makedirs(JOBS_DIR)

def slugify(title):
    return (
        title.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(":", "")
        .replace(",", "")
        .replace("?", "")
        .replace(".", "")
        .strip("-")
        + ".json"
    )

def extract_last_date(text):
    import re
    possible = re.findall(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", text)
    for date_str in possible:
        try:
            return str(dateparser.parse(date_str, dayfirst=True).date())
        except:
            continue
    return "Not Specified"

def fetch_private_portal_jobs():
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    seen_titles = set()

    for site in PRIVATE_SOURCES:
        try:
            res = requests.get(site, headers=headers, timeout=15, verify=False)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", href=True)

            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href")

                if not title or not href:
                    continue

                if not any(word in title.lower() for word in ["job", "vacancy", "recruitment", "post", "opening"]):
                    continue

                if title in seen_titles:
                    continue

                seen_titles.add(title)

                full_link = href if href.startswith("http") else site.rstrip("/") + "/" + href.lstrip("/")
                official_link = full_link
                last_date = "Not Specified"

                # Deep crawl
                try:
                    detail = requests.get(full_link, headers=headers, timeout=10, verify=False)
                    detail.raise_for_status()
                    page = BeautifulSoup(detail.text, "html.parser")
                    text = page.get_text()
                    last_date = extract_last_date(text)

                    for tag in page.find_all("a", href=True):
                        h = tag['href']
                        if h.startswith("http") and (".gov.in" in h or ".nic.in" in h):
                            official_link = h
                            break
                except Exception as e:
                    logging.warning(f"Deep crawl failed on {full_link}: {e}")

                job = {
                    "title": title.strip()[:80],
                    "category": "General",
                    "state": "N/A",
                    "last_date": last_date,
                    "apply_link": official_link
                }

                jobs.append(job)

        except Exception as e:
            logging.warning(f"❌ Failed to fetch from {site}: {e}")

    return jobs

def save_jobs(jobs):
    ensure_jobs_dir()
    for job in jobs:
        fname = slugify(job["title"])
        try:
            with open(os.path.join(JOBS_DIR, fname), "w", encoding="utf-8") as f:
                json.dump(job, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"⚠️ Could not save job '{job['title']}': {e}")

def delete_expired_jobs():
    ensure_jobs_dir()
    today = datetime.today().date()
    for file in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, file)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
            last_date_str = job.get("last_date")
            if last_date_str and last_date_str != "Not Specified":
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                if last_date < today:
                    os.remove(path)
                    logging.info(f"🗑️ Deleted expired job: {file}")
        except Exception as e:
            logging.warning(f"Error checking expiry for {file}: {e}")

if __name__ == "__main__":
    logging.info("🔄 Starting job scraping...")
    jobs = fetch_private_portal_jobs()
    save_jobs(jobs)
    delete_expired_jobs()
    logging.info(f"✅ {len(jobs)} jobs scraped, saved, and cleaned.")
