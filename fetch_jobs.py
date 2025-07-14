import os
import json
import requests
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Optional: PDF parsing tools (requires PyMuPDF if used)
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# === Settings ===
JOBS_DIR = "jobs"
ENABLE_PDF_PARSING = True
ENABLE_PRIVATE_PORTALS = True
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 20
VERIFY_SSL = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def ensure_jobs_dir():
    if not os.path.exists(JOBS_DIR):
        os.makedirs(JOBS_DIR)

def slugify(title):
    return (
        title.lower().replace(" ", "-").replace("/", "-").replace(":", "").replace(",", "") + ".json"
    )

def save_jobs(jobs):
    ensure_jobs_dir()
    for job in jobs:
        if not job.get("title"):
            continue
        fname = slugify(job["title"])
        try:
            with open(os.path.join(JOBS_DIR, fname), "w", encoding="utf-8") as f:
                json.dump(job, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save {job['title']}: {e}")

def is_valid_last_date(last_date):
    try:
        return bool(datetime.strptime(last_date, "%Y-%m-%d"))
    except:
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
            last_date = job.get("last_date")
            if is_valid_last_date(last_date) and datetime.strptime(last_date, "%Y-%m-%d").date() < today:
                os.remove(path)
                logging.info(f"Deleted expired job: {file}")
        except Exception as e:
            logging.warning(f"Failed to process {file}: {e}")

# --- PDF Parser ---
def parse_pdf_from_url(url):
    if not ENABLE_PDF_PARSING or not fitz:
        return []
    try:
        res = requests.get(url, timeout=TIMEOUT, verify=VERIFY_SSL)
        res.raise_for_status()
        with open("temp.pdf", "wb") as f:
            f.write(res.content)
        doc = fitz.open("temp.pdf")
        text = "\n".join([page.get_text() for page in doc])
        doc.close()
        return text.split("\n")
    except Exception as e:
        logging.error(f"PDF parse failed from {url}: {e}")
        return []

# --- Official Sources ---
def fetch_upsc_jobs():
    jobs = []
    url = "https://upsc.gov.in/examinations/active-examinations"
    try:
        soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL).content, "html.parser")
        rows = soup.select("table.views-table tr")[1:]
        for row in rows:
            title = row.find_all("td")[0].get_text(strip=True)
            date_str = row.find_all("td")[1].get_text(strip=True)
            try:
                last_date = datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
            except:
                last_date = None
            jobs.append({"title": title, "category": "UPSC", "last_date": last_date, "apply_link": url})
    except Exception as e:
        logging.error(f"UPSC fetch error: {e}")
    return jobs

def fetch_ssc_jobs():
    jobs = []
    url = "https://ssc.nic.in/"
    try:
        soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL).content, "html.parser")
        for li in soup.select(".latest-news li"):
            title = li.get_text(strip=True)
            if "Advt" in title or "Recruitment" in title:
                link = urljoin(url, li.find("a")["href"])
                jobs.append({"title": title, "category": "SSC", "last_date": None, "apply_link": link})
    except Exception as e:
        logging.error(f"SSC fetch error: {e}")
    return jobs

def fetch_ibps_jobs():
    jobs = []
    url = "https://www.ibps.in/"
    try:
        soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL).content, "html.parser")
        for li in soup.select(".exam-list li"):
            title = li.get_text(strip=True)
            link = urljoin(url, li.find("a")["href"])
            jobs.append({"title": title, "category": "IBPS", "last_date": None, "apply_link": link})
    except Exception as e:
        logging.error(f"IBPS fetch error: {e}")
    return jobs

# --- Private Portals (Summarized Public Data) ---
def fetch_freejobalert():
    jobs = []
    try:
        soup = BeautifulSoup(requests.get("https://www.freejobalert.com/", headers=HEADERS, timeout=TIMEOUT, verify=VERIFY_SSL).content, "html.parser")
        for li in soup.select(".category li")[:10]:
            title = li.get_text(strip=True)
            link = li.find("a")["href"]
            jobs.append({"title": title, "category": "Private", "last_date": None, "apply_link": link})
    except Exception as e:
        logging.error(f"FreeJobAlert fetch error: {e}")
    return jobs

# --- Master Job Runner ---
def main():
    all_jobs = []
    all_jobs += fetch_upsc_jobs()
    all_jobs += fetch_ssc_jobs()
    all_jobs += fetch_ibps_jobs()
    if ENABLE_PRIVATE_PORTALS:
        all_jobs += fetch_freejobalert()
    save_jobs(all_jobs)
    delete_expired_jobs()

if __name__ == "__main__":
    main()
