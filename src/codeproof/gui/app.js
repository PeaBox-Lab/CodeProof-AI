const state = { report: null, findings: [], currentJob: null, pollTimer: null };
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
  const title = { dashboard: 'Repository overview', findings: 'Findings', inventory: 'Public symbols', policy: 'Policy & tools', history: 'Report history' }[name] || name;
  $('#view-title').textContent = title;
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
  setProgress(100);
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
  </tr>`).join('') || '<tr><td colspan="6" class="empty-cell"><strong>No results yet</strong><span>Run a scan to populate this table.</span></td></tr>';
}

function renderFindings() {
  const q = ($('#finding-search')?.value || '').toLowerCase();
  const rows = state.findings.filter(f => !q || JSON.stringify(f).toLowerCase().includes(q));
  $('#findings-table tbody').innerHTML = rows.map(f => `<tr>
    <td>${esc(f.check)}</td><td>${esc(f.level)}</td><td>${esc(f.rule || '')}</td>
    <td>${esc(f.path || '')}</td><td>${f.line ?? ''}</td><td>${esc(f.message)}</td>
  </tr>`).join('') || '<tr><td colspan="6" class="empty-cell"><strong>No findings to show</strong><span>Run a scan to see reported findings.</span></td></tr>';
}

function setProgress(pct) {
  const bar = $('#progress-bar');
  if (bar) bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
}

function stopPolling() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

async function pollJob(jobId) {
  try {
    const j = await api(`/api/jobs/${jobId}`);
    state.currentJob = j;
    setProgress(j.progress || 0);
    if (j.status === 'running' || j.status === 'queued') {
      $('#scan-status').textContent = `Running ${j.stage || 'scan'} (${j.checks_done}/${j.checks_total})… ${j.progress || 0}%`;
      return;
    }
    stopPolling();
    $('#run-scan').disabled = false;
    $('#cancel-scan').style.display = 'none';
    if (j.status === 'done' && j.report) {
      renderReport(j.report);
      $('#scan-status').textContent = `Scan complete. Policy ${j.report.policy_passed ? 'PASS' : 'FAIL'}.`;
    } else if (j.status === 'cancelled') {
      $('#scan-status').textContent = 'Scan cancelled.';
      setProgress(0);
    } else {
      $('#scan-status').textContent = `Error: ${j.error || 'unknown'}`;
      setProgress(0);
    }
  } catch (e) {
    stopPolling();
    $('#run-scan').disabled = false;
    $('#cancel-scan').style.display = 'none';
    $('#scan-status').textContent = `Error: ${e.message}`;
  }
}

async function runScan() {
  const btn = $('#run-scan');
  btn.disabled = true;
  $('#cancel-scan').style.display = 'inline-flex';
  setProgress(5);
  $('#scan-status').textContent = 'Queuing scan…';
  try {
    const target = $('#target').value.trim();
    const res = await api('/api/scan', { method: 'POST', body: JSON.stringify({ path: target }) });
    state.currentJob = { id: res.job_id };
    stopPolling();
    state.pollTimer = setInterval(() => pollJob(res.job_id), 600);
    pollJob(res.job_id);
  } catch (e) {
    btn.disabled = false;
    $('#cancel-scan').style.display = 'none';
    $('#scan-status').textContent = `Error: ${e.message}`;
    setProgress(0);
  }
}

async function cancelScan() {
  if (!state.currentJob?.id) return;
  try { await api(`/api/jobs/${state.currentJob.id}/cancel`, { method: 'POST' }); } catch {}
  $('#scan-status').textContent = 'Cancelling…';
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
    $('#inventory-table tbody').innerHTML = (data.symbols || []).map(s => `<tr><td>${esc(s.name)}</td><td>${esc(s.file)}</td><td>${s.line}</td></tr>`).join('') || '<tr><td colspan="3" class="empty-cell"><strong>No symbols found</strong><span>Load inventory to browse public symbols.</span></td></tr>';
  } catch (e) { $('#inventory-table tbody').innerHTML = `<tr><td colspan="3" class="empty-cell"><strong>Could not load inventory</strong><span>${esc(e.message)}</span></td></tr>`; }
}

async function loadPolicy() {
  try {
    const target = $('#target').value.trim();
    const data = await api(`/api/policy?path=${encodeURIComponent(target)}`);
    $('#policy-json').textContent = JSON.stringify(data, null, 2);
  } catch (e) { $('#policy-json').textContent = `Error: ${e.message}`; }
}

function renderTrend(reports) {
  const el = $('#trend');
  if (!el) return;
  const pts = [...reports].reverse().filter(r => typeof r.score === 'number');
  if (pts.length < 2) { el.innerHTML = '<p class="muted small">Need at least two saved reports to show a trend.</p>'; return; }
  const w = 420, h = 120, pad = 8;
  const min = Math.min(...pts.map(p => p.score)), max = Math.max(...pts.map(p => p.score));
  const range = (max - min) || 1;
  const xs = pts.map((_, i) => pad + (i / (pts.length - 1)) * (w - pad * 2));
  const ys = pts.map(p => h - pad - ((p.score - min) / range) * (h - pad * 2));
  const d = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" role="img" aria-label="Score trend">
    <path d="${d}" fill="none" stroke="#5ca38a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    ${xs.map((x, i) => `<circle cx="${x.toFixed(1)}" cy="${ys[i].toFixed(1)}" r="3" fill="#5ca38a"/>`).join('')}
  </svg><p class="muted small">Latest: ${fmt(last.score)} (${last.grade}) · ${pts.length} reports</p>`;
}

async function loadHistory() {
  try {
    const target = $('#target').value.trim();
    const data = await api(`/api/history?path=${encodeURIComponent(target)}`);
    const reports = data.reports || [];
    $('#history-table tbody').innerHTML = reports.map(r => `<tr>
      <td>${esc(new Date(r.generated_at).toLocaleString())}</td><td>${esc(r.project)}</td><td>${fmt(r.score)}</td><td>${esc(r.grade)}</td>
      <td><span class="badge ${r.policy_passed ? 'pass' : 'fail'}">${r.policy_passed ? 'PASS' : 'FAIL'}</span></td>
      <td><button class="ghost" data-load-report="${esc(r.file)}">Load</button></td>
    </tr>`).join('') || '<tr><td colspan="6" class="empty-cell"><strong>No saved reports yet</strong><span>Run a scan to create report history.</span></td></tr>';
    $$('#history-table [data-load-report]').forEach(btn => btn.addEventListener('click', async () => {
      const report = await api(`/api/report?path=${encodeURIComponent(target)}&file=${encodeURIComponent(btn.dataset.loadReport)}`);
      renderReport(report); setView('dashboard');
    }));
    renderTrend(reports);
  } catch (e) { $('#history-table tbody').innerHTML = `<tr><td colspan="6" class="empty-cell"><strong>Could not load history</strong><span>${esc(e.message)}</span></td></tr>`; }
}

$$('.nav-btn').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));
$('#run-scan').addEventListener('click', runScan);
$('#cancel-scan').addEventListener('click', cancelScan);
$('#status-filter').addEventListener('change', renderResults);
$('#finding-search').addEventListener('input', renderFindings);
$('#refresh-doctor').addEventListener('click', loadDoctor);
$('#load-inventory').addEventListener('click', loadInventory);
$('#load-policy').addEventListener('click', () => { loadPolicy(); loadDoctor(); });
$('#load-history').addEventListener('click', loadHistory);
$('#open-reports').addEventListener('click', async () => {
  try { await api('/api/open-reports', { method: 'POST', body: JSON.stringify({ path: $('#target').value.trim() }) }); }
  catch (e) { alert(e.message); }
});

(async function init() {
  try { const info = await api('/api/info'); $('#target').value = info.default_target || ''; } catch {}
  loadDoctor();
  loadHistory();
})();
