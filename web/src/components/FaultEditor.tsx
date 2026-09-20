import type { FaultConfig, FaultKind, Model } from '../types';
import { number } from '../types';

export const FAULT_OPTIONS: { id: FaultKind; label: string }[] = [
  { id: 'stuck_closed', label: 'Outlet stuck closed' },
  { id: 'valve_stuck', label: 'Outlet stuck at an opening' },
  { id: 'sensor_bias', label: 'Biased depth reading' },
  { id: 'sensor_dropout', label: 'Depth sensor reads zero' },
];

export function isSensorFault(kind?: string) { return kind === 'sensor_bias' || kind === 'sensor_dropout'; }
export function faultAssets(model: Model | undefined, kind?: string): string[] {
  return isSensorFault(kind) ? (model?.nodes ?? []).filter(node => ['basin', 'storage'].includes(node.kind)).map(node => node.id) : model?.asset_ids ?? [];
}
export function faultLabel(kind?: string) { return FAULT_OPTIONS.find(option => option.id === kind)?.label ?? String(kind ?? 'Outlet stuck closed').replaceAll('_', ' '); }

export default function FaultEditor({ model, fault, onChange, prefix = 'fault' }: { model?: Model; fault: FaultConfig; onChange: (next: FaultConfig) => void; prefix?: string }) {
  const kind = fault.kind ?? 'stuck_closed';
  const assets = faultAssets(model, kind);
  const invalidHorizon = fault.start_hour + fault.duration_hours > (model?.duration_hours ?? 78);
  const set = (patch: Partial<FaultConfig>) => onChange({ ...fault, ...patch });
  return <div className="fault-editor">
    <div className="field"><label htmlFor={`${prefix}-kind`}>Fault behavior</label><select id={`${prefix}-kind`} value={kind} onChange={event => {
      const next = event.target.value as FaultKind;
      const options = faultAssets(model, next);
      set({ kind: next, asset: options.includes(fault.asset) ? fault.asset : options[0] ?? '' });
    }}>{FAULT_OPTIONS.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select></div>
    <div className="field"><label htmlFor={`${prefix}-asset`}>{isSensorFault(kind) ? 'Observed basin' : 'Outlet asset'}</label><select id={`${prefix}-asset`} value={fault.asset} onChange={event => set({ asset: event.target.value })} required>{!assets.length && <option value="">No supported asset available</option>}{assets.map(asset => <option key={asset} value={asset}>{asset}</option>)}</select></div>
    {kind === 'valve_stuck' && <div className="field"><label htmlFor={`${prefix}-setting`}>Stuck opening</label><input id={`${prefix}-setting`} type="number" required min="0" max="1" step="any" value={Number.isFinite(fault.setting ?? 0) ? fault.setting ?? 0 : ''} onChange={event => set({ setting: event.target.valueAsNumber })} /><p className="field-description">0 is closed; 1 is fully open. The physical outlet holds this setting.</p></div>}
    {kind === 'sensor_bias' && <div className="field"><label htmlFor={`${prefix}-bias`}>Reading offset</label><div className="input-with-unit"><input id={`${prefix}-bias`} type="number" required min="-5" max="5" step="any" value={Number.isFinite(fault.bias_m ?? 1) ? fault.bias_m ?? 1 : ''} onChange={event => set({ bias_m: event.target.valueAsNumber })} /><span>m</span></div><p className="field-description">Added to the measured depth during the fault window. Negative values under-read.</p></div>}
    {kind === 'sensor_dropout' && <p className="fault-behavior-note">The controller receives a zero-depth reading during this window. The true water level still evolves in the simulation.</p>}
    <div className="field-pair"><div className="field"><label htmlFor={`${prefix}-start`}>Starts at</label><div className="input-with-unit"><input id={`${prefix}-start`} type="number" required min="0" max={Math.max(0, (model?.duration_hours ?? 78) - .01)} step="any" value={Number.isFinite(fault.start_hour) ? fault.start_hour : ''} onChange={event => set({ start_hour: event.target.valueAsNumber })} /><span>h</span></div></div><div className="field"><label htmlFor={`${prefix}-duration`}>Duration</label><div className="input-with-unit"><input id={`${prefix}-duration`} type="number" required min=".01" max={Math.max(.01, (model?.duration_hours ?? 78) - fault.start_hour)} step="any" value={Number.isFinite(fault.duration_hours) ? fault.duration_hours : ''} aria-invalid={invalidHorizon} aria-describedby={invalidHorizon ? `${prefix}-duration-error` : undefined} onChange={event => set({ duration_hours: event.target.valueAsNumber })} /><span>h</span></div></div></div>
    {invalidHorizon && <p id={`${prefix}-duration-error`} className="field-error" role="alert">This disturbance must end within the {number(model?.duration_hours)} h model horizon.</p>}
  </div>;
}
