import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, FileUp, FolderCheck, Info, LoaderCircle, TriangleAlert, Upload, X } from 'lucide-react';
import type { Model } from '../types';
import { number } from '../types';

type ImportEntry = string | Record<string, unknown>;
interface Inspection {
  name: string;
  sha256: string;
  flow_units: string;
  duration_hours: number;
  assets: ImportEntry[];
  nodes: ImportEntry[];
  downstream_links: ImportEntry[];
  warnings: (string | { message: string })[];
}
interface InspectionResult { inspection: Inspection; token: string }

function entryId(entry: ImportEntry): string {
  return typeof entry === 'string' ? entry : String(entry.id ?? entry.link_id ?? entry.asset_id ?? entry.asset ?? '');
}
function entryLabel(entry: ImportEntry): string {
  if (typeof entry === 'string') return entry;
  const id = entryId(entry);
  const node = entry.node_id ?? entry.observation_node ?? entry.from ?? entry.source;
  const to = entry.to ?? entry.target;
  return node && to ? `${id} · ${node} → ${to}` : node ? `${id} · observes ${node}` : id;
}
async function post<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const result = await response.json();
  if (!response.ok) throw new Error(String(result.error ?? result.message ?? `Request failed (${response.status}).`));
  return result as T;
}

export default function ModelImport({ open, onClose, onImported }: { open: boolean; onClose: () => void; onImported: (model: Model) => Promise<void> }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const downstreamInput = useRef<HTMLSelectElement>(null);
  const errorPanel = useRef<HTMLDivElement>(null);
  const [fileName, setFileName] = useState('');
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const [inspection, setInspection] = useState<InspectionResult | null>(null);
  const [downstream, setDownstream] = useState('');
  const [threshold, setThreshold] = useState('0.5');
  const [targets, setTargets] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<'reading' | 'inspecting' | 'saving' | null>(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
    else if (!open && dialog.current?.open) dialog.current?.close();
  }, [open]);

  function showError(message: string) { setError(message); requestAnimationFrame(() => errorPanel.current?.focus()); }

  async function readFile(file?: File) {
    if (!file) return;
    setError(''); setInspection(null); setBusy('reading');
    if (file.size > 256 * 1024) { showError('This input exceeds the supported 256 KiB file limit. Choose a smaller supported model.'); setBusy(null); return; }
    if (!file.name.toLowerCase().endsWith('.inp')) { showError('Choose a SWMM input file with the .inp extension.'); setBusy(null); return; }
    try {
      const contents = await file.text();
      if (!contents.trim()) throw new Error('This file is empty. Choose a SWMM model with input data.');
      setText(contents); setFileName(file.name); setName(file.name.replace(/\.inp$/i, '').replaceAll('_', ' '));
    } catch (cause) { showError(cause instanceof Error ? cause.message : 'The model file could not be read.'); }
    finally { setBusy(null); }
  }

  async function inspect(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() || busy) return;
    setError(''); setBusy('inspecting');
    try {
      const result = await post<InspectionResult>('/api/models/inspect', { name: name.trim() || fileName, inp_text: text });
      setInspection(result);
      setDownstream('');
      setTargets({});
      requestAnimationFrame(() => downstreamInput.current?.focus());
    } catch (cause) { showError(cause instanceof Error ? cause.message : 'The model could not be inspected.'); }
    finally { setBusy(null); }
  }

  async function register(event: React.FormEvent) {
    event.preventDefault();
    if (!inspection || busy || !downstream) return;
    setError(''); setBusy('saving');
    const hasOverrides = Object.values(targets).some(value => value.trim() !== '');
    const orderedTargets = inspection.inspection.assets.map(asset => { const value = targets[entryId(asset)]?.trim(); return value ? Number(value) : Number(threshold) / inspection.inspection.assets.length; });
    try {
      const result = await post<{ model: Model }>('/api/models', {
        token: inspection.token, downstream_link: downstream, downstream_threshold_m3s: Number(threshold),
        ...(hasOverrides ? { targets_m3s: orderedTargets } : {}),
      });
      await onImported(result.model);
      onClose();
      setInspection(null); setText(''); setFileName(''); setName(''); setTargets({});
      if (fileInput.current) fileInput.current.value = '';
    } catch (cause) { showError(cause instanceof Error ? cause.message : 'The model could not be added. Your inspected file is still available.'); }
    finally { setBusy(null); }
  }

  const preview = inspection?.inspection;
  return <dialog ref={dialog} className="validation-dialog model-import-dialog" aria-labelledby="model-import-title" onClose={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="dialog-inner">
      <div className="dialog-heading"><div><div className="section-index"><FileUp size={16} />Use your own model</div><h2 id="model-import-title">Bring a catchment to the test.</h2></div><button className="icon-button" aria-label="Close model import" onClick={onClose}><X size={21} /></button></div>
      <p className="dialog-intro">Import a supported, self-contained SWMM input file. Inspect its structure, then choose the downstream comparison point before running an experiment.</p>
      <div className="import-stage-strip" aria-label="Import progress"><span className={!preview ? 'current' : 'done'}><span>{preview ? <CheckCircle2 size={14} /> : '1'}</span>Inspect file</span><span className={preview ? 'current' : ''}><span>2</span>Confirm model context</span></div>
      {error && <div className="import-error" role="alert" ref={errorPanel} tabIndex={-1}><TriangleAlert size={18} /><div><strong>Model needs attention</strong><p>{error}</p></div></div>}
      {!preview ? <form onSubmit={inspect}>
        <div className={`model-dropzone ${dragging ? 'dragging' : ''} ${fileName ? 'has-file' : ''} ${error ? 'has-error' : ''}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!busy) void readFile(event.dataTransfer.files[0]); }}>
          <span className="dropzone-icon">{error ? <TriangleAlert size={31} strokeWidth={1.3} /> : fileName ? <FileUp size={31} strokeWidth={1.3} /> : <Upload size={31} strokeWidth={1.3} />}</span>
          <strong>{fileName || 'Choose a SWMM model'}</strong>
          <p>{fileName ? error ? 'Review the inspection issue above, or choose another file.' : `${number(new Blob([text]).size / 1024, 1)} KB · Ready for structural inspection` : 'Drop an .inp file here, or select it from your computer. Up to 256 KiB.'}</p>
          <label className="button secondary file-input-label">{fileName ? 'Choose another file' : 'Choose .inp file'}<input ref={fileInput} type="file" accept=".inp" disabled={Boolean(busy)} onChange={event => void readFile(event.target.files?.[0])} aria-label="Choose SWMM input file" /></label>
        </div>
        <div className="field import-name-field"><label htmlFor="import-model-name">Model name</label><input id="import-model-name" type="text" required maxLength={80} placeholder="e.g. North catchment study" value={name} onChange={event => setName(event.target.value)} disabled={Boolean(busy)} /></div>
        <div className="import-scope-note"><Info size={16} /><p>The supported subset uses DYNWAVE routing, embedded rainfall/time-series data and rectangular bottom storage outlets. Inspection flags unsupported features or external dependencies. Structural acceptance does not establish field calibration.</p></div>
        <div className="dialog-footer"><button className="text-button" type="button" onClick={onClose}>Return to workspace</button><button className="button primary" type="submit" disabled={!text.trim() || !name.trim() || Boolean(busy)}>{busy ? <LoaderCircle className="spin" size={16} /> : <FileUp size={16} />}{busy === 'reading' ? 'Reading file…' : busy ? 'Inspecting model…' : 'Inspect model'}{!busy && <ArrowRight size={15} />}</button></div>
      </form> : <form onSubmit={register}>
        <div className="import-model-summary"><div><strong>{preview.name}</strong><span>{fileName}</span></div><span className="import-accepted"><CheckCircle2 size={15} />Structure inspected</span></div>
        <dl className="import-facts"><div><dt>Native flow units</dt><dd>{preview.flow_units}</dd></div><div><dt>Model horizon</dt><dd>{number(preview.duration_hours)} <small>h</small></dd></div><div><dt>Control assets</dt><dd>{preview.assets.length}</dd></div><div><dt>Model nodes</dt><dd>{preview.nodes.length}</dd></div></dl>
        {!!preview.warnings?.length && <div className="import-warnings"><strong><Info size={15} />Model observations</strong><ul>{preview.warnings.map((warning, index) => <li key={index}>{typeof warning === 'string' ? warning : warning.message}</li>)}</ul></div>}
        <div className="import-mapping"><div><h3>Where should downstream flow be checked?</h3><p>This link becomes the comparison point for peak flow and excess discharge. Values shown in the workspace use SI units.</p></div><div className="import-mapping-fields"><div className="field"><label htmlFor="import-downstream">Downstream link</label><select ref={downstreamInput} id="import-downstream" required value={downstream} onChange={event => setDownstream(event.target.value)} disabled={Boolean(busy)}><option value="">{preview.downstream_links.length ? 'Choose the downstream comparison link' : 'No supported link found'}</option>{preview.downstream_links.map(link => <option key={entryId(link)} value={entryId(link)}>{entryLabel(link)}</option>)}</select></div><div className="field"><label htmlFor="import-flow-threshold">Downstream excess threshold</label><div className="input-with-unit"><input id="import-flow-threshold" type="number" min="0" max="100000" step="any" required value={threshold} onChange={event => setThreshold(event.target.value)} disabled={Boolean(busy)} /><span>m³/s</span></div></div></div></div>
        <details className="import-targets"><summary>Set per-outlet flow targets <span>Optional</span><ChevronDownIcon /></summary><p>By default, the downstream threshold is divided equally across {preview.assets.length} control outlets: {number(Number(threshold) / Math.max(1, preview.assets.length), 4)} m³/s each. This is an initial control assumption, not an optimized setting. Enter a value to override it.</p><div className="import-target-grid">{preview.assets.map(asset => <div className="field" key={entryId(asset)}><label htmlFor={`import-target-${entryId(asset)}`}>{entryLabel(asset)}</label><div className="input-with-unit"><input id={`import-target-${entryId(asset)}`} type="number" min="0" max="100000" step="any" placeholder={number(Number(threshold) / Math.max(1, preview.assets.length), 4)} value={targets[entryId(asset)] ?? ''} onChange={event => setTargets(previous => ({ ...previous, [entryId(asset)]: event.target.value }))} disabled={Boolean(busy)} /><span>m³/s</span></div></div>)}</div></details>
        <div className="import-hash"><span>Input SHA-256</span><code>{preview.sha256}</code></div>
        <div className="dialog-footer"><button className="text-button" type="button" onClick={() => { setInspection(null); setError(''); requestAnimationFrame(() => fileInput.current?.focus()); }} disabled={Boolean(busy)}><ArrowLeft size={14} />Back to file</button><button className="button primary" type="submit" disabled={Boolean(busy) || !downstream}>{busy ? <LoaderCircle className="spin" size={16} /> : <FolderCheck size={16} />}{busy ? 'Adding model…' : 'Add model to workspace'}</button></div>
      </form>}
    </div>
  </dialog>;
}

function ChevronDownIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>; }
