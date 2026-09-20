import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { ArrowLeft, ArrowRight, ChartNoAxesCombined } from 'lucide-react';
import { nearestPoint, number, ROLE_LABELS, timeLabel } from '../types';
import type { InvestigationView, RunCase, TracePoint } from '../types';

type Quantity = 'total_flooding_m3s' | 'downstream_flow_m3s' | 'total_storage_m3';
const QUANTITIES: { key: Quantity; label: string; unit: string }[] = [
  { key: 'total_flooding_m3s', label: 'Flooding rate', unit: 'm³/s' },
  { key: 'downstream_flow_m3s', label: 'Downstream flow', unit: 'm³/s' },
  { key: 'total_storage_m3', label: 'Stored water', unit: 'm³' },
];

// Preserve local extremes when reducing the number of SVG vertices. Reported
// metrics always come from the evidence packet, never this display sampling.
function displayPoints(points: TracePoint[], key: Quantity): TracePoint[] {
  if (points.length <= 1200) return points;
  const stride = Math.ceil(points.length / 550);
  const out: TracePoint[] = [points[0]];
  for (let start = 1; start < points.length - 1; start += stride) {
    const bucket = points.slice(start, Math.min(start + stride, points.length - 1));
    let min = bucket[0];
    let max = bucket[0];
    for (const p of bucket) {
      if (p[key] < min[key]) min = p;
      if (p[key] > max[key]) max = p;
    }
    out.push(...(min.time_s < max.time_s ? [min, max] : min === max ? [min] : [max, min]));
  }
  out.push(points[points.length - 1]);
  return out;
}

interface Props {
  view: InvestigationView;
  time: number;
  setTime: (value: number) => void;
  selectedCase: string;
  setSelectedCase: (id: string) => void;
}

export default function Hydrograph({ view, time, setTime, selectedCase, setSelectedCase }: Props) {
  const [quantity, setQuantity] = useState<Quantity>('total_flooding_m3s');
  const [focused, setFocused] = useState(false);
  const [focusFaultId, setFocusFaultId] = useState('');
  const meta = QUANTITIES.find(q => q.key === quantity)!;
  const plottedCases = view.cases.filter(c => c.trace.length > 0);
  const duration = Math.max(1, ...plottedCases.map(c => c.trace[c.trace.length - 1].time_s));
  const active = view.cases.find(c => c.id === selectedCase) ?? view.cases.find(c => c.role === 'reduced') ?? view.cases.find(c => c.role === 'stress') ?? view.cases[0];
  const faults = [{ id: 'primary', asset: view.config.fault_asset, start_s: view.config.start_hour * 3600, end_s: (view.config.start_hour + view.config.duration_hours) * 3600 }, ...(view.config.additional_faults ?? []).map((fault, i) => ({ id: `extra-${i}`, asset: fault.asset, start_s: fault.start_hour * 3600, end_s: (fault.start_hour + fault.duration_hours) * 3600 }))];
  const activeFaults = active?.faults.map((fault, index) => ({ id: String(fault.id ?? index), asset: String(fault.asset ?? ''), start_s: Number(fault.start_s), end_s: Number(fault.end_s) })).filter(fault => Number.isFinite(fault.start_s) && Number.isFinite(fault.end_s)) ?? [];
  const focusOptions = activeFaults.length ? activeFaults : faults;
  const focusFault = focusOptions.find(fault => fault.id === focusFaultId) ?? focusOptions[0];
  const padding = focusFault ? Math.max(900, (focusFault.end_s - focusFault.start_s) * .2) : 0;
  const rangeStart = focused && focusFault ? Math.max(0, focusFault.start_s - padding) : 0;
  const rangeEnd = focused && focusFault ? Math.min(duration, focusFault.end_s + padding) : duration;
  const span = Math.max(1, rangeEnd - rangeStart);
  const clampTime = (t: number) => Math.max(rangeStart, Math.min(rangeEnd, t));
  useEffect(() => { if (time < rangeStart || time > rangeEnd) setTime(Math.max(rangeStart, Math.min(rangeEnd, time))); }, [rangeStart, rangeEnd, time, setTime]);
  const threshold = quantity === 'downstream_flow_m3s' && view.config.metric === 'peak_downstream_flow_m3s' ? view.finding.threshold : null;
  const data = useMemo(() => view.cases.map(c => ({ ...c, points: displayPoints(c.trace.filter(point => point.time_s >= rangeStart && point.time_s <= rangeEnd), quantity) })), [view, quantity, rangeStart, rangeEnd]);
  const rawMax = useMemo(() => {
    let max = threshold ?? 0;
    for (const c of view.cases) for (const point of c.trace) if (point.time_s >= rangeStart && point.time_s <= rangeEnd && Number.isFinite(point[quantity])) max = Math.max(max, point[quantity]);
    return max;
  }, [view, quantity, threshold, rangeStart, rangeEnd]);
  const max = rawMax > 0 ? rawMax * 1.15 : 1;
  const w = 1000, h = 276, left = 64, right = 20, top = 26, bottom = 37;
  const x = (t: number) => left + (clampTime(t) - rangeStart) / span * (w - left - right);
  const y = (v: number) => h - bottom - (v / max) * (h - top - bottom);
  const path = (c: { points: TracePoint[] }) => {
    let started = false;
    return c.points.map(p => {
      if (!Number.isFinite(p[quantity])) { started = false; return ''; }
      const segment = `${started ? 'L' : 'M'}${x(p.time_s).toFixed(2)},${y(p[quantity]).toFixed(2)}`;
      started = true;
      return segment;
    }).join(' ');
  };
  const point = active ? nearestPoint(active.trace.filter(p => p.time_s >= rangeStart && p.time_s <= rangeEnd), clampTime(time)) : undefined;
  const inspectedTime = point?.time_s ?? time;

  return <section className="hydrograph panel" aria-labelledby="hydrograph-title">
    <div className="section-heading">
      <div><div className="section-index"><ChartNoAxesCombined size={15} /> Trace explorer</div><h2 id="hydrograph-title">Follow the water.</h2></div>
      <div className="segmented" aria-label="Chart quantity">{QUANTITIES.map(q => <button key={q.key} aria-pressed={quantity === q.key} onClick={() => setQuantity(q.key)}>{q.label}</button>)}</div>
    </div>
    <div className="chart-legend" aria-label="Cases">{view.cases.map(c => <button key={c.id} className={`legend-item ${selectedCase === c.id ? 'selected' : ''}`} aria-pressed={selectedCase === c.id} onClick={() => setSelectedCase(c.id)}><span className={`line-key ${c.role}`} />{ROLE_LABELS[c.role]}<span className="sr-only">: {c.label}</span></button>)}</div>
    <div className="chart-range-controls"><div className="range-buttons" aria-label="Plot time range"><button aria-pressed={!focused} onClick={() => setFocused(false)}>Full horizon</button><button aria-pressed={focused} onClick={() => setFocused(true)} disabled={!focusFault}>Focus on fault</button></div>{focused && focusOptions.length > 1 && <select aria-label="Fault window to focus" value={focusFault?.id} onChange={event => setFocusFaultId(event.target.value)}>{focusOptions.map(fault => <option key={fault.id} value={fault.id}>Outlet {fault.asset}: {timeLabel(fault.start_s)}–{timeLabel(fault.end_s)}</option>)}</select>}<span>{timeLabel(rangeStart)}–{timeLabel(rangeEnd)} <span className="range-scale-note">{focused ? '· visible-range scale' : '· full horizon'}</span></span></div>
    {!plottedCases.length ? <p className="chart-missing">No trace is available for this experiment.</p> : <>
      <p className="horizontal-scroll-hint">Scroll horizontally to inspect the full chart.</p>
      <div className="plot-wrap" role="region" aria-label="Hydraulic trace chart. Scroll horizontally on narrow screens." tabIndex={0}>
        <svg className="hydrograph-svg" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${meta.label} in ${meta.unit}, from ${timeLabel(rangeStart)} to ${timeLabel(rangeEnd)} elapsed simulation time. Values are available in the time inspector below.`} onClick={event => {
          const box = event.currentTarget.getBoundingClientRect();
          setTime(clampTime(rangeStart + ((event.clientX - box.left) / box.width * w - left) / (w - left - right) * span));
        }}>
          <defs><linearGradient id="stress-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#bf7434" stopOpacity=".13" /><stop offset="100%" stopColor="#bf7434" stopOpacity="0" /></linearGradient></defs>
          {faults.filter(fault => fault.end_s > rangeStart && fault.start_s < rangeEnd).map((fault, index) => <g key={fault.id}><title>{`Declared fault: ${fault.asset}, ${timeLabel(fault.start_s)} to ${timeLabel(fault.end_s)}`}</title><rect x={x(fault.start_s)} y={top} width={Math.max(0, x(fault.end_s) - x(fault.start_s))} height={h - top - bottom} className="fault-window" /><path d={`M${x(fault.start_s)},${top}V${h - bottom}`} className="fault-edge" />{index === 0 && <text x={Math.min(w - 165, x(fault.start_s) + 7)} y={top - 9} className="fault-label">Declared disturbance window</text>}</g>)}
          {[0, 1, 2, 3, 4].map(i => <g key={`y${i}`}><line x1={left} x2={w - right} y1={y(max * i / 4)} y2={y(max * i / 4)} className="grid-line" /><text x={left - 12} y={y(max * i / 4) + 4} textAnchor="end" className="axis-label">{number(max * i / 4, max < 1 ? 3 : 1)}</text></g>)}
          {[0, 1, 2, 3, 4, 5, 6].map(i => <g key={`x${i}`}><line x1={x(rangeStart + span * i / 6)} x2={x(rangeStart + span * i / 6)} y1={top} y2={h - bottom} className="grid-line vertical" /><text x={x(rangeStart + span * i / 6)} y={h - 13} textAnchor="middle" className="axis-label">{number((rangeStart + span * i / 6) / 3600, 1)} h</text></g>)}
          <text x={left - 12} y={top - 9} textAnchor="end" className="axis-unit">{meta.unit}</text>
          {threshold !== null && <g><line x1={left} x2={w - right} y1={y(threshold)} y2={y(threshold)} className="threshold-line" /><text x={w - right - 4} y={y(threshold) - 7} textAnchor="end" className="threshold-label">Declared check: {number(threshold)} {meta.unit}</text></g>}
          {data.filter(c => c.points.length).map(c => <path key={c.id} d={path(c)} className={`trace-line ${c.role} ${selectedCase === c.id ? 'active' : ''}`} />)}
          <line x1={x(inspectedTime)} x2={x(inspectedTime)} y1={top} y2={h - bottom} className="inspection-line" />
          {data.map(c => { const p = nearestPoint(c.trace.filter(point => point.time_s >= rangeStart && point.time_s <= rangeEnd), inspectedTime); return p && Number.isFinite(p[quantity]) ? <circle key={c.id} cx={x(p.time_s)} cy={y(p[quantity])} r={c.id === selectedCase ? 5 : 3} className={`trace-dot ${c.role}`} /> : null; })}
        </svg>
      </div>
      <div className="time-control">
        <label htmlFor="inspection-time">Inspect time <strong>{timeLabel(inspectedTime)}</strong></label>
        <button className="icon-button" aria-label="Inspect one hour earlier" onClick={() => setTime(clampTime(time - 3600))}><ArrowLeft size={15} /></button>
        <input id="inspection-time" type="range" min={rangeStart} max={rangeEnd} step={Math.max(1, span / 1000)} value={clampTime(time)} onChange={e => setTime(Number(e.target.value))} aria-valuetext={`${timeLabel(clampTime(time))} elapsed simulation time`} />
        <button className="icon-button" aria-label="Inspect one hour later" onClick={() => setTime(clampTime(time + 3600))}><ArrowRight size={15} /></button>
      </div>
      <div className="time-readings" style={{ '--case-count': Math.max(1, view.cases.length) } as CSSProperties}>{view.cases.map((c: RunCase) => { const p = nearestPoint(c.trace, inspectedTime); return <div key={c.id} className={`time-reading ${c.id === selectedCase ? 'active' : ''}`}><span><i className={`legend-dot ${c.role}`} />{ROLE_LABELS[c.role]}</span><strong>{number(p?.[quantity], 4)} <small>{meta.unit}</small></strong><small>Sample at {timeLabel(p?.time_s)}</small></div>; })}</div>
      <p className="chart-note">{focused ? 'Focused view; all outcome metrics still cover the full horizon. ' : 'Elapsed simulation time. '}Plot vertices may be reduced for display; reported metrics come from the evidence packet.</p>
    </>}
  </section>;
}
