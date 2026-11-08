const state = { report: null, findings: [] };
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

function fmt(n, d = 2) { return typeof n === 'number' ? n.toFixed(d).replace(/\.00$/, '') : n; }
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function setView(name) {
  $$('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  const titles = { dashboard: 'Repository overview', findings: 'Findings', inventory: 'Inventory', policy: 'Policy & tools', history: 'Report history' };
  $('#view-title').textContent = titles[name];
  $('#breadcrumb').textContent = name === 'dashboard' ? 'OVERVIEW' : name.toUpperCase();
  if (name === 'policy') { loadPolicy(); loadDoctor(); }
  if (name === 'history') loadHistory();
}

function scoreColor(score) {
  if (score >= 80) return 'var(--good)';
  if (score >= 60) return 'var(--warn)';
  return 'var(--bad)';
}

function renderReport(report) {
  state.report = report;
  state.findings = [];
  (report.results || []).forEach(r => (r.findings || []).forEach(f => state.findings.push({ check: r.name, ...f })));
  $('#project-meta').textContent = `${report.project} • ${report.target} • ${new Date(report.generated_at).toLocaleString()}`;
  $('#score-value').textContent = fmt(report.score, 0);
  $('#grade').textContent = `Grade ${report.grade}`;
  const deg = Math.max(0, Math.min(100, report.score)) * 3.6;
  $('#score-ring').style.background = `conic-gradient(${scoreColor(report.score)} ${deg}deg, rgba(255,255,255,0.06) ${deg}deg)`;
  const badge = $('#policy-badge');
  badge.textContent = report.policy_passed ? 'Policy PASS' : 'Policy FAIL';
  badge.className = 'badge ' + (report.policy_passed ? 'pass' : 'fail');
  $('#kpi-checks').textContent = (report.results || []).length;
  const passed = (report.results || []).filter(r => r.status === 'passed').length;
  $('#kpi-checks-sub').textContent = `${passed} passed`;
  $('#kpi-findings').textContent = state.findings.length;
  $('#kpi-threshold').textContent = `≥ ${fmt(report.fail_under)}`;
  $('#kpi-generated').textContent = `CodeProof ${report.codeproof_version}`;
  renderResults();
  renderFindings();
  $('#limitations').innerHTML = (report.limitations || []).map(l => `<li>${esc(l)}</li>`).join('') || '<li>None.</li>';
}

function renderResults() {
  const filter = $('#status-filter').value;
  const rows = (state.report?.results || []).filter(r => filter === 'all' || r.status === filter);
  $('#results-table tbody').innerHTML = rows.map(r => `<tr>
    <td><strong>${esc(r.name)}</strong></td>
    <td><span class="status ${esc(r.status)}">${esc(r.status)}</span></td>
    <td>${fmt(r.weight)}</td>
    <td>${r.required ? 'Yes' : 'No'}</td>
    <td>${fmt(r.duration_seconds, 3)}s</td>
    <td>${esc(r.summary)}</td>
  </tr>`).join('') || `<tr><td colspan="6" class="empty-cell"><strong>No results to show</strong><span>${state.report ? 'Try another status filter.' : 'Run a scan to see your check results here.'}</span></td></tr>`;
}

function renderFindings() {
  const q = ($('#finding-search')?.value || '').toLowerCase();
  const rows = state.findings.filter(f => !q || JSON.stringify(f).toLowerCase().includes(q));
  $('#findings-table tbody').innerHTML = rows.map(f => `<tr>
    <td>${esc(f.check)}</td><td>${esc(f.level)}</td><td>${esc(f.rule || '')}</td>
    <td>${esc(f.path || '')}</td><td>${f.line ?? ''}</td><td>${esc(f.message)}</td>
  </tr>`).join('') || `<tr><td colspan="6" class="empty-cell"><strong>No findings to show</strong><span>${q ? 'Try a different search.' : state.report ? 'No structured findings were reported in this scan.' : 'Run a scan to see reported findings.'}</span></td></tr>`;
}

async function runScan() {
  const btn = $('#run-scan');
  btn.disabled = true; $('#scan-status').textContent = 'Running scan… this may take a while (tools execute in the target repo).';
  try {
    const target = $('#target').value.trim();
    const report = await api('/api/scan', { method: 'POST', body: JSON.stringify({ path: target }) });
    renderReport(report);
    $('#scan-status').textContent = `Scan complete. Policy ${report.policy_passed ? 'PASS' : 'FAIL'}.`;
    loadHistory();
  } catch (e) {
    $('#scan-status').textContent = `Error: ${e.message}`;
  } finally { btn.disabled = false; }
}

async function loadDoctor() {
  try {
    const data = await api('/api/doctor');
    $('#doctor').innerHTML = (data.tools || []).map(t => `<div class="doctor-item"><div class="name">${esc(t.name)}</div><div class="status ${t.available ? 'passed' : 'unavailable'}">${t.available ? 'Available' : 'Missing'}</div>${t.path ? `<div class="muted small">${esc(t.path)}</div>` : ''}</div>`).join('');
  } catch (e) { $('#doctor').innerHTML = `<p class="muted">Error: ${esc(e.message)}</p>`; }
}

async function loadInventory() {
  try {
    const target = $('#target').value.trim();
    const data = await api(`/api/inventory?path=${encodeURIComponent(target)}`);
    $('#inventory-table tbody').innerHTML = (data.symbols || []).map(s => `<tr><td>${esc(s.name)}</td><td>${esc(s.file)}</td><td>${s.line}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">No public symbols found.</td></tr>';
  } catch (e) { $('#inventory-table tbody').innerHTML = `<tr><td colspan="3" class="muted">Error: ${esc(e.message)}</td></tr>`; }
}

async function loadPolicy() {
  try {
    const target = $('#target').value.trim();
    const data = await api(`/api/policy?path=${encodeURIComponent(target)}`);
    $('#policy-json').textContent = JSON.stringify(data, null, 2);
  } catch (e) { $('#policy-json').textContent = `Error: ${e.message}`; }
}

async function loadHistory() {
  try {
    const target = $('#target').value.trim();
    const data = await api(`/api/history?path=${encodeURIComponent(target)}`);
    $('#history-table tbody').innerHTML = (data.reports || []).map(r => `<tr>
      <td>${esc(new Date(r.generated_at).toLocaleString())}</td><td>${esc(r.project)}</td><td>${fmt(r.score)}</td><td>${esc(r.grade)}</td>
      <td><span class="badge ${r.policy_passed ? 'pass' : 'fail'}">${r.policy_passed ? 'PASS' : 'FAIL'}</span></td>
      <td><button class="ghost" data-load-report="${esc(r.file)}">Load</button></td>
    </tr>`).join('') || '<tr><td colspan="6" class="muted">No saved JSON reports found in .codeproof/reports.</td></tr>';
    $$('#history-table [data-load-report]').forEach(btn => btn.addEventListener('click', async () => {
      try {
        const report = await api(`/api/report?path=${encodeURIComponent(target)}&file=${encodeURIComponent(btn.dataset.loadReport)}`);
        renderReport(report); setView('dashboard');
      } catch (e) {
        $('#history-table tbody').innerHTML = `<tr><td colspan="6" class="muted">Error: ${esc(e.message)}</td></tr>`;
      }
    }));
  } catch (e) { $('#history-table tbody').innerHTML = `<tr><td colspan="6" class="muted">Error: ${esc(e.message)}</td></tr>`; }
}

$$('.nav-btn').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));
$('#run-scan').addEventListener('click', runScan);
$('#status-filter').addEventListener('change', renderResults);
$('#finding-search').addEventListener('input', renderFindings);
$('#refresh-doctor').addEventListener('click', () => setView('policy'));
$('#load-inventory').addEventListener('click', loadInventory);
$('#load-policy').addEventListener('click', () => { loadPolicy(); loadDoctor(); });
$('#load-history').addEventListener('click', loadHistory);
$('#open-reports').addEventListener('click', async () => {
  try { await api('/api/open-reports', { method: 'POST', body: JSON.stringify({ path: $('#target').value.trim() }) }); }
  catch (e) { alert(e.message); }
});

(async function init() {
  try { const info = await api('/api/info'); $('#target').value = info.default_target || ''; } catch {}
  loadDoctor(); loadHistory();
})();
