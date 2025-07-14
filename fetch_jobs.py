import os
import json
import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime

JOBS_DIR = "jobs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def ensure_jobs_dir():
    """Ensure the jobs directory exists before any operation."""
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
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        rows = soup.select("table.views-table tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            title = cols[0].get_text(strip=True)
            date_text = cols[1].get_text(strip=True)
            # Robust last_date parsing
            try:
                last_date = datetime.strptime(date_text, "%d-%m-%Y").strftime("%Y-%m-%d")
            except Exception:
                # If invalid or missing, set last_date to None
                last_date = None
            jobs.append({
                "title": title,
                "category": "UPSC",
                "last_date": last_date,
                "apply_link": url
            })
    except Exception as e:
        logging.error(f"Error fetching jobs: {e}")
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
    """Checks if last_date is a valid date string in YYYY-MM-DD."""
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
    # Only proceed if jobs dir exists and is actually a directory
    if not os.path.isdir(JOBS_DIR):
        logging.error(f"Jobs directory '{JOBS_DIR}' does not exist or is not a directory.")
        return
    for file in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, file)
        # Skip non-files
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Skipping invalid JSON file: {file}")
            continue
        except Exception as e:
            logging.error(f"Error reading file '{file}': {e}")
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
    jobs = fetch_upsc_jobs()
    save_jobs(jobs)
    delete_expired_jobs()
