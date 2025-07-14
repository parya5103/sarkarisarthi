import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

JOBS_DIR = "jobs"
PRIVATE_SOURCES = [
    "https://www.freejobalert.com/",  # Example private portal
    "https://www.sarkarinaukridaily.in/",
    "https://www.sarkarinaukri.com/",
    "https://www.fresherslive.com/govt-jobs",
    "https://www.jobsarkari.com/",
    "https://www.naukrigulf.com/government-jobs",
    "https://rojgarresult.com/",
    "https://www.employmentnews.gov.in/",
    "https://www.latestgovtjobs.in/",
    "https://www.indiagovtjobs.in/"
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
        + ".json"
    )

def fetch_private_portal_jobs():
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    for site in PRIVATE_SOURCES:
        try:
            res = requests.get(site, headers=headers, timeout=15, verify=False)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a")
            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href")
                if not href or not title:
                    continue
                if any(keyword in title.lower() for keyword in ["recruitment", "vacancy", "job", "post", "opening"]):
                    jobs.append({
                        "title": title[:80],
                        "category": "General",
                        "last_date": None,
                        "apply_link": href if href.startswith("http") else site.rstrip("/") + "/" + href.lstrip("/")
                    })
        except Exception as e:
            logging.warning(f"Failed to fetch from {site}: {e}")
    return jobs

def save_jobs(jobs):
    ensure_jobs_dir()
    for job in jobs:
        fname = slugify(job["title"])
        try:
            with open(os.path.join(JOBS_DIR, fname), "w", encoding="utf-8") as f:
                json.dump(job, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving job '{job['title']}' to {fname}: {e}")

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
        except Exception:
            continue
        last_date_str = job.get("last_date")
        if last_date_str:
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                if last_date < today:
                    os.remove(path)
                    logging.info(f"Deleted expired job: {file}")
            except:
                continue

if __name__ == "__main__":
    jobs = fetch_private_portal_jobs()
    save_jobs(jobs)
    delete_expired_jobs()
    logging.info(f"✅ {len(jobs)} jobs scraped from private portals.")
