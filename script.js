// 🌐 Language Switch
document.getElementById("langToggle").addEventListener("change", (e) => {
  const lang = e.target.value;
  document.documentElement.lang = lang;
  location.reload(); // optional: force reload to switch language
});

// 🌙 Dark Mode Toggle
const toggle = document.getElementById("darkModeToggle");
toggle.addEventListener("click", () => {
  document.body.classList.toggle("dark-mode");
});

// 🔍 Load Job Manifest
fetch("jobs/job_manifest.json")
  .then((res) => res.json())
  .then((files) => {
    files.forEach((filename) => loadJobFile(`jobs/${filename}`));
  })
  .catch((err) => {
    console.error("Failed to load job manifest:", err);
  });

// 📦 Load Individual Job JSON
function loadJobFile(url) {
  fetch(url)
    .then((res) => res.json())
    .then((job) => {
      renderJob(job);
      populateFilter(job.category);
    })
    .catch((err) => {
      console.error("Failed to load job:", url, err);
    });
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
    <a href="${job.apply_link}" class="apply-link" target="_blank" rel="noopener noreferrer">Apply Now</a>
  `;
  container.appendChild(card);
}

// 🧩 Populate Filter Dropdown
const categories = new Set();
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
    const cat = card.querySelector("p strong").nextSibling?.textContent?.trim();
    const match = (!query || title.includes(query)) && (!category || cat === category);
    card.style.display = match ? "block" : "none";
  });
}
document.getElementById("langToggleHero").addEventListener("change", function () {
  const lang = this.value;

  const translations = {
    hi: {
      title: "Sarkari Sarthi",
      tagline: "आपकी सरकारी नौकरी की सच्ची साथी!",
      cta: "🔍 सरकारी नौकरी देखें",
    },
    en: {
      title: "Sarkari Sarthi",
      tagline: "Your true partner for Government Jobs!",
      cta: "🔍 View Government Jobs",
    },
  };

  const t = translations[lang];
  document.getElementById("heroTitle").innerText = t.title;
  document.getElementById("heroTagline").innerText = t.tagline;
  document.getElementById("heroCTA").innerText = t.cta;
});
