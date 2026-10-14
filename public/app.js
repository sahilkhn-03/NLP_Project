/* Browser workspace for the existing NL-to-SQL API. */
const $ = id => document.getElementById(id);
function readHistory() {
  try { const value = JSON.parse(localStorage.getItem('nl_sql_history') || '[]'); return Array.isArray(value) ? value.filter(q => typeof q === 'string' && q.trim()).slice(-20) : []; }
  catch { return []; }
}
const state = { samples: [], activeCategory: '📋 Basic', history: readHistory(), currentResults: null, queriesRun: 0, loading: false };
const input = $('query-input'), form = $('query-form'), generate = $('btn-generate'), clear = $('btn-clear');

async function fetchJson(url, options = {}) {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(30000) });
  let data;
  try { data = await response.json(); } catch { throw new Error('The server returned an unreadable response. Try again shortly.'); }
  if (!response.ok) throw new Error(data?.error || 'The database service is unavailable. Try again shortly.');
  return data;
}
function updateInput() { $('query-count').textContent = `${input.value.length} / 500`; generate.disabled = state.loading || !input.value.trim(); }
async function loadStats() {
  const button = $('connection-status'); $('connection-label').textContent = 'Connecting…'; button.classList.remove('offline');
  try {
    const data = await fetchJson('/api/stats?endpoint=stats');
    if (![data.students, data.courses, data.enrollments].every(n => Number.isFinite(n))) throw new Error('Incomplete stats');
    for (const name of ['students', 'courses', 'enrollments']) $(`stat-${name}`).textContent = data[name].toLocaleString();
    $('connection-label').textContent = 'Database connected';
  } catch { $('connection-label').textContent = 'Reconnect database'; button.classList.add('offline'); for (const name of ['students', 'courses', 'enrollments']) $(`stat-${name}`).textContent = '—'; }
}
async function loadSamples() {
  try { const data = await fetchJson('/api/samples?endpoint=samples'); state.samples = Array.isArray(data.samples) ? data.samples : []; renderSamples(); }
  catch { $('sample-list').textContent = 'Examples unavailable. You can still type a question.'; }
}
async function loadSchema() {
  try { const data = await fetchJson('/api/schema?endpoint=schema'); if (!data.schema || typeof data.schema !== 'object') throw new Error('Schema unavailable'); renderSchema(data.schema); }
  catch { $('schema-accordion').textContent = 'Tables could not load. Check the database connection.'; }
}
function selectPanel(id) {
  for (const panel of document.querySelectorAll('.sidebar-section')) panel.hidden = panel.id !== id;
  for (const button of document.querySelectorAll('[data-panel]')) { const active = button.dataset.panel === id; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); }
}
function renderSamples() {
  const list = $('sample-list'); list.replaceChildren();
  for (const item of state.samples.filter(s => s.category === state.activeCategory)) {
    const button = document.createElement('button'); button.className = 'sample-btn'; button.textContent = item.question; button.disabled = state.loading;
    button.addEventListener('click', () => chooseQuestion(item.question)); list.append(button);
  }
  if (!list.children.length) list.textContent = 'No examples in this category.';
}
function renderSchema(schema) {
  const container = $('schema-accordion'); container.replaceChildren();
  for (const [name, columns] of Object.entries(schema)) {
    if (!Array.isArray(columns)) continue;
    const details = document.createElement('details'); details.className = 'schema-table-item';
    const summary = document.createElement('summary'); summary.className = 'schema-table-summary'; summary.textContent = `${name} (${columns.length})`;
    const content = document.createElement('div'); content.className = 'schema-table-content';
    for (const column of columns) {
      const row = document.createElement('div'); row.className = 'schema-col-row';
      const label = document.createElement('span'); label.className = 'schema-col-name'; label.textContent = `${column.name}${column.pk ? ' · primary key' : ''}`;
      const type = document.createElement('span'); type.className = 'schema-col-type'; type.textContent = column.type;
      row.append(label, type); content.append(row);
    }
    details.append(summary, content); container.append(details);
  }
}
function saveHistory() { try { localStorage.setItem('nl_sql_history', JSON.stringify(state.history)); } catch { /* Queries still run if storage is blocked. */ } }
function renderHistory() {
  const list = $('history-list'); list.replaceChildren();
  for (const question of state.history.slice(-5).reverse()) {
    const button = document.createElement('button'); button.className = 'history-btn'; button.textContent = question; button.disabled = state.loading;
    button.addEventListener('click', () => chooseQuestion(question)); list.append(button);
  }
  if (!list.children.length) { const note = document.createElement('p'); note.className = 'sidebar-note'; note.textContent = 'Your next query starts the collection.'; list.append(note); }
}
function addHistory(question) { state.history = [...state.history.filter(q => q !== question), question].slice(-20); saveHistory(); renderHistory(); }
function selectTab(id, focus = false) {
  for (const tab of document.querySelectorAll('.tab-btn')) {
    const active = tab.dataset.tab === id; tab.classList.toggle('active', active); tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
    if (active && focus) tab.focus();
  }
  for (const panel of document.querySelectorAll('.tab-content')) panel.hidden = panel.id !== id;
}
function setLoading(loading) {
  state.loading = loading; input.disabled = loading; clear.disabled = loading; document.body.classList.toggle('busy', loading);
  document.querySelector('.output-panel').setAttribute('aria-busy', String(loading));
  generate.querySelector('.button-label').textContent = loading ? 'Running…' : 'Run query';
  for (const button of document.querySelectorAll('.sample-btn,.history-btn,[data-question]')) button.disabled = loading;
  $('loading-state').hidden = !loading;
  if (loading) { $('empty-state').hidden = true; $('results-section').hidden = true; $('empty-footer').hidden = true; $('output-label').textContent = 'Processing your question'; }
  updateInput();
}
function showError(message) {
  $('error-text').textContent = message; $('error-card').hidden = false; $('results-section').hidden = true; $('empty-state').hidden = true; $('empty-footer').hidden = false; $('output-label').textContent = 'Try another question';
}
function chooseQuestion(question) { if (state.loading) return; input.value = question; updateInput(); void runQuery(question); }
async function runQuery(question) {
  question = String(question || '').trim(); if (!question || state.loading) return;
  if (question.length > 500) return showError('Keep your question to 500 characters.');
  $('error-card').hidden = true; setLoading(true);
  try {
    const data = await fetchJson('/api/query?endpoint=query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
    if (!data.success || typeof data.sql !== 'string' || !Array.isArray(data.rows) || !Array.isArray(data.columns)) throw new Error(data.error || 'The query response was incomplete. Try again.');
    state.currentResults = data; state.queriesRun++; $('stat-queries-run').textContent = state.queriesRun; addHistory(question); displayResults(data);
  } catch (error) { showError(error instanceof TypeError ? 'Could not reach the database. Check your connection and try again.' : error.name === 'TimeoutError' ? 'The request timed out. Try again shortly.' : error.message || 'The query could not run. Try again.'); }
  finally { setLoading(false); }
}
function displayResults(data) {
  $('empty-state').hidden = true; $('results-section').hidden = false; $('empty-footer').hidden = true; $('output-label').textContent = 'Query complete';
  $('sql-display').textContent = data.sql;
  $('sql-time-pill').textContent = `${data.exec_time_ms ?? '—'} ms database time`;
  $('badge-row-count').textContent = `${data.row_count} rows`; $('data-meta').textContent = `${data.row_count} rows · ${data.columns.length} columns`; $('btn-download-csv').disabled = !data.rows.length;
  const head = $('results-thead'), body = $('results-tbody'); head.replaceChildren(); body.replaceChildren(); const header = document.createElement('tr');
  for (const column of data.columns) { const th = document.createElement('th'); th.scope = 'col'; th.textContent = column; header.append(th); } head.append(header);
  for (const row of data.rows) { const tr = document.createElement('tr'); for (const column of data.columns) { const td = document.createElement('td'); td.textContent = row[column] == null ? 'NULL' : String(row[column]); tr.append(td); } body.append(tr); }
  if (!data.rows.length) { const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = Math.max(data.columns.length, 1); td.className = 'empty-row'; td.textContent = 'No rows matched this question. Try a broader filter.'; tr.append(td); body.append(tr); }
  $('explanation-text').textContent = data.explanation || 'No explanation was returned.'; $('explanation-question-text').textContent = data.question; selectTab('tab-data');
  if (window.innerWidth <= 780) document.querySelector('.output-panel').scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
}
function csvCell(value) { let text = value == null ? '' : String(value); if (/^\s*[=+@-]/.test(text)) text = `'${text}`; return `"${text.replace(/"/g, '""')}"`; }
function bindEvents() {
  input.addEventListener('input', () => { updateInput(); if (state.currentResults && input.value.trim() !== state.currentResults.question) $('output-label').textContent = 'Previous question · run to update'; });
  input.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); void runQuery(input.value); } });
  form.addEventListener('submit', event => { event.preventDefault(); void runQuery(input.value); });
  clear.addEventListener('click', () => { if (state.loading) return; input.value = ''; state.currentResults = null; $('error-card').hidden = true; $('results-section').hidden = true; $('empty-state').hidden = false; $('empty-footer').hidden = false; $('output-label').textContent = 'Ready when you are'; updateInput(); input.focus(); });
  for (const button of document.querySelectorAll('[data-panel]')) button.addEventListener('click', () => selectPanel(button.dataset.panel));
  for (const button of document.querySelectorAll('[data-question]')) button.addEventListener('click', () => chooseQuestion(button.dataset.question));
  $('category-tabs').addEventListener('click', event => { const button = event.target.closest('.cat-pill'); if (!button) return; state.activeCategory = button.dataset.category; for (const pill of document.querySelectorAll('.cat-pill')) { const active = pill === button; pill.classList.toggle('active', active); pill.setAttribute('aria-pressed', String(active)); } renderSamples(); });
  $('btn-clear-history').addEventListener('click', () => { state.history = []; saveHistory(); renderHistory(); });
  const tabs = [...document.querySelectorAll('.tab-btn')];
  for (const [index, tab] of tabs.entries()) {
    tab.addEventListener('click', () => selectTab(tab.dataset.tab));
    tab.addEventListener('keydown', event => { let target; if (event.key === 'ArrowRight') target = (index + 1) % tabs.length; if (event.key === 'ArrowLeft') target = (index + tabs.length - 1) % tabs.length; if (event.key === 'Home') target = 0; if (event.key === 'End') target = tabs.length - 1; if (target !== undefined) { event.preventDefault(); selectTab(tabs[target].dataset.tab, true); } });
  }
  $('btn-copy-sql').addEventListener('click', async () => { if (!state.currentResults) return; const label = $('btn-copy-sql').querySelector('span'); try { await navigator.clipboard.writeText(state.currentResults.sql); label.textContent = 'Copied'; } catch { label.textContent = 'Select SQL to copy'; } setTimeout(() => label.textContent = 'Copy SQL', 2500); });
  $('btn-download-csv').addEventListener('click', () => { const data = state.currentResults; if (!data?.rows.length) return; const lines = [data.columns.map(csvCell).join(','), ...data.rows.map(row => data.columns.map(column => csvCell(row[column])).join(','))]; const url = URL.createObjectURL(new Blob(['\uFEFF', lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })); const link = document.createElement('a'); link.href = url; link.download = 'query_results.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
  $('connection-status').addEventListener('click', () => void Promise.all([loadStats(), loadSamples(), loadSchema()]));
}
bindEvents(); updateInput(); renderHistory(); void Promise.all([loadStats(), loadSamples(), loadSchema()]);
