/**
 * app.js
 * Client-side script for NL-to-SQL web application on Vercel.
 */

// Application state
const state = {
  samples: [],
  activeCategory: "📋 Basic",
  history: JSON.parse(localStorage.getItem("nl_sql_history") || "[]"),
  currentResults: null,
  queriesRun: 0,
};

// DOM references
const queryInput = document.getElementById("query-input");
const queryForm = document.getElementById("query-form");
const btnClear = document.getElementById("btn-clear");
const sampleList = document.getElementById("sample-list");
const categoryTabs = document.getElementById("category-tabs");
const schemaAccordion = document.getElementById("schema-accordion");
const historySection = document.getElementById("history-section");
const historyList = document.getElementById("history-list");
const errorCard = document.getElementById("error-card");
const errorText = document.getElementById("error-text");
const resultsSection = document.getElementById("results-section");
const emptyState = document.getElementById("empty-state");
const sqlDisplay = document.getElementById("sql-display");
const sqlTimePill = document.getElementById("sql-time-pill");
const btnCopySql = document.getElementById("btn-copy-sql");
const resultsThead = document.getElementById("results-thead");
const resultsTbody = document.getElementById("results-tbody");
const badgeRowCount = document.getElementById("badge-row-count");
const dataMeta = document.getElementById("data-meta");
const btnDownloadCsv = document.getElementById("btn-download-csv");
const explanationText = document.getElementById("explanation-text");
const explanationQuestionText = document.getElementById("explanation-question-text");
const statStudents = document.getElementById("stat-students");
const statCourses = document.getElementById("stat-courses");
const statEnrollments = document.getElementById("stat-enrollments");
const statQueriesRun = document.getElementById("stat-queries-run");

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
async function init() {
  bindEvents();
  renderHistory();
  await Promise.all([loadStats(), loadSchema(), loadSamples()]);
}

// ---------------------------------------------------------------------------
// API Calls
// ---------------------------------------------------------------------------
async function loadStats() {
  try {
    const res = await fetch("/api/stats?endpoint=stats");
    if (!res.ok) return;
    const data = await res.json();
    if (statStudents && data.students) statStudents.textContent = data.students;
    if (statCourses && data.courses) statCourses.textContent = data.courses;
    if (statEnrollments && data.enrollments) statEnrollments.textContent = data.enrollments;
  } catch (err) {
    console.warn("Could not load stats:", err);
  }
}

async function loadSchema() {
  try {
    const res = await fetch("/api/schema?endpoint=schema");
    if (!res.ok) return;
    const data = await res.json();
    if (data.schema) renderSchema(data.schema);
    if (data.samples && (!state.samples || !state.samples.length)) {
      state.samples = data.samples;
      renderSamples();
    }
  } catch (err) {
    if (schemaAccordion) schemaAccordion.innerHTML = `<div class="schema-col-row">Schema unavailable</div>`;
  }
}

async function loadSamples() {
  try {
    const res = await fetch("/api/samples?endpoint=samples");
    if (!res.ok) return;
    const data = await res.json();
    state.samples = data.samples || [];
    renderSamples();
  } catch (err) {
    console.warn("Could not load samples:", err);
  }
}

async function runQuery(question) {
  question = (question || "").trim();
  if (!question) return;

  hideError();
  showLoading(true);

  try {
    const res = await fetch("/api/query?endpoint=query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      showError(data.error || "An unexpected error occurred while generating query.");
      showLoading(false);
      return;
    }

    state.currentResults = data;
    state.queriesRun++;
    if (statQueriesRun) statQueriesRun.textContent = state.queriesRun;

    addToHistory(question);
    displayResults(data);
  } catch (err) {
    showError("Network error: Could not reach NL-to-SQL API serverless function.");
  } finally {
    showLoading(false);
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderSamples() {
  if (!sampleList) return;
  sampleList.innerHTML = "";

  const filtered = state.samples.filter(s => s.category === state.activeCategory);
  filtered.forEach(item => {
    const btn = document.createElement("button");
    btn.className = "sample-btn";
    btn.textContent = item.question;
    btn.onclick = () => {
      queryInput.value = item.question;
      runQuery(item.question);
    };
    sampleList.appendChild(btn);
  });
}

function renderSchema(schema) {
  if (!schemaAccordion) return;
  schemaAccordion.innerHTML = "";

  const icons = { students: "👤", courses: "📚", enrollments: "📝" };

  for (const [table, cols] of Object.entries(schema)) {
    const details = document.createElement("details");
    details.className = "schema-table-item";

    const summary = document.createElement("summary");
    summary.className = "schema-table-summary";
    summary.textContent = `${icons[table] || "📋"} ${table} (${cols.length})`;

    const content = document.createElement("div");
    content.className = "schema-table-content";

    cols.forEach(col => {
      const row = document.createElement("div");
      row.className = "schema-col-row";
      row.innerHTML = `
        <span class="schema-col-name">${col.name}${col.pk ? " 🔑" : ""}</span>
        <span class="schema-col-type">${col.type}</span>
      `;
      content.appendChild(row);
    });

    details.appendChild(summary);
    details.appendChild(content);
    schemaAccordion.appendChild(details);
  }
}

function renderHistory() {
  if (!historyList || !historySection) return;
  if (!state.history.length) {
    historySection.style.display = "none";
    return;
  }

  historySection.style.display = "flex";
  historyList.innerHTML = "";

  state.history.slice(-5).reverse().forEach(q => {
    const btn = document.createElement("button");
    btn.className = "history-btn";
    btn.textContent = `↩ ${q}`;
    btn.onclick = () => {
      queryInput.value = q;
      runQuery(q);
    };
    historyList.appendChild(btn);
  });
}

function addToHistory(q) {
  if (!state.history.includes(q)) {
    state.history.push(q);
    if (state.history.length > 20) state.history.shift();
    localStorage.setItem("nl_sql_history", JSON.stringify(state.history));
    renderHistory();
  }
}

function displayResults(data) {
  if (emptyState) emptyState.style.display = "none";
  if (resultsSection) resultsSection.style.display = "flex";

  // SQL tab
  if (sqlDisplay) sqlDisplay.textContent = data.sql || "";
  if (sqlTimePill) sqlTimePill.textContent = `⏱ ${data.exec_time_ms} ms`;

  // Results tab
  if (badgeRowCount) badgeRowCount.textContent = `${data.row_count} rows`;
  if (dataMeta) dataMeta.textContent = `Returned ${data.row_count} rows across ${data.columns.length} columns`;

  // Render Table
  if (resultsThead && resultsTbody) {
    resultsThead.innerHTML = "";
    resultsTbody.innerHTML = "";

    if (data.columns && data.columns.length) {
      const trHead = document.createElement("tr");
      data.columns.forEach(col => {
        const th = document.createElement("th");
        th.textContent = col;
        trHead.appendChild(th);
      });
      resultsThead.appendChild(trHead);
    }

    if (data.rows && data.rows.length) {
      data.rows.forEach(row => {
        const tr = document.createElement("tr");
        data.columns.forEach(col => {
          const td = document.createElement("td");
          td.textContent = row[col] !== null ? row[col] : "NULL";
          tr.appendChild(td);
        });
        resultsTbody.appendChild(tr);
      });
    } else {
      resultsTbody.innerHTML = `<tr><td colspan="${Math.max(data.columns.length, 1)}" style="text-align:center;color:#94a3b8;padding:24px;">Query returned 0 rows.</td></tr>`;
    }
  }

  // Explanation tab
  if (explanationText) explanationText.textContent = data.explanation || "No explanation provided.";
  if (explanationQuestionText) explanationQuestionText.textContent = data.question || "";
}

function showError(msg) {
  if (errorText) errorText.textContent = msg;
  if (errorCard) errorCard.style.display = "flex";
  if (resultsSection) resultsSection.style.display = "none";
}

function hideError() {
  if (errorCard) errorCard.style.display = "none";
}

function showLoading(isLoading) {
  const btn = document.getElementById("btn-generate");
  if (!btn) return;
  if (isLoading) {
    btn.innerHTML = `<span class="btn-icon">⏳</span> Running...`;
    btn.disabled = true;
  } else {
    btn.innerHTML = `<span class="btn-icon">⚡</span> Generate`;
    btn.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Event Listeners
// ---------------------------------------------------------------------------
function bindEvents() {
  // Query Form
  if (queryForm) {
    queryForm.addEventListener("submit", (e) => {
      e.preventDefault();
      runQuery(queryInput.value);
    });
  }

  // Clear Button
  if (btnClear) {
    btnClear.addEventListener("click", () => {
      if (queryInput) queryInput.value = "";
      hideError();
      if (resultsSection) resultsSection.style.display = "none";
      if (emptyState) emptyState.style.display = "block";
    });
  }

  // Category Tabs
  if (categoryTabs) {
    categoryTabs.addEventListener("click", (e) => {
      const pill = e.target.closest(".cat-pill");
      if (!pill) return;
      categoryTabs.querySelectorAll(".cat-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      state.activeCategory = pill.dataset.category;
      renderSamples();
    });
  }

  // Result Tabs
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");
    });
  });

  // Copy SQL
  if (btnCopySql) {
    btnCopySql.addEventListener("click", async () => {
      if (!state.currentResults || !state.currentResults.sql) return;
      try {
        await navigator.clipboard.writeText(state.currentResults.sql);
        btnCopySql.textContent = "✅ Copied!";
        setTimeout(() => { btnCopySql.textContent = "📋 Copy SQL"; }, 2000);
      } catch (err) {
        btnCopySql.textContent = "Error copying";
      }
    });
  }

  // Download CSV
  if (btnDownloadCsv) {
    btnDownloadCsv.addEventListener("click", () => {
      if (!state.currentResults || !state.currentResults.rows || !state.currentResults.rows.length) return;
      const data = state.currentResults;
      const csvRows = [data.columns.join(",")];

      data.rows.forEach(row => {
        const values = data.columns.map(col => {
          const val = row[col] === null ? "" : String(row[col]);
          return `"${val.replace(/"/g, '""')}"`;
        });
        csvRows.push(values.join(","));
      });

      const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "query_results.csv";
      a.click();
      URL.revokeObjectURL(url);
    });
  }
}

// Start application
window.addEventListener("DOMContentLoaded", init);
