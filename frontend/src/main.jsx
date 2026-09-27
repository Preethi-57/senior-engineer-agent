import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const API_KEY = import.meta.env.VITE_API_KEY || 'local-dev-key';

function normalizeRun(payload) {
  const run = payload && typeof payload === 'object' ? payload : {};
  const metrics = run.metrics && typeof run.metrics === 'object' ? run.metrics : {};
  return {
    ...run,
    status: run.status || 'READY',
    findings: Array.isArray(run.findings) ? run.findings : [],
    proposals: Array.isArray(run.proposals) ? run.proposals : [],
    tool_events: Array.isArray(run.tool_events) ? run.tool_events : [],
    metrics: {
      findings: metrics.findings ?? 0,
      critical_high_findings: metrics.critical_high_findings ?? 0,
      approved_fixes: metrics.approved_fixes ?? 0,
      patches_applied: metrics.patches_applied ?? 0,
      tests_passed: metrics.tests_passed ?? 0,
      tests_failed: metrics.tests_failed ?? 0,
      security_findings_before: metrics.security_findings_before ?? 0,
      security_findings_after: metrics.security_findings_after ?? 0,
      tool_calls: metrics.tool_calls ?? 0,
      llm_calls: metrics.llm_calls ?? 0,
      llm_input_tokens: metrics.llm_input_tokens ?? 0,
      llm_output_tokens: metrics.llm_output_tokens ?? 0,
      elapsed_ms: metrics.elapsed_ms ?? 0,
      before: metrics.before || {},
      after: metrics.after || {},
    },
  };
}

function App() {
  const [url, setUrl] = useState('');
  const [run, setRun] = useState(null);
  const [execution, setExecution] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState('');
  const [tab, setTab] = useState('findings');

  async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) }; if (API_KEY) headers['X-API-Key'] = API_KEY; const r = await fetch(API + path, { ...options, headers }); const d = await r.json();
    if (!r.ok) throw Error(d.detail || d.error || 'Request failed'); return d;
  }
  async function create() {
    if (!url.trim()) return setError('Enter a repository URL.');
    setError(''); setLoading(true);
    try {
      const created = await request('/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_url: url, description: 'Perform evidence-grounded security, reliability, architecture, scalability and performance analysis.' }) });
      const first = normalizeRun(created); setRun(first);
      const analyzed = await request(`/runs/${first.id}/analyze`, { method: 'POST' });
      setRun(normalizeRun({ ...first, ...analyzed, metrics: { ...first.metrics, ...(analyzed.metrics || {}) } }));
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  async function approve() {
    const current = normalizeRun(run);
    try { const d = await request(`/runs/${current.id}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ finding_ids: [...selected] }) }); setRun(normalizeRun(d)) } catch (e) { setError(e.message) }
  }
  async function execute() {
    const current = normalizeRun(run);
    setError(''); setLoading(true);
    try { const d = await request(`/runs/${current.id}/execute`, { method: 'POST' }); setRun(normalizeRun(d.run || d)); setExecution(d || null) } catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  const runData = normalizeRun(run);
  const findings = runData.findings || [];
  const selectedCount = selected.size;
  const resolved = execution?.resolved_findings || 0; const pr = execution?.pull_request;
  const scannerSummary = useMemo(() => Object.entries(execution?.verification || {}).map(([k, v]) => ({ name: k, ok: v.returncode === 0, code: v.returncode })), [execution]);
  return <div className="shell">
    <header><div><span className="eyebrow">REPOSITORY REVIEW</span><h1>Repository Review</h1><p>Assess code quality, operational risk, and remediation readiness with evidence.</p></div><div className="status">{runData.status}</div></header>
    <section className="hero"><form className="inputrow" onSubmit={e => { e.preventDefault(); create(); }}><input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://github.com/owner/repository" /><button type="submit" disabled={loading}>{loading ? 'Reviewing…' : 'Review repository'}</button></form><div className="trustline"><span>SECURITY</span><span>ARCHITECTURE</span><span>PERFORMANCE</span><span>APPROVAL FLOW</span><span>EVIDENCE</span><span>VERIFY</span></div></section>
    {error && <div className="error">{error}</div>}
    {runData && <>
      <section className="metrics">
        <Card n={findings.length} l="Findings" /><Card n={runData.metrics.critical_high_findings} l="Critical / High" /><Card n={runData.metrics.llm_calls} l="LLM calls" /><Card n={runData.metrics.tool_calls} l="Tool calls" /><Card n={runData.metrics.llm_input_tokens + runData.metrics.llm_output_tokens} l="LLM tokens" />
      </section>
      <section className="panel tabs"><button className={tab === 'findings' ? 'tab active' : 'tab'} onClick={() => setTab('findings')}>Findings</button><button className={tab === 'proposals' ? 'tab active' : 'tab'} onClick={() => setTab('proposals')}>Remediation</button><button className={tab === 'verification' ? 'tab active' : 'tab'} onClick={() => setTab('verification')}>Verification</button></section>
      {tab === 'findings' && <section className="panel"><div className="panelhead"><div><h2>Evidence-backed findings</h2><p>Specialist agents combine repository RAG with deterministic scanners. Select findings for remediation.</p></div><div><button className="secondary" onClick={() => setSelected(new Set(findings.map(f => f.id)))}>Select all</button><button className="secondary" onClick={approve} disabled={!selectedCount}>Approve {selectedCount}</button></div></div><div className="findings">{findings.map(f => <label className="finding" key={f.id}><input type="checkbox" checked={selected.has(f.id)} onChange={e => { const s = new Set(selected); e.target.checked ? s.add(f.id) : s.delete(f.id); setSelected(s) }} /><div className={'badge ' + f.severity}>{f.severity}</div><div className="fbody"><div className="titleline"><h3>{f.title}</h3><span>{f.confidence.toFixed(2)} confidence</span></div><p>{f.description}</p><div className="meta">{f.category} · {f.source_agent} · {(f.files || []).join(', ')} {(f.line_refs || []).join(', ')}</div><pre>{(f.evidence || []).join('\n')}</pre><details><summary>Root cause & impact</summary><p><strong>Root cause:</strong> {f.root_cause}</p><p><strong>Impact:</strong> {f.impact}</p></details></div></label>)}</div></section>}
      {tab === 'proposals' && <section className="panel"><div className="panelhead"><div><h2>Approval-gated remediation</h2><p>Approval is required before any code is changed. Execution occurs in a detached workspace.</p></div><button onClick={execute} disabled={loading || !runData.metrics.approved_fixes}>{loading ? 'Executing…' : 'Apply approved fixes & verify'}</button></div>{runData.proposals.map(p => <div className="proposal" key={p.finding_id}><div><strong>{p.summary}</strong><p>{p.rationale}</p><div className="meta">{(p.files || []).join(', ')}</div>{p.patch_preview && <pre>{p.patch_preview}</pre>}</div><span className={p.approved ? 'approved' : 'pending'}>{p.approved ? 'APPROVED' : 'PENDING'}</span></div>)}</section>}
      {tab === 'verification' && <section className="panel"><div className="verifygrid"><MetricBlock n={runData.metrics.patches_applied} l="Patches applied" /><MetricBlock n={resolved} l="Findings resolved" /><MetricBlock n={runData.metrics.security_findings_before} l="Security before" /><MetricBlock n={runData.metrics.security_findings_after} l="Security after" /><MetricBlock n={execution?.repair_attempts || 0} l="Repair attempts" /></div>{execution && <><h2>Verification gates</h2><div className="checks">{scannerSummary.map(x => <div className={x.ok ? 'check pass' : 'check fail'} key={x.name}><span>{x.ok ? 'PASS' : 'FAIL'}</span><strong>{x.name}</strong><small>exit code {x.code}</small></div>)}</div>{pr && <div className="pr"><strong>Pull request created</strong><a href={pr.url} target="_blank" rel="noreferrer">#{pr.number} · Open PR</a></div>}<h2>Resulting diff</h2><pre className="diff">{execution.diff || 'No changes were applied.'}</pre></>}</section>}
    </>}
  </div>
}
function Card({ n, l }) { return <div className="card"><strong>{n}</strong><span>{l}</span></div> }
function MetricBlock({ n, l }) { return <div className="metricblock"><strong>{n}</strong><span>{l}</span></div> }
createRoot(document.getElementById('root')).render(<App />);
