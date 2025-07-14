// Load JSON files from jobs/ folder
const jobFiles = [
    'government-jobs.json',
    'defence-jobs.json',
    'railway-jobs.json',
    'teaching-jobs.json',
    // Add more files as needed
];

const jobListings = document.getElementById('job-listings');
const searchBar = document.getElementById('search-bar');
const stateFilter = document.getElementById('state-filter');
const departmentFilter = document.getElementById('department-filter');

let jobs = [];
let states = new Set();
let departments = new Set();

// Load jobs from JSON files
Promise.all(jobFiles.map(file => fetch(`jobs/${file}`).then(response => response.json())))
    .then(data => {
        data.forEach(json => {
            json.forEach(job => {
                jobs.push(job);
                states.add(job.state);
                departments.add(job.department);
            });
        });
        // Populate filters
        Array.from(states).sort().forEach(state => {
            const option = document.createElement('option');
            option.value = state;
            option.textContent = state;
            stateFilter.appendChild(option);
        });
        Array.from(departments).sort().forEach(department => {
            const option = document.createElement('option');
            option.value = department;
            option.textContent = department;
            departmentFilter.appendChild(option);
        });
        // Render job listings
        renderJobs();
    })
    .catch(error => console.error('Error loading jobs:', error));

// Render job listings based on filters
function renderJobs() {
    const filteredJobs = jobs.filter(job => {
        const searchQuery = searchBar.value.toLowerCase();
        const state = stateFilter.value;
        const department = departmentFilter.value;
        return (searchQuery === '' || job.title.toLowerCase().includes(searchQuery)) &&
               (state === '' || job.state === state) &&
               (department === '' || job.department === department);
    }).sort((a, b) => new Date(b.last_date) - new Date(a.last_date));
    jobListings.innerHTML = '';
    filteredJobs.forEach(job => {
        const listing = document.createElement('li');
        listing.innerHTML = `
            <h2>${job.title}</h2>
            <p>Department: ${job.department}</p>
            <p>State: ${job.state}</p>
            <p>Last Date: ${job.last_date}</p>
            <p><a href="${job.apply_link}">Apply Now</a></p>
            ${job.pdf_link ? `<p><a href="${job.pdf_link}">Download PDF</a></p>` : ''}
        `;
        jobListings.appendChild(listing);
    });
}

// Update job listings on filter change
searchBar.addEventListener('input', renderJobs);
stateFilter.addEventListener('change', renderJobs);
departmentFilter.addEventListener('change', renderJobs);

// Auto-refresh every 12 hours
setInterval(() => {
    window.location.reload();
}, 12 * 60 * 60 * 1000);
