// Static GitHub Pages cannot provide server-side authentication.
// GitHub's own token and repository permissions authorize all writes.
const ADMIN_REPOSITORY = 'parya5103/sarkarisarthi';

let ghToken = '';
let ghRepo = ADMIN_REPOSITORY;
let currentJobs = [];
let currentManifest = null;
let manifestSha = '';

function isAllowedAdminRepository(repository) {
    return typeof repository === 'string'
        && repository.trim().toLowerCase() === ADMIN_REPOSITORY;
}

function githubHeaders(json = false) {
    const headers = {
        'Authorization': `Bearer ${ghToken}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    };
    if (json) headers['Content-Type'] = 'application/json';
    return headers;
}

async function validateGitHubAccess(token, repository) {
    if (!token || !isAllowedAdminRepository(repository)) {
        throw new Error('Use a GitHub token for the configured Sarkari Sarthi repository.');
    }
    const headers = {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    };
    const userResponse = await fetch('https://api.github.com/user', { headers });
    if (!userResponse.ok) throw new Error('GitHub token is invalid or expired.');
    const repoResponse = await fetch(`https://api.github.com/repos/${ADMIN_REPOSITORY}`, { headers });
    if (!repoResponse.ok) throw new Error('Token cannot access the Sarkari Sarthi repository.');
    const repoData = await repoResponse.json();
    if (repoData.permissions?.push !== true && repoData.permissions?.admin !== true) {
        throw new Error('Token needs repository Contents: Read and write permission.');
    }
    return true;
}

// Initialize without pretending a client-side password is real authentication.
document.addEventListener('DOMContentLoaded', () => {
    // Remove credentials saved by older dashboard versions.
    sessionStorage.removeItem('ghToken');
    sessionStorage.removeItem('ghRepo');
    sessionStorage.removeItem('adminLoggedIn');
    localStorage.removeItem('ghToken');
    localStorage.removeItem('ghRepo');

    const repoInput = document.getElementById('ghRepo');
    if (repoInput) repoInput.value = ADMIN_REPOSITORY;
    showDashboard();
});

function showDashboard() {
    document.getElementById('adminContainer').style.display = 'block';
}

function logout() {
    ghToken = '';
    ghRepo = ADMIN_REPOSITORY;
    currentJobs = [];
    currentManifest = null;
    manifestSha = '';
    const tokenInput = document.getElementById('ghToken');
    if (tokenInput) tokenInput.value = '';
    const repoInput = document.getElementById('ghRepo');
    if (repoInput) repoInput.value = ADMIN_REPOSITORY;
    const status = document.getElementById('settingsStatus');
    if (status) status.textContent = 'GitHub token cleared from memory. Reconnect to edit.';
    const count = document.getElementById('jobCount');
    if (count) count.textContent = '—';
    renderJobsTable();
}

async function saveSettings() {
    const tokenInput = document.getElementById('ghToken');
    const status = document.getElementById('settingsStatus');
    const candidateToken = tokenInput.value.trim();
    const candidateRepo = document.getElementById('ghRepo').value.trim();

    if (!candidateToken) {
        status.textContent = 'Enter a GitHub fine-grained token.';
        return;
    }
    if (!isAllowedAdminRepository(candidateRepo)) {
        status.textContent = 'Only parya5103/sarkarisarthi is allowed.';
        return;
    }

    status.textContent = 'Validating GitHub permissions…';
    try {
        await validateGitHubAccess(candidateToken, candidateRepo);
        ghToken = candidateToken;
        ghRepo = ADMIN_REPOSITORY;
        tokenInput.value = '';
        status.textContent = 'Connected. Token is held in memory only.';
        await fetchJobsFromRepo();
    } catch (error) {
        ghToken = '';
        tokenInput.value = '';
        status.textContent = error.message;
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
                'Authorization': `Bearer ${ghToken}`,
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
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
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28'
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
        currentManifest = manifest;
        currentJobs = Array.isArray(manifest.jobs) ? manifest.jobs : [];

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
        // Editing fields is not an independent source re-verification.
        // Keep the prior last_verified timestamp and downgrade the record
        // to review until its employer evidence is checked again.
        merged.verification_status = 'needs_review';
        currentJobs[existingIndex] = merged;
    } else {
        newJobData.source = 'manual_admin';
        newJobData.source_refs = [];
        newJobData.verification_status = 'needs_review';
        newJobData.last_verified = null;
        newJobData.published_date = null;
        newJobData.date_posted_verified = false;
        newJobData.description_complete = false;
        newJobData.description = newJobData.summary || '';
        newJobData.important_dates = {
            found_date: newJobData.found_date,
            application_start_date: newJobData.application_start_date,
            last_date: newJobData.last_date
        };
        currentJobs.unshift(newJobData); // New manual records remain hidden until reviewed
    }

    closeModal();
    await updateManifestOnGithub(`Admin: ${existingIndex >= 0 ? 'Updated' : 'Added manual'} job ${id}`);
}

async function updateManifestOnGithub(commitMessage) {
    if (!ghToken || !isAllowedAdminRepository(ghRepo) || !manifestSha || !currentManifest) {
        alert('Missing GitHub access or manifest data. Reconnect and refresh before editing.');
        return;
    }

    try {
        // Refuse to overwrite a manifest changed by the nightly pipeline or
        // another admin session since this dashboard loaded it.
        const latestResponse = await fetch(`https://api.github.com/repos/${ADMIN_REPOSITORY}/contents/jobs/job_manifest.json`, {
            headers: githubHeaders()
        });
        if (!latestResponse.ok) throw new Error('Could not re-check the latest manifest.');
        const latestFile = await latestResponse.json();
        if (latestFile.sha !== manifestSha) {
            throw new Error('The manifest changed elsewhere. Reload the dashboard before saving to avoid overwriting newer jobs.');
        }

        const counts = currentJobs.reduce((acc, job) => {
            const state = String(job.status || '').toLowerCase();
            if (state === 'expired') acc.expired_jobs += 1;
            else if (state === 'active' || state === 'upcoming') acc.active_jobs += 1;
            return acc;
        }, { active_jobs: 0, expired_jobs: 0 });

        const manifestData = {
            ...currentManifest,
            last_updated: new Date().toISOString(),
            total_jobs: currentJobs.length,
            active_jobs: counts.active_jobs,
            expired_jobs: counts.expired_jobs,
            jobs: currentJobs
        };

        const encodeBase64 = (value) => {
            const bytes = new TextEncoder().encode(value);
            const binary = Array.from(bytes, byte => String.fromCharCode(byte)).join('');
            return window.btoa(binary);
        };

        // A backup must be committed successfully before the live manifest.
        const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '');
        const backupPath = `jobs/backup/manifest_backup_admin_${stamp}.json`;
        const backupResponse = await fetch(`https://api.github.com/repos/${ADMIN_REPOSITORY}/contents/${backupPath}`, {
            method: 'PUT',
            headers: githubHeaders(true),
            body: JSON.stringify({
                message: `Backup manifest before admin change: ${commitMessage}`,
                content: encodeBase64(JSON.stringify(currentManifest, null, 2)),
                branch: 'main'
            })
        });
        if (!backupResponse.ok) {
            throw new Error('Manifest backup failed; no changes were applied.');
        }

        const manifestResponse = await fetch(`https://api.github.com/repos/${ADMIN_REPOSITORY}/contents/jobs/job_manifest.json`, {
            method: 'PUT',
            headers: githubHeaders(true),
            body: JSON.stringify({
                message: commitMessage,
                content: encodeBase64(JSON.stringify(manifestData, null, 2)),
                sha: manifestSha,
                branch: 'main'
            })
        });

        if (!manifestResponse.ok) {
            throw new Error(`Failed to update manifest: ${manifestResponse.statusText}. The backup was retained.`);
        }

        const updatedFile = await manifestResponse.json();
        manifestSha = updatedFile.content.sha;
        currentManifest = manifestData;
        document.getElementById('jobCount').textContent = currentJobs.length;
        renderJobsTable();
        alert('Successfully updated jobs on GitHub. A pre-change backup was also saved.');
    } catch (error) {
        console.error('Error updating GitHub:', error);
        alert(`Error updating data: ${error.message}`);
    }
}
