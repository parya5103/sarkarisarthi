import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

JOBS_DIR = "jobs"

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

def fetch_upsc_jobs():
    url = "https://upsc.gov.in/examinations/active-examinations"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=20, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        rows = soup.select("table.views-table tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            title = cols[0].get_text(strip=True)
            date_text = cols[1].get_text(strip=True)
            try:
                last_date = datetime.strptime(date_text, "%d-%m-%Y").strftime("%Y-%m-%d")
            except Exception:
                last_date = None
            jobs.append({
                "title": title,
                "category": "UPSC",
                "last_date": last_date,
                "apply_link": url
            })
        logging.info(f"[UPSC] Total jobs found: {len(jobs)}")
    except Exception as e:
        logging.error(f"Error fetching UPSC jobs: {e}")
    return jobs

# Dummy placeholder for other sources
def fetch_dummy_jobs(source_name, url):
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=20, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        jobs.append({
            "title": f"Sample {source_name} Job",
            "category": source_name.upper(),
            "last_date": "2025-12-31",
            "apply_link": url
        })
        logging.info(f"[{source_name.upper()}] Fetched 1 test job")
    except Exception as e:
        logging.error(f"Error fetching {source_name.upper()} jobs: {e}")
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

def is_valid_last_date(last_date):
    if not last_date or not isinstance(last_date, str):
        return False
    try:
        datetime.strptime(last_date, "%Y-%m-%d")
        return True
    except Exception:
        return False

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
            logging.error(f"Skipping invalid JSON file: {file}")
            continue
        last_date_str = job.get("last_date")
        if not is_valid_last_date(last_date_str):
            logging.warning(f"Skipping job '{job.get('title', 'unknown')}' in file '{file}' due to invalid last_date: {last_date_str}")
            continue
        try:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            if last_date < today:
                os.remove(path)
                logging.info(f"Deleted expired job file: {file}")
        except Exception as e:
            logging.error(f"Error parsing last_date in file '{file}': {e}")

if __name__ == "__main__":
    all_jobs = []
    all_jobs += fetch_upsc_jobs()
    all_jobs += fetch_dummy_jobs("IBPS", "https://www.ibps.in/")
    all_jobs += fetch_dummy_jobs("BPSC", "https://www.bpsc.bih.nic.in/")
    all_jobs += fetch_dummy_jobs("MPPSC", "https://mppsc.mp.gov.in/")
    all_jobs += fetch_dummy_jobs("SSC", "https://ssc.nic.in/")
    all_jobs += fetch_dummy_jobs("RRB", "https://indianrailways.gov.in/")
    all_jobs += fetch_dummy_jobs("UPPSC", "https://uppsc.up.nic.in/")
    all_jobs += fetch_dummy_jobs("GUJARAT", "https://gpsc.gujarat.gov.in/")
    all_jobs += fetch_dummy_jobs("RAJASTHAN", "https://rpsc.rajasthan.gov.in/")

    save_jobs(all_jobs)
    delete_expired_jobs()
