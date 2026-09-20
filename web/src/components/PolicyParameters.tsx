import type { Policy, PolicyParameter } from '../types';

const FALLBACK_SCHEMA: Record<string, PolicyParameter[]> = {
  constant_flow: [{ id: 'target_scale', label: 'Discharge target scale', default: 1, min: .5, max: 1.5, unit: '×', description: 'Multiplies the model’s recorded per-outlet discharge targets.' }],
  equal_filling: [{ id: 'target_scale', label: 'Discharge target scale', default: 1, min: .5, max: 1.5, unit: '×' }, { id: 'equal_filling_gain', label: 'Equal-filling gain', default: 1, min: 0, max: 4 }],
  balanced_flow: [{ id: 'target_scale', label: 'Discharge target scale', default: 1, min: .5, max: 1.5, unit: '×' }, { id: 'balance_gain', label: 'Balance gain', default: 1, min: 0, max: 8 }],
  plausible_depth: [{ id: 'target_scale', label: 'Discharge target scale', default: 1, min: .5, max: 1.5, unit: '×' }, { id: 'jump_threshold_m', label: 'Reading-jump threshold', default: .65, min: .2, max: 2, unit: 'm', description: 'An observation-change threshold that updates the offset hypothesis; it is not a confirmed fault diagnosis.' }, { id: 'correction_fraction', label: 'Positive-offset correction', default: .75, min: 0, max: 1, description: 'Fraction of the estimated positive offset removed from the control input. Negative offsets are tracked without increasing throttling.' }],
  uncontrolled: [],
};

export default function PolicyParameters({ policy, values, onChange, prefix, title = 'Policy parameters' }: { policy?: Policy; values: Record<string, number>; onChange: (next: Record<string, number>) => void; prefix: string; title?: string }) {
  const supplied = policy?.parameters;
  const schema: PolicyParameter[] = Array.isArray(supplied) ? supplied : supplied ? Object.entries(supplied).map(([id, parameter]) => ({ id, ...parameter })) : FALLBACK_SCHEMA[policy?.id ?? ''] ?? [];
  if (!schema.length) return null;
  return <details className="policy-parameters"><summary>{title}<span>{schema.length} {schema.length === 1 ? 'setting' : 'settings'}</span><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg></summary><div>{schema.map(parameter => {
    const key = parameter.id ?? parameter.key ?? '';
    parameter = { ...FALLBACK_SCHEMA[policy?.id ?? '']?.find(item => item.id === key), ...parameter };
    if (!key) return null;
    return <div className="field" key={key}><label htmlFor={`${prefix}-${key}`}>{parameter.label ?? parameter.name ?? key.replaceAll('_', ' ')}</label><div className={parameter.unit ? 'input-with-unit' : ''}><input id={`${prefix}-${key}`} type="number" required min={parameter.min} max={parameter.max} step="any" value={Number.isFinite(values[key] ?? parameter.default) ? values[key] ?? parameter.default : ''} onChange={event => onChange({ ...values, [key]: event.target.valueAsNumber })} />{parameter.unit && <span>{parameter.unit}</span>}</div>{parameter.description && <p className="field-description">{parameter.description}</p>}</div>;
  })}</div></details>;
}
