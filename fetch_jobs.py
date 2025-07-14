import os
import json
from datetime import datetime

JOBS_DIR = "jobs"

def fetch_dummy_jobs():
    # Create the jobs directory if it doesn't exist
    os.makedirs(JOBS_DIR, exist_ok=True)

    # Dummy job
    job_data = {
        "title": "UPSC NDA 2025",
        "category": "Defence",
        "last_date": "2025-09-01",
        "apply_link": "https://example.com/nda2025"
    }

    # Save to file
    file_name = f"{JOBS_DIR}/upsc-nda-2025.json"
    with open(file_name, "w") as f:
        json.dump(job_data, f, indent=2)

def delete_expired_jobs():
    today = datetime.today().date()
    for filename in os.listdir(JOBS_DIR):
        filepath = os.path.join(JOBS_DIR, filename)
        try:
            with open(filepath, "r") as f:
                job = json.load(f)
            last_date = datetime.strptime(job.get("last_date", ""), "%Y-%m-%d").date()
            if last_date < today:
                os.remove(filepath)
                print(f"Deleted expired job: {filename}")
        except Exception as e:
            print(f"Skipping {filename}: {e}")

if __name__ == "__main__":
    fetch_dummy_jobs()
    delete_expired_jobs()
    print("✅ Jobs fetched and expired ones deleted.")
