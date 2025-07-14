import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

JOBS_DIR = "jobs"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 20
VERIFY_SSL = False

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

def is_valid_last_date(last_date):
    if not last_date or not isinstance(last_date, str):
        return False
    try:
        datetime.strptime(last_date, "%Y-%m-%d")
        return True
    except:
        return False

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
    today = datetime.today().date()
    for file in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, file)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
            last_date = job.get("last_date")
            if is_valid_last_date(last_date):
                dt = datetime.strptime(last_date, "%Y-%m-%d").date()
                if dt < today:
                    os.remove(path)
                    logging.info(f"Deleted expired job file: {file}")
        except Exception as e:
            logging.warning(f"Error processing file {file}: {e}")

### --- SCRAPER FUNCTIONS --- ###

def fetch_upsc():
    url = "https://upsc.gov.in/examinations/active-examinations"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        rows = soup.select("table.views-table tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            title = cols[0].get_text(strip=True)
            date = cols[1].get_text(strip=True)
            try:
                last_date = datetime.strptime(date, "%d-%m-%Y").strftime("%Y-%m-%d")
            except:
                last_date = None
            jobs.append({"title": title, "category": "UPSC", "last_date": last_date, "apply_link": url})
    except Exception as e:
        logging.error(f"UPSC error: {e}")
    return jobs

def fetch_ibps():
    url = "https://www.ibps.in/"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for li in soup.select(".widget_recent_entries li"):
            title = li.get_text(strip=True)
            link = li.find("a")['href'] if li.find("a") else url
            jobs.append({"title": title, "category": "IBPS", "last_date": None, "apply_link": link})
    except Exception as e:
        logging.error(f"IBPS error: {e}")
    return jobs

def fetch_mppsc():
    url = "https://mppsc.mp.gov.in/"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for a in soup.select("#ctl00_ContentPlaceHolder1_dlLatestAdvertisements a"):
            title = a.get_text(strip=True)
            link = a.get("href")
            if link and not link.startswith("http"):
                link = url + link
            jobs.append({"title": title, "category": "MPPSC", "last_date": None, "apply_link": link})
    except Exception as e:
        logging.error(f"MPPSC error: {e}")
    return jobs

def fetch_uppsc():
    url = "https://uppsc.up.nic.in/"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for a in soup.select("#ctl00_ContentPlaceHolder1_GridView1 a"):
            title = a.get_text(strip=True)
            link = url + a.get("href") if a.get("href") else url
            jobs.append({"title": title, "category": "UPPSC", "last_date": None, "apply_link": link})
    except Exception as e:
        logging.error(f"UPPSC error: {e}")
    return jobs

def fetch_bpsc():
    url = "https://www.bpsc.bih.nic.in/"
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")
        for a in soup.select("a"):
            title = a.get_text(strip=True)
            href = a.get("href")
            if href and (".pdf" in href or "Notice" in title):
                full_link = url + href if not href.startswith("http") else href
                jobs.append({"title": title, "category": "BPSC", "last_date": None, "apply_link": full_link})
    except Exception as e:
        logging.error(f"BPSC error: {e}")
    return jobs

# Add similar methods: fetch_rrb(), fetch_ssc(), fetch_gujarat(), fetch_rajasthan()

if __name__ == "__main__":
    all_jobs = []
    all_jobs.extend(fetch_upsc())
    all_jobs.extend(fetch_ibps())
    all_jobs.extend(fetch_mppsc())
    all_jobs.extend(fetch_uppsc())
    all_jobs.extend(fetch_bpsc())
    # Add calls to fetch_ssc(), fetch_rrb(), fetch_rajasthan(), fetch_gujarat() later

    save_jobs(all_jobs)
    delete_expired_jobs()
    logging.info(f"Total jobs fetched and saved: {len(all_jobs)}")
