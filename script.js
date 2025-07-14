document.addEventListener('DOMContentLoaded', () => {
    const jobListingsContainer = document.getElementById('jobListings');
    const searchJobInput = document.getElementById('searchJob');
    // const stateFilterSelect = document.getElementById('stateFilter'); // REMOVED: Since it's removed from HTML
    const departmentFilterSelect = document.getElementById('departmentFilter'); // Now maps to category
    const darkModeToggle = document.getElementById('darkModeToggle');
    const resetFiltersButton = document.getElementById('resetFilters');

    let allJobs = []; // This will hold all parsed job data
    const jobsFolderPath = './jobs/';
    const manifestFileName = 'job_manifest.json'; // The file listing all job JSONs

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

    // Add event listener for dark mode toggle, checking if it exists
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', () => {
            if (document.body.classList.contains('dark-mode')) {
                disableDarkMode();
            } else {
                enableDarkMode();
            }
        });
    } else {
        console.error("Error: Dark mode toggle button not found in HTML.");
    }


    // --- Fetching Job Data ---
    async function fetchJobs() {
        jobListingsContainer.innerHTML = '<p class="loading-message">Loading jobs...</p>';
        try {
            // 1. Fetch the manifest file first
            const manifestResponse = await fetch(`${jobsFolderPath}${manifestFileName}`);
            if (!manifestResponse.ok) {
                throw new Error(`Failed to load manifest file: ${manifestResponse.status} ${manifestResponse.statusText}`);
            }
            const jobFileNames = await manifestResponse.json();
            console.log(`Manifest loaded, found ${jobFileNames.length} job files.`);

            const fetchPromises = jobFileNames.map(async fileName => {
                try {
                    const response = await fetch(`${jobsFolderPath}${fileName}`);
                    if (!response.ok) {
                        console.warn(`Could not load ${fileName}: ${response.status} ${response.statusText}`);
                        return []; // Return empty array if file not found or error
                    }
                    const data = await response.json();
                    // Ensure the fetched data is an array. If it's a single object, wrap it.
                    if (!Array.isArray(data)) {
                        console.warn(`File ${fileName} did not return an array. Wrapping in an array.`);
                        return [data]; // Wrap single object in an array
                    }
                    return data;
                } catch (error) {
                    console.error(`Error fetching or parsing ${fileName}:`, error);
                    return []; // Return empty array on fetch/parse error
                }
            });

            const results = await Promise.allSettled(fetchPromises); // Use Promise.allSettled to handle individual file failures
            allJobs = [];
            results.forEach(result => {
                if (result.status === 'fulfilled' && Array.isArray(result.value)) {
                    // *** MODIFIED VALIDATION LOGIC HERE ***
                    const validJobsInFile = result.value.filter(job =>
                        job && job.title && job.apply_link
                    ).map(job => ({
                        title: job.title,
                        department: job.category || 'N/A', // Use 'category' as 'department', default to 'N/A'
                        state: job.state || 'N/A', // Default to 'N/A' if state is missing
                        last_date: job.last_date || 'Not Specified', // Default if last_date is missing or null
                        apply_link: job.apply_link,
                        pdf_link: job.pdf_link || null // Keep pdf_link optional
                    }));
                    allJobs.push(...validJobsInFile);
                } else if (result.status === 'rejected') {
                    console.error("Promise rejected during job file fetch:", result.reason);
                }
            });

            console.log(`Total jobs loaded and validated: ${allJobs.length}`); // THIS WILL NOW SHOW > 0

            populateFilters();
            displayJobs(allJobs);

        } catch (error) {
            jobListingsContainer.innerHTML = '<p class="no-jobs-message">Failed to load jobs. Please try again later. Check console for details.</p>';
            console.error("Error fetching all jobs:", error);
        }
    }

    // --- Populate Filters ---
    function populateFilters() {
        const states = new Set();
        const departments = new Set(); // This will now collect categories

        allJobs.forEach(job => {
            // if (job.state && job.state !== 'N/A') states.add(job.state); // REMOVED: No longer populate state filter
            if (job.department && job.department !== 'N/A') departments.add(job.department); // Only add if not N/A (this is your 'category')
        });

        // Clear existing options except "All"
        // stateFilterSelect.innerHTML = '<option value="">All States</option>'; // REMOVED: No longer populate state filter
        if (departmentFilterSelect) { // Added null check
            departmentFilterSelect.innerHTML = '<option value="">All Categories</option>'; // Label changed to reflect 'category'
        }


        // REMOVED: State filter population loop
        // Array.from(states).sort().forEach(state => {
        //     const option = document.createElement('option');
        //     option.value = state;
        //     option.textContent = state;
        //     stateFilterSelect.appendChild(option);
        // });

        if (departmentFilterSelect) { // Added null check
            Array.from(departments).sort().forEach(department => {
                const option = document.createElement('option');
                option.value = department;
                option.textContent = department;
                departmentFilterSelect.appendChild(option);
            });
        }
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

            // Basic check for essential properties before rendering (already handled in fetch, but good to double check)
            if (!job.title || !job.apply_link) {
                console.warn("Skipping malformed job entry during display:", job);
                return; // Skip this job if essential data is missing
            }

            jobCard.innerHTML = `
                <h3>${job.title}</h3>
                <p><strong>Category:</strong> ${job.department}</p> <p><strong>State:</strong> ${job.state}</p>
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
        // const selectedState = stateFilterSelect.value; // REMOVED
        const selectedDepartment = departmentFilterSelect ? departmentFilterSelect.value : ""; // Added null check

        const filteredJobs = allJobs.filter(job => {
            const matchesSearch = job.title.toLowerCase().includes(searchTerm);
            // const matchesState = selectedState === "" || job.state === selectedState; // REMOVED
            const matchesDepartment = selectedDepartment === "" || job.department === selectedDepartment; // Filter using 'department' field (which is your 'category')

            return matchesSearch && matchesDepartment; // Removed matchesState
        });

        displayJobs(filteredJobs);
    }

    // --- Event Listeners (with null checks to prevent the first error) ---
    if (searchJobInput) {
        searchJobInput.addEventListener('input', applyFilters);
    } else { console.error("Error: Search input not found."); }

    // if (stateFilterSelect) { // REMOVED
    //     stateFilterSelect.addEventListener('change', applyFilters);
    // } else { console.error("Error: State filter select not found."); }

    if (departmentFilterSelect) {
        departmentFilterSelect.addEventListener('change', applyFilters);
    } else { console.error("Error: Department filter select not found."); }

    if (resetFiltersButton) {
        resetFiltersButton.addEventListener('click', () => {
            searchJobInput.value = '';
            // stateFilterSelect.value = ''; // REMOVED
            if (departmentFilterSelect) { // Added null check
                departmentFilterSelect.value = '';
            }
            applyFilters(); // Re-apply filters to show all jobs
        });
    } else { console.error("Error: Reset filters button not found."); }


    // Initial fetch and display of jobs
    fetchJobs();
});
