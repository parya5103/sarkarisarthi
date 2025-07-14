document.addEventListener('DOMContentLoaded', () => {
    const jobListingsContainer = document.getElementById('jobListings');
    const searchJobInput = document.getElementById('searchJob');
    const stateFilterSelect = document.getElementById('stateFilter');
    const departmentFilterSelect = document.getElementById('departmentFilter');
    const darkModeToggle = document.getElementById('darkModeToggle');
    const resetFiltersButton = document.getElementById('resetFilters');

    let allJobs = [];
    const jobFileNames = [
        "government-jobs.json",
        "defence-jobs.json",
        "railway-jobs.json",
        "teaching-jobs.json",
        // Add more JSON file names here as you create them
        // Example for more: "engineering-jobs.json", "medical-jobs.json"
    ];
    const jobsFolderPath = './jobs/'; // Assuming 'jobs' folder is in the same directory as index.html

    // --- Dark Mode Functionality ---
    const enableDarkMode = () => {
        document.body.classList.add('dark-mode');
        localStorage.setItem('darkMode', 'enabled');
        darkModeToggle.textContent = '☀️'; // Sun icon for light mode
    };

    const disableDarkMode = () => {
        document.body.classList.remove('dark-mode');
        localStorage.setItem('darkMode', 'disabled');
        darkModeToggle.textContent = '🌙'; // Moon icon for dark mode
    };

    // Check for saved dark mode preference
    if (localStorage.getItem('darkMode') === 'enabled') {
        enableDarkMode();
    } else {
        disableDarkMode();
    }

    darkModeToggle.addEventListener('click', () => {
        if (document.body.classList.contains('dark-mode')) {
            disableDarkMode();
        } else {
            enableDarkMode();
        }
    });

    // --- Fetching Job Data ---
    async function fetchJobs() {
        jobListingsContainer.innerHTML = '<p class="loading-message">Loading jobs...</p>';
        try {
            const fetchPromises = jobFileNames.map(fileName =>
                fetch(`${jobsFolderPath}${fileName}`)
                    .then(response => {
                        if (!response.ok) {
                            console.warn(`Could not load ${fileName}: ${response.statusText}`);
                            return []; // Return empty array if file not found or error
                        }
                        return response.json();
                    })
                    .catch(error => {
                        console.error(`Error fetching ${fileName}:`, error);
                        return []; // Return empty array on fetch error
                    })
            );

            const results = await Promise.all(fetchPromises);
            allJobs = results.flat(); // Flatten the array of arrays into a single array
            allJobs = allJobs.filter(job => job && job.title && job.department && job.state && job.last_date && job.apply_link); // Basic validation

            populateFilters();
            displayJobs(allJobs);

        } catch (error) {
            jobListingsContainer.innerHTML = '<p class="no-jobs-message">Failed to load jobs. Please try again later.</p>';
            console.error("Error fetching all jobs:", error);
        }
    }

    // --- Populate Filters ---
    function populateFilters() {
        const states = new Set();
        const departments = new Set();

        allJobs.forEach(job => {
            if (job.state) states.add(job.state);
            if (job.department) departments.add(job.department);
        });

        // Clear existing options except "All"
        stateFilterSelect.innerHTML = '<option value="">All States</option>';
        departmentFilterSelect.innerHTML = '<option value="">All Departments</option>';

        Array.from(states).sort().forEach(state => {
            const option = document.createElement('option');
            option.value = state;
            option.textContent = state;
            stateFilterSelect.appendChild(option);
        });

        Array.from(departments).sort().forEach(department => {
            const option = document.createElement('option');
            option.value = department;
            option.textContent = department;
            departmentFilterSelect.appendChild(option);
        });
    }

    // --- Display Jobs ---
    function displayJobs(jobsToDisplay) {
        jobListingsContainer.innerHTML = ''; // Clear previous listings

        if (jobsToDisplay.length === 0) {
            jobListingsContainer.innerHTML = '<p class="no-jobs-message">No jobs found matching your criteria.</p>';
            return;
        }

        jobsToDisplay.forEach(job => {
            const jobCard = document.createElement('div');
            jobCard.classList.add('job-card');

            jobCard.innerHTML = `
                <h3>${job.title}</h3>
                <p><strong>Department:</strong> ${job.department}</p>
                <p><strong>State:</strong> ${job.state}</p>
                <p><strong>Last Date:</strong> ${job.last_date}</p>
                <div class="job-links">
                    <a href="${job.apply_link}" target="_blank" rel="noopener noreferrer">Apply Now</a>
                    ${job.pdf_link ? `<a href="${job.pdf_link}" target="_blank" rel="noopener noreferrer" class="pdf-link">Download PDF</a>` : ''}
                </div>
            `;
            jobListingsContainer.appendChild(jobCard);
        });
    }

    // --- Filtering Logic ---
    function applyFilters() {
        const searchTerm = searchJobInput.value.toLowerCase();
        const selectedState = stateFilterSelect.value;
        const selectedDepartment = departmentFilterSelect.value;

        const filteredJobs = allJobs.filter(job => {
            const matchesSearch = job.title.toLowerCase().includes(searchTerm);
            const matchesState = selectedState === "" || job.state === selectedState;
            const matchesDepartment = selectedDepartment === "" || job.department === selectedDepartment;

            return matchesSearch && matchesState && matchesDepartment;
        });

        displayJobs(filteredJobs);
    }

    // --- Event Listeners ---
    searchJobInput.addEventListener('input', applyFilters);
    stateFilterSelect.addEventListener('change', applyFilters);
    departmentFilterSelect.addEventListener('change', applyFilters);
    resetFiltersButton.addEventListener('click', () => {
        searchJobInput.value = '';
        stateFilterSelect.value = '';
        departmentFilterSelect.value = '';
        applyFilters(); // Re-apply filters to show all jobs
    });

    // Initial fetch and display of jobs
    fetchJobs();
});
