import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from dateutil import parser as dateparser
import hashlib
import re

from transformers import pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# =======================
# CONFIGURATION SECTION
# =======================
JOBS_DIR = "jobs"
JOB_MANIFEST = "job_manifest.json"
ENABLE_PDF_PARSING = True  # Toggle PDF parsing
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
    "https://www.indiagovtjobs.in/",
    "https://www.kirannewsagency.com/",
    "https://www.mysarkarinaukri.com/",
    "https://sarkariprep.in/",
    "https://linkingsky.com/"
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SarkariSarthiBot/1.0; +https://sarkarisarthi.in/bot)"
}
REQUEST_TIMEOUT = 15  # seconds
DEEP_CRAWL = True     # Toggle deep crawling for official links
TELEGRAM_BOT_TOKEN = "8124593711:AAFeVuf_x7ok_8PJx97e92SaDpcdTwafYlg"
TELEGRAM_CHAT_ID = "-1002642236931"

# =======================
# LOGGING SETUP
# =======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# =======================
# UTILITY FUNCTIONS
# =======================

def ensure_jobs_dir():
    """Ensure the jobs directory exists."""
    if not os.path.exists(JOBS_DIR):
        os.makedirs(JOBS_DIR)
        logging.info("🗂️ Created jobs directory.")

def slugify(text):
    """Create a safe filename from job title."""
    return (
        text.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(":", "")
        .replace(",", "")
        .replace("?", "")
        .replace(".", "")
        .strip("-")
    )[:60] + ".json"

def job_hash(title, link):
    """Create a hash for deduplication."""
    return hashlib.sha256((title + link).encode("utf-8")).hexdigest()

def extract_last_date(text):
    """
    Extract the last date from text using regex and dateutil.
    Looks for phrases like 'Last Date', 'Apply before', etc.
    """
    # Common patterns and phrases
    patterns = [
        r"(?:last\s*date|apply\s*before|closing\s*date|last\s*day|deadline)[^\n:]*[:\-]?\s*([\d]{1,2}[\/\-][\d]{1,2}[\/\-][\d]{2,4})",
        r"([\d]{1,2}[\/\-][\d]{1,2}[\/\-][\d]{2,4})",
        r"(?:last\s*date|apply\s*before|closing\s*date|last\s*day|deadline)[^\n:]*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            try:
                dt = dateparser.parse(match, dayfirst=True, fuzzy=True)
                if dt and dt.date() >= date.today():
                    return str(dt.date())
            except Exception:
                continue
    return "Not Specified"

def is_pdf_link(href):
    """Check if a link is a PDF."""
    return href.lower().endswith('.pdf')

def download_pdf(url, dest):
    """Download PDF from URL to destination path."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True, verify=False)
        resp.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in resp.iter_content(1024):
                f.write(chunk)
        return True
    except Exception as e:
        logging.warning(f"Failed to download PDF {url}: {e}")
        return False

def extract_pdf_text(pdf_path):
    """Extract text from PDF using PyMuPDF or pdfplumber."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join(page.extract_text() or '' for page in pdf.pages)
            return text
        except Exception as ex:
            logging.warning(f"PDF parsing failed ({pdf_path}): {e}, {ex}")
            return None

def categorize(title: str) -> str:
    """Categorize job based on keywords in the title."""
    title_l = title.lower()
    if any(k in title_l for k in ["police", "constable"]):
        return "Police"
    if any(k in title_l for k in ["bank", "ibps", "sbi"]):
        return "Banking"
    if any(k in title_l for k in ["railway", "rrb"]):
        return "Railway"
    if any(k in title_l for k in ["teacher", "school", "education"]):
        return "Education"
    return "General"

# --- Advanced PDF parsing using Hugging Face transformer (Donut/LayoutLM) ---
def parse_pdf_for_job_info(text, pdf_path=None):
    """
    Extract job info using a transformer-based model (Donut/LayoutLM) if possible.
    Fallback to regex if model or inference fails.
    """
    try:
        # Attempt to use Donut (OCR+NLP) if available
        from transformers import DonutProcessor, VisionEncoderDecoderModel
        from PIL import Image
        import torch
        import fitz
        # Extract images from PDF (first page)
        if pdf_path:
            doc = fitz.open(pdf_path)
            pix = doc[0].get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base-finetuned-docvqa")
            model = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base-finetuned-docvqa")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device)
            task_prompt = "<s_docvqa><s_question>Extract job title, department, apply link, last date<sep/>"
            inputs = processor(img, task_prompt, return_tensors="pt").to(device)
            outputs = model.generate(**inputs, max_length=512)
            result = processor.batch_decode(outputs, skip_special_tokens=True)[0]
            # Try to extract fields from result string (very basic, can be improved)
            job_title, department, apply_link, last_date = "", "", "", "Not Specified"
            for line in result.split("\n"):
                if "title" in line.lower():
                    job_title = line.split(":",1)[-1].strip()[:80]
                if "department" in line.lower():
                    department = line.split(":",1)[-1].strip()
                if "apply" in line.lower() and "http" in line:
                    match = re.search(r'(https?://\S+)', line)
                    if match:
                        apply_link = match.group(1)
                if "last date" in line.lower():
                    date_match = extract_last_date(line)
                    if date_match != "Not Specified":
                        last_date = date_match
            # If any field missing, fallback to regex
            if not job_title or not last_date:
                raise ValueError("Model extraction incomplete, fallback to regex")
            return {
                "title": job_title,
                "last_date": last_date,
                "department": department,
                "apply_link": apply_link
            }
    except Exception as e:
        logging.warning(f"⚠️ Donut/LayoutLM model failed or unavailable: {e}. Falling back to regex.")
    # --- Fallback: Regex-based extraction ---
    job_title = ""
    last_date = "Not Specified"
    department = ""
    apply_link = ""
    lines = text.splitlines()
    for line in lines:
        if not job_title and any(w in line.lower() for w in ["recruitment", "job", "vacancy", "post"]):
            job_title = line.strip()[:80]
        if not last_date or last_date == "Not Specified":
            date_match = extract_last_date(line)
            if date_match != "Not Specified":
                last_date = date_match
        if not department and any(w in line.lower() for w in ["department", "ministry", "state", "organization"]):
            department = line.strip()
        if not apply_link and "http" in line:
            match = re.search(r'(https?://\S+)', line)
            if match:
                apply_link = match.group(1)
    return {
        "title": job_title,
        "last_date": last_date,
        "department": department,
        "apply_link": apply_link
    }

def find_official_link(soup, fallback_link):
    """
    Prefer official .gov.in or .nic.in links.
    Returns (official_link, is_gov).
    """
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.startswith("http") and (".gov.in" in href or ".nic.in" in href):
            return href, True
    return fallback_link, False

# =======================
# MAIN SCRAPER LOGIC
# =======================

from portals import PORTALS

def fetch_govt_portal_jobs():
    """
    Scrape jobs from official central and state government portals listed in portals.py.
    Each portal can have its own scraping logic based on its structure.
    Returns a list of job dicts.
    """
    jobs = []
    for portal in PORTALS:
        try:
            resp = requests.get(portal['url'], headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            # --- Each portal may need custom parsing logic below ---
            # For demonstration, just create a stub entry:
            jobs.append({
                'title': f"{portal['name']} - See official site for latest jobs",
                'apply_link': portal['url'],
                'category': 'Govt',
                'source': portal['name'],
                'last_date': 'Not Specified',
                'description': f"Visit {portal['url']} for the latest official notifications.",
                'summary': f"Official portal for {portal['name']} government jobs.",
                'skills': [],
                'faq': [],
                'is_official': True
            })
        except Exception as e:
            logging.warning(f"Failed to fetch {portal['name']}: {e}")
    return jobs

def fetch_private_portal_jobs():
    """Scrape jobs from private portals with deduplication and deep crawl."""
    jobs = []
    seen = set()
    for site in PRIVATE_SOURCES:
        try:
            logging.info(f"🔍 Fetching {site}")
            res = requests.get(site, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", href=True)

            for link in links:
                title = link.get_text(strip=True)
                href = link.get("href")

                if not title or not href:
                    continue
                # Only consider job-like links
                if not any(word in title.lower() for word in ["job", "vacancy", "recruitment", "post", "opening"]):
                    continue

                # Normalize and deduplicate
                full_link = href if href.startswith("http") else site.rstrip("/") + "/" + href.lstrip("/")
                job_id = job_hash(title[:80], full_link)
                if job_id in seen_hashes:
                    continue
                seen_hashes.add(job_id)

                # Limit job title length
                job_title = title.strip()[:80]

                # Deep crawl for details
                last_date = "Not Specified"
                official_link = full_link
                is_gov = False
                pdf_info = None
                pdf_url = None
                if DEEP_CRAWL:
                    try:
                        detail = requests.get(full_link, headers=HEADERS, timeout=REQUEST_TIMEOUT, verify=False)
                        detail.raise_for_status()
                        page = BeautifulSoup(detail.text, "html.parser")
                        text = page.get_text(separator="\n")
                        last_date = extract_last_date(text)
                        official_link, is_gov = find_official_link(page, full_link)
                        # PDF detection and parsing
                        if ENABLE_PDF_PARSING:
                            for tag in page.find_all("a", href=True):
                                href = tag["href"]
                                if is_pdf_link(href):
                                    pdf_url = href if href.startswith("http") else site.rstrip("/") + "/" + href.lstrip("/")
                                    pdf_name = os.path.join(JOBS_DIR, "_tmp.pdf")
                                    if download_pdf(pdf_url, pdf_name):
                                        pdf_text = extract_pdf_text(pdf_name)
                                        if pdf_text:
                                            pdf_info = parse_pdf_for_job_info(pdf_text)
                                        os.remove(pdf_name)
                                    break
                    except Exception as e:
                        logging.warning(f"❌ Deep crawl failed on {full_link}: {e}")

                job = {
                    "title": pdf_info["title"] if pdf_info and pdf_info["title"] else job_title,
                    "category": categorize(job_title),
                    "state": "N/A",
                    "last_date": pdf_info["last_date"] if pdf_info and pdf_info["last_date"] else last_date,
                    "apply_link": pdf_info["apply_link"] if pdf_info and pdf_info["apply_link"] else official_link,
                    "is_gov": is_gov,
                    "pdf_url": pdf_url,
                    "pdf_parsed": bool(pdf_info)
                }
                if 'description' in locals():
                    job['description'] = description
                if summarizer and job.get('description'):
                    try:
                        summary = summarizer(job['description'], max_length=60, min_length=15, do_sample=False)[0]['summary_text']
                        job['summary'] = summary.strip()
                    except Exception as e:
                        logging.warning(f"Summarization failed: {e}")
                        job['summary'] = job.get('description', '')[:180]

                # --- AI Skill Extraction ---
                if job.get('description'):
                    job['skills'] = extract_skills(job['description'])

                # --- AI FAQ Generation ---
                if job.get('description'):
                    job['faqs'] = generate_faqs(job['description'])

                # --- Hindi Summary Generation ---
                if translator and job.get('summary'):
                    try:
                        summary_hi = translator(job['summary'])[0]['translation_text']
                        job['summary_hi'] = summary_hi.strip()
                    except Exception as e:
                        logging.warning(f"Hindi summary translation failed: {e}")
                        job['summary_hi'] = ''

                jobs.append(job)
                logging.info(f" Scraped: {job['title']} ({' GOV' if is_gov else ' NON-GOV'}){' [PDF]' if pdf_info else ''}")

        except Exception as e:
            logging.warning(f" Failed to fetch from {site}: {e}")

    return jobs

def save_jobs(jobs):
    """Save jobs to files and generate job_manifest.json."""
    ensure_jobs_dir()
    manifest = []
    for job in jobs:
        fname = slugify(job["title"])
        try:
            with open(os.path.join(JOBS_DIR, fname), "w", encoding="utf-8") as f:
                json.dump(job, f, indent=2, ensure_ascii=False)
            manifest.append(fname)
            logging.info(f"🗂️ Saved: {fname}")
        except Exception as e:
            logging.error(f"❌ Could not save job '{job['title']}': {e}")

    # Write manifest
    try:
        with open(os.path.join(JOBS_DIR, JOB_MANIFEST), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        logging.info(f"🗂️ Updated {JOB_MANIFEST} with {len(manifest)} jobs.")
    except Exception as e:
        logging.error(f"❌ Could not write job manifest: {e}")

def delete_expired_jobs():
    """Delete jobs whose last_date has passed."""
    ensure_jobs_dir()
    today = date.today()
    deleted = 0
    for file in os.listdir(JOBS_DIR):
        if not file.endswith(".json") or file == JOB_MANIFEST:
            continue
        path = os.path.join(JOBS_DIR, file)
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
            last_date_str = job.get("last_date")
            if last_date_str and last_date_str != "Not Specified":
                try:
                    last_date = dateparser.parse(last_date_str, dayfirst=True).date()
                    if last_date < today:
                        os.remove(path)
                        deleted += 1
                        logging.info(f"🗑️ Deleted expired job: {file}")
                except Exception as e:
                    logging.warning(f"❌ Invalid date in {file}: {last_date_str} ({e})")
        except Exception as e:
            logging.warning(f"❌ Error checking expiry for {file}: {e}")
    if deleted:
        logging.info(f"🧹 Deleted {deleted} expired jobs.")

def escape_markdown(text):
    # Escape Telegram Markdown special characters
    if not text:
        return ''
    for ch in ('_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'):
        text = text.replace(ch, f'\\{ch}')
    return text

def send_telegram_notification(jobs):
    """Send top 5 new jobs to Telegram group using Markdown. Includes title, deadline, summary, tags, and apply link."""
    if not jobs:
        logging.info("No jobs to notify on Telegram.")
        return
    top_jobs = jobs[:5]
    for job in top_jobs:
        title = escape_markdown(job.get('title', 'New Job'))
        deadline = job.get('last_date') or job.get('deadline') or ''
        summary = escape_markdown(job.get('summary') or job.get('description', '')[:180])
        tags = job.get('tags') or job.get('skills') or []
        tags_str = ''
        if tags and isinstance(tags, list):
            tags_str = ' | '.join([escape_markdown(str(t)) for t in tags])
        link = job.get('apply_link') or job.get('url') or ''
        message = f"*{title}*"
        if deadline:
            message += f"\n🗓️ Deadline: {escape_markdown(deadline)}"
        if summary:
            message += f"\n{summary}"
        if tags_str:
            message += f"\n🏷️ {tags_str}"
        if link:
            message += f"\n[Apply Here]({link})"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "MarkdownV2"
        }
        try:
            resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json=payload, timeout=10)
            if resp.status_code == 200:
                logging.info(f"Telegram notification sent for: {title}")
            else:
                logging.warning(f"Failed to send Telegram notification: {resp.text}")
        except Exception as e:
            logging.error(f"Telegram notification error: {e}")

# =======================
# MAIN EXECUTION BLOCK
# =======================

if __name__ == "__main__":
    logging.info("🔄 Starting job scraping...")
    ensure_jobs_dir()
    # Scrape official government portals
    gov_jobs = fetch_govt_portal_jobs()
    # Scrape private aggregator portals
    private_jobs = fetch_private_portal_jobs()
    # Combine and deduplicate jobs (by title+link hash)
    all_jobs = {job_hash(j['title'], j.get('apply_link','')): j for j in gov_jobs + private_jobs}
    jobs = list(all_jobs.values())
    save_jobs(jobs)
    delete_expired_jobs()
    logging.info(f"✅ {len(jobs)} jobs scraped, saved, and cleaned.")
