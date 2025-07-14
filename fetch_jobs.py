import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

JOBS_DIR = "jobs"
TIMEOUT = 20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

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

def is_valid_last_date(last_date):
    try:
        datetime.strptime(last_date, "%Y-%m-%d")
        return True
    except:
        return False

def save_jobs(jobs, source=""):
    ensure_jobs_dir()
    for job in jobs:
        fname = slugify(f"{source}-{job['title']}")
        try:
            with open(os.path.join(JOBS_DIR, fname), "w", encoding="utf-8") as f:
                json.dump(job, f, indent=2)
        except Exception as e:
            logging.error(f"[{source}] ❌ Failed to save: {job['title']} | {e}")

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
            last_date = job.get("last_date")
            if not is_valid_last_date(last_date):
                logging.warning(f"⚠️ Invalid last_date in {file}")
                continue
            if datetime.strptime(last_date, "%Y-%m-%d").date() < today:
                os.remove(path)
                logging.info(f"🗑 Deleted expired job: {file}")
        except Exception as e:
            logging.error(f"❌ Error reading/deleting {file}: {e}")

# ---------------- SCRAPERS ----------------

def fetch_upsc_jobs():
    url = "https://upsc.gov.in/examinations/active-examinations"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        rows = soup.select("table.views-table tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                title = cols[0].get_text(strip=True)
                date_text = cols[1].get_text(strip=True)
                try:
                    last_date = datetime.strptime(date_text, "%d-%m-%Y").strftime("%Y-%m-%d")
                except:
                    last_date = None
                jobs.append({
                    "title": title,
                    "category": "UPSC",
                    "last_date": last_date,
                    "apply_link": url
                })
        logging.info(f"[UPSC] ✅ Found {len(jobs)} jobs")
    except Exception as e:
        logging.error(f"[UPSC] ❌ Error: {e}")
    return jobs

def fetch_ibps_jobs():
    url = "https://www.ibps.in"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for li in soup.select("marquee ul li"):
            text = li.get_text(strip=True)
            if "recruitment" in text.lower():
                jobs.append({
                    "title": text,
                    "category": "IBPS",
                    "last_date": None,
                    "apply_link": url
                })
        logging.info(f"[IBPS] ✅ Found {len(jobs)} jobs")
    except Exception as e:
        logging.error(f"[IBPS] ❌ Error: {e}")
    return jobs

def fetch_mppsc_jobs():
    url = "https://mppsc.mp.gov.in"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for a in soup.select("marquee a"):
            title = a.get_text(strip=True)
            if "exam" in title.lower() or "recruitment" in title.lower():
                jobs.append({
                    "title": title,
                    "category": "MPPSC",
                    "last_date": None,
                    "apply_link": url
                })
        logging.info(f"[MPPSC] ✅ Found {len(jobs)} jobs")
    except Exception as e:
        logging.error(f"[MPPSC] ❌ Error: {e}")
    return jobs

def fetch_uppsc_jobs():
    url = "https://uppsc.up.nic.in"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for td in soup.select("marquee td a"):
            title = td.get_text(strip=True)
            if "recruitment" in title.lower():
                jobs.append({
                    "title": title,
                    "category": "UPPSC",
                    "last_date": None,
                    "apply_link": url
                })
        logging.info(f"[UPPSC] ✅ Found {len(jobs)} jobs")
    except Exception as e:
        logging.error(f"[UPPSC] ❌ Error: {e}")
    return jobs

def fetch_bpsc_jobs():
    url = "https://www.bpsc.bih.nic.in"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for a in soup.select("marquee a"):
            title = a.get_text(strip=True)
            if "advt" in title.lower() or "recruitment" in title.lower():
                jobs.append({
                    "title": title,
                    "category": "BPSC",
                    "last_date": None,
                    "apply_link": url
                })
        logging.info(f"[BPSC] ✅ Found {len(jobs)} jobs")
    except Exception as e:
        logging.error(f"[BPSC] ❌ Error: {e}")
    return jobs

# ---------------- MAIN ----------------

if __name__ == "__main__":
    all_jobs = []

    for fetcher in [
        fetch_upsc_jobs,
        fetch_ibps_jobs,
        fetch_mppsc_jobs,
        fetch_uppsc_jobs,
        fetch_bpsc_jobs
    ]:
        jobs = fetcher()
        if jobs:
            save_jobs(jobs, source=jobs[0]["category"])
            all_jobs.extend(jobs)

    logging.info(f"✅ Total saved jobs: {len(all_jobs)}")
    delete_expired_jobs()
