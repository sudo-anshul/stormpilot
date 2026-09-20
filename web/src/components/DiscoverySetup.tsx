import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Plus, ScanSearch, X } from 'lucide-react';
import type { DiscoveryConfig, Model } from '../types';
import { number } from '../types';
import { faultAssets } from './FaultEditor';

export function defaultDiscovery(model?: Model): DiscoveryConfig {
  const end = Math.max(300, Math.floor((model?.duration_hours ?? 78) * 12) * 300);
  const scale = end >= 28800 ? 1 : end / 28800;
  const onGrid = (seconds: number) => Math.floor(seconds * scale / 300) * 300;
  return { sensor_asset: faultAssets(model, 'sensor_bias').at(-1) ?? '', valve_asset: model?.asset_ids.at(-1) ?? '', bias_values_m: [.25, .5, 1], sensor_windows_s: [[onGrid(10800), Math.max(300, onGrid(21600))]], valve_settings: [.03, .035, .04], valve_windows_s: [[Math.min(end - 300, onGrid(21600)), Math.min(end, Math.max(300, onGrid(28800)))]], budget: 40 };
}

export function NumberList({ id, label, values, onChange, min, max, unit }: { id: string; label: string; values: number[]; onChange: (values: number[]) => void; min: number; max: number; unit?: string }) {
  const [raw, setRaw] = useState(values.join(', '));
  const input = useRef<HTMLInputElement>(null);
  const pieces = raw.split(',').map(value => value.trim());
  const parsed = pieces.map(Number);
  const error = pieces.some(value => !value) || parsed.length < 1 || parsed.length > 8 || parsed.some(value => !Number.isFinite(value) || value < min || value > max) || new Set(parsed).size !== parsed.length ? `Enter 1–8 unique values from ${min} to ${max}, separated by commas.` : '';
  useEffect(() => { input.current?.setCustomValidity(error); }, [error]);
  return <div className="field discovery-list-field"><label htmlFor={id}>{label}{unit && <span> · {unit}</span>}</label><input ref={input} id={id} value={raw} required onChange={event => { const text = event.target.value; setRaw(text); const list = text.split(',').map(value => value.trim()); onChange(list.map(value => value ? Number(value) : NaN)); }} aria-describedby={`${id}-help`} aria-invalid={Boolean(error)} /><p id={`${id}-help`} className={error ? 'field-error' : 'field-description'}>{error || 'Comma-separated values. Each value is tested in the declared grid.'}</p></div>;
}

function Windows({ id, title, windows, onChange, horizon }: { id: string; title: string; windows: [number, number][]; onChange: (values: [number, number][]) => void; horizon: number }) {
  const update = (index: number, endpoint: 0 | 1, hours: number) => {
    const seconds = Math.round(hours * 3600 * 1e6) / 1e6;
    onChange(windows.map((window, i) => i === index ? endpoint === 0 ? [seconds, window[1]] : [window[0], seconds] : window));
  };
  return <div className="discovery-windows"><div className="discovery-window-title">{title}</div>{windows.map((window, index) => {
    const error = window.some(value => !Number.isFinite(value) || value < 0 || value > horizon * 3600 || Math.abs(value / 300 - Math.round(value / 300)) > 1e-8) || window[0] >= window[1] || windows.some((other, i) => i !== index && other[0] === window[0] && other[1] === window[1]);
    return <div key={index} className="discovery-window"><div className="field-pair">{(['Starts at', 'Ends at'] as const).map((label, endpoint) => <div className="field" key={label}><label htmlFor={`${id}-${index}-${endpoint}`}>{label}<span className="sr-only"> · {title} {index + 1}</span></label><div className="input-with-unit"><input id={`${id}-${index}-${endpoint}`} type="number" step="any" min="0" max={horizon} required value={Number.isFinite(window[endpoint]) ? window[endpoint] / 3600 : ''} aria-invalid={error} aria-describedby={error ? `${id}-${index}-error` : undefined} ref={element => element?.setCustomValidity(error ? 'Use a unique window within the horizon, aligned to five-minute intervals.' : '')} onChange={event => update(index, endpoint as 0 | 1, event.target.valueAsNumber)} /><span>h</span></div></div>)}</div>{windows.length > 1 && <button type="button" className="icon-button" aria-label={`Remove ${title.toLowerCase()} ${index + 1}`} onClick={() => onChange(windows.filter((_, i) => i !== index))}><X size={13} /></button>}{error && <p id={`${id}-${index}-error`} className="field-error">Use a unique window within {number(horizon)} h, aligned to five-minute intervals.</p>}</div>;
  })}{windows.length < 8 && <button className="add-fault-button" type="button" onClick={() => onChange([...windows, [0, Math.min(300, horizon * 3600)]])}><Plus size={12} />Add time window</button>}</div>;
}

export default function DiscoverySetup({ model, value, onChange }: { model?: Model; value: DiscoveryConfig; onChange: (value: DiscoveryConfig) => void }) {
  const sensorCount = value.bias_values_m.length * value.sensor_windows_s.length;
  const valveCount = value.valve_settings.length * value.valve_windows_s.length;
  return <div className="discovery-setup"><div className="group-label"><span><ScanSearch size={13} /> Search for a compound failure</span></div><p className="field-description discovery-intro">Test the clean model, each fault alone, then eligible pairs. Find a pair that exceeds the check while each individual fault passes.</p>
    <div className="discovery-fault-group"><div className="discovery-kind"><span>A</span>Biased depth reading</div><div className="field"><label htmlFor="discovery-sensor">Observed basin</label><select id="discovery-sensor" value={value.sensor_asset} onChange={event => onChange({ ...value, sensor_asset: event.target.value })}>{faultAssets(model, 'sensor_bias').map(id => <option key={id} value={id}>{id}</option>)}</select></div><NumberList id="discovery-bias" label="Reading offsets" values={value.bias_values_m} onChange={bias_values_m => onChange({ ...value, bias_values_m })} min={-5} max={5} unit="m" /><Windows id="discovery-sensor-window" title="Sensor windows" windows={value.sensor_windows_s} onChange={sensor_windows_s => onChange({ ...value, sensor_windows_s })} horizon={model?.duration_hours ?? 78} /></div>
    <div className="discovery-fault-group"><div className="discovery-kind"><span>B</span>Outlet stuck at an opening</div><div className="field"><label htmlFor="discovery-valve">Outlet asset</label><select id="discovery-valve" value={value.valve_asset} onChange={event => onChange({ ...value, valve_asset: event.target.value })}>{model?.asset_ids.map(id => <option key={id} value={id}>{id}</option>)}</select></div><NumberList id="discovery-openings" label="Stuck openings" values={value.valve_settings} onChange={valve_settings => onChange({ ...value, valve_settings })} min={0} max={1} /><Windows id="discovery-valve-window" title="Valve windows" windows={value.valve_windows_s} onChange={valve_windows_s => onChange({ ...value, valve_windows_s })} horizon={model?.duration_hours ?? 78} /></div>
    <div className="discovery-grid-size"><strong>{sensorCount} × {valveCount}</strong><span>{sensorCount * valveCount} declared pairs</span></div>{(sensorCount > 32 || valveCount > 32) && <p className="field-error">Use at most 32 variants per fault type.</p>}
    <div className="field"><label htmlFor="discovery-budget">Total simulation budget</label><input id="discovery-budget" type="number" min="9" max="300" step="1" required value={Number.isFinite(value.budget) ? value.budget : ''} onChange={event => onChange({ ...value, budget: event.target.valueAsNumber })} /><p className="field-description">Includes screening, retained proof and comparison calls. A budget may stop before every pair is tested.</p></div>
    <details className="discovery-scope"><summary>What the search covers <ChevronDown size={12} /></summary><p>Only these assets, offsets, openings and time windows are searched. Time windows use elapsed model hours on five-minute control intervals. Screening summaries and retained, independently checked traces have separate evidence scopes.</p></details>
  </div>;
}
