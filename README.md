# 🇮🇳 SarkariSarthi – Free Govt Job Portal

![Build Status](https://github.com/yourusername/SarkariSarthi/actions/workflows/fetch.yml/badge.svg)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/github/license/yourusername/SarkariSarthi)


SarkariSarthi is a fully automated, free-to-host static Indian Government Job Portal.  
Built with **Python**, **BeautifulSoup**, **GitHub Actions**, and **Pico.css** – this site auto-fetches real jobs from UPSC and will support more sources soon.

## ✅ Features

---

## 🛠️ How it works

```mermaid
graph TD;
  A[fetch_jobs.py: Scrape jobs, parse PDFs, categorize] --> B[Save .json files to jobs/]
  B --> C[generate_manifest.py: Build manifest]
  C --> D[Frontend: index.html + script.js]
  D --> E[User: Search, filter, view, apply]
```

- Real-time scraping from **UPSC**
- Auto-delete expired jobs
- Filters + search bar
- Hosted on GitHub Pages
- SEO + AdSense Ready

## 🌏 Deploy at:
https://parya5103.github.io/SarkariSarthi/

---

## 🤝 Contributing

1. Fork this repo and clone your fork.
2. Create a new branch for your feature or bugfix.
3. Run `pip install -r requirements.txt` (and optionally `pytest` for tests).
4. Make your changes and submit a pull request!

See [CONTRIBUTING.md](CONTRIBUTING.md) for more.
