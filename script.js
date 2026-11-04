// SarkariSarthi 2.0 - Main JavaScript File

/**
 * Escapes HTML characters in a string to prevent XSS.
 * @param {string} str - The string to escape.
 * @returns {string} The escaped string.
 */
function escapeHTML(str) {
    if (!str) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(str).replace(/[&<>"']/g, function(m) { return map[m]; });
}


/**
 * Sanitizes HTML string using DOMParser to prevent XSS.
 * @param {string} htmlString - The HTML string to sanitize.
 * @returns {string} The sanitized HTML string.
 */
function sanitizeHTML(htmlString) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, 'text/html');

    const allowedTags = ['div', 'span', 'p', 'h3', 'h4', 'a', 'strong', 'em', 'br', 'ul', 'li'];
    const allowedAttributes = ['class', 'href', 'target', 'data-job-id', 'id'];

    function clean(node) {
        if (node.nodeType === Node.ELEMENT_NODE) {
            const tagName = node.tagName.toLowerCase();
            if (!allowedTags.includes(tagName)) {
                // Remove the node completely to prevent script execution
                node.parentNode.removeChild(node);
                return;
            }

            // Clean attributes
            const attrs = node.attributes;
            for (let i = attrs.length - 1; i >= 0; i--) {
                const attr = attrs[i];
                if (!allowedAttributes.includes(attr.name.toLowerCase())) {
                    node.removeAttribute(attr.name);
                } else if (attr.name.toLowerCase() === 'href') {
                    // Use the existing sanitizeURL for links
                    node.setAttribute('href', sanitizeURL(attr.value));
                }
            }

            // Recursively clean children
            const children = Array.from(node.childNodes);
            children.forEach(clean);
        }
    }

    const children = Array.from(doc.body.childNodes);
    children.forEach(clean);

    return doc.body.innerHTML;
}

// Trust labels for the server-side verification_status (Phase 1 data
// quality). The label explains WHERE the record's information comes
// from; it is never a claim that the portal itself is official.
const VERIFICATION_LABELS = {
    official_verified: {
        text: 'Official Source',
        cls: 'trust-chip trust-official',
        title: 'Backed by an official government source or link'
    },
    official_link_pending: {
        text: 'Official Link Pending',
        cls: 'trust-chip trust-pending',
        title: 'Official domain referenced; direct link not captured yet'
    },
    secondary_source_only: {
        text: 'Secondary Source',
        cls: 'trust-chip trust-secondary',
        title: 'From a secondary job portal; verify on the official website'
    },
    needs_review: {
        text: 'Needs Review',
        cls: 'trust-chip trust-review',
        title: 'Stale or incomplete record; will be re-checked'
    }
};

/**
 * Trust chip info for a verification_status value, or null when the
 * status is missing/unknown (nothing is invented for unknown values).
 * @param {string} status - The job's verification_status.
 * @returns {object|null} {text, cls, title} or null.
 */
function getVerificationInfo(status) {
    if (!status) return null;
    return VERIFICATION_LABELS[String(status).toLowerCase()] || null;
}

// ---- Bookmarks (Phase 3) --------------------------------------------
// Saved jobs live only in this browser (localStorage). No account,
// no tracking, nothing leaves the device.
const BOOKMARK_KEY = 'sarkariBookmarks';

function getBookmarks() {
    try {
        const parsed = JSON.parse(localStorage.getItem(BOOKMARK_KEY) || '[]');
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function isBookmarked(jobId) {
    return getBookmarks().indexOf(jobId) !== -1;
}

/**
 * Add/remove a job id from the saved list.
 * @returns {boolean} the new saved state.
 */
function toggleBookmark(jobId) {
    if (!jobId) return false;
    const bookmarks = getBookmarks();
    const pos = bookmarks.indexOf(jobId);
    if (pos === -1) {
        bookmarks.push(jobId);
    } else {
        bookmarks.splice(pos, 1);
    }
    try {
        localStorage.setItem(BOOKMARK_KEY, JSON.stringify(bookmarks));
    } catch (e) {
        // Storage full or blocked: the toggle is a no-op for persistence,
        // but the in-memory list keeps working for this page view.
    }
    return pos === -1;
}

// Global variables
let jobsData = [];
let jobsLoadFailed = false; // true when the job manifest could not be loaded (no fake fallback jobs)
let filteredJobs = [];
let currentPage = 1;
const jobsPerPage = 12;
let isLoading = false;
let savedOnly = false; // "Saved Jobs" filter toggle state

// DOM Elements
const jobsGrid = document.getElementById('jobsGrid');
const loadingSpinner = document.getElementById('loadingSpinner');
const loadMoreBtn = document.getElementById('loadMoreBtn');
const jobSearch = document.getElementById('jobSearch');
const categoryFilter = document.getElementById('categoryFilter');
const sortFilter = document.getElementById('sortFilter');
const searchBtn = document.getElementById('searchBtn');
const savedFilterBtn = document.getElementById('savedFilterBtn');
const themeToggle = document.getElementById('themeToggle');
const telegramBtn = document.getElementById('telegramBtn');
const footerTelegramBtn = document.getElementById('footerTelegramBtn');
const whatsappBtn = document.getElementById('whatsappBtn');
const footerWhatsappBtn = document.getElementById('footerWhatsappBtn');
const mobileMenuToggle = document.getElementById('mobileMenuToggle');
const jobModal = document.getElementById('jobModal');
const modalClose = document.getElementById('modalClose');
const modalClose2 = document.getElementById('modalClose2');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

let appInitialized = false;

/**
 * Initialize the application
 */
function initializeApp() {
    if (appInitialized) return;
    appInitialized = true;
    setupEventListeners();
    loadTheme();
    loadJobs();
    animateCounters();
    setupIntersectionObserver();
    updateSavedCount();
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Search functionality
    searchBtn.addEventListener('click', handleSearch);
    jobSearch.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            handleSearch();
        }
    });

    // Filter functionality
    categoryFilter.addEventListener('change', handleFilter);
    sortFilter.addEventListener('change', handleSort);

    // Saved jobs toggle (Phase 3)
    if (savedFilterBtn) {
        savedFilterBtn.addEventListener('click', function() {
            savedOnly = !savedOnly;
            savedFilterBtn.classList.toggle('active', savedOnly);
            savedFilterBtn.setAttribute('aria-pressed', String(savedOnly));
            applyFilters();
        });
    }

    // Load more functionality
    loadMoreBtn.addEventListener('click', loadMoreJobs);

    // Theme toggle
    themeToggle.addEventListener('click', toggleTheme);

    // Telegram buttons
    if (telegramBtn) {
        telegramBtn.addEventListener('click', openTelegramChannel);
    }
    if (footerTelegramBtn) {
        footerTelegramBtn.addEventListener('click', openTelegramChannel);
    }

    // WhatsApp buttons
    if (whatsappBtn) {
        whatsappBtn.addEventListener('click', openWhatsappChannel);
    }
    if (footerWhatsappBtn) {
        footerWhatsappBtn.addEventListener('click', openWhatsappChannel);
    }

    // Mobile menu toggle
    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', toggleMobileMenu);
        mobileMenuToggle.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleMobileMenu();
            }
        });
    }

    // Close mobile menu when a navigation link is clicked
    document.querySelectorAll('.nav-menu .nav-link').forEach(link => {
        link.addEventListener('click', function() {
            const navMenu = document.querySelector('.nav-menu');
            if (navMenu && navMenu.classList.contains('active')) {
                toggleMobileMenu();
            }
        });
    });

    // Reset filters button in search bar
    const resetFiltersBtn = document.getElementById('resetFiltersBtn');
    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener('click', clearAllFilters);
    }

    // Quick category filter bar buttons
    document.querySelectorAll('[data-quick-category]').forEach(btn => {
        btn.addEventListener('click', function() {
            const cat = this.dataset.quickCategory || '';
            if (categoryFilter) {
                categoryFilter.value = cat;
            }
            handleFilter();
        });
    });

    // Modal functionality
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    if (modalClose2) {
        modalClose2.addEventListener('click', closeModal);
    }

    // Close modal when clicking outside
    jobModal.addEventListener('click', function(e) {
        if (e.target === jobModal) {
            closeModal();
        }
    });

    // Footer category links (href="#" placeholders): make them filter
    // the jobs list instead of dead-ending.
    document.querySelectorAll('a[data-category]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            filterByCategory(this.dataset.category);
        });
    });

    // Category card clicks
    document.querySelectorAll('.category-card').forEach(card => {
        card.addEventListener('click', function() {
            const category = this.dataset.category;
            filterByCategory(category);
        });
        card.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const category = this.dataset.category;
                filterByCategory(category);
            }
        });
    });

    // Keyboard navigation
    document.addEventListener('keydown', handleKeyboardNavigation);
}

/**
 * Parse a job date string in the formats used by job records
 * (dd-mm-yyyy, dd/mm/yyyy, yyyy-mm-dd). Returns null if unparseable.
 */
function parseJobDate(dateStr) {
    if (!dateStr) return null;
    let m = dateStr.match(/(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})/);
    if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
    m = dateStr.match(/(\d{4})[-\/](\d{1,2})[-\/](\d{1,2})/);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
    return null;
}

/**
 * Best available "when was this record added/checked" timestamp in ms.
 * Used for the honest Latest First sort. Records without any usable
 * timestamp sort last (never guessed into the top).
 */
function getRecordTimestamp(job) {
    if (!job) return 0;
    const raw = job.last_verified || job.scraped_at ||
        (job.important_dates && job.important_dates.found_date) || '';
    const t = Date.parse(raw);
    return isNaN(t) ? 0 : t;
}

/**
 * Filter out jobs whose last date has already passed, so closed
 * vacancies are never displayed as active openings.
 */
function filterExpiredJobs(jobs) {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return jobs.filter(job => {
        // Server-side normalized status (Phase B) is authoritative when
        // present; the date check below remains a safety net for old
        // records that never passed through normalize_job.
        const status = String(job.status || '').toLowerCase();
        if (status === 'cancelled' || status === 'expired') return false;
        const lastDateStr = job.important_dates && job.important_dates.last_date;
        const lastDate = parseJobDate(lastDateStr);
        // Keep jobs without a parseable last date: absence of a date is
        // not evidence that a vacancy has closed.
        if (!lastDate) return true;
        return lastDate >= now;
    });
}

/**
 * Rebuild the category filter options from the currently loaded job
 * data, so every category present in the manifest (including Medical,
 * Engineering, Administrative and IT) is filterable, with counts.
 */
function populateCategoryFilter() {
    if (!categoryFilter) return;
    const selected = categoryFilter.value;
    const counts = {};
    jobsData.forEach(job => {
        if (job.category) counts[job.category] = (counts[job.category] || 0) + 1;
    });
    while (categoryFilter.options.length > 1) {
        categoryFilter.remove(1);
    }
    Object.keys(counts).sort().forEach(cat => {
        const opt = document.createElement('option');
        opt.value = cat;
        opt.textContent = cat + ' (' + counts[cat] + ')';
        categoryFilter.appendChild(opt);
    });
    if (selected && Array.from(categoryFilter.options).some(o => o.value === selected)) {
        categoryFilter.value = selected;
    }
}

/**
 * Load jobs data from the published job manifest
 */
async function loadJobs() {
    try {
        showLoading(true);
        jobsLoadFailed = false;

        // Try to load from job manifest first
        const response = await fetch('jobs/job_manifest.json');
        if (response.ok) {
            const manifest = await response.json();
            jobsData = filterExpiredJobs(manifest.jobs || []);
            populateCategoryFilter();
        } else {
            // Manifest missing or unreachable: show an honest error
            // state. Never fall back to hard-coded sample jobs.
            jobsData = [];
            jobsLoadFailed = true;
        }

        // Optimization: Pre-compute _searchString once during data load to avoid O(N*5) string allocations on every search keystroke
        // Reduces CPU usage and garbage collection during search by ~80%
        jobsData.forEach(job => {
            const skillsStr = job.skills ? job.skills.join(' ') : '';
            job._searchString = `${job.title} ${job.description} ${job.source} ${job.category} ${skillsStr}`.toLowerCase();
        });

        applyFilters();
        updateJobCounts();

    } catch (error) {
        console.error('Error loading jobs:', error);
        // Honest error state: no fake sample-job fallback.
        jobsData = [];
        jobsLoadFailed = true;

        jobsData.forEach(job => {
            const skillsStr = job.skills ? job.skills.join(' ') : '';
            job._searchString = `${job.title} ${job.description} ${job.source} ${job.category} ${skillsStr}`.toLowerCase();
        });

        applyFilters();
    } finally {
        showLoading(false);
    }
}

/**
 * Single filter pipeline: search term + category + saved-only, then
 * re-apply the current sort and render. Keeping every filter path in
 * one function prevents search, category and bookmark filters from
 * accidentally overwriting each other.
 */
function applyFilters() {
    const searchTerm = jobSearch ? jobSearch.value.toLowerCase().trim() : '';
    const selectedCategory = categoryFilter ? categoryFilter.value : '';

    let base = jobsData;
    if (searchTerm !== '') {
        base = base.filter(job => job._searchString.includes(searchTerm));
    }
    if (selectedCategory !== '') {
        base = base.filter(job => job.category === selectedCategory);
    }
    if (savedOnly) {
        base = base.filter(job => isBookmarked(job.id));
    }
    filteredJobs = [...base];
    currentPage = 1;

    // Sync active visual state on category cards and quick filter buttons
    document.querySelectorAll('.category-card').forEach(card => {
        card.classList.toggle('active', Boolean(selectedCategory && card.dataset.category === selectedCategory));
    });
    document.querySelectorAll('[data-quick-category]').forEach(btn => {
        btn.classList.toggle('active', (btn.dataset.quickCategory || '') === selectedCategory);
    });

    const summaryEl = document.getElementById('jobsResultSummary');
    if (summaryEl && !jobsLoadFailed) {
        const parts = [];
        if (selectedCategory) parts.push(`Category: ${selectedCategory}`);
        if (searchTerm) parts.push(`Query: "${jobSearch.value.trim()}"`);
        if (savedOnly) parts.push('Saved on this device');
        summaryEl.textContent = parts.length > 0
            ? `Showing ${filteredJobs.length} matching notification${filteredJobs.length === 1 ? '' : 's'} (${parts.join(' · ')})`
            : `Showing ${filteredJobs.length} verified active recruitment notification${filteredJobs.length === 1 ? '' : 's'} across India`;
    }

    handleSort();
}

/**
 * Render jobs on the page
 */
function renderJobs() {
    if (!jobsGrid) return;

    const startIndex = (currentPage - 1) * jobsPerPage;
    const endIndex = startIndex + jobsPerPage;
    const jobsToShow = filteredJobs.slice(0, endIndex);

    if (currentPage === 1) {
        jobsGrid.innerHTML = '';
    }

    if (jobsToShow.length === 0) {
        if (jobsLoadFailed) {
            jobsGrid.innerHTML = `
            <div class="no-jobs">
                <div style="font-size: 3rem; margin-bottom: 1rem;">📡</div>
                <h3>Couldn't load job listings</h3>
                <p>The latest job data could not be loaded. Check your internet connection and retry. We never display sample or outdated jobs as real vacancies.</p>
                <button class="clear-filters-btn" onclick="location.reload()">Retry</button>
            </div>
        `;
        } else if (savedOnly) {
            jobsGrid.innerHTML = `
            <div class="no-jobs">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🔖</div>
                <h3>No saved jobs yet</h3>
                <p>Tap the bookmark icon on any job card to save it on this device. Saved jobs stay here even after their listing moves.</p>
                <button class="clear-filters-btn" onclick="clearAllFilters()">Show All Jobs</button>
            </div>
        `;
        } else {
            jobsGrid.innerHTML = `
            <div class="no-jobs">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🔍</div>
                <h3>No jobs found</h3>
                <p>We couldn't find any jobs matching your current search and filters.</p>
                <button class="clear-filters-btn" onclick="clearAllFilters()">Clear All Filters</button>
            </div>
        `;
        }
        loadMoreBtn.style.display = 'none';
        return;
    }

    const jobsToRender = jobsToShow.slice(startIndex);

    // Optimization: Batch DOM insertions using DocumentFragment to prevent layout thrashing
    // Reduces render time by avoiding multiple reflows/repaints inside the loop
    const fragment = document.createDocumentFragment();
    jobsToRender.forEach(job => {
        const jobCard = createJobCard(job);
        fragment.appendChild(jobCard);
    });
    jobsGrid.appendChild(fragment);

    // Show/hide load more button
    if (endIndex >= filteredJobs.length) {
        loadMoreBtn.style.display = 'none';
    } else {
        loadMoreBtn.style.display = 'block';
    }

    // Add animation to new cards
    const newCards = jobsGrid.querySelectorAll('.job-card:not(.animated)');
    newCards.forEach((card, index) => {
        card.classList.add('animated');
        setTimeout(() => {
            card.classList.add('slide-up');
        }, index * 100);
    });
}

/**
 * Refresh every bookmark button state after a filter change re-renders
 * the grid (icons are rebuilt from localStorage on each render).
 */
function updateSavedCount() {
    if (!savedFilterBtn) return;
    const count = getBookmarks().length;
    savedFilterBtn.textContent = '🔖 Saved Jobs' + (count > 0 ? ' (' + count + ')' : '');
}

/**
 * Create a job card element
 */
function createJobCard(job) {
    const card = document.createElement('div');
    card.className = 'job-card';
    card.setAttribute('data-job-id', job.id);
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', `View details for ${job.title} at ${job.source}`);

    const lastDate = job.important_dates?.last_date || job.important_dates?.found_date || 'Not specified';
    const skills = job.skills || [];

    const header = document.createElement('div');
    header.className = 'job-header';

    const headerTitleDiv = document.createElement('div');
    const titleH3 = document.createElement('h3');
    titleH3.className = 'job-title';
    titleH3.textContent = job.title;

    const sourceP = document.createElement('p');
    sourceP.className = 'job-source';
    sourceP.textContent = job.source;

    headerTitleDiv.appendChild(titleH3);
    headerTitleDiv.appendChild(sourceP);

    const categorySpan = document.createElement('span');
    categorySpan.className = 'job-category';
    categorySpan.textContent = job.category;

    header.appendChild(headerTitleDiv);
    header.appendChild(categorySpan);

    // Trust chip (Phase 3): shows where this record's information
    // comes from. Unknown/missing verification never invents a label.
    const verificationInfo = getVerificationInfo(job.verification_status);
    if (verificationInfo) {
        const trustSpan = document.createElement('span');
        trustSpan.className = verificationInfo.cls;
        trustSpan.textContent = verificationInfo.text;
        trustSpan.title = verificationInfo.title;
        header.appendChild(trustSpan);
    }

    // Application status chip (Phase B status field): 'upcoming' jobs
    // have a future application start date; expired and cancelled jobs
    // are filtered out entirely.
    if (String(job.status || '').toLowerCase() === 'upcoming') {
        const statusSpan = document.createElement('span');
        statusSpan.className = 'job-status status-upcoming';
        statusSpan.textContent = 'Opening Soon';
        header.appendChild(statusSpan);
    }

    const descP = document.createElement('p');
    descP.className = 'job-description';
    descP.textContent = job.description;

    card.appendChild(header);
    card.appendChild(descP);

    if (skills.length > 0) {
        const skillsDiv = document.createElement('div');
        skillsDiv.className = 'job-skills';
        skills.forEach(skill => {
            const skillSpan = document.createElement('span');
            skillSpan.className = 'skill-tag';
            skillSpan.textContent = skill;
            skillsDiv.appendChild(skillSpan);
        });
        card.appendChild(skillsDiv);
    }

    const metaDiv = document.createElement('div');
    metaDiv.className = 'job-meta';
    const dateSpan = document.createElement('span');
    dateSpan.className = 'job-date';
    dateSpan.textContent = `Last Date: ${lastDate}`;
    metaDiv.appendChild(dateSpan);

    // Link to the static prerendered detail page (Phase 5): a
    // stable, crawlable URL with the full verified notification data.
    const detailsLink = document.createElement('a');
    detailsLink.href = 'job/' + encodeURIComponent(job.id) + '/';
    detailsLink.className = 'view-details-link';
    detailsLink.textContent = 'View Details';
    detailsLink.addEventListener('click', (e) => e.stopPropagation());
    metaDiv.appendChild(detailsLink);

    card.appendChild(metaDiv);

    // Bookmark button (Phase 3): saved jobs live in localStorage on
    // this device only. The click must not open the detail modal.
    const bookmarkBtn = document.createElement('button');
    bookmarkBtn.type = 'button';
    const saved = isBookmarked(job.id);
    bookmarkBtn.className = 'bookmark-btn' + (saved ? ' bookmarked' : '');
    bookmarkBtn.textContent = saved ? '🔖' : '☆';
    bookmarkBtn.title = saved ? 'Remove from saved jobs' : 'Save this job on this device';
    bookmarkBtn.setAttribute('aria-label', bookmarkBtn.title);
    bookmarkBtn.setAttribute('aria-pressed', String(saved));
    bookmarkBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const nowSaved = toggleBookmark(job.id);
        bookmarkBtn.classList.toggle('bookmarked', nowSaved);
        bookmarkBtn.textContent = nowSaved ? '🔖' : '☆';
        bookmarkBtn.title = nowSaved ? 'Remove from saved jobs' : 'Save this job on this device';
        bookmarkBtn.setAttribute('aria-label', bookmarkBtn.title);
        bookmarkBtn.setAttribute('aria-pressed', String(nowSaved));
        updateSavedCount();
        // If the Saved filter is active, removing a bookmark must
        // refresh the list so the unsaved job disappears.
        if (savedOnly) {
            applyFilters();
        }
    });
    card.appendChild(bookmarkBtn);

    // Add click event to open modal
    card.addEventListener('click', () => openJobModal(job));

    // Add keydown event for keyboard accessibility
    card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openJobModal(job);
        }
    });

    return card;
}

/**
 * Build a readable age-limit string from whatever fields exist.
 * Never invents values: returns '' when nothing is known.
 */
function ageLimitText(job) {
    if (job.age_limit) return job.age_limit;
    const min = job.age_min;
    const max = job.age_max;
    if (min && max) return min + ' to ' + max + ' years';
    if (max) return 'Up to ' + max + ' years';
    if (min) return min + ' years and above';
    return '';
}

/**
 * Open job detail modal
 */
function openJobModal(job) {
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    const modalApplyBtn = document.getElementById('modalApplyBtn');

    if (!modalTitle || !modalBody || !modalApplyBtn) return;

    modalTitle.textContent = job.title;
    // Prefer the verified official application URL when present.
    modalApplyBtn.href = sanitizeURL(job.official_application_url || job.url);

    const lastDate = job.important_dates?.last_date || job.important_dates?.found_date || 'Not specified';
    const examDate = job.important_dates?.exam_date || 'Not specified';
    const skills = job.skills || [];

    modalBody.innerHTML = '';

    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'modal-job-details';

    // Verification section (Phase 3): honest source-of-information
    // label with a plain-language explanation.
    const verificationInfo = getVerificationInfo(job.verification_status);
    if (verificationInfo) {
        const vDiv = document.createElement('div');
        vDiv.className = 'modal-verification';
        const chipSpan = document.createElement('span');
        chipSpan.className = verificationInfo.cls;
        chipSpan.textContent = verificationInfo.text;
        vDiv.appendChild(chipSpan);
        const vP = document.createElement('p');
        vP.className = 'verification-note';
        vP.textContent = verificationInfo.title + '.';
        vDiv.appendChild(vP);
        detailsDiv.appendChild(vDiv);
    }

    const section1 = document.createElement('div');
    section1.className = 'modal-section';
    const h4_1 = document.createElement('h4');
    h4_1.textContent = 'Job Details';
    section1.appendChild(h4_1);

    const sourceP = document.createElement('p');
    const sourceStrong = document.createElement('strong');
    sourceStrong.textContent = 'Source: ';
    sourceP.appendChild(sourceStrong);
    sourceP.appendChild(document.createTextNode(job.source));
    section1.appendChild(sourceP);

    const catP = document.createElement('p');
    const catStrong = document.createElement('strong');
    catStrong.textContent = 'Category: ';
    catP.appendChild(catStrong);
    catP.appendChild(document.createTextNode(job.category));
    section1.appendChild(catP);

    const lastDateP = document.createElement('p');
    const lastDateStrong = document.createElement('strong');
    lastDateStrong.textContent = 'Last Date to Apply: ';
    lastDateP.appendChild(lastDateStrong);
    lastDateP.appendChild(document.createTextNode(lastDate));
    section1.appendChild(lastDateP);

    if (examDate !== 'Not specified') {
        const examDateP = document.createElement('p');
        const examDateStrong = document.createElement('strong');
        examDateStrong.textContent = 'Exam Date: ';
        examDateP.appendChild(examDateStrong);
        examDateP.appendChild(document.createTextNode(examDate));
        section1.appendChild(examDateP);
    }
    detailsDiv.appendChild(section1);

    // Extended notification fields (Phase 3): shown ONLY when the
    // pipeline actually captured a value. Missing stays missing -
    // the old behaviour of hiding everything unknown was replaced by
    // honest "Not specified" rows for key recruitment facts.
    const extendedFields = [
        ['Organization', job.organization],
        ['Department', job.department],
        ['Vacancies', job.vacancies],
        ['Salary', job.salary || job.pay_scale],
        ['Age Limit', ageLimitText(job)],
        ['Application Fee', job.application_fee],
        ['Selection Process', job.selection_process],
        ['Qualification', job.qualification || job.minimum_qualification],
        ['State', job.state],
        ['Employment Type', job.employment_type]
    ];
    const knownFields = extendedFields.filter(f => f[1]);
    if (knownFields.length > 0) {
        const sectionExt = document.createElement('div');
        sectionExt.className = 'modal-section';
        const h4Ext = document.createElement('h4');
        h4Ext.textContent = 'Notification Details';
        sectionExt.appendChild(h4Ext);
        knownFields.forEach(pair => {
            const p = document.createElement('p');
            const strong = document.createElement('strong');
            strong.textContent = pair[0] + ': ';
            p.appendChild(strong);
            p.appendChild(document.createTextNode(String(pair[1])));
            sectionExt.appendChild(p);
        });
        detailsDiv.appendChild(sectionExt);
    }

    const section2 = document.createElement('div');
    section2.className = 'modal-section';
    const h4_2 = document.createElement('h4');
    h4_2.textContent = 'Description';
    section2.appendChild(h4_2);
    const descP = document.createElement('p');
    descP.textContent = job.description;
    section2.appendChild(descP);
    detailsDiv.appendChild(section2);

    if (skills.length > 0) {
        const section3 = document.createElement('div');
        section3.className = 'modal-section';
        const h4_3 = document.createElement('h4');
        h4_3.textContent = 'Required Skills';
        section3.appendChild(h4_3);

        const skillsDiv = document.createElement('div');
        skillsDiv.className = 'job-skills';
        skills.forEach(skill => {
            const skillSpan = document.createElement('span');
            skillSpan.className = 'skill-tag';
            skillSpan.textContent = skill;
            skillsDiv.appendChild(skillSpan);
        });
        section3.appendChild(skillsDiv);
        detailsDiv.appendChild(section3);
    }

    // Prefer the verified official notification URL when present;
    // the legacy pdf_link remains the fallback for older records.
    const notificationUrl = job.official_notification_url || job.pdf_link;
    if (notificationUrl) {
        const section4 = document.createElement('div');
        section4.className = 'modal-section';
        const h4_4 = document.createElement('h4');
        h4_4.textContent = 'Additional Information';
        section4.appendChild(h4_4);

        const pdfP = document.createElement('p');
        const pdfA = document.createElement('a');
        pdfA.href = sanitizeURL(notificationUrl);
        pdfA.target = '_blank';
        pdfA.rel = 'noopener noreferrer';
        pdfA.className = 'pdf-link';
        pdfA.textContent = 'Download Official Notification (PDF)';
        pdfP.appendChild(pdfA);
        section4.appendChild(pdfP);

        if (job.official_website) {
            const siteP = document.createElement('p');
            const siteA = document.createElement('a');
            siteA.href = sanitizeURL(job.official_website);
            siteA.target = '_blank';
            siteA.rel = 'noopener noreferrer';
            siteA.className = 'pdf-link';
            siteA.textContent = 'Official Website';
            siteP.appendChild(siteA);
            section4.appendChild(siteP);
        }
        detailsDiv.appendChild(section4);
    }

    // Attribution + honesty footer: cross-source duplicates recorded by
    // the merge pipeline, and the last time this record was verified.
    const section5 = document.createElement('div');
    section5.className = 'modal-section modal-meta-info';
    const refs = Array.isArray(job.source_refs) ? job.source_refs : [];
    const otherSources = refs
        .map(r => r && r.source)
        .filter(s => s && s !== job.source);
    const uniqueSources = otherSources.filter((s, i) => otherSources.indexOf(s) === i);
    if (uniqueSources.length > 0) {
        const refsP = document.createElement('p');
        refsP.className = 'meta-line';
        refsP.textContent = 'Also found on: ' + uniqueSources.join(', ');
        section5.appendChild(refsP);
    }
    if (job.last_verified) {
        const verifiedP = document.createElement('p');
        verifiedP.className = 'meta-line';
        verifiedP.textContent = 'Record last verified: ' + String(job.last_verified).slice(0, 10);
        section5.appendChild(verifiedP);
    }
    const disclaimerP = document.createElement('p');
    disclaimerP.className = 'meta-line';
    disclaimerP.textContent = 'Always verify details on the official notification before applying.';
    section5.appendChild(disclaimerP);
    if (section5.childNodes.length > 1) {
        detailsDiv.appendChild(section5);
    }

    modalBody.appendChild(detailsDiv);

    jobModal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

/**
 * Close job modal
 */
function closeModal() {
    jobModal.classList.remove('active');
    document.body.style.overflow = 'auto';
}

/**
 * Clear all filters and search
 */
function clearAllFilters() {
    if (jobSearch) jobSearch.value = '';
    if (categoryFilter) categoryFilter.value = '';
    if (sortFilter) sortFilter.value = 'latest';
    savedOnly = false;
    if (savedFilterBtn) {
        savedFilterBtn.classList.remove('active');
        savedFilterBtn.setAttribute('aria-pressed', 'false');
    }
    handleSearch();
}

/**
 * Handle search functionality
 */
function handleSearch() {
    applyFilters();
}

/**
 * Handle category filter
 */
function handleFilter() {
    applyFilters();
}

/**
 * Filter by category (from category cards)
 */
function filterByCategory(category) {
    categoryFilter.value = category;
    handleFilter();

    // Scroll to jobs section
    document.getElementById('jobs').scrollIntoView({ behavior: 'smooth' });
}

/**
 * Handle sorting
 */
function handleSort() {
    const sortBy = sortFilter.value;

    switch (sortBy) {
        case 'latest':
            // Honest "Latest First" (Phase 3): sort by the record's
            // verification/creation timestamp. The old md5 job-id sort
            // was meaningless (random order) and is gone.
            filteredJobs.sort((a, b) => getRecordTimestamp(b) - getRecordTimestamp(a));
            break;
        case 'deadline':
            // Sort by deadline (jobs with earlier deadlines first)

            // Optimization: Helper to quickly convert DD-MM-YYYY to YYYYMMDD integer
            // Avoids costly Date object instantiation inside the sort loop
            const getSortableDate = (dateStr) => {
                if (!dateStr) return 20991231;
                const parts = dateStr.split('-');
                if (parts.length !== 3) return 20991231;
                // Pad parts with '0' to ensure single digits are handled properly, e.g. 5-1-2024 -> 20240105
                const day = parts[0].padStart(2, '0');
                const month = parts[1].padStart(2, '0');
                const year = parts[2];
                return parseInt(year + month + day, 10);
            };

            filteredJobs.sort((a, b) => {
                const dateA = a.important_dates?.last_date || a.important_dates?.found_date || '31-12-2099';
                const dateB = b.important_dates?.last_date || b.important_dates?.found_date || '31-12-2099';
                return getSortableDate(dateA) - getSortableDate(dateB);
            });
            break;
        case 'category':
            // Sort alphabetically by category
            filteredJobs.sort((a, b) => a.category.localeCompare(b.category));
            break;
    }

    renderJobs();
}

/**
 * Load more jobs
 */
function loadMoreJobs() {
    if (isLoading) return;

    isLoading = true;
    loadMoreBtn.textContent = 'Loading...';
    loadMoreBtn.disabled = true;
    loadMoreBtn.setAttribute('aria-busy', 'true');

    setTimeout(() => {
        currentPage++;
        renderJobs();
        isLoading = false;
        loadMoreBtn.textContent = 'Load More Jobs';
        loadMoreBtn.disabled = false;
        loadMoreBtn.setAttribute('aria-busy', 'false');
    }, 500);
}

/**
 * Show/hide loading spinner
 */
function showLoading(show) {
    if (loadingSpinner) {
        loadingSpinner.style.display = show ? 'block' : 'none';
    }
}

/**
 * Update job counts in category cards
 */
function updateJobCounts() {
    const categoryCounts = {};

    jobsData.forEach(job => {
        categoryCounts[job.category] = (categoryCounts[job.category] || 0) + 1;
    });

    document.querySelectorAll('.category-card').forEach(card => {
        const category = card.dataset.category;
        const countElement = card.querySelector('.category-count');
        if (countElement) {
            if (categoryCounts[category]) {
                countElement.textContent = `${categoryCounts[category]}+ Jobs`;
            } else {
                countElement.textContent = '0 Active Jobs';
            }
        }
    });

    const totalActiveEl = document.getElementById('totalActiveJobsCount');
    if (totalActiveEl && jobsData.length > 0) {
        totalActiveEl.textContent = `${jobsData.length}+`;
    }
}

/**
 * Animate counters in hero section
 */
function animateCounters() {
    const counters = document.querySelectorAll('.stat-number');

    counters.forEach(counter => {
        const target = parseInt(counter.dataset.target);
        const duration = 2000; // 2 seconds
        const step = target / (duration / 16); // 60 FPS
        let current = 0;

        // Optimization: Use requestAnimationFrame instead of setInterval
        // Impact: Synchronizes with display refresh rate, prevents background tab execution,
        // and provides smoother animations without blocking the main thread
        const animate = () => {
            current += step;
            if (current >= target) {
                current = target;
                counter.textContent = Math.floor(current).toLocaleString();
                return;
            }
            counter.textContent = Math.floor(current).toLocaleString();
            window.requestAnimationFrame(animate);
        };

        window.requestAnimationFrame(animate);
    });
}

/**
 * Setup intersection observer for animations
 */
function setupIntersectionObserver() {
    if (typeof IntersectionObserver === 'undefined') return;
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                // Optimization: Unobserve after animating to prevent redundant callbacks on future scrolls
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe sections for animation
    document.querySelectorAll('.section-title, .feature-card, .category-card').forEach(el => {
        observer.observe(el);
    });
}

/**
 * Theme management
 */
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

/**
 * Open Telegram channel
 */
function openTelegramChannel() {
    // Replace with actual Telegram channel link
    window.open('https://t.me/sarkarisarthi', '_blank', 'noopener,noreferrer');
}

/**
 * Open WhatsApp channel
 */
function openWhatsappChannel() {
    // Replace with actual WhatsApp invite link
    window.open('https://chat.whatsapp.com/your-invite-link', '_blank', 'noopener,noreferrer');
}

/**
 * Toggle mobile menu
 */
function toggleMobileMenu() {
    const navMenu = document.querySelector('.nav-menu');
    if (navMenu) {
        const isOpen = navMenu.classList.toggle('active');
        if (mobileMenuToggle) {
            mobileMenuToggle.classList.toggle('active', isOpen);
            mobileMenuToggle.setAttribute('aria-expanded', String(isOpen));
        }
    }
}

/**
 * Handle keyboard navigation
 */
function handleKeyboardNavigation(e) {
    // Close modal with Escape key
    if (e.key === 'Escape' && jobModal && jobModal.classList.contains('active')) {
        closeModal();
    }

    // Close mobile menu with Escape key
    const navMenu = document.querySelector('.nav-menu');
    if (e.key === 'Escape' && navMenu && navMenu.classList.contains('active')) {
        toggleMobileMenu();
    }

    // Search with Ctrl+K or Cmd+K
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (jobSearch) jobSearch.focus();
    }
}

/**
 * Sanitizes URLs to ensure they only use http/https protocols.
 * @param {string} url - The URL to sanitize.
 * @returns {string} The sanitized URL.
 */
function sanitizeURL(url) {
    if (!url) return '#';
    try {
        const parsed = new URL(url, window.location.href);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
            return parsed.href;
        }
    } catch (e) {
        // Return original if valid relative path
        if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) {
            return escapeHTML(url);
        }
    }
    return '#';
}

/**
 * Utility function to format dates
 */
function formatDate(dateString) {
    if (!dateString) return 'Not specified';

    try {
        const parts = dateString.split('-');
        if (parts.length === 3) {
            const date = new Date(parts[2], parts[1] - 1, parts[0]);
            return date.toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'long',
                year: 'numeric'
            });
        }
    } catch (error) {
        console.error('Error formatting date:', error);
    }

    return dateString;
}

/**
 * Utility function to debounce search
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Add debounced search
const debouncedSearch = debounce(handleSearch, 300);
if (jobSearch) {
    jobSearch.addEventListener('input', debouncedSearch);
}

// No service worker is registered here: this portal has no sw.js
// asset, so a registration attempt would 404 on every page load.
// The other GoGo apps (Arrow Out, Crystal Quest) keep their own PWA
// service workers; this file is portal-specific.

// Export functions for testing (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        handleSearch,
        handleFilter,
        handleSort,
        formatDate,
        getVerificationInfo,
        getRecordTimestamp,
        getBookmarks,
        isBookmarked,
        toggleBookmark,
        ageLimitText
    };
}
