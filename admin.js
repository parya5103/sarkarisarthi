// Simple admin authentication (not highly secure, just a deterrence)
const ADMIN_PASSWORD_HASH = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918";

async function hashPassword(password) {
    const encoder = new TextEncoder();
    const data = encoder.encode(password);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// Global state
let ghToken = sessionStorage.getItem('ghToken') || '';
let ghRepo = sessionStorage.getItem('ghRepo') || '';
let currentJobs = [];
let manifestSha = '';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Security: Clean up old credentials from localStorage
    localStorage.removeItem('ghToken');
    localStorage.removeItem('ghRepo');

    // Check if already logged in this session
    if (sessionStorage.getItem('adminLoggedIn') === 'true') {
        showDashboard();
    }

    // Load saved settings
    if (ghToken) document.getElementById('ghToken').value = ghToken;
    if (ghRepo) document.getElementById('ghRepo').value = ghRepo;

    // Fetch jobs if credentials exist
    if (ghToken && ghRepo) {
        fetchJobsFromRepo();
    }
});

async function checkPassword() {
    const input = document.getElementById('adminPassword').value;
    const hashedInput = await hashPassword(input);
    if (hashedInput === ADMIN_PASSWORD_HASH) {
        sessionStorage.setItem('adminLoggedIn', 'true');
        showDashboard();
    } else {
        document.getElementById('loginError').style.display = 'block';
    }
}

function showDashboard() {
    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('adminContainer').style.display = 'block';
}

function logout() {
    sessionStorage.removeItem('adminLoggedIn');
    document.getElementById('loginOverlay').style.display = 'flex';
    document.getElementById('adminContainer').style.display = 'none';
    document.getElementById('adminPassword').value = '';
    document.getElementById('loginError').style.display = 'none';
}

function saveSettings() {
    ghToken = document.getElementById('ghToken').value.trim();
    ghRepo = document.getElementById('ghRepo').value.trim();

    if (ghToken && ghRepo) {
        sessionStorage.setItem('ghToken', ghToken);
        sessionStorage.setItem('ghRepo', ghRepo);

        const status = document.getElementById('settingsStatus');
        status.textContent = 'Settings saved!';
        setTimeout(() => status.textContent = '', 3000);

        fetchJobsFromRepo();
    } else {
        alert('Please provide both Token and Repository details.');
    }
}

async function triggerScraper() {
    if (!ghToken || !ghRepo) {
        alert('Please configure GitHub API Settings first.');
        return;
    }

    if (!confirm('Are you sure you want to trigger the GitHub Actions job scraper manually?')) return;

    try {
        const response = await fetch(`https://api.github.com/repos/${ghRepo}/actions/workflows/daily-job-fetch-deploy.yml/dispatches`, {
            method: 'POST',
            headers: {
                'Authorization': `token ${ghToken}`,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                ref: 'main'
            })
        });

        if (response.ok || response.status === 204) {
            alert('Scraper triggered successfully! It may take a few minutes to complete and deploy.');
        } else {
            const data = await response.json();
            alert(`Failed to trigger scraper: ${data.message || response.statusText}`);
        }
    } catch (error) {
        console.error('Error triggering scraper:', error);
        alert('An error occurred while triggering the scraper.');
    }
}

async function fetchJobsFromRepo() {
    if (!ghToken || !ghRepo) return;

    const tbody = document.getElementById('jobsTableBody');
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Fetching data from GitHub...</td></tr>';

    try {
        const response = await fetch(`https://api.github.com/repos/${ghRepo}/contents/jobs/job_manifest.json`, {
            headers: {
                'Authorization': `token ${ghToken}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch manifest: ${response.statusText}`);
        }

        const fileData = await response.json();
        manifestSha = fileData.sha;

        // Decode base64 content
        const binString = window.atob(fileData.content);
        const bytes = Uint8Array.from(binString, (m) => m.charCodeAt(0));
        const contentStr = new TextDecoder().decode(bytes);
        const manifest = JSON.parse(contentStr);
        currentJobs = manifest.jobs || [];

        document.getElementById('jobCount').textContent = manifest.total_jobs || currentJobs.length;
        renderJobsTable();

    } catch (error) {
        console.error('Error fetching jobs:', error);
        tbody.innerHTML = '';
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 5;
        td.style.textAlign = 'center';
        td.style.color = '#ef4444';
        td.textContent = `Error fetching data: ${error.message}`;
        tr.appendChild(td);
        tbody.appendChild(tr);
    }
}

function renderJobsTable() {
    const tbody = document.getElementById('jobsTableBody');
    tbody.innerHTML = '';

    if (currentJobs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">No jobs found.</td></tr>';
        return;
    }

    // Optimization: Batch DOM insertions using DocumentFragment to prevent layout thrashing
    // Reduces render time by avoiding multiple reflows/repaints inside the loop
    const fragment = document.createDocumentFragment();
    currentJobs.forEach(job => {
        const tr = document.createElement('tr');

        const tdTitle = document.createElement('td');
        const strongTitle = document.createElement('strong');
        strongTitle.textContent = job.title;
        tdTitle.appendChild(strongTitle);
        tr.appendChild(tdTitle);

        const tdDept = document.createElement('td');
        tdDept.textContent = job.department || 'N/A';
        tr.appendChild(tdDept);

        const tdCategory = document.createElement('td');
        const spanCategory = document.createElement('span');
        spanCategory.className = 'category-tag';
        spanCategory.textContent = job.category || 'Other';
        tdCategory.appendChild(spanCategory);
        tr.appendChild(tdCategory);

        const tdDate = document.createElement('td');
        tdDate.textContent = job.last_date || (job.important_dates && job.important_dates.last_date) || 'Not specified';
        tr.appendChild(tdDate);

        const tdActions = document.createElement('td');
        tdActions.className = 'action-buttons';

        const editBtn = document.createElement('button');
        editBtn.className = 'primary-btn';
        editBtn.style.padding = '0.3rem 0.6rem';
        editBtn.style.minWidth = '0';
        editBtn.textContent = 'Edit';
        editBtn.onclick = () => editJob(job.id);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'primary-btn btn-danger';
        deleteBtn.style.padding = '0.3rem 0.6rem';
        deleteBtn.style.minWidth = '0';
        deleteBtn.textContent = 'Delete';
        deleteBtn.onclick = () => deleteJob(job.id);

        tdActions.appendChild(editBtn);
        tdActions.appendChild(deleteBtn);
        tr.appendChild(tdActions);

        fragment.appendChild(tr);
    });
    tbody.appendChild(fragment);
}

// Security: job IDs become file names in the fetch pipeline
// (jobs/<id>.json). Only [A-Za-z0-9_-]{1,80} is ever safe.
function isValidJobId(id) {
    return /^[A-Za-z0-9_-]{1,80}$/.test(id);
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g,
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

// Store dates in the portal house format (DD-MM-YYYY). Accepts a
// YYYY-MM-DD value from the form and converts it; any other text is
// kept as typed so free-text values are never corrupted.
function normalizeHouseDate(raw) {
    const v = (raw || '').trim();
    const m = v.match(/^([0-9]{4})-([0-9]{2})-([0-9]{2})$/);
    if (m) return m[3] + '-' + m[2] + '-' + m[1];
    return v || null;
}

function generateHash() {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

function openAddJobModal() {
    document.getElementById('modalTitle').textContent = 'Add Manual Job';
    document.getElementById('jobId').value = '';
    document.getElementById('jobTitle').value = '';
    document.getElementById('jobDepartment').value = '';
    document.getElementById('jobOrganization').value = '';
    document.getElementById('jobAdvtNo').value = '';
    document.getElementById('jobVacancies').value = '';
    document.getElementById('jobQualification').value = '';
    document.getElementById('jobStartDate').value = '';
    document.getElementById('jobNotificationUrl').value = '';
    document.getElementById('jobApplyUrl').value = '';
    document.getElementById('jobStatus').value = 'active';
    document.getElementById('jobCategory').value = 'Other Govt Jobs';
    document.getElementById('jobLastDate').value = '';
    document.getElementById('jobUrl').value = '';
    document.getElementById('jobSummary').value = '';

    document.getElementById('jobModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('jobModal').style.display = 'none';
}

function editJob(jobId) {
    const job = currentJobs.find(j => j.id === jobId);
    if (!job) return;

    document.getElementById('modalTitle').textContent = 'Edit Job';
    document.getElementById('jobId').value = job.id;
    document.getElementById('jobTitle').value = job.title || '';
    document.getElementById('jobDepartment').value = job.department || '';
    document.getElementById('jobOrganization').value = job.organization || '';
    document.getElementById('jobAdvtNo').value = job.advertisement_no || '';
    document.getElementById('jobVacancies').value = job.vacancies || '';
    document.getElementById('jobQualification').value = job.qualification || '';
    document.getElementById('jobStartDate').value = (job.important_dates && job.important_dates.application_start_date) || job.application_start_date || '';
    document.getElementById('jobNotificationUrl').value = job.official_notification_url || '';
    document.getElementById('jobApplyUrl').value = job.official_application_url || '';
    document.getElementById('jobStatus').value = job.status || 'active';
    document.getElementById('jobCategory').value = job.category || 'Other Govt Jobs';
    document.getElementById('jobLastDate').value = job.last_date || (job.important_dates && job.important_dates.last_date) || '';
    document.getElementById('jobUrl').value = job.url || '';
    document.getElementById('jobSummary').value = job.summary || job.description || '';

    document.getElementById('jobModal').style.display = 'flex';
}

async function deleteJob(jobId) {
    if (!confirm('Are you sure you want to delete this job? This will remove it from the manifest.')) return;

    // Filter out the job
    const originalLength = currentJobs.length;
    currentJobs = currentJobs.filter(j => j.id !== jobId);

    if (currentJobs.length === originalLength) {
        alert('Job not found!');
        return;
    }

    await updateManifestOnGithub('Admin: Deleted job ' + jobId);
}

async function saveJobData() {
    const rawId = document.getElementById('jobId').value;
    if (rawId && !isValidJobId(rawId)) {
        alert('Invalid job ID. Use 1-80 characters: letters, numbers, hyphens and underscores only.');
        return;
    }
    const id = document.getElementById('jobId').value || `manual_${generateHash()}`;

    // Manual import (Phase 3): optional fields are stored as null when
    // left blank, never as invented values. null means 'not specified in
    // the official notification'.
    const val = (elemId) => (document.getElementById(elemId).value || '').trim() || null;
    const newJobData = {
        id: id,
        title: document.getElementById('jobTitle').value.trim(),
        department: document.getElementById('jobDepartment').value.trim(),
        organization: val('jobOrganization'),
        advertisement_no: val('jobAdvtNo'),
        vacancies: val('jobVacancies'),
        qualification: val('jobQualification'),
        official_notification_url: val('jobNotificationUrl'),
        official_application_url: val('jobApplyUrl'),
        application_start_date: normalizeHouseDate(document.getElementById('jobStartDate').value),
        status: val('jobStatus') || 'active',
        category: document.getElementById('jobCategory').value,
        last_date: normalizeHouseDate(document.getElementById('jobLastDate').value),
        url: document.getElementById('jobUrl').value.trim(),
        summary: document.getElementById('jobSummary').value.trim(),
        found_date: new Date().toISOString()
    };

    if (!newJobData.title || !newJobData.department) {
        alert('Title and Department are required.');
        return;
    }

    // Check if editing or adding
    const existingIndex = currentJobs.findIndex(j => j.id === id);
    if (existingIndex >= 0) {
        // Keep original found_date if it exists
        const existing = currentJobs[existingIndex];
        newJobData.found_date = existing.found_date || newJobData.found_date;
        const merged = { ...existing, ...newJobData };
        // Scraped jobs keep dates inside important_dates. Mirror the flat
        // admin field into the nested structure so the public listing
        // (which reads important_dates.last_date) stays in sync.
        if (existing.important_dates) {
            merged.important_dates = { ...existing.important_dates };
            if (newJobData.last_date) {
                merged.important_dates.last_date = newJobData.last_date;
            }
            if (newJobData.application_start_date) {
                merged.important_dates.application_start_date = newJobData.application_start_date;
            }
        }
        if (existing.description && newJobData.summary) {
            merged.description = newJobData.summary;
        }
        merged.last_verified = new Date().toISOString();
        currentJobs[existingIndex] = merged;
    } else {
        newJobData.last_verified = new Date().toISOString();
        currentJobs.unshift(newJobData); // Add to top
    }

    closeModal();
    await updateManifestOnGithub(`Admin: ${existingIndex >= 0 ? 'Updated' : 'Added manual'} job ${id}`);
}

async function updateManifestOnGithub(commitMessage) {
    if (!ghToken || !ghRepo || !manifestSha) {
        alert('Missing GitHub credentials or manifest data. Please refresh.');
        return;
    }

    const manifestData = {
        last_updated: new Date().toISOString(),
        total_jobs: currentJobs.length,
        active_jobs: currentJobs.length,
        expired_jobs: 0,
        jobs: currentJobs
    };

    // Convert string to base64 encoding (supporting Unicode)
    const contentStr = JSON.stringify(manifestData, null, 2);
    const bytes = new TextEncoder().encode(contentStr);
    const binString = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
    const contentBase64 = window.btoa(binString);

    try {
        // Update manifest
        const manifestResponse = await fetch(`https://api.github.com/repos/${ghRepo}/contents/jobs/job_manifest.json`, {
            method: 'PUT',
            headers: {
                'Authorization': `token ${ghToken}`,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: commitMessage,
                content: contentBase64,
                sha: manifestSha,
                branch: 'main'
            })
        });

        if (!manifestResponse.ok) {
            throw new Error(`Failed to update manifest: ${manifestResponse.statusText}`);
        }

        const newManifestData = await manifestResponse.json();
        manifestSha = newManifestData.content.sha; // Update SHA for subsequent edits

        document.getElementById('jobCount').textContent = currentJobs.length;
        renderJobsTable();
        alert('Successfully updated jobs on GitHub!');

    } catch (error) {
        console.error('Error updating GitHub:', error);
        alert(`Error updating data: ${error.message}`);
    }
}
