// Sarkari Sarthi Job Portal Script
// Modular, accessible, and ready for future migration to React/Vue

// --- Constants ---
const JOBS_MANIFEST_URL = 'jobs/job_manifest.json';
const JOBS_CONTAINER_ID = 'jobListings';
const JOBS_SKELETON_ID = 'jobs-skeleton';
const JOB_COUNTER_ID = 'job-counter';
const LIVE_REGION_ID = 'jobs-live-region';
const DARK_MODE_KEY = 'sarkari_dark_mode';
const LANG_KEY = 'sarkari_lang';
const DARK_MODE_TOGGLE_ID = "darkModeToggle";
const FADE_IN_CLASS = "fade-in";
const DARK_MODE_CLASS = "dark-mode";
const LOCALSTORAGE_DARK = "sarkari_dark_mode";
const LOCALSTORAGE_LANG = "sarkari_lang";
const LANG_TOGGLE_ID = "langToggle"; // Added missing constant

// --- State ---
let jobsData = [];
let filteredJobs = [];
let trendingSkills = [];
let currentLang = localStorage.getItem(LOCALSTORAGE_LANG) || "en";
let searchDebounceTimeout = null;
let showBookmarksOnly = false;
let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
let chartInstance = null; // For Chart.js trending roles


/**** DOM READY ****/
document.addEventListener("DOMContentLoaded", () => {
  setupLanguageSwitcher();
  setupDarkMode();
  setupFiltersAndSort();
  setupBookmarksToggle();
  renderTrendingChart([]); // Empty initially

  setupSearchAndFilter();
  loadJobsManifest();
});

function setupFiltersAndSort() {
  // Populate dropdowns after jobs load
  // Handlers attached in renderJobs
  document.getElementById('sortBy').addEventListener('change', applyFiltersAndSort);
  document.getElementById('filterDeadline').addEventListener('change', applyFiltersAndSort);
  document.getElementById('clearFilters').addEventListener('click', clearAllFilters);
}

function setupBookmarksToggle() {
  document.getElementById('toggleBookmarks').addEventListener('click', () => {
    showBookmarksOnly = !showBookmarksOnly;
    applyFiltersAndSort();
    document.getElementById('toggleBookmarks').classList.toggle('active', showBookmarksOnly);
  });
}

function clearAllFilters() {
  document.getElementById('filterState').value = '';
  document.getElementById('filterCategory').value = '';
  document.getElementById('filterDeadline').value = '';
  document.getElementById('sortBy').value = 'latest';
  showBookmarksOnly = false;
  document.getElementById('toggleBookmarks').classList.remove('active');
  applyFiltersAndSort();
}

function applyFiltersAndSort() {
  let state = document.getElementById('filterState').value;
  let cat = document.getElementById('filterCategory').value;
  let deadline = document.getElementById('filterDeadline').value;
  let sortBy = document.getElementById('sortBy').value;
  let jobs = [...jobsData];
  if (state) jobs = jobs.filter(j => j.state === state);
  if (cat) jobs = jobs.filter(j => j.category === cat);
  if (deadline) jobs = jobs.filter(j => j.last_date && j.last_date >= deadline);
  if (showBookmarksOnly) jobs = jobs.filter(j => bookmarks.includes(j.id));
  if (sortBy === 'latest') jobs.sort((a, b) => new Date(b.last_date) - new Date(a.last_date));
  else jobs.sort((a, b) => new Date(a.last_date) - new Date(b.last_date));
  filteredJobs = jobs;
  renderJobs(filteredJobs);
  renderTrendingChart(jobs);
}

function setMetaTagsForJob(job) {
  // Save old values
  const oldTitle = document.title;
  const oldDesc = document.querySelector('meta[name="description"]').getAttribute('content');
  document.title = job.title + ' | Sarkari Sarthi';
  let desc = (job.summary || '') + ' ' + (job.skills ? job.skills.join(', ') : '');
  document.querySelector('meta[name="description"]').setAttribute('content', desc.trim());
  // For social sharing (Open Graph)
  let ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle) ogTitle.setAttribute('content', document.title);
  let ogDesc = document.querySelector('meta[property="og:description"]');
  if (ogDesc) ogDesc.setAttribute('content', desc.trim());
  return () => {
    document.title = oldTitle;
    document.querySelector('meta[name="description"]').setAttribute('content', oldDesc);
    if (ogTitle) ogTitle.setAttribute('content', oldTitle);
    if (ogDesc) ogDesc.setAttribute('content', oldDesc);
  };
}

// --- Pagination State ---
let currentPage = 1;
const JOBS_PER_PAGE = 10;

function renderJobs(jobs) {
  const container = document.getElementById(JOBS_CONTAINER_ID);
  container.innerHTML = '';
  if (!jobs.length) {
    container.innerHTML = `<div class="no-jobs">${currentLang === 'hi' ? 'कोई नौकरी नहीं मिली।' : 'No jobs found.'}</div>`;
    // Clear pagination controls if present
    renderPaginationControls(0, 1);
    return;
  }
  // --- Pagination logic ---
  const totalPages = Math.ceil(jobs.length / JOBS_PER_PAGE);
  if (currentPage > totalPages) currentPage = totalPages || 1;
  const startIdx = (currentPage - 1) * JOBS_PER_PAGE;
  const endIdx = startIdx + JOBS_PER_PAGE;
  const jobsToShow = jobs.slice(startIdx, endIdx);
  // --- End Pagination logic ---
  const frag = document.createDocumentFragment();
  jobsToShow.forEach(job => {
    const card = document.createElement('div');
    card.className = 'job-card';
    card.tabIndex = 0;
    card.setAttribute('role', 'article');
    card.setAttribute('aria-label', job.title);
    // Bookmark button
    const bmBtn = document.createElement('button');
    bmBtn.className = 'bookmark-btn' + (bookmarks.includes(job.id) ? ' active' : '');
    bmBtn.setAttribute('aria-label', bookmarks.includes(job.id) ? (currentLang==='hi'?'बुकमार्क हटाएं':'Remove bookmark') : (currentLang==='hi'?'बुकमार्क करें':'Bookmark'));
    bmBtn.innerHTML = bookmarks.includes(job.id) ? '★' : '☆';
    bmBtn.onclick = e => { e.stopPropagation(); toggleBookmark(job.id); };
    card.appendChild(bmBtn);
    // Title
    const title = document.createElement('h3');
    title.className = 'job-title';
    title.textContent = job.title;
    card.appendChild(title);
    // --- AI Summary Section ---
    const summaryText = (currentLang === 'hi' && job.summary_hi) ? job.summary_hi : (job.summary || job.description || '');
    const sum = document.createElement('div');
    sum.className = 'job-summary';
    sum.textContent = summaryText;
    // Tooltip for summary
    sum.title = summaryText;
    card.appendChild(sum);
    // --- End AI Summary Section ---
    // Deadline
    if (job.last_date) {
      const dl = document.createElement('div');
      dl.className = 'job-deadline';
      dl.textContent = (currentLang==='hi'?'अंतिम तिथि: ':'Deadline: ') + job.last_date;
      card.appendChild(dl);
    }
    // --- AI Skill tags ---
    if (job.skills && job.skills.length) {
      const tagWrap = document.createElement('div');
      tagWrap.className = 'job-tags';
      job.skills.forEach(skill => {
        const chip = document.createElement('span');
        chip.className = 'job-chip';
        chip.textContent = skill;
        tagWrap.appendChild(chip);
      });
      card.appendChild(tagWrap);
    }
    // --- End AI Skill tags ---
    if (job.category) {
      const cat = document.createElement('div');
      cat.className = 'job-category';
      cat.textContent = job.category;
      card.appendChild(cat);
      // --- AI FAQ Section ---
      if (job.faqs && job.faqs.length) {
        const faqWrap = document.createElement('details');
        const sumEl = document.createElement('summary');
        sumEl.textContent = currentLang==='hi'? 'सामान्य प्रश्न' : 'FAQs';
        faqWrap.appendChild(sumEl);
        // Show summary/summary_hi as context above FAQ
        const faqContext = (currentLang === 'hi' && job.summary_hi) ? job.summary_hi : (job.summary || job.description || '');
        if (faqContext) {
          const contextDiv = document.createElement('div');
          contextDiv.className = 'faq-context';
          contextDiv.textContent = faqContext;
          faqWrap.appendChild(contextDiv);
        }
        const ul = document.createElement('ul');
        job.faqs.forEach(faq => {
          const li = document.createElement('li');
          // Support both string and {q,a} object FAQ formats
          if (typeof faq === 'object' && faq.q && faq.a) {
            li.innerHTML = `<b>Q:</b> ${faq.q}<br/><b>A:</b> ${faq.a}`;
          } else {
            li.textContent = faq;
          }
          ul.appendChild(li);
        });
        faqWrap.appendChild(ul);
        card.appendChild(faqWrap);
      }
      // --- End AI FAQ Section ---
    }
    // Download as PDF
    const pdfBtn = document.createElement('button');
    pdfBtn.className = 'download-pdf-btn';
    pdfBtn.textContent = currentLang==='hi'? 'PDF डाउनलोड करें' : 'Download PDF';
    pdfBtn.onclick = e => {
      e.stopPropagation();
      if (window.jspdf && window.jspdf.jsPDF) {
        const doc = new window.jspdf.jsPDF();
        doc.setFontSize(14);
        doc.text(job.title, 10, 15);
        let y = 25;
        // --- AI Summary in PDF ---
        const pdfSummary = (currentLang === 'hi' && job.summary_hi) ? job.summary_hi : (job.summary || job.description || '');
        doc.setFontSize(11);
        doc.text(pdfSummary, 10, y); y += 10;
        if (job.last_date) { doc.text((currentLang==='hi'?'अंतिम तिथि: ':'Deadline: ') + job.last_date, 10, y); y += 10; }
        if (job.skills && job.skills.length) { doc.text((currentLang==='hi'?'कौशल: ':'Skills: ') + job.skills.join(', '), 10, y); y += 10; }
        if (job.category) { doc.text((currentLang==='hi'?'श्रेणी: ':'Category: ') + job.category, 10, y); y += 10; }
        if (job.faqs && job.faqs.length) {
          doc.text((currentLang==='hi'?'सामान्य प्रश्न: ':'FAQs:'), 10, y); y += 7;
          job.faqs.forEach(f => {
            if (typeof f === 'object' && f.q && f.a) {
              doc.text('Q: ' + f.q, 12, y); y += 7;
              doc.text('A: ' + f.a, 12, y); y += 7;
            } else {
              doc.text('- ' + f, 12, y); y += 7;
            }
          });
        }
        doc.save((job.title || 'job') + '.pdf');
      } else {
        alert(currentLang==='hi'? 'PDF डाउनलोड अस्थायी रूप से उपलब्ध नहीं है।' : 'PDF download temporarily unavailable.');
      }
    };
    card.appendChild(pdfBtn);
    // Card click opens job link
    if (job.apply_link || job.url) {
      card.onclick = () => {
        // Open in modal or new tab; for SEO, update meta tags
        let restoreMeta = setMetaTagsForJob(job);
        window.open(job.apply_link || job.url, '_blank', 'noopener');
        setTimeout(restoreMeta, 2000); // Restore after user leaves
      };
      card.style.cursor = 'pointer';
    }
    frag.appendChild(card);
  });
  container.appendChild(frag);
  // Render pagination controls below jobs
  renderPaginationControls(jobs.length, totalPages);
  updateFilterDropdowns(jobsData);
}

// --- Pagination Controls ---
function renderPaginationControls(totalJobs, totalPages) {
  let pagContainer = document.getElementById('pagination-controls');
  if (!pagContainer) {
    pagContainer = document.createElement('div');
    pagContainer.id = 'pagination-controls';
    pagContainer.className = 'pagination-controls';
    document.getElementById(JOBS_CONTAINER_ID).after(pagContainer);
  }
  pagContainer.innerHTML = '';
  if (totalPages <= 1) {
    pagContainer.style.display = 'none';
    return;
  }
  pagContainer.style.display = '';
  // Prev button
  const prevBtn = document.createElement('button');
  prevBtn.textContent = currentLang==='hi' ? 'पिछला' : 'Prev';
  prevBtn.disabled = currentPage === 1;
  prevBtn.onclick = () => { if (currentPage > 1) { currentPage--; renderJobs(filteredJobs); window.scrollTo(0,0); } };
  pagContainer.appendChild(prevBtn);
  // Page numbers (show up to 5 pages)
  let startPage = Math.max(1, currentPage - 2);
  let endPage = Math.min(totalPages, startPage + 4);
  if (endPage - startPage < 4) startPage = Math.max(1, endPage - 4);
  for (let i = startPage; i <= endPage; i++) {
    const btn = document.createElement('button');
    btn.textContent = i;
    btn.className = (i === currentPage) ? 'active' : '';
    btn.onclick = () => { currentPage = i; renderJobs(filteredJobs); window.scrollTo(0,0); };
    pagContainer.appendChild(btn);
  }
  // Next button
  const nextBtn = document.createElement('button');
  nextBtn.textContent = currentLang==='hi' ? 'अगला' : 'Next';
  nextBtn.disabled = currentPage === totalPages;
  nextBtn.onclick = () => { if (currentPage < totalPages) { currentPage++; renderJobs(filteredJobs); window.scrollTo(0,0); } };
  pagContainer.appendChild(nextBtn);
}
// --- End Pagination Controls ---


function updateFilterDropdowns(jobs) {
  let states = Array.from(new Set(jobs.map(j => j.state).filter(Boolean))).sort();
  let cats = Array.from(new Set(jobs.map(j => j.category).filter(Boolean))).sort();
  const stateSel = document.getElementById('filterState');
  const catSel = document.getElementById('filterCategory');
  stateSel.innerHTML = '<option value="">All States</option>' + states.map(s => `<option value="${s}">${s}</option>`).join('');
  catSel.innerHTML = '<option value="">All Categories</option>' + cats.map(c => `<option value="${c}">${c}</option>`).join('');
}

function toggleBookmark(jobId) {
  let idx = bookmarks.indexOf(jobId);
  if (idx !== -1) bookmarks.splice(idx, 1);
  else bookmarks.push(jobId);
  localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
  applyFiltersAndSort();
}

function renderTrendingChart(jobs) {
  // Compute top categories/skills
  let freq = {};
  jobs.forEach(j => {
    let key = j.category || 'Other';
    freq[key] = (freq[key] || 0) + 1;
  });
  let entries = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 6);
  let labels = entries.map(e => e[0]);
  let data = entries.map(e => e[1]);
  let ctx = document.getElementById('trendingChart').getContext('2d');
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Trending Roles', data, backgroundColor: '#229ED9' }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });
}


// --- Bilingual UI translations ---
const translations = {
  en: {
    allStates: 'All States',
    allCategories: 'All Categories',
    filterDeadline: 'Filter by Deadline',
    sortLatest: 'Sort: Latest',
    sortExpiring: 'Sort: Expiring Soon',
    clear: 'Clear',
    bookmarks: 'My Bookmarks',
    trendingChart: 'Trending Roles',
    noJobs: 'No jobs found.',
    removeBookmark: 'Remove bookmark',
    bookmark: 'Bookmark',
    downloadPDF: 'Download PDF',
    deadline: 'Deadline: ',
    skills: 'Skills: ',
    category: 'Category: ',
    faqs: 'FAQs',
    pdfUnavailable: 'PDF download temporarily unavailable.'
  },
  hi: {
    allStates: 'सभी राज्य',
    allCategories: 'सभी श्रेणियाँ',
    filterDeadline: 'अंतिम तिथि द्वारा छाँटें',
    sortLatest: 'नवीनतम पहले',
    sortExpiring: 'शीघ्र समाप्त',
    clear: 'साफ करें',
    bookmarks: 'मेरे बुकमार्क',
    trendingChart: 'रुझान वाली भूमिकाएँ',
    noJobs: 'कोई नौकरी नहीं मिली।',
    removeBookmark: 'बुकमार्क हटाएं',
    bookmark: 'बुकमार्क करें',
    downloadPDF: 'PDF डाउनलोड करें',
    deadline: 'अंतिम तिथि: ',
    skills: 'कौशल: ',
    category: 'श्रेणी: ',
    faqs: 'सामान्य प्रश्न',
    pdfUnavailable: 'PDF डाउनलोड अस्थायी रूप से उपलब्ध नहीं है।'
  }
};
function t(key) { return translations[currentLang][key] || key; }

function updateUITranslations() {
  document.getElementById('filterState').options[0].text = t('allStates');
  document.getElementById('filterCategory').options[0].text = t('allCategories');
  document.getElementById('filterDeadline').setAttribute('aria-label', t('filterDeadline'));
  document.getElementById('sortBy').options[0].text = t('sortLatest');
  document.getElementById('sortBy').options[1].text = t('sortExpiring');
  document.getElementById('clearFilters').textContent = t('clear');
  document.getElementById('toggleBookmarks').textContent = t('bookmarks');
  document.getElementById('trendingChart').setAttribute('aria-label', t('trendingChart'));
}

// --- JSON-LD JobPosting microdata injection ---
function injectJobPostingLD(jobs) {
  // Remove old blocks
  document.querySelectorAll('.jobposting-jsonld').forEach(e => e.remove());
  jobs.forEach(job => {
    const ld = {
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": job.title,
      "description": job.summary || job.description || '',
      "datePosted": job.date_posted || '',
      "validThrough": job.last_date || '',
      "employmentType": job.category || '',
      "hiringOrganization": { "@type": "Organization", "name": job.org || 'Sarkari Sarthi' },
      "jobLocation": { "@type": "Place", "address": { "addressRegion": job.state || '' } },
      "skills": job.skills ? job.skills.join(', ') : ''
    };
    const script = document.createElement('script');
    if (script) script.type = 'application/ld+json';
    script.className = 'jobposting-jsonld';
    script.textContent = JSON.stringify(ld);
    document.body.appendChild(script);
  });
}

/**** LANGUAGE SWITCHING ****/
const setupLanguageSwitcher = () => {
  const langToggle = document.getElementById(LANG_TOGGLE_ID);
  if (!langToggle) return;
  langToggle.value = currentLang;
  langToggle.setAttribute("aria-label", "Switch language");
  langToggle.addEventListener("change", e => {
    currentLang = e.target.value;
    localStorage.setItem(LOCALSTORAGE_LANG, currentLang);
    updateLanguage();
  });
  updateLanguage();
};

const updateLanguage = () => {
  document.documentElement.lang = currentLang;
  // Show/hide language-specific elements using data-lang
  document.querySelectorAll("[data-lang]").forEach(el => {
    el.style.display = el.getAttribute("data-lang") === currentLang ? "" : "none";
  });
};

/**** DARK MODE ****/
const setupDarkMode = () => {
  const darkToggle = document.getElementById(DARK_MODE_TOGGLE_ID);
  if (!darkToggle) return;
  // Restore dark mode state
  if (localStorage.getItem(LOCALSTORAGE_DARK) === "1") {
    document.body.classList.add(DARK_MODE_CLASS);
  }
  darkToggle.setAttribute("aria-label", "Toggle dark mode");
  darkToggle.tabIndex = 0;
  const toggleDark = () => {
    document.body.classList.toggle(DARK_MODE_CLASS);
    localStorage.setItem(
      LOCALSTORAGE_DARK,
      document.body.classList.contains(DARK_MODE_CLASS) ? "1" : "0"
    );
  };
  darkToggle.addEventListener("click", toggleDark);
  darkToggle.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") toggleDark();
  });
};

/**** JOB LOADING ****/
const loadJobsManifest = () => {
  showError("");
  fetch(JOBS_MANIFEST_URL)
    .then(res => {
      if (!res.ok) throw new Error("Manifest not found");
      return res.json();
    })
    .then(files => {
      if (!Array.isArray(files)) throw new Error("Invalid manifest format");
      Promise.all(files.map(filename => loadJobFile(JOBS_DIR + filename)))
        .then(jobsArr => {
          jobsData = jobsArr.filter(Boolean); // Remove failed jobs
          filteredJobs = jobsData;
          renderJobs(filteredJobs);
        });
    })
    .catch(err => {
      showError(currentLang === "hi" ? "नौकरी सूची लोड नहीं हो सकी।" : "Failed to load job list.");
      renderJobs([]);
      console.error("Failed to load job manifest:", err);
    });
};

const loadJobFile = url => {
  return fetch(url)
    .then(res => {
      if (!res.ok) throw new Error("Job file not found");
      return res.json();
    })
    .catch(err => {
      // Optionally display per-job error

/**** JOB RENDERING ****/
function renderJobs(jobs) {
  const container = document.getElementById(JOBS_CONTAINER_ID);
  const skeleton = document.getElementById("jobs-skeleton");
  const counter = document.getElementById("job-counter");
  const liveRegion = document.getElementById("jobs-live-region");
  if (!container) return;

  // Show skeleton loader if jobs are loading
  if (jobs === null) {
    if (skeleton) skeleton.style.display = "flex";
    container.innerHTML = "";
    if (counter) counter.textContent = "";
    if (liveRegion) liveRegion.textContent = "";
    return;
  } else {
    if (skeleton) skeleton.style.display = "none";
  }

  // Animate job counter
  if (counter) {
    let prev = parseInt(counter.textContent) || 0;
    let curr = jobs.length;
    if (prev !== curr) {
      let step = prev < curr ? 1 : -1;
      let i = prev;
      const animate = () => {
        i += step;
        counter.textContent = `${i} ${currentLang === "hi" ? "नौकरियाँ" : "Jobs"}`;
        if (i !== curr) requestAnimationFrame(animate);
      };
      animate();
    } else {
      counter.textContent = `${curr} ${currentLang === "hi" ? "नौकरियाँ" : "Jobs"}`;
    }
  }

  // ARIA live update
  if (liveRegion) {
    liveRegion.textContent = jobs.length
      ? `${jobs.length} ${currentLang === "hi" ? "नौकरियाँ मिलीं" : "jobs found"}`
      : (currentLang === "hi" ? "कोई नौकरी नहीं मिली।" : "No jobs found.");
  }

  if (!jobs.length) {
    container.innerHTML = `<div class="no-jobs" tabindex="0">${currentLang === "hi" ? "कोई नौकरी नहीं मिली।" : "No jobs found."}</div>`;
    return;
  }
  const frag = document.createDocumentFragment();
  jobs.forEach(job => {
    frag.appendChild(createJobCard(job));
  });
  container.innerHTML = "";
  container.appendChild(frag);
  requestAnimationFrame(() => {
    container.querySelectorAll(".job-card").forEach(card => {
      card.classList.add(FADE_IN_CLASS);
    });
  });
  setupJobCardInteractivity();
}

// Modal logic for job details and PDF preview
function setupJobCardInteractivity() {
  const modal = document.getElementById("job-modal");
  const modalContent = document.getElementById("modal-job-content");
  const closeBtn = document.querySelector(".close-modal");
  document.querySelectorAll(".job-card").forEach(card => {
    card.onclick = () => {
      const job = card.__jobData;
      if (!job) return;
      modalContent.innerHTML = `
        <div class="job-category">${job.category}</div>
        <h3>${job.title}</h3>
        <div class="job-meta">
          <span><i class="icon-calendar"></i> Last Date: ${job.last_date}</span>
          <span><i class="icon-location"></i> ${job.state}</span>
        </div>
        <a class="cta" href="${job.apply_link}" target="_blank" rel="noopener noreferrer">Apply Now</a>
        ${job.pdf_url ? `<button class="pdf-preview" data-pdf="${job.pdf_url}">Preview PDF</button>` : ""}
      `;
      modal.classList.remove("hidden");
      trapFocus(modal);
    };
    // Save job data for modal
    card.__jobData = card.__jobData || card.dataset && JSON.parse(card.dataset.job || '{}');
  });
  if (closeBtn) {
    closeBtn.onclick = () => { modal.classList.add("hidden"); };
  }
  window.addEventListener("keydown", e => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      modal.classList.add("hidden");
    }
  });
  // PDF preview logic
  modalContent && modalContent.addEventListener("click", e => {
    if (e.target && e.target.classList.contains("pdf-preview")) {
      const url = e.target.getAttribute("data-pdf");
      if (url) {
        window.open(url, "_blank");
      }
    }
  });
}

// createJobCard function (fixed)
const createJobCard = job => {
  const card = document.createElement("div");
  card.className = "job-card";
  card.tabIndex = 0;
  card.setAttribute("role", "article");
  card.setAttribute("aria-label", job.title);

  // Category
  const cat = document.createElement("span");
  cat.className = "job-category";
  cat.textContent = job.category;
  card.appendChild(cat);

  // Last date
  const lastDate = document.createElement("span");
  lastDate.className = "last-date";
  lastDate.textContent = (currentLang === "hi" ? "अंतिम तिथि: " : "Last Date: ") + (job.lastDate || job.last_date || "");
  card.appendChild(lastDate);

  // Title
  const title = document.createElement("div");
  title.className = "job-title";
  title.textContent = job.title;
  card.appendChild(title);

  // Apply Button
  const apply = document.createElement("a");
  apply.className = "apply-btn";
  apply.href = job.applyUrl || job.apply_link || "#";
  apply.target = "_blank";
  apply.rel = "noopener noreferrer";
  apply.tabIndex = 0;
  apply.textContent = currentLang === "hi" ? "अभी आवेदन करें" : "Apply Now";
  apply.setAttribute("aria-label", apply.textContent + ' ' + job.title);
  card.appendChild(apply);

  // Save job data for modal
  card.__jobData = job;

  return card;
};

/**** ERROR UI ****/
const showError = msg => {
  let errorEl = document.getElementById(ERROR_CONTAINER_ID);
  if (!errorEl) {
    errorEl = document.createElement("div");
    errorEl.id = ERROR_CONTAINER_ID;
    errorEl.setAttribute("role", "alert");
    errorEl.style.color = "#b91c1c";
    errorEl.style.margin = "1rem auto";
    errorEl.style.textAlign = "center";
    errorEl.style.fontWeight = "bold";
    errorEl.style.fontSize = "1.1rem";
    document.body.insertBefore(errorEl, document.body.firstChild);
  }
  errorEl.textContent = msg;
  errorEl.style.display = msg ? "block" : "none";
};

/**** SEARCH & FILTER ****/
const setupSearchAndFilter = () => {
  const searchInput = document.getElementById(SEARCH_INPUT_ID);
  const deptSelect = document.getElementById(DEPT_SELECT_ID);
  if (searchInput) {
    searchInput.setAttribute("aria-label", "Search jobs");
    searchInput.addEventListener("input", e => {
      if (searchDebounceTimeout) clearTimeout(searchDebounceTimeout);
      searchDebounceTimeout = setTimeout(() => {
        filterJobs();
      }, 250);
    });
  }
  if (deptSelect) {
    deptSelect.setAttribute("aria-label", "Filter by department");
    deptSelect.addEventListener("change", filterJobs);
  }
};

const filterJobs = () => {
  const searchValue = (document.getElementById(SEARCH_INPUT_ID)?.value || "").trim().toLowerCase();
  const deptValue = (document.getElementById(DEPT_SELECT_ID)?.value || "").toLowerCase();
  filteredJobs = jobsData.filter(job => {
    const matchesSearch = !searchValue || job.title.toLowerCase().includes(searchValue);
    const matchesDept = !deptValue || deptValue === "all" || job.category.toLowerCase() === deptValue;
    return matchesSearch && matchesDept;
  });
  renderJobs(filteredJobs);
};

/**** FADE-IN ANIMATION CLASS ****/
// Add this CSS to your stylesheet:
// .fade-in { opacity: 0; animation: fadeIn 0.7s forwards; }
// @keyframes fadeIn { to { opacity: 1; } }
