import { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, CheckCircle2, ChevronDown, ClipboardCheck, FileText, LoaderCircle, TriangleAlert } from 'lucide-react';
import { METRICS, number } from '../types';
import type { EvaluationReport, EvaluationSubset, InvestigationView, Job, MetricId } from '../types';

const SUBSETS: Record<string, string> = { empty: 'Neither condition', a: 'Condition A only', b: 'Condition B only', ab: 'Both conditions' };
const METRIC_ORDER: MetricId[] = ['flood_volume_m3', 'peak_downstream_flow_m3s', 'downstream_excess_volume_m3', 'terminal_storage_m3'];
async function get<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(String(body.error ?? body.message ?? response.statusText));
  return body as T;
}
function human(value: string) { return value.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()); }
function formatValue(value: unknown): string { return value !== null && typeof value === 'object' ? JSON.stringify(value) : String(value); }
function clarificationText(content: string | Record<string, unknown>): string { return typeof content === 'string' ? content : Object.entries(content).map(([key, value]) => `${human(key)}: ${formatValue(value)}`).join('\n\n'); }
function timing(transform: Record<string, unknown>): string { const shifts = transform.fault_time_shift_s; return shifts && typeof shifts === 'object' ? Object.entries(shifts).map(([kind, value]) => `${kind.startsWith('sensor') ? 'Sensor' : 'Valve'} ${Number(value) >= 0 ? '+' : ''}${number(Number(value) / 60)} min`).join(' · ') : `Timing ${Number(transform.time_shift_s) >= 0 ? '+' : ''}${number(Number(transform.time_shift_s) / 60)} min`; }
function delta(value: number, precision = 4) { return `${value > 0 ? '+' : ''}${number(value, precision)}`; }
function save(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function policyName(policy: { controller_id: string; parameters: Record<string, number> }) { return `${human(policy.controller_id)} (${Object.entries(policy.parameters).map(([key, value]) => `${human(key)} ${number(value, 4)}`).join(', ') || 'no parameters'})`; }
function rememberEvaluation(id: string) { const url = new URL(window.location.href); url.searchParams.set('evaluation', id); window.history.replaceState({}, '', url); }

function downloadDecision(report: EvaluationReport, source: string) {
  const escape = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]!));
  const aggregate = report.holdout.aggregate_metrics;
  const before = Number(aggregate.joint_aggregate_reference_flood_m3);
  const after = Number(aggregate.joint_aggregate_candidate_flood_m3);
  const material = report.holdout.cases.filter(test => test.subsets.find(row => row.subset === 'ab')?.material_flood_improvement).length;
  const primaryAllowance = Number(report.holdout.criteria.maximum_primary_increase_m3_each_case);
  const regressions = report.holdout.cases.reduce((sum, test) => sum + test.subsets.filter(row => row.changes.flood_volume_m3 > primaryAllowance + .000001).length, 0);
  const decisionLine = `Aggregate joint flooding: ${number(before, 2)} → ${number(after, 2)} m³${before > 0 ? ` (${delta((after - before) / before * 100, 2)}%)` : ''}. ${material} of ${report.holdout.case_count} perturbations met the individual material-improvement criterion. ${regressions} condition subsets exceeded the +${number(primaryAllowance)} m³ primary non-regression allowance.`;
  const clarification = report.information_boundary_clarification;
  const clarificationHtml = clarification ? `<h2>Information-boundary clarification</h2><p>Source: ${escape(clarification.path)}<br>SHA-256: <code>${escape(clarification.sha256)}</code></p><p style="white-space:pre-wrap">${escape(clarificationText(clarification.content))}</p>` : '';
  const rows = report.holdout.cases.flatMap(test => test.status === 'completed' ? test.subsets.map(subset => `<tr><th>${escape(test.case_id)} · ${escape(SUBSETS[subset.subset] ?? subset.subset)}</th><td>${number(subset.reference_metrics.flood_volume_m3, 5)}</td><td>${number(subset.candidate_metrics.flood_volume_m3, 5)}</td>${METRIC_ORDER.map(metric => `<td>${escape(delta(subset.changes[metric], 6))}</td>`).join('')}<td>${subset.all_guards_pass ? 'Pass' : 'FAIL'}</td></tr>`) : [`<tr><th>${escape(test.case_id)}</th><td colspan="7">INVALID: ${escape(test.error)}</td></tr>`]).join('');
  const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>StormPilot decision report</title><style>body{font:15px/1.6 system-ui,sans-serif;max-width:1200px;margin:48px auto;padding:0 28px;color:#203738}h1{font-size:34px;letter-spacing:-1px}h2{margin-top:36px}table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;border-bottom:1px solid #d8dfd8;padding:9px;vertical-align:top}code{overflow-wrap:anywhere}li{margin:6px 0}.verdict{border-left:4px solid ${report.acceptance.overall ? '#24746b' : '#a44031'};padding:12px 20px;background:#f2f5ef}.scroll{overflow-x:auto}@media print{body{margin:0;padding:12px;font-size:11px}h1{font-size:23px}table{font-size:8px}td,th{padding:5px}tr{break-inside:avoid}}</style><body><p>STORMPILOT · SIMULATION EVIDENCE</p><h1>${report.suite_type === 'declared_robustness' ? 'Declared robustness decision report' : 'Recorded benchmark evaluation'}</h1><p>Source: <code>${escape(source)}</code><br>Completed: ${escape(report.completed_at_utc)}</p><div class="verdict"><strong>${report.acceptance.overall ? 'All declared criteria met' : 'Candidate rejected by these criteria'}</strong><p>${escape(report.conclusion)}</p><p>${escape(decisionLine)}</p><p>Required by this suite: at least ${number(Number(report.holdout.criteria.joint_case_aggregate_minimum_relative_reduction) * 100)}% aggregate joint-flood reduction and ${number(Number(report.holdout.criteria.minimum_joint_cases_with_10m3_and_10pct_individual_reduction))} individually improved perturbations, with every declared guard and non-regression check satisfied.</p></div><h2>Recorded policies</h2><p>Reference: ${escape(policyName(report.reference))}<br>Candidate: ${escape(policyName(report.candidate))}</p><p>${report.holdout.policy_run_count} completed policy runs / ${report.holdout.expected_policy_run_count} expected across ${report.holdout.case_count} perturbations.</p><h2>Complete outcome table</h2><p>Flooding in m³. Δ is candidate minus reference. Guard allowances: ${Object.entries(report.holdout.guard_allowances).map(([key, value]) => `${escape(METRICS[key as MetricId]?.label ?? key)} +${number(value, 6)} ${escape(METRICS[key as MetricId]?.unit ?? '')}`).join('; ')}.</p><div class="scroll"><table><thead><tr><th>Case / conditions</th><th>Reference flood</th><th>Candidate flood</th>${METRIC_ORDER.map(metric => `<th>Δ ${escape(METRICS[metric].label)} (${escape(METRICS[metric].unit)})</th>`).join('')}<th>Guards</th></tr></thead><tbody>${rows}</tbody></table></div><h2>Declared transformations</h2><ul>${report.holdout.cases.map(test => `<li><strong>${escape(test.case_id)}</strong>: ${Object.entries(test.transform).filter(([key]) => key !== 'id').map(([key, value]) => `${escape(human(key))} ${escape(formatValue(value))}`).join('; ')}</li>`).join('')}</ul><h2>Scope and limitations</h2><ul>${report.limitations.map(value => `<li>${escape(value)}</li>`).join('')}</ul>${clarificationHtml}<h2>Evidence identities</h2><p>Protocol: ${escape(report.protocol.id)}<br><code>${escape(report.protocol.sha256)}</code><br>Frozen: ${escape(report.protocol.frozen_at_utc)}</p><p>Candidate snapshot SHA-256:<br><code>${escape(report.candidate_snapshot_sha256)}</code></p><ul>${Object.entries(report.matching_identity).map(([key, value]) => `<li>${escape(human(key))}: <code>${escape(value)}</code></li>`).join('')}</ul><p>The machine-readable report preserves the complete reported metrics, criteria, transforms and trace identities. A report alone is not a field safety certificate.</p></body></html>`;
  save(`stormpilot-decision-${source.replace(/[^a-z0-9-]/gi, '-').slice(0, 60)}.html`, html, 'text/html;charset=utf-8');
}

function OutcomeRows({ rows, primaryAllowance }: { rows: EvaluationSubset[]; primaryAllowance: number }) {
  return <>{rows.map(row => <tr key={row.subset}><th scope="row">{SUBSETS[row.subset] ?? row.subset}</th><td>{number(row.reference_metrics.flood_volume_m3, 3)}</td><td>{number(row.candidate_metrics.flood_volume_m3, 3)}</td>{METRIC_ORDER.map(metric => <td key={metric} className={row.guards[metric] === false || metric === 'flood_volume_m3' && row.changes[metric] > primaryAllowance + .000001 ? 'guard-fail' : ''}>{delta(row.changes[metric], metric === 'peak_downstream_flow_m3s' ? 6 : 3)}</td>)}<td><span className={`criterion-result ${row.all_guards_pass ? 'pass' : 'fail'}`}>{row.all_guards_pass ? 'Pass' : 'Fail'}</span></td></tr>)}</>;
}

function Report({ report, source, evaluationId, frozenPhase }: { report: EvaluationReport; source: string; evaluationId: string | null; frozenPhase: 1 | 2 | null }) {
  const aggregate = report.holdout.aggregate_metrics;
  const failedSubsets = report.holdout.cases.reduce((sum, test) => sum + test.subsets.filter(row => !row.all_guards_pass).length, 0);
  const invalidCases = report.holdout.cases.filter(test => test.status !== 'completed').length;
  const primaryAllowance = Number(report.holdout.criteria.maximum_primary_increase_m3_each_case);
  const primaryRegressions = report.holdout.cases.reduce((sum, test) => sum + test.subsets.filter(row => row.changes.flood_volume_m3 > primaryAllowance + .000001).length, 0);
  const materialCases = report.holdout.cases.filter(test => test.subsets.find(row => row.subset === 'ab')?.material_flood_improvement).length;
  const before = Number(aggregate.joint_aggregate_reference_flood_m3);
  const after = Number(aggregate.joint_aggregate_candidate_flood_m3);
  const percent = before > 0 ? (after - before) / before * 100 : null;
  const suiteFailures: string[] = [];
  const minimumRelative = Number(report.holdout.criteria.joint_case_aggregate_minimum_relative_reduction);
  const minimumMaterialCases = Number(report.holdout.criteria.minimum_joint_cases_with_10m3_and_10pct_individual_reduction);
  if (Number.isFinite(minimumRelative) && percent != null && -percent < minimumRelative * 100 - .000001) suiteFailures.push(`The suite requires at least ${number(minimumRelative * 100)}% aggregate joint-flood reduction.`);
  if (Number.isFinite(minimumMaterialCases) && materialCases < minimumMaterialCases) suiteFailures.push(`Only ${materialCases} perturbations meet the individual improvement criterion; at least ${minimumMaterialCases} are required.`);
  for (const test of report.holdout.cases) for (const subset of test.subsets) for (const [metric, passed] of Object.entries(subset.guards)) if (!passed) suiteFailures.push(`${test.case_id.toUpperCase()} · ${SUBSETS[subset.subset] ?? subset.subset}: ${METRICS[metric as MetricId]?.label ?? human(metric)} increased ${number(subset.changes[metric as MetricId], 6)} ${METRICS[metric as MetricId]?.unit ?? ''}; allowance ${number(report.holdout.guard_allowances[metric], 6)} ${METRICS[metric as MetricId]?.unit ?? ''}.`);
  return <div className="evaluation-report"><div className="evaluation-source"><span>{report.suite_type === 'declared_robustness' ? 'Declared robustness suite' : 'Recorded, frozen benchmark evaluation'}</span><p>Source <code>{source}</code> · {new Date(report.completed_at_utc).toLocaleString('en', { dateStyle: 'medium', timeStyle: 'short' })}</p></div>
    <div className={`evaluation-verdict ${report.acceptance.overall ? 'pass' : 'fail'}`}>{report.acceptance.overall ? <CheckCircle2 size={21} /> : <TriangleAlert size={21} />}<div><h3>{report.acceptance.overall ? 'All declared criteria met.' : 'Candidate rejected by these criteria.'}</h3><p>{report.conclusion}</p>{Number.isFinite(before) && Number.isFinite(after) && <p className="evaluation-key-outcome"><strong>Aggregate joint flooding {after > before ? 'increased' : 'decreased'} by {number(Math.abs(after - before), 2)} m³{percent != null ? ` (${percent > 0 ? '+' : ''}${number(percent, 2)}%)` : ''}.</strong> {materialCases} of {report.holdout.case_count} perturbations met the individual material-improvement criterion.</p>}</div></div>
    {!!suiteFailures.length && <div className="evaluation-failure-reasons"><strong>Why the suite does not pass</strong><ul>{suiteFailures.map((reason, index) => <li key={index}>{reason}</li>)}</ul></div>}
    <div className="evaluation-policy-pair"><div><span>Frozen reference</span><strong>{policyName(report.reference)}</strong></div><ArrowRight size={18} /><div><span>Frozen candidate</span><strong>{policyName(report.candidate)}</strong></div></div>
    <div className="evaluation-criteria" aria-label="Separate acceptance criteria">{[['Base-case joint failure', report.acceptance.development_joint_failure], ['Base-case response', report.acceptance.development_mitigation], ['Suite usefulness', report.acceptance.suite_usefulness ?? report.acceptance.heldout_usefulness]].map(([label, passed]) => <span key={String(label)} className={passed ? 'pass' : 'fail'}>{passed ? <CheckCircle2 size={13} /> : <TriangleAlert size={13} />}{label}: {passed ? 'pass' : 'fail'}</span>)}</div>
    <div className="discovery-accounting"><div><strong>{report.holdout.policy_run_count}<small> / {report.holdout.expected_policy_run_count}</small></strong><span>Completed policy runs</span></div><div><strong>{number(Number(aggregate.joint_aggregate_reference_flood_m3), 2)}</strong><span>Reference joint flooding · m³</span></div><div><strong>{number(Number(aggregate.joint_aggregate_candidate_flood_m3), 2)}</strong><span>Candidate joint flooding · m³</span></div><div><strong>{failedSubsets}</strong><span>Condition subsets with failed guards</span></div></div>
    {!!primaryRegressions && <p className="evaluation-regression-note"><TriangleAlert size={15} />Flooding increased beyond the +{number(primaryAllowance)} m³ allowance in {primaryRegressions} of {report.holdout.cases.reduce((sum, test) => sum + test.subsets.length, 0)} evaluated condition subsets.</p>}
    {!!invalidCases && <div className="evaluation-invalid" role="alert"><TriangleAlert size={16} />{invalidCases} invalid case{invalidCases === 1 ? '' : 's'} retained. These prevent a complete-success claim.</div>}
    <div className="evaluation-case-list"><div className="evaluation-table-heading"><h3>Every declared perturbation</h3><p>Open each case to inspect all four condition subsets and every metric.</p></div>{report.holdout.cases.map(test => { const joint = test.subsets.find(row => row.subset === 'ab'); const fails = test.subsets.filter(row => !row.all_guards_pass).length; const primaryFails = test.subsets.filter(row => row.changes.flood_volume_m3 > primaryAllowance + .000001).length; return <details key={test.case_id} className="evaluation-case" open={Boolean(fails) || Boolean(primaryFails) || test.status !== 'completed'}><summary><span className="evaluation-case-id">{test.case_id.toUpperCase()}</span><span className="case-transform-summary">Rainfall {number(Number(test.transform.rainfall_multiplier))}×<small>{timing(test.transform)} · duration {number(Number(test.transform.duration_scale))}×</small></span><span className="case-joint-result">{number(joint?.reference_metrics.flood_volume_m3, 2)} → {number(joint?.candidate_metrics.flood_volume_m3, 2)}<small>joint flooding · m³</small></span><span className={`criterion-result ${test.status !== 'completed' || fails || primaryFails ? 'fail' : 'pass'}`}>{test.status !== 'completed' ? 'Invalid' : fails ? `${fails} guard failure${fails === 1 ? '' : 's'}` : primaryFails ? `${primaryFails} flood regressions` : 'Guards pass'}</span><ChevronDown size={14} /></summary><div className="evaluation-case-content"><p>{Object.entries(test.transform).filter(([key]) => key !== 'id').map(([key, value]) => `${human(key)}: ${formatValue(value)}`).join(' · ')}</p>{test.status !== 'completed' ? <p className="field-error">{test.error ?? 'This case did not produce a complete validated result.'}</p> : <div className="campaign-table-wrap" role="region" tabIndex={0} aria-label={`${test.case_id} complete physical outcomes; scroll horizontally if needed`}><table className="campaign-table evaluation-table"><caption>{test.case_id.toUpperCase()}: all condition subsets. Δ is candidate minus reference.</caption><thead><tr><th scope="col">Conditions</th><th scope="col">Reference flood<small>m³</small></th><th scope="col">Candidate flood<small>m³</small></th>{METRIC_ORDER.map(metric => <th scope="col" key={metric}>Δ {METRICS[metric].label}<small>{METRICS[metric].unit}</small></th>)}<th scope="col">Guards</th></tr></thead><tbody><OutcomeRows rows={test.subsets} primaryAllowance={primaryAllowance} /></tbody></table></div>}</div></details>; })}</div>
    <details className="campaign-details"><summary>Criteria, guard allowances and identity <ChevronDown size={13} /></summary><dl>{Object.entries(report.holdout.guard_allowances).map(([metric, allowance]) => <div key={metric}><dt>{METRICS[metric as MetricId]?.label ?? human(metric)}</dt><dd>Maximum increase +{number(allowance, 6)} {METRICS[metric as MetricId]?.unit}</dd></div>)}{Object.entries(report.holdout.criteria).map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd>{typeof value === 'boolean' ? value ? 'Required' : 'Not required' : String(value)}</dd></div>)}<div><dt>Protocol</dt><dd>{report.protocol.id}</dd></div><div><dt>Protocol SHA-256</dt><dd><code>{report.protocol.sha256}</code></dd></div><div><dt>Candidate snapshot SHA-256</dt><dd><code>{report.candidate_snapshot_sha256}</code></dd></div>{Object.entries(report.matching_identity).map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd><code>{value}</code></dd></div>)}</dl></details>
    {report.information_boundary_clarification && <details className="campaign-details information-boundary-details"><summary>Information-boundary clarification <ChevronDown size={13} /></summary><p>{clarificationText(report.information_boundary_clarification.content)}</p><dl><div><dt>Source</dt><dd>{report.information_boundary_clarification.path}</dd></div><div><dt>SHA-256</dt><dd><code>{report.information_boundary_clarification.sha256}</code></dd></div></dl></details>}<ul className="evaluation-limitations">{report.limitations.map(limitation => <li key={limitation}>{limitation}</li>)}</ul><div className="evaluation-exports"><button className="button primary" onClick={() => downloadDecision(report, source)}><FileText size={16} />Download decision report</button><button className="button secondary" onClick={() => save(`stormpilot-evaluation-${evaluationId ?? source.replace(/[^a-z0-9-]/gi, '-').slice(0, 60)}.json`, JSON.stringify(report, null, 2), 'application/json')}><ArrowDownToLine size={15} />Complete data · JSON</button>{evaluationId && <a className="text-button" href={`/api/evaluations/${encodeURIComponent(evaluationId)}/export`} download>Evaluation evidence bundle <ArrowDownToLine size={14} /></a>}{frozenPhase && !evaluationId && <a className="text-button" href={frozenPhase === 2 ? '/api/evaluation/phase2/export' : '/api/evaluation/export'} download>Export frozen evidence <ArrowDownToLine size={14} /></a>}</div>
  </div>;
}

export default function EvaluationPanel({ view, busy }: { view: InvestigationView; busy: boolean }) {
  const [job, setJob] = useState<Job | null>(null);
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [source, setSource] = useState('');
  const [evaluationId, setEvaluationId] = useState<string | null>(null);
  const [frozenPhase, setFrozenPhase] = useState<1 | 2 | null>(null);
  const activeId = useRef<string | null>(null);
  const reportHeading = useRef<HTMLHeadingElement>(null);
  const faults = (view.cases.find(run => run.role === 'reduced') ?? view.cases.find(run => run.role === 'stress'))?.faults ?? [];
  const supported = faults.length === 2 && faults.some(fault => ['sensor_bias', 'sensor_dropout'].includes(String(fault.type))) && faults.some(fault => fault.type === 'valve_stuck') && view.config.metric === 'flood_volume_m3';
  const running = loading || Boolean(job && ['queued', 'running'].includes(job.status));
  useEffect(() => {
    activeId.current = null; setJob(null); setReport(null); setSource(''); setError(''); setEvaluationId(null); setFrozenPhase(null);
    const saved = new URL(window.location.href).searchParams.get('evaluation');
    if (!saved || !['benchmark', 'phase2'].includes(saved) && !/^[a-f0-9]{16}$/.test(saved)) return;
    let cancelled = false;
    setLoading(true);
    async function restore() {
      try {
        if (saved === 'benchmark' || saved === 'phase2') {
          const next = await get<EvaluationReport>(saved === 'phase2' ? '/api/evaluation/phase2' : '/api/evaluation');
          if (!cancelled) { setReport(next); setFrozenPhase(saved === 'phase2' ? 2 : 1); setSource(saved === 'phase2' ? 'Recorded Theta benchmark · phase 2' : 'Recorded Theta benchmark · phase 1'); }
        } else {
          const next = await get<Job>(`/api/evaluations/${saved}`);
          if (cancelled) return;
          activeId.current = saved; setEvaluationId(saved); setSource(`Evaluation ${saved}`); setJob(next);
          if (next.status === 'completed') { const result = await get<EvaluationReport>(`/api/evaluations/${saved}/result`); if (!cancelled) setReport(result); }
          else if (next.status === 'failed') setError(next.error ?? 'The recorded evaluation did not complete.');
        }
      } catch (cause) { if (!cancelled) setError(cause instanceof Error ? cause.message : 'The saved evaluation could not be restored.'); }
      finally { if (!cancelled) setLoading(false); }
    }
    void restore();
    return () => { cancelled = true; };
  }, [view.id]);
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const next = await get<Job>(`/api/evaluations/${job.id}`);
        if (cancelled || activeId.current !== job.id) return;
        if (next.status === 'completed') {
          const result = await get<EvaluationReport>(`/api/evaluations/${job.id}/result`);
          if (cancelled || activeId.current !== job.id) return;
          setReport(result); setJob(next);
          requestAnimationFrame(() => reportHeading.current?.focus({ preventScroll: true }));
        } else if (next.status === 'failed') { setError(next.error ?? 'The evaluation did not finish. The original experiment remains available.'); setJob(next); }
        else setJob(next);
      } catch (cause) { if (!cancelled) { setError(cause instanceof Error ? cause.message : 'Could not read evaluation status.'); setJob(previous => previous ? { ...previous, status: 'failed' } : null); } }
    }, 900);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job]);
  async function start() {
    setLoading(true); setError(''); setReport(null); setSource(view.id); setFrozenPhase(null);
    try { const next = await get<Job>(`/api/jobs/${view.id}/evaluate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); activeId.current = next.id; setEvaluationId(next.id); setJob(next); rememberEvaluation(next.id); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not start the evaluation.'); }
    finally { setLoading(false); }
  }
  async function benchmark(phase: 1 | 2 = 1) {
    setLoading(true); setError('');
    try { const next = await get<EvaluationReport>(phase === 2 ? '/api/evaluation/phase2' : '/api/evaluation'); setReport(next); setEvaluationId(null); setFrozenPhase(phase); setSource(`Recorded Theta benchmark · phase ${phase}`); rememberEvaluation(phase === 2 ? 'phase2' : 'benchmark'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'The recorded benchmark evaluation is unavailable.'); }
    finally { setLoading(false); }
  }
  return <section id="robustness-evaluation" className="evaluation-panel panel" aria-labelledby="evaluation-title"><div className="section-heading"><div><div className="section-index"><ClipboardCheck size={15} />Evaluate the response</div><h2 id="evaluation-title" ref={reportHeading} tabIndex={-1}>Does the response hold up?</h2></div><div className="benchmark-versions" aria-label="Recorded evaluation versions"><button className="text-button benchmark-link" onClick={() => void benchmark(1)} disabled={busy || running}>Phase 1 benchmark <ArrowRight size={13} /></button><button className="text-button benchmark-link" onClick={() => void benchmark(2)} disabled={busy || running}>Phase 2 benchmark <ArrowRight size={13} /></button></div></div>
    {!report && <><p className="section-description">Run the recorded reference and alternative through six declared changes in rainfall, fault timing, duration, severity and sensor noise. Inspect every result, including invalid cases and guard failures.</p><div className="evaluation-start"><div><strong>6 perturbations · 4 condition subsets · 2 policies</strong><p>The suite preserves the recorded model’s full horizon. Its transforms are visible and reusable, so this is a declared robustness suite.</p></div><button className="button primary" disabled={busy || running || !supported} onClick={start}>{running ? <LoaderCircle size={16} className="spin" /> : <ClipboardCheck size={16} />}Evaluate recorded response</button></div><p className="evaluation-record-note">{supported ? <>Uses source experiment <code>{view.id}</code> and its recorded alternative parameters. Draft setup changes do not alter this evaluation.</> : 'This suite requires a recorded sensor fault and valve fault, an alternative policy, and a flooding-volume check. Run compound discovery to create a supported case.'}</p></>}
    {running && <div className="evaluation-progress" role="status"><LoaderCircle size={18} className="spin" /><div><strong>{loading ? 'Preparing evaluation' : human(job?.phase ?? 'Running evaluation')}</strong><p>{loading ? 'Preparing the recorded comparison. The request may take a moment before progress is available.' : job?.message ?? 'Loading the recorded evaluation.'}</p></div></div>}
    {error && <div className="evaluation-error" role="alert"><TriangleAlert size={17} /><p>{error}</p></div>}
    {report && <Report report={report} source={source} evaluationId={evaluationId} frozenPhase={frozenPhase} />}
  </section>;
}
