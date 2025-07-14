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
    if not os.path.exists(JOBS_DIR):
        os.makedirs(JOBS_DIR)

def slugify(title):
    return (
        title.lower().replace(" ", "-").replace("/", "-").replace(":", "").replace(",", "") + ".json"
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
    except Exception as e:
        logging.error(f"Error fetching UPSC jobs: {e}")
    return jobs

def fetch_ibps_jobs():
    url = "https://www.ibps.in/"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        notices = soup.select(".text-blk a")
        for link in notices:
            title = link.get_text(strip=True)
            href = link.get("href")
            if href:
                jobs.append({
                    "title": title,
                    "category": "IBPS",
                    "last_date": None,
                    "apply_link": href if href.startswith("http") else url + href
                })
    except Exception as e:
        logging.error(f"Error fetching IBPS jobs: {e}")
    return jobs

def fetch_bpsc_jobs():
    url = "https://www.bpsc.bih.nic.in/"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        rows = soup.select("table tr td a")
        for a in rows:
            title = a.get_text(strip=True)
            href = a.get("href")
            if href and ("recruitment" in href.lower() or "advt" in href.lower()):
                jobs.append({
                    "title": title,
                    "category": "BPSC",
                    "last_date": None,
                    "apply_link": url + href
                })
    except Exception as e:
        logging.error(f"Error fetching BPSC jobs: {e}")
    return jobs

def fetch_ssc_jobs():
    url = "https://ssc.nic.in/"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for link in soup.select("#whatsNew marquee a"):
            title = link.get_text(strip=True)
            href = link.get("href")
            if href:
                jobs.append({
                    "title": title,
                    "category": "SSC",
                    "last_date": None,
                    "apply_link": url + href if not href.startswith("http") else href
                })
    except Exception as e:
        logging.error(f"Error fetching SSC jobs: {e}")
    return jobs

def fetch_rrb_jobs():
    url = "https://www.rrbcdg.gov.in/"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for link in soup.select(".marquee1 a"):
            title = link.get_text(strip=True)
            href = link.get("href")
            if href:
                jobs.append({
                    "title": title,
                    "category": "RRB",
                    "last_date": None,
                    "apply_link": url + href if not href.startswith("http") else href
                })
    except Exception as e:
        logging.error(f"Error fetching RRB jobs: {e}")
    return jobs

def fetch_mppsc_jobs():
    url = "https://mppsc.mp.gov.in/"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for li in soup.select(".listing a"):
            title = li.get_text(strip=True)
            href = li.get("href")
            if href:
                jobs.append({
                    "title": title,
                    "category": "MPPSC",
                    "last_date": None,
                    "apply_link": url + href if not href.startswith("http") else href
                })
    except Exception as e:
        logging.error(f"Error fetching MPPSC jobs: {e}")
    return jobs

def fetch_uppsc_jobs():
    url = "https://uppsc.up.nic.in/"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for a in soup.select("a"):
            title = a.get_text(strip=True)
            href = a.get("href")
            if href and ("recruitment" in href.lower() or "notice" in href.lower()):
                jobs.append({
                    "title": title,
                    "category": "UPPSC",
                    "last_date": None,
                    "apply_link": url + href if not href.startswith("http") else href
                })
    except Exception as e:
        logging.error(f"Error fetching UPPSC jobs: {e}")
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
    if not os.path.isdir(JOBS_DIR):
        logging.error(f"Jobs directory '{JOBS_DIR}' does not exist or is not a directory.")
        return
    for file in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, file)
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
    all_jobs = []
    all_jobs += fetch_upsc_jobs()
    all_jobs += fetch_ibps_jobs()
    all_jobs += fetch_bpsc_jobs()
    all_jobs += fetch_ssc_jobs()
    all_jobs += fetch_rrb_jobs()
    all_jobs += fetch_mppsc_jobs()
    all_jobs += fetch_uppsc_jobs()

    save_jobs(all_jobs)
    delete_expired_jobs()
