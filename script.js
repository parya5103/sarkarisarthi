document.addEventListener('DOMContentLoaded', () => {
  const jobListingsContainer = document.getElementById('jobListings');
  const departmentFilterSelect = document.getElementById('departmentFilter');
  const searchJobInput = document.getElementById('searchJob');
  const resetFiltersButton = document.getElementById('resetFilters');
  const darkModeToggle = document.getElementById('darkModeToggle');
  const languageToggle = document.getElementById('languageToggle');
  const trendingKeywordsList = document.getElementById('trendingKeywords');
  const paginationContainer = document.getElementById('pagination');

  let allJobs = [];
  let currentLanguage = 'en';
  let currentPage = 1;
  const jobsPerPage = 10;

  const translations = {
    en: {
      category: 'Category',
      state: 'State',
      lastDate: 'Last Date',
      apply: 'Apply Now',
      pdf: 'Download PDF',
      notSpecified: 'Not Specified',
      allCategories: 'All Categories',
      reset: 'Reset',
      search: 'Search by job title...',
      noJobs: 'No jobs found.',
      trending: 'Trending Keywords'
    },
    hi: {
      category: 'विभाग',
      state: 'राज्य',
      lastDate: 'अंतिम तिथि',
      apply: 'अब आवेदन करें',
      pdf: 'पीडीएफ डाउनलोड करें',
      notSpecified: 'निर्दिष्ट नहीं',
      allCategories: 'सभी श्रेणियाँ',
      reset: 'रीसेट',
      search: 'जॉब टाइटल से खोजें...',
      noJobs: 'कोई नौकरी नहीं मिली।',
      trending: 'रुझान वाले कीवर्ड'
    }
  };

  const t = (key) => translations[currentLanguage][key];

  // 🌓 Dark Mode
  const applyDarkMode = (enabled) => {
    document.body.classList.toggle('dark-mode', enabled);
    localStorage.setItem('darkMode', enabled ? 'enabled' : 'disabled');
    darkModeToggle.textContent = enabled ? '☀️' : '🌙';
  };

  if (localStorage.getItem('darkMode') === 'enabled') {
    applyDarkMode(true);
  }

  darkModeToggle.addEventListener('click', () => {
    const isDark = document.body.classList.contains('dark-mode');
    applyDarkMode(!isDark);
  });

  // 🌐 Language Switch
  languageToggle.addEventListener('change', () => {
    currentLanguage = languageToggle.value;
    updatePlaceholders();
    displayJobs(paginateJobs(allJobs, currentPage));
    populateFilters();
    updateTrendingKeywords();
  });

  function updatePlaceholders() {
    searchJobInput.placeholder = t('search');
    resetFiltersButton.textContent = t('reset');
    document.querySelector('option[value=""]').textContent = t('allCategories');
  }

  // 🔍 Trending Keywords (Mock)
  function updateTrendingKeywords() {
    const keywords = ["SSC", "Railway", "IBPS", "UPSC", "Defence", "Teacher", "Police", "Apprentice"];
    trendingKeywordsList.innerHTML = "";
    keywords.forEach(keyword => {
      const li = document.createElement('li');
      li.textContent = keyword;
      trendingKeywordsList.appendChild(li);
    });
  }

  // 📄 Fetch Jobs
  async function fetchJobs() {
    try {
      const manifest = await fetch('./jobs/job_manifest.json').then(res => res.json());
      const jobFetches = manifest.map(file =>
        fetch(`./jobs/${file}`)
          .then(r => r.json())
          .then(data => Array.isArray(data) ? data : [data])
          .catch(() => [])
      );
      const all = await Promise.all(jobFetches);
      allJobs = all.flat().filter(j => j.title && j.apply_link).map(j => ({
        title: j.title,
        department: j.category || 'N/A',
        state: j.state || 'N/A',
        last_date: j.last_date || t('notSpecified'),
        apply_link: j.apply_link,
        pdf_link: j.pdf_link || null
      }));
      populateFilters();
      updateTrendingKeywords();
      applyFilters(); // initial display
    } catch (err) {
      jobListingsContainer.innerHTML = `<p>${t('noJobs')}</p>`;
      console.error("Job loading error:", err);
    }
  }

  // 🎛️ Filters
  function populateFilters() {
    const departments = new Set(allJobs.map(j => j.department).filter(d => d !== 'N/A'));
    departmentFilterSelect.innerHTML = `<option value="">${t('allCategories')}</option>`;
    [...departments].sort().forEach(dep => {
      const opt = document.createElement('option');
      opt.value = dep;
      opt.textContent = dep;
      departmentFilterSelect.appendChild(opt);
    });
  }

  // 📤 Display Jobs
  function displayJobs(jobs) {
    jobListingsContainer.innerHTML = '';
    if (jobs.length === 0) {
      jobListingsContainer.innerHTML = `<p>${t('noJobs')}</p>`;
      return;
    }

    jobs.forEach(job => {
      const card = document.createElement('div');
      card.className = 'job-card';
      card.innerHTML = `
        <h3>${job.title}</h3>
        <p><strong>${t('category')}:</strong> ${job.department}</p>
        <p><strong>${t('state')}:</strong> ${job.state}</p>
        <p><strong>${t('lastDate')}:</strong> ${job.last_date}</p>
        <div class="job-links">
          <a href="${job.apply_link}" target="_blank">${t('apply')}</a>
          ${job.pdf_link ? `<a href="${job.pdf_link}" class="pdf-link" target="_blank">${t('pdf')}</a>` : ''}
        </div>
      `;
      jobListingsContainer.appendChild(card);
    });

    updatePaginationControls(allJobs);
  }

  // 🔎 Apply Filters
  function applyFilters() {
    const search = searchJobInput.value.toLowerCase();
    const category = departmentFilterSelect.value;

    const filtered = allJobs.filter(job => {
      return (!category || job.department === category) &&
             (!search || job.title.toLowerCase().includes(search));
    });

    currentPage = 1;
    displayJobs(paginateJobs(filtered, currentPage));
  }

  searchJobInput.addEventListener('input', applyFilters);
  departmentFilterSelect.addEventListener('change', applyFilters);
  resetFiltersButton.addEventListener('click', () => {
    searchJobInput.value = '';
    departmentFilterSelect.value = '';
    applyFilters();
  });

  // 📑 Pagination Helpers
  function paginateJobs(jobs, page) {
    const start = (page - 1) * jobsPerPage;
    return jobs.slice(start, start + jobsPerPage);
  }

  function updatePaginationControls(jobs) {
    const totalPages = Math.ceil(jobs.length / jobsPerPage);
    paginationContainer.innerHTML = '';

    for (let i = 1; i <= totalPages; i++) {
      const btn = document.createElement('button');
      btn.textContent = i;
      if (i === currentPage) btn.classList.add('active');
      btn.addEventListener('click', () => {
        currentPage = i;
        displayJobs(paginateJobs(jobs, currentPage));
      });
      paginationContainer.appendChild(btn);
    }
  }

  // 🚀 Start
  fetchJobs();
});
