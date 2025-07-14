import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import glob

# Mock scraper for top 10 Indian govt job portals
def fetch_jobs():
    portals = [
        'https://www.ssc.nic.in',
        'https://www.upsc.gov.in',
        'https://www.indianrailways.gov.in',
        'https://www.ibps.in',
        # Add other portals here
    ]
    jobs = []
    for portal in portals:
        try:
            response = requests.get(portal, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Mock parsing logic (replace with actual scraping logic)
            job = {
                'title': f'Sample Job from {portal}',
                'category': 'SSC' if 'ssc' in portal else 'UPSC' if 'upsc' in portal else 'Railways' if 'railways' in portal else 'Bank',
                'description': 'This is a sample job description.',
                'last_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
                'link': portal
            }
            jobs.append(job)
        except Exception as e:
            print(f"Error fetching {portal}: {e}")

    # Save jobs to index.json
    os.makedirs('jobs', exist_ok=True)
    with open('jobs/index.json', 'w') as f:
        json.dump(jobs, f, indent=2)

    # Save individual job files
    for i, job in enumerate(jobs):
        with open(f'jobs/job_{i}.json', 'w') as f:
            json.dump(job, f, indent=2)

    # Save scrape stats
    with open('meta.json', 'w') as f:
        json.dump({'last_scraped': datetime.now().isoformat(), 'job_count': len(jobs)}, f)

# Delete expired jobs
def clean_expired_jobs():
    today = datetime.now()
    for job_file in glob.glob('jobs/job_*.json'):
        with open(job_file, 'r') as f:
            job = json.load(f)
            last_date = datetime.strptime(job['last_date'], '%Y-%m-%d')
            if last_date < today:
                os.remove(job_file)

# Generate RSS feed
def generate_rss():
    with open('jobs/index.json', 'r') as f:
        jobs = json.load(f)
    rss = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>SarkariSarthi Job Feed</title>
    <link>https://yourusername.github.io/sarkarisarthi/</link>
    <description>Latest Indian Government Jobs</description>
'''
    for job in jobs:
        rss += f'''
    <item>
        <title>{job['title']}</title>
        <link>{job['link']}</link>
        <description>{job['description']}</description>
        <pubDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
    </item>
'''
    rss += '</channel></rss>'
    with open('feed.xml', 'w') as f:
        f.write(rss)

if __name__ == '__main__':
    fetch_jobs()
    clean_expired_jobs()
    generate_rss()