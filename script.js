// 🌐 Language Switch
document.getElementById("langToggle").addEventListener("change", (e) => {
  const lang = e.target.value;
  document.documentElement.lang = lang;
  localStorage.setItem("lang", lang);
  location.reload(); // Optional: force reload
});

// 🌙 Dark Mode Toggle
const toggle = document.getElementById("darkModeToggle");
toggle.addEventListener("click", () => {
  document.body.classList.toggle("dark-mode");
  localStorage.setItem("dark", document.body.classList.contains("dark-mode"));
});

// 🌍 Load persisted preferences
if (localStorage.getItem("dark") === "true") {
  document.body.classList.add("dark-mode");
}
if (localStorage.getItem("lang")) {
  document.getElementById("langToggle").value = localStorage.getItem("lang");
}

// 🔍 Load Job Manifest
fetch("jobs/job_manifest.json")
  .then((res) => res.json())
  .then((files) => {
    files.forEach((filename) => loadJobFile(`jobs/${filename}`));
  })
  .catch((err) => {
    console.error("Failed to load job manifest:", err);
  });

const categories = new Set();

// 📦 Load Each Job File
function loadJobFile(url) {
  fetch(url)
    .then((res) => res.json())
    .then((job) => {
      renderJob(job);
      populateFilter(job.category);
    })
    .catch((err) => console.warn("Job load failed:", err));
}

// 🎨 Render Job Card
function renderJob(job) {
  const container = document.getElementById("jobListings");
  const card = document.createElement("div");
  card.className = "job-card";
  card.innerHTML = `
    <h3>${job.title || "Untitled Job"}</h3>
    <p><strong>Category:</strong> ${job.category || "N/A"}</p>
    <p><strong>State:</strong> ${job.state || "N/A"}</p>
    <p><strong>Last Date:</strong> ${job.last_date || "Not Specified"}</p>
    <a href="${job.apply_link}" class="apply-link" target="_blank">Apply Now</a>
    ${job.pdf_url ? `<button class="preview-btn" data-pdf="${job.pdf_url}">Preview PDF</button>` : ""}
  `;
  card.addEventListener("click", () => showModal(job));
  container.appendChild(card);
}

// 🧩 Populate Filter Dropdown
function populateFilter(category) {
  if (!category || categories.has(category)) return;
  categories.add(category);
  const select = document.getElementById("departmentFilter");
  const option = document.createElement("option");
  option.value = category;
  option.textContent = category;
  select.appendChild(option);
}

// 🔎 Filters
document.getElementById("resetFilters").addEventListener("click", () => {
  document.getElementById("searchJob").value = "";
  document.getElementById("departmentFilter").value = "";
  document.getElementById("jobListings").innerHTML = "";
  fetch("jobs/job_manifest.json")
    .then((res) => res.json())
    .then((files) => {
      files.forEach((filename) => loadJobFile(`jobs/${filename}`));
    });
});

document.getElementById("searchJob").addEventListener("input", applyFilters);
document.getElementById("departmentFilter").addEventListener("change", applyFilters);

function applyFilters() {
  const query = document.getElementById("searchJob").value.toLowerCase();
  const category = document.getElementById("departmentFilter").value;
  const cards = document.querySelectorAll(".job-card");
  cards.forEach((card) => {
    const title = card.querySelector("h3").textContent.toLowerCase();
    const cat = card.querySelector("p").textContent.toLowerCase();
    const match = (!query || title.includes(query)) && (!category || cat.includes(category.toLowerCase()));
    card.style.display = match ? "block" : "none";
  });
}

// 📄 Modal Renderer
function showModal(job) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-box">
      <span class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</span>
      <div class="modal-content">
        <p class="job-category">${job.category || "General"}</p>
        <h2>${job.title}</h2>
        <p><strong>Last Date:</strong> ${job.last_date || "Not Specified"}</p>
        <p><strong>State:</strong> ${job.state || "N/A"}</p>
        <a href="${job.apply_link}" target="_blank" class="apply-btn">Apply Now</a>
        ${job.pdf_url ? `<a href="${job.pdf_url}" target="_blank" class="pdf-btn">Preview PDF</a>` : ""}
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}
