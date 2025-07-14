import os, json, requests
from bs4 import BeautifulSoup
from datetime import datetime

JOBS_DIR = "jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

def slugify(title):
    return title.lower().replace(" ", "-").replace("/", "-").replace(":", "").replace(",", "") + ".json"

def fetch_upsc_jobs():
    url = "https://upsc.gov.in/examinations/active-examinations"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")
        rows = soup.select("table.views-table tr")[1:]
    except:
        return []

    jobs = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2: continue
        title = cols[0].get_text(strip=True)
        date_text = cols[1].get_text(strip=True)
        try:
            last_date = datetime.strptime(date_text, "%d-%m-%Y").strftime("%Y-%m-%d")
        except:
            last_date = datetime.today().strftime("%Y-%m-%d")
        jobs.append({
            "title": title,
            "category": "UPSC",
            "last_date": last_date,
            "apply_link": url
        })
    return jobs

def save_jobs(jobs):
    for job in jobs:
        fname = slugify(job["title"])
        with open(os.path.join(JOBS_DIR, fname), "w") as f:
            json.dump(job, f, indent=2)

def delete_expired_jobs():
    today = datetime.today().date()
    for file in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, file)
        with open(path) as f:
            job = json.load(f)
        try:
            last_date = datetime.strptime(job["last_date"], "%Y-%m-%d").date()
            if last_date < today:
                os.remove(path)
        except: continue

if __name__ == "__main__":
    save_jobs(fetch_upsc_jobs())
    delete_expired_jobs()
