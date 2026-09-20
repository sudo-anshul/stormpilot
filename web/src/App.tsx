import { useEffect, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowRight, CheckCircle2, ChevronDown, CircleDashed, Clock3, ExternalLink, FileCheck2, FlaskConical, Info, LoaderCircle, Play, Plus, RotateCcw, Settings2, ShieldCheck, TriangleAlert, Waves, X, XCircle } from 'lucide-react';
import Hydrograph from './components/Hydrograph';
import Network from './components/Network';
import ModelImport from './components/ModelImport';
import FaultEditor, { faultAssets, faultLabel, isSensorFault } from './components/FaultEditor';
import PolicyParameters from './components/PolicyParameters';
import DiscoverySetup, { defaultDiscovery } from './components/DiscoverySetup';
import DiscoveryEvidence from './components/DiscoveryEvidence';
import RepairPanel from './components/RepairPanel';
import EvaluationPanel from './components/EvaluationPanel';
import SensorInspector from './components/SensorInspector';
import WorkspaceNavigation from './components/WorkspaceNavigation';
import { METRICS, number, caseRoleLabel, timeLabel } from './types';
import type { Catalog, ExperimentConfig, InvestigationView, Job, MetricId, Model, FaultKind, RepairSearchConfig } from './types';

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { const body = await response.json(); detail = String(body.error ?? body.message ?? detail); } catch { /* retain HTTP error */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

const fields: (keyof ExperimentConfig)[] = ['model_id', 'controller_id', 'fallback_controller_id', 'metric', 'threshold', 'fault_asset', 'start_hour', 'duration_hours', 'budget', 'rainfall_multiplier', 'noise_std_m', 'seed'];
function sameConfig(a: ExperimentConfig, b: ExperimentConfig): boolean {
  const defaults: Record<string, unknown> = { rainfall_multiplier: 1, noise_std_m: 0, seed: 42 };
  const fault = (kind?: string, setting?: number, bias?: number) => ({ kind: kind === 'stuck_closed' || !kind ? 'valve_stuck' : kind, setting: kind === 'valve_stuck' ? setting ?? 0 : 0, bias: kind === 'sensor_bias' ? bias ?? 1 : 1 });
  const extras = (config: ExperimentConfig) => (config.additional_faults ?? []).map(value => ({ asset: value.asset, start: value.start_hour, duration: value.duration_hours, ...fault(value.kind, value.setting, value.bias_m) }));
  const parameters = (id: string, values?: Record<string, number>) => { const base = id === 'uncontrolled' ? {} : { target_scale: 1, ...(id === 'equal_filling' ? { equal_filling_gain: 1 } : id === 'balanced_flow' ? { balance_gain: 1 } : {}) }; return Object.entries({ ...base, ...values }).sort(([a], [b]) => a.localeCompare(b)); };
  return fields.every(key => String(a[key] ?? defaults[key]) === String(b[key] ?? defaults[key])) && JSON.stringify(fault(a.fault_kind, a.fault_setting, a.sensor_bias_m)) === JSON.stringify(fault(b.fault_kind, b.fault_setting, b.sensor_bias_m)) && JSON.stringify(extras(a)) === JSON.stringify(extras(b)) && JSON.stringify(parameters(a.controller_id, a.controller_parameters)) === JSON.stringify(parameters(b.controller_id, b.controller_parameters)) && JSON.stringify(parameters(a.fallback_controller_id, a.fallback_controller_parameters)) === JSON.stringify(parameters(b.fallback_controller_id, b.fallback_controller_parameters)) && (a.mode === 'discover') === (b.mode === 'discover') && (b.mode !== 'discover' || JSON.stringify(a.discovery) === JSON.stringify(b.discovery));
}
function human(value: string | null | undefined) { return value ? value.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()) : 'Not available'; }
function engineLabel(value: string) { return value.toUpperCase().startsWith('EPA SWMM') ? value : `EPA SWMM ${value}`; }
function shortId(value: string) { return value.length > 18 ? `${value.slice(0, 12)}…${value.slice(-4)}` : value; }
function statusKind(status: string) {
  return ['passed', 'pass', 'valid', 'verified', 'complete', 'completed'].includes(status) ? 'pass' : ['failed', 'fail', 'invalid', 'error'].includes(status) ? 'fail' : 'pending';
}
function CheckIcon({ status }: { status: string }) { const kind = statusKind(status); return kind === 'pass' ? <CheckCircle2 size={17} /> : kind === 'fail' ? <XCircle size={17} /> : <CircleDashed size={17} />; }
function CheckRows({ checks }: { checks: InvestigationView['validation']['checks'] }) {
  return <ul className="check-list">{checks.map(check => <li key={check.id} className={statusKind(check.status)}><CheckIcon status={check.status} /><div><strong>{human(check.id)}</strong><p>{check.message}</p></div><span>{human(check.status)}</span></li>)}</ul>;
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [config, setConfig] = useState<ExperimentConfig | null>(null);
  const [view, setView] = useState<InvestigationView | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [booting, setBooting] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const repairRequest = useRef<RepairSearchConfig | undefined>(undefined);
  const [retryAction, setRetryAction] = useState<'load' | 'experiment' | 'replay' | 'repair' | 'export'>('load');
  const [notice, setNotice] = useState('');
  const [time, setTime] = useState(0);
  const [selectedCase, setSelectedCase] = useState('');
  const [exporting, setExporting] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [loadKey, setLoadKey] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const activeJobId = useRef<string | null>(null);
  const busy = submitting || job?.status === 'queued' || job?.status === 'running';
  const selectedModel = catalog?.models.find(m => m.id === config?.model_id);
  const resultModel = view?.model ?? selectedModel;
  const activeCase = view?.cases.find(c => c.id === selectedCase) ?? view?.cases.find(c => c.role === 'reduced') ?? view?.cases.find(c => c.role === 'stress') ?? view?.cases[0];
  const stale = Boolean(view && config && !sameConfig(view.config, config));
  const metric = config ? METRICS[config.metric] : null;
  const policyName = (id: string) => catalog?.policies.find(p => p.id === id)?.name ?? human(id);
  const modelSource = view ? view.provenance.source_url : selectedModel?.source;

  function displayView(next: InvestigationView) {
    setView(next);
    if (!next.recorded) {
      const url = new URL(window.location.href);
      if (url.searchParams.get('run') !== next.id) url.searchParams.delete('evaluation');
      url.searchParams.set('run', next.id);
      window.history.replaceState({}, '', url);
    }
    const stressed = next.cases.find(c => c.role === 'reduced') ?? next.cases.find(c => c.role === 'stress') ?? next.cases[0];
    setSelectedCase(stressed?.id ?? '');
    let initialTime = next.finding.first_time_s;
    if (initialTime == null && stressed?.trace.length) {
      const peak = stressed.trace.reduce((max, point) => point.total_flooding_m3s > max.total_flooding_m3s ? point : max, stressed.trace[0]);
      initialTime = peak.time_s;
    }
    setTime(initialTime ?? 0);
  }

  useEffect(() => {
    let cancelled = false;
    setBooting(true); setError('');
    const requestedId = new URL(window.location.href).searchParams.get('run');
    const request = requestedId && /^[a-f0-9]{16}$/.test(requestedId) ? api<InvestigationView>(`/api/jobs/${requestedId}/result`) : Promise.resolve(null);
    Promise.allSettled([api<Catalog>('/api/catalog'), api<InvestigationView>('/api/demo'), request]).then(([catalogResult, demoResult, requestedResult]) => {
      if (cancelled) return;
      const requested = requestedResult.status === 'fulfilled' ? requestedResult.value : null;
      const initialView = requested ?? (demoResult.status === 'fulfilled' ? { ...demoResult.value, recorded: true } : null);
      if (catalogResult.status === 'fulfilled') {
        setCatalog(catalogResult.value);
        setConfig(initialView ? { ...catalogResult.value.defaults, ...initialView.config } : catalogResult.value.defaults);
      } else setError(`The model runner is unavailable. ${catalogResult.reason instanceof Error ? catalogResult.reason.message : 'Could not load the experiment catalog.'}`);
      if (initialView) displayView(initialView);
      if (requestedResult.status === 'rejected') setError(`The requested experiment could not be restored. ${requestedResult.reason instanceof Error ? requestedResult.reason.message : ''}${initialView ? ' The recorded benchmark is shown instead.' : ''}`);
      setBooting(false);
    });
    return () => { cancelled = true; };
  }, [loadKey]);

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    let cancelled = false;
    const id = job.id;
    const timer = window.setTimeout(async () => {
      try {
        const updated = await api<Job>(`/api/jobs/${encodeURIComponent(id)}`);
        if (cancelled || activeJobId.current !== id) return;
        if (updated.status === 'completed') {
          const result = await api<InvestigationView>(`/api/jobs/${encodeURIComponent(id)}/result`);
          if (cancelled || activeJobId.current !== id) return;
          displayView(result);
          setConfig(result.config);
          setNotice(`Experiment ${shortId(result.id)} completed.`);
          setJob(updated);
          requestAnimationFrame(() => { const heading = result.repair ? document.getElementById('repair-title') : result.discovery ? document.getElementById('discovery-title') : resultHeading.current; heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' }); });
        } else if (updated.status === 'failed') {
          setError(updated.error ?? updated.message ?? 'The experiment failed. No new simulation result was produced.');
          setJob(updated);
        } else setJob(updated);
      } catch (cause) {
        if (cancelled || activeJobId.current !== id) return;
        setError(cause instanceof Error ? cause.message : 'The experiment status could not be read.');
        setJob(previous => previous ? { ...previous, status: 'failed' } : null);
      }
    }, 650);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job]);

  function updateConfig<K extends keyof ExperimentConfig>(key: K, value: ExperimentConfig[K]) {
    setConfig(previous => previous ? { ...previous, [key]: value } : previous);
    setNotice('');
  }

  function updateAdditionalFault(index: number, patch: Partial<NonNullable<ExperimentConfig['additional_faults']>[number]>) {
    if (!config) return;
    updateConfig('additional_faults', (config.additional_faults ?? []).map((fault, i) => i === index ? { ...fault, ...patch } : fault));
  }

  async function importedModel(model: Model) {
    const latest = await api<Catalog>('/api/catalog');
    if (!latest.models.some(item => item.id === model.id)) latest.models = [...latest.models, model];
    setCatalog(latest);
    setConfig(previous => {
      const next = { ...latest.defaults, ...previous };
      const start = Math.min(Number(next.start_hour) || 0, Math.max(0, model.duration_hours - .01));
      return { ...next, model_id: model.id, fault_asset: faultAssets(model, next.fault_kind)[0] ?? '', additional_faults: [], discovery: next.mode === 'discover' ? defaultDiscovery(model) : null, start_hour: start, duration_hours: Math.max(.01, Math.min(Number(next.duration_hours) || 1, model.duration_hours - start)) };
    });
    setNotice(`Model ${model.name} added. Review its policy and performance check before running.`);
  }

  async function startExperiment(replay = false) {
    if ((!config && !replay) || busy) return;
    setRetryAction(replay ? 'replay' : 'experiment');
    setError(''); setNotice(''); setJob(null); setSubmitting(true);
    try {
      const next = await api<Job>(replay && view ? `/api/jobs/${encodeURIComponent(view.id)}/replay` : '/api/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        ...(!replay ? { body: JSON.stringify({ ...config, mode: config?.mode === 'discover' ? 'discover' : 'investigate' }) } : {}),
      });
      activeJobId.current = next.id;
      setJob({ ...next, status: next.status === 'completed' ? 'running' : next.status, phase: next.phase ?? 'Preparing experiment', message: next.message ?? 'The model runner is preparing the experiment.' });
      setSetupOpen(false);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'The experiment could not be started.'); }
    finally { setSubmitting(false); }
  }

  async function searchResponse(settings?: RepairSearchConfig) {
    if (!view || busy) return;
    setRetryAction('repair');
    if (settings) repairRequest.current = settings;
    setError(''); setNotice(''); setJob(null); setSubmitting(true);
    try {
      const next = await api<Job>(`/api/jobs/${encodeURIComponent(view.id)}/repair`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(repairRequest.current ?? {}) });
      activeJobId.current = next.id;
      setJob({ ...next, status: next.status === 'completed' ? 'running' : next.status });
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'The response search could not be started.'); }
    finally { setSubmitting(false); }
  }

  async function exportPacket() {
    if (!view) return;
    setRetryAction('export'); setExporting(true); setError('');
    try {
      const response = await fetch(`/api/jobs/${encodeURIComponent(view.id)}/export`);
      if (!response.ok) throw new Error('The packet could not be created. Your run is still available.');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `stormpilot-${view.id}.zip`; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice(`Evidence exported for ${shortId(view.id)}.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'The evidence packet could not be downloaded.'); }
    finally { setExporting(false); }
  }

  const metricKeys: MetricId[] = ['flood_volume_m3', 'peak_downstream_flow_m3s', 'downstream_excess_volume_m3', 'terminal_storage_m3'];
  const stressCase = view?.cases.find(c => c.role === 'reduced') ?? view?.cases.find(c => c.role === 'stress');
  const fallbackCase = view?.cases.find(c => c.role === 'fallback');
  const validationKind = statusKind(view?.validation.status ?? 'pending');
  const fallbackClaim = view?.validation.claims?.fallback;
  const failedGuards = Object.entries(fallbackClaim?.changes ?? {}).filter(([, change]) => change.guard_passed === false).map(([id]) => METRICS[id as MetricId]?.label ?? human(id));
  const artifactChecks = view?.validation.checks.filter(check => check.id.startsWith('artifact:')) ?? [];
  const scienceChecks = view?.validation.checks.filter(check => !check.id.startsWith('artifact:')) ?? [];
  const reductionLabel = validationKind === 'fail' ? 'Unverified witness' : view?.finding.status !== 'violation' ? 'No verified failure witness' : view?.validation.claims?.witness?.claim ? human(view.validation.claims.witness.claim) : (view?.search.reduced_to ?? 0) < (view?.search.reduced_from ?? 0) ? 'Reduced witness' : 'Recorded witness';

  const removalTests = [...new Map((view?.search.tests ?? []).map(test => [test.id, test])).values()];
  const conditionName = (id: string) => { const condition = view?.search.conditions?.find(item => item.id === id); return condition ? `${condition.asset} (${id})` : id; };
  const findingLabel = { violation: 'A check was exceeded', no_violation: 'No violation found in tested cases', baseline_failure: 'Nominal reference exceeds the check', incomplete: 'Investigation incomplete', unverified: 'Evidence remains unverified' };
  const responseAvailable = Boolean(view?.repair || view && view.finding.status === 'violation' && view.search.reduced_to === 2 && validationKind === 'pass' && view.config.metric === 'flood_volume_m3');
  const measuredValue = view ? stressCase?.metrics[view.config.metric] : null;
  const outcomeScale = view && typeof measuredValue === 'number' && Number.isFinite(measuredValue)
    ? Math.max(measuredValue, view.finding.threshold, 1) * 1.12 : null;

  return <div className="app-shell">
    <a className="skip-link" href="#investigation">Skip to investigation</a>
    <header className="masthead">
      <a className="brand" href="#" aria-label="StormPilot workspace"><span className="brand-mark"><Waves size={24} strokeWidth={1.8} /></span><span>StormPilot<span className="brand-dot">.</span></span></a>
      <div className="masthead-divider" /><span className="workspace-name">The stormwater test bench</span>
      <div className="masthead-right"><span className={`engine-status ${catalog?.engine.status === 'unavailable' ? 'unavailable' : ''}`}><span />{booting ? 'Connecting to solver' : catalog ? engineLabel(catalog.engine.version) : 'Solver unavailable'}</span><a className="source-link" href={modelSource || 'https://www.epa.gov/water-research/storm-water-management-model-swmm'} target="_blank" rel="noreferrer">{modelSource ? 'Model source' : 'SWMM reference'} <ExternalLink size={13} /></a></div>
    </header>

    <div className="workspace-layout">
      <aside className={`setup-rail ${setupOpen ? 'is-open' : ''}`} aria-label="Experiment settings">
        <button className="mobile-setup-toggle" aria-expanded={setupOpen} aria-controls="setup-content" onClick={() => setSetupOpen(!setupOpen)}><span><Settings2 size={17} />Experiment setup</span><span>{selectedModel?.name ?? 'Configure'}<ChevronDown size={16} /></span></button>
        <div id="setup-content" className="setup-content">
          <div className="setup-heading"><span className="step-marker">1</span><div><h2>Set up a test</h2><p>One policy. A precise question.</p></div></div>
          {booting && !config ? <div className="setup-loading"><LoaderCircle className="spin" size={20} /><p>Loading models and policies…</p></div> : config && catalog ? <form id="experiment-form" onSubmit={event => { event.preventDefault(); void startExperiment(); }}>
            <fieldset disabled={busy}>
              <div className="experiment-mode" role="group" aria-label="Investigation method"><button type="button" aria-pressed={config.mode !== 'discover'} onClick={() => updateConfig('mode', 'investigate')}>Test defined faults</button><button type="button" aria-pressed={config.mode === 'discover'} onClick={() => setConfig({ ...config, mode: 'discover', discovery: config.discovery ?? view?.discovery?.declared_grid ?? defaultDiscovery(selectedModel) })}>Discover interactions</button></div>
              <div className="field"><label htmlFor="model">Model</label><select id="model" value={config.model_id} onChange={e => { const next = catalog.models.find(m => m.id === e.target.value); setConfig({ ...config, model_id: e.target.value, additional_faults: [], discovery: config.mode === 'discover' ? defaultDiscovery(next) : null, fault_asset: faultAssets(next, config.fault_kind)[0] ?? '', start_hour: Math.min(config.start_hour, Math.max(0, (next?.duration_hours ?? 1) - 1)), duration_hours: Math.min(config.duration_hours, next?.duration_hours ?? 1) }); }}>
                {catalog.models.map(model => <option key={model.id} value={model.id}>{model.name}</option>)}
              </select><button type="button" className="import-model-button" onClick={() => setImportOpen(true)}><Plus size={13} />Import a supported model</button><p className="field-description">{selectedModel?.description}</p><div className="model-facts"><span>{selectedModel?.asset_ids.length ?? '—'} control assets</span><span>{number(selectedModel?.duration_hours)} h horizon</span></div>{selectedModel?.downstream_link && <details className="registered-model-context"><summary>Registered model context <ChevronDown size={12} /></summary><dl><div><dt>Origin</dt><dd>{selectedModel.origin === 'imported' ? 'Imported input' : 'Published benchmark'}</dd></div><div><dt>Native units</dt><dd>{selectedModel.flow_units ?? '—'}</dd></div><div><dt>Downstream link</dt><dd>{selectedModel.downstream_link}</dd></div><div><dt>Excess flow threshold</dt><dd>{number(selectedModel.downstream_threshold_m3s)} m³/s</dd></div></dl>{selectedModel.targets_m3s && <p>Base outlet targets: {selectedModel.targets_m3s.map(value => number(value, 4)).join(', ')} m³/s, in displayed asset order.</p>}</details>}</div>
              <div className="field"><label htmlFor="policy">Control policy</label><select id="policy" value={config.controller_id} onChange={e => setConfig({ ...config, controller_id: e.target.value, controller_parameters: {} })}>{catalog.policies.map(policy => <option key={policy.id} value={policy.id}>{policy.name}</option>)}</select><p className="field-description">{catalog.policies.find(p => p.id === config.controller_id)?.description}</p></div><PolicyParameters policy={catalog.policies.find(policy => policy.id === config.controller_id)} values={config.controller_parameters ?? {}} onChange={values => updateConfig('controller_parameters', values)} prefix="policy" />
              <div className="field-group"><div className="group-label"><span>What should the plan satisfy?</span></div><div className="field"><label htmlFor="metric">Performance check</label><select id="metric" value={config.metric} onChange={e => updateConfig('metric', e.target.value as MetricId)}><option value="flood_volume_m3">Flooding volume</option><option value="peak_downstream_flow_m3s">Peak downstream flow</option><option value="downstream_excess_volume_m3">Downstream excess volume</option></select></div><div className="field"><label htmlFor="threshold">Maximum allowed</label><div className="input-with-unit"><input id="threshold" type="number" required min="0" step="any" value={config.threshold} onChange={e => updateConfig('threshold', e.target.valueAsNumber)} /><span>{metric?.unit}</span></div><p className="field-description">An experiment threshold, not a field safety standard.</p></div></div>
              {config.mode === 'discover' ? <DiscoverySetup key={config.model_id} model={selectedModel} value={config.discovery ?? defaultDiscovery(selectedModel)} onChange={discovery => updateConfig('discovery', discovery)} /> : <><div className="field-group"><div className="group-label"><span>Introduce a disturbance</span><span className="fault-mini"><span />{isSensorFault(config.fault_kind) ? 'Observation fault' : 'Actuator fault'}</span></div><FaultEditor model={selectedModel} fault={{ asset: config.fault_asset, kind: config.fault_kind as FaultKind, start_hour: config.start_hour, duration_hours: config.duration_hours, setting: config.fault_setting ?? 0, bias_m: config.sensor_bias_m ?? 1 }} onChange={fault => setConfig({ ...config, fault_asset: fault.asset, fault_kind: fault.kind ?? 'stuck_closed', start_hour: fault.start_hour, duration_hours: fault.duration_hours, fault_setting: fault.setting ?? 0, sensor_bias_m: fault.bias_m ?? 1 })} /></div>
              <div className="additional-faults">{(config.additional_faults ?? []).map((fault, index) => <div className="additional-fault" key={index}><div className="additional-fault-heading"><strong>Additional fault {index + 1}</strong><button type="button" className="icon-button" aria-label={`Remove additional fault ${index + 1}`} onClick={() => updateConfig('additional_faults', (config.additional_faults ?? []).filter((_, i) => i !== index))}><X size={13} /></button></div><FaultEditor model={selectedModel} prefix={`extra-${index}`} fault={fault} onChange={next => updateAdditionalFault(index, next)} /></div>)}{(config.additional_faults?.length ?? 0) < 3 && <button type="button" className="add-fault-button" onClick={() => updateConfig('additional_faults', [...(config.additional_faults ?? []), { asset: selectedModel?.asset_ids.find(asset => asset !== config.fault_asset) ?? selectedModel?.asset_ids[0] ?? '', kind: 'stuck_closed', start_hour: config.start_hour, duration_hours: config.duration_hours }])}><Plus size={13} />Add another fault</button>}</div>
              </>}<details className="scenario-settings"><summary>Rainfall & observations <ChevronDown size={14} /></summary><div className="field"><label htmlFor="rainfall-multiplier">Rainfall multiplier</label><div className="input-with-unit"><input id="rainfall-multiplier" type="number" min="0.25" max="2.5" step="any" required value={Number.isFinite(config.rainfall_multiplier ?? 1) ? config.rainfall_multiplier ?? 1 : ''} onChange={event => updateConfig('rainfall_multiplier', event.target.valueAsNumber)} /><span>×</span></div><p className="field-description">Scales the model’s supplied rainfall. It is a scenario transformation, not a forecast.</p></div><div className="field"><label htmlFor="observation-noise">Depth observation noise</label><div className="input-with-unit"><input id="observation-noise" type="number" min="0" max="0.5" step="any" required value={Number.isFinite(config.noise_std_m ?? 0) ? config.noise_std_m ?? 0 : ''} onChange={event => updateConfig('noise_std_m', event.target.valueAsNumber)} /><span>m</span></div><p className="field-description">Standard deviation of the declared observation noise.</p></div></details>
              <details className="advanced-settings"><summary>Search & comparison <ChevronDown size={14} /></summary><div className="field" hidden={config.mode === 'discover'}><label htmlFor="budget">Search budget</label><select id="budget" value={config.budget} onChange={e => updateConfig('budget', Number(e.target.value))}>{[...new Set([4, 8, 12, 20, 24, config.budget])].filter(value => value <= 24).sort((a, b) => a - b).map(value => <option key={value} value={value}>{value} simulator calls</option>)}</select></div><div className="field"><label htmlFor="fallback">Fallback policy</label><select id="fallback" value={config.fallback_controller_id} onChange={e => setConfig({ ...config, fallback_controller_id: e.target.value, fallback_controller_parameters: {} })}>{catalog.policies.map(policy => <option key={policy.id} value={policy.id}>{policy.name}</option>)}</select></div><PolicyParameters policy={catalog.policies.find(policy => policy.id === config.fallback_controller_id)} values={config.fallback_controller_parameters ?? {}} onChange={values => updateConfig('fallback_controller_parameters', values)} prefix="fallback-policy" title="Alternative parameters" /></details>
            </fieldset>
            <div className="run-controls"><button className="button primary investigate-button" type="submit" disabled={busy || !Number.isFinite(config.threshold) || !Number.isFinite(config.start_hour) || !Number.isFinite(config.duration_hours)}>{busy ? <LoaderCircle size={17} className="spin" /> : <Play size={15} fill="currentColor" />}{busy ? 'Running experiment…' : config.mode === 'discover' ? 'Run fault discovery' : stale ? 'Run with new settings' : 'Test defined faults'}{!busy && <ArrowRight size={17} />}</button>
            <p className="run-description">{config.mode === 'discover' ? 'Search the declared grid, then retain the selected four-case proof.' : 'Run the reference, stress the policy, then compare the evidence.'}</p>
            </div>
          </form> : <p className="field-description">Connect to the model runner to configure an experiment.</p>}
          <div className="rail-footer"><FlaskConical size={17} /><p>Published models. Real hydraulics.<br /><strong>Conclusions bounded by the test.</strong></p></div>
        </div>
      </aside>

      <main id="investigation" className="investigation">
        <div className="workspace-purpose"><div className="workspace-breadcrumb"><FlaskConical size={16} /><span>Investigation workbench</span><span aria-hidden="true">/</span><strong>{resultModel?.name ?? 'New experiment'}</strong></div><p className="workspace-intro">Discover failure. Inspect the physics. Challenge the response.</p></div>
        <WorkspaceNavigation hasView={Boolean(view)} responseAvailable={responseAvailable} runId={view?.id} onConfigure={() => {
          setSetupOpen(true);
          requestAnimationFrame(() => {
            const setup = document.getElementById('setup-content');
            if (setup) setup.scrollTop = 0;
            setup?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
            document.getElementById('model')?.focus({ preventScroll: true });
          });
        }} />
        {error && <div className="error-banner" role="alert"><TriangleAlert size={19} /><div><strong>Experiment needs attention</strong><p>{error}</p>{!view && <p>No simulation result was produced.</p>}</div><button className="text-button" onClick={() => retryAction === 'load' ? setLoadKey(key => key + 1) : retryAction === 'repair' ? void searchResponse() : retryAction === 'export' ? void exportPacket() : retryAction === 'replay' ? void startExperiment(true) : catalog ? void startExperiment() : setLoadKey(key => key + 1)} disabled={busy}>Retry <RotateCcw size={14} /></button><button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
        {notice && <div className="sr-only" role="status">{notice}</div>}
        {busy && <div className="progress-banner" role="status"><LoaderCircle className="spin" size={19} /><div><strong>{job?.phase ? human(job.phase) : 'Preparing experiment'}</strong><p>{job?.message || 'The model runner is starting. Results appear after the experiment completes.'}</p></div><span className="mono">{job ? shortId(job.id) : 'Starting'}</span></div>}
        {stale && <div className="stale-banner"><Info size={16} /><span>Settings changed. Showing results from <strong className="mono">{shortId(view!.id)}</strong>.</span></div>}
        {view && validationKind === 'fail' && <div className="error-banner"><XCircle size={18} /><div><strong>Evidence checks failed</strong><p>These results are unverified. Inspect the failed checks before interpreting the finding.</p></div><button className="text-button" onClick={() => dialog.current?.showModal()}>View checks <ArrowRight size={14} /></button></div>}

        {view ? <>
          <section className={`finding-section ${view.finding.status}`} aria-labelledby="result-title">
            <div className="finding-topline"><span className={`finding-status ${view.finding.status}`}>{view.finding.status === 'no_violation' ? <CheckCircle2 size={15} /> : <TriangleAlert size={15} />}{findingLabel[view.finding.status]}</span><div className="run-tags">{view.recorded && <span className="recorded-tag"><Clock3 size={12} />Recorded run</span>}<span className="run-id" title={view.id}>{shortId(view.id)}</span></div></div>
            <h1 id="result-title" ref={resultHeading} tabIndex={-1}>{view.finding.title}</h1>
            <p className="finding-description">{view.finding.description}</p>
            <div className="experiment-scope"><span><strong>{policyName(view.config.controller_id)}</strong> tested in {view.model.name}</span><span><Clock3 size={13} />{number(view.model.duration_hours)} h horizon</span><button className={`validation-link ${validationKind}`} onClick={() => dialog.current?.showModal()}><ShieldCheck size={14} />Evidence: {human(view.validation.status)}<ArrowRight size={13} /></button></div>
            <div className="outcome-strip">
              <div className="outcome-primary"><span>{METRICS[view.config.metric]?.label ?? human(view.finding.metric)} <span className="subtle">/ {stressCase?.role === 'reduced' ? 'reduced witness' : 'stressed policy'}</span></span><div><strong>{number(measuredValue)}</strong><span>{view.finding.unit || METRICS[view.config.metric]?.unit}</span></div>{outcomeScale && typeof measuredValue === 'number' && <div className="outcome-meter" data-status={measuredValue > view.finding.threshold ? 'exceeded' : 'within'} aria-hidden="true"><span className="outcome-meter-fill" style={{ width: `${Math.max(0, measuredValue) / outcomeScale * 100}%` }} /><span className="outcome-meter-limit" style={{ left: `${Math.max(0, view.finding.threshold) / outcomeScale * 100}%` }} /></div>}<p>Declared check: ≤ {number(view.finding.threshold)} {view.finding.unit || METRICS[view.config.metric]?.unit}</p></div>
              <div className="outcome-support"><span>Nominal reference</span><strong>{number(view.cases.find(c => c.role === 'nominal')?.metrics[view.config.metric])}<small>{view.finding.unit || METRICS[view.config.metric]?.unit}</small></strong><p>Same model and horizon</p></div>
              <div className="outcome-support"><span>Total simulator calls</span><strong>{number(view.repair?.simulator_calls ?? view.discovery?.simulator_calls ?? view.search.evaluated, 0)}<small>calls</small></strong><p>{number(view.repair?.budget ?? view.discovery?.budget ?? view.search.budget, 0)}-call budget</p></div>
              <div className="outcome-action"><button className="button secondary" onClick={exportPacket} disabled={exporting}>{exporting ? <LoaderCircle size={16} className="spin" /> : <ArrowDownToLine size={16} />}Export evidence</button><span>Configuration, traces & checks</span></div>
            </div>
          </section>

          <DiscoveryEvidence view={view} />
          <Hydrograph view={view} time={time} setTime={setTime} selectedCase={selectedCase} setSelectedCase={setSelectedCase} />
          <SensorInspector key={`sensor-${view.id}`} view={view} time={time} setTime={setTime} selectedCase={selectedCase} setSelectedCase={setSelectedCase} />

          <div className="investigation-details">
            {resultModel && <Network model={resultModel} runCase={activeCase} time={time} faultAsset={String(activeCase?.faults[0]?.asset ?? '')} />}
            <section className="witness-panel panel" aria-labelledby="witness-title"><div className="section-heading"><div><div className="section-index"><Activity size={15} />Failure investigation</div><h2 id="witness-title">Conditions behind the result.</h2></div><span className="small-badge" title={view.search.method}>{view.search.method.includes('subset') ? 'Subset search' : view.search.method.includes('proof') ? 'Retained proof' : human(view.search.method)}</span></div>
              <div className="fault-record"><span className="fault-record-icon"><Settings2 size={21} /></span><div><span className="fault-record-label">Declared disturbance</span><h3>{faultLabel(view.config.fault_kind)} <span>at {view.config.fault_asset}</span></h3><p>Starts at {number(view.config.start_hour)} h · lasts {number(view.config.duration_hours)} h</p></div></div>
              {!!view.config.additional_faults?.length && <div className="additional-fault-summary">{view.config.additional_faults.map((fault, index) => <span key={index}>{faultLabel(fault.kind)}: {fault.asset} · {number(fault.start_hour)}–{number(fault.start_hour + fault.duration_hours)} h</span>)}</div>}
              {view.finding.status === 'violation' && validationKind === 'pass' ? <div className="witness-stats"><div><span>Original conditions</span><strong>{number(view.search.reduced_from, 0)}</strong></div><ArrowRight size={20} /><div><span>Retained conditions</span><strong>{number(view.search.reduced_to, 0)}</strong></div><span className="witness-claim">{reductionLabel}</span></div> : <div className="witness-unavailable"><Info size={16} /><span>{view.finding.status === 'baseline_failure' ? 'The nominal policy already exceeds the check. Fault-specific reduction is not established.' : view.finding.status === 'no_violation' ? 'No failure witness is available to reduce.' : 'A verified failure witness is not available for this investigation.'}</span></div>}
              {!!view.search.conditions?.length && <div className="condition-list" aria-label="Declared conditions and reduction outcome">{view.search.conditions.map(condition => <div key={condition.id} className={`condition-item ${condition.retained === true ? 'retained' : condition.retained === false ? 'removed' : 'unresolved'}`}><span className="condition-indicator">{condition.retained === true ? <CheckCircle2 size={15} /> : condition.retained === false ? <X size={15} /> : <CircleDashed size={15} />}</span><div><strong>{faultLabel(String(view.cases.flatMap(run => run.faults).find(fault => fault.id === condition.id)?.type ?? view.config.fault_kind))} at {condition.asset} <code>{condition.id}</code></strong><span>{number(condition.start_hour)}–{number(condition.start_hour + condition.duration_hours)} h</span></div><span className="condition-state">{condition.retained === true ? 'Retained' : condition.retained === false ? 'Removed' : 'Unresolved'}</span></div>)}</div>}
              <p className="bounded-copy">{view.finding.status === 'violation' ? 'The witness records conditions sufficient to exceed this check in the model. Reduction claims apply only to the removals actually evaluated.' : view.finding.status === 'no_violation' ? 'No violation was found within this test set. A passing search does not establish safety outside the tested conditions.' : 'Interpret only completed, verified checks. Missing runs and incomplete investigations are not counted as passes.'}</p>
              {view.finding.status === 'violation' && view.search.claim && <p className="reduction-explanation">{view.search.claim}</p>}
              {view.search.stopping_reason && <p className="search-stop-reason"><strong>{human(view.search.status)}.</strong> {human(view.search.stopping_reason)}</p>}<details className="coverage-details"><summary>Inspect search coverage <ChevronDown size={14} /></summary>{Array.isArray(view.search.coverage) ? <ul>{view.search.coverage.map((item, index) => <li key={index}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>)}</ul> : <p>{view.search.coverage || 'Coverage details are included in the evidence packet.'}</p>}</details>
              {!!removalTests.length && <details className="removal-details"><summary>Inspect tested removals <span>{removalTests.length} unique runs</span><ChevronDown size={14} /></summary><p>Recorded full-horizon outcomes. A reused run appears once.</p><div className="removal-table-wrap" role="region" aria-label="Tested fault removals and outcomes, horizontally scrollable" tabIndex={0}><table className="removal-table"><thead><tr><th scope="col">Active conditions</th><th scope="col">{METRICS[view.search.metric ?? view.config.metric]?.label ?? 'Outcome'}<small>{view.search.unit ?? view.finding.unit}</small></th><th scope="col">Declared check</th></tr></thead><tbody>{removalTests.map(test => <tr key={test.id}><th scope="row"><span>{test.active_fault_ids.length ? test.active_fault_ids.map(conditionName).join(', ') : 'No active faults'}</span><small>{human(test.phase)}</small><code title={test.id}>{shortId(test.id)}</code></th><td>{number(test.value)}</td><td><span className={test.violated === true ? 'test-exceeded' : test.violated === false ? 'test-within' : ''}>{test.violated === true ? 'Exceeded' : test.violated === false ? 'Within bound' : 'Unverified'}</span></td></tr>)}</tbody></table></div></details>}
              <div className="witness-footnote"><Info size={14} /><span>A model fault is not a field maintenance diagnosis.</span></div>
            </section>
          </div>

          <section className="comparison-panel panel" aria-labelledby="comparison-title"><div className="section-heading"><div><div className="section-index"><span className="step-marker small">2</span>Policy comparison</div><h2 id="comparison-title">Same case. Different policy.</h2></div><span className="comparison-assumption"><Info size={14} />Paired policy comparison</span></div><p className="section-description">The fallback faces the same active faults as the {stressCase?.role === 'reduced' ? 'reduced witness' : 'stressed policy'}, with shared weather and horizon. Read the whole outcome, including water left in storage.</p>
            {fallbackClaim && validationKind === 'pass' && <div className={`comparison-verdict ${failedGuards.length ? 'tradeoff' : ''}`}>{failedGuards.length ? <TriangleAlert size={17} /> : <Info size={17} />}<div><strong>{fallbackClaim.guarded_improvement ? 'Primary metric improves; all specified guards pass.' : fallbackClaim.primary_improved ? `Primary metric improves; ${failedGuards.length ? `${failedGuards.length} guard checks fail.` : 'overall improvement is unconfirmed.'}` : 'No primary improvement in this comparison.'}</strong><p>{failedGuards.length ? `Failed guards: ${failedGuards.join(', ')}. A lower primary metric does not make this an overall improvement.` : 'This statement follows the independent checks and their recorded numerical tolerances.'}</p></div></div>}
            <p className="horizontal-scroll-hint">Scroll horizontally to compare all cases.</p><div className="comparison-table-wrap" role="region" aria-label="Policy comparison table. Scroll horizontally to compare all cases." tabIndex={0}><table className="comparison-table"><caption className="sr-only">Physical outcomes for all cases. Lower values are not by themselves evidence of overall improvement.</caption><thead><tr><th scope="col">Physical outcome</th>{view.cases.map(c => <th scope="col" key={c.id}><span className={`column-case ${c.role}`}><span className={`line-key ${c.role}`} />{caseRoleLabel(c.role, Boolean(view.repair))}</span><small>{policyName(c.controller_id)}</small></th>)}<th scope="col">{view.repair ? 'Candidate' : 'Fallback'} − {stressCase?.role === 'reduced' ? 'reduced' : 'stressed'}</th></tr></thead><tbody>{metricKeys.map(key => { const delta = fallbackCase?.metrics[key] != null && stressCase?.metrics[key] != null ? fallbackCase.metrics[key]! - stressCase.metrics[key]! : null; return <tr key={key} className={key === view.config.metric ? 'primary-metric-row' : ''}><th scope="row"><span>{METRICS[key].label}{key === view.config.metric && <span className="primary-check-label">Primary check</span>}</span><small>{METRICS[key].unit}</small></th>{view.cases.map(c => <td key={c.id}>{number(c.metrics[key])}</td>)}<td className="delta-value">{delta !== null && delta > 0 ? '+' : ''}{number(delta)}</td></tr>; })}</tbody></table></div><div className="comparison-note"><Info size={15} /><p>Metric improvement and passing non-regression checks are separate claims. Differences shown here are arithmetic comparisons, not an overall ranking.</p></div>
          </section>

          <RepairPanel key={`repair-${view.id}`} view={view} busy={busy} policies={catalog?.policies ?? []} onRepair={settings => void searchResponse(settings)} />
          <EvaluationPanel view={view} busy={busy} />
          <section className="evidence-panel" aria-labelledby="evidence-title"><div className="evidence-seal"><FileCheck2 size={28} strokeWidth={1.4} /></div><div className="evidence-copy"><div className="section-index">The result goes with its evidence</div><h2 id="evidence-title">Inspect it. Export it. Replay it.</h2><p>One experiment, with its inputs, physical traces, provenance and independent checks. Every claim stays attached to the run that produced it.</p><span className="evidence-id">Run <code>{view.id}</code></span></div><div className="evidence-actions"><button className="button primary" onClick={exportPacket} disabled={exporting}>{exporting ? <LoaderCircle className="spin" size={16} /> : <ArrowDownToLine size={16} />}Export evidence packet</button><div><button className="text-button" onClick={() => void startExperiment(true)} disabled={busy}><RotateCcw size={14} />Replay run</button><button className="text-button" onClick={() => dialog.current?.showModal()}>View checks <ArrowRight size={14} /></button></div></div></section>
          <div className="provenance-line"><span>{engineLabel(view.provenance.engine_version)}</span><span>Model hash <code title={view.provenance.model_sha256}>{shortId(view.provenance.model_sha256)}</code></span><span>{number(view.provenance.run_seconds, 2)} s model execution</span></div>
        </> : <section className="welcome-state"><div className="welcome-intro"><span className="welcome-symbol"><Waves size={38} strokeWidth={1.2} /></span><h1>Put a stormwater plan<br />to the test.</h1><p>Introduce a fault. Follow the water. Find out which conditions change the outcome, and take the evidence with you.</p><button className="button primary welcome-run" type="submit" form="experiment-form" disabled={busy || !config}>{busy ? <LoaderCircle className="spin" size={16} /> : <Play size={14} fill="currentColor" />}{busy ? 'Investigating…' : 'Investigate current plan'}<ArrowRight size={16} /></button><button className="text-button welcome-import" type="button" onClick={() => setImportOpen(true)}>Use your own SWMM model <ArrowRight size={14} /></button><div className="welcome-next"><span className="step-marker">1</span><div><strong>Choose a policy and a question to test.</strong><p>Set up an experiment in the {window.innerWidth < 850 ? 'panel above' : 'panel on the left'}, then investigate your plan.</p></div></div></div><div className="welcome-model">{resultModel ? <Network model={resultModel} time={0} faultAsset={config?.fault_asset ?? ''} /> : <div className="empty-solver"><FlaskConical size={44} strokeWidth={1} /><p>{booting ? 'Connecting to the model runner…' : 'The model runner is unavailable.'}</p><span>{booting ? 'Loading the published model catalog.' : 'No simulation result was produced.'}</span></div>}</div><div className="welcome-bottom"><span><ShieldCheck size={19} />A testable claim, with limits.</span><p>StormPilot evaluates published simulations. Results describe the tested model and conditions; they do not certify a real drainage network.</p></div></section>}

        <footer className="workspace-footer"><span className="footer-brand"><Waves size={16} />StormPilot</span><p>Simulation evidence, not a field safety certificate.</p><span>Built on public models & EPA SWMM</span></footer>
      </main>
    </div>

    <ModelImport open={importOpen} onClose={() => setImportOpen(false)} onImported={importedModel} />
    <dialog className="validation-dialog" ref={dialog} aria-labelledby="validation-title" onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}><div className="dialog-inner"><div className="dialog-heading"><div><div className="section-index"><ShieldCheck size={16} />Independent evidence checks</div><h2 id="validation-title">What this packet supports.</h2></div><button className="icon-button" aria-label="Close evidence checks" onClick={() => dialog.current?.close()}><X size={21} /></button></div>{view && <><p className="dialog-intro">Checks for <code>{view.id}</code>. Numerical verification, real-world calibration and field impact are different claims.</p><div className={`validation-summary ${validationKind}`}><CheckIcon status={view.validation.status} /><strong>{human(view.validation.status)}</strong><span>{view.validation.checks.length} recorded checks</span></div><div className="limitations"><h3>Scope & limits</h3>{view.validation.limitations.length ? <ul>{view.validation.limitations.map((limit, index) => <li key={index}>{limit}</li>)}</ul> : <p>These checks apply to this recorded simulation and its declared artifacts. No field validity or general safety claim follows.</p>}{view.validation.replay_status && <p className="replay-status"><strong>Independent simulator replay:</strong> {human(view.validation.replay_status)}</p>}</div><CheckRows checks={scienceChecks} />{!!artifactChecks.length && <details className="artifact-checks"><summary>Included artifact integrity <span>{artifactChecks.length} checks</span><ChevronDown size={14} /></summary><CheckRows checks={artifactChecks} /></details>}<div className="dialog-provenance"><span>Model source</span><span>{view.provenance.source_url ? <a href={view.provenance.source_url} target="_blank" rel="noreferrer">{view.provenance.model_name}<ExternalLink size={13} /></a> : `${view.provenance.model_name} · imported input`}</span><span>Engine</span><strong>{engineLabel(view.provenance.engine_version)}</strong><span>Model SHA-256</span><code>{view.provenance.model_sha256}</code></div><div className="dialog-footer"><button className="button secondary" onClick={() => dialog.current?.close()}>Return to investigation</button><button className="button primary" onClick={exportPacket} disabled={exporting}><ArrowDownToLine size={16} />Export packet</button></div></>}</div></dialog>
  </div>;
}
