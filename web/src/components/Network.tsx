import { useState } from 'react';
import { GitBranch } from 'lucide-react';
import type { Model, RunCase } from '../types';
import { nearestPoint, number, timeLabel } from '../types';

export default function Network({ model, runCase, time, faultAsset }: { model: Model; runCase?: RunCase; time: number; faultAsset: string }) {
  const [selectedNode, setSelectedNode] = useState('');
  const nodes = model.nodes ?? [];
  const selected = nodes.find(n => n.id === selectedNode) ?? nodes[0];
  const sample = runCase ? nearestPoint(runCase.trace, time) : undefined;
  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = Math.max(1, maxX - minX), height = Math.max(1, maxY - minY);
  const scale = Math.min(270 / width, 180 / height);
  const position = (n: {x: number; y: number}) => ({ x: 175 + (n.x - (minX + maxX) / 2) * scale, y: 126 - (n.y - (minY + maxY) / 2) * scale });
  return <section className="network-panel panel" aria-labelledby="network-title">
    <div className="section-heading"><div><div className="section-index"><GitBranch size={15} /> Model context</div><h2 id="network-title">A system, connected.</h2></div></div>
    {nodes.length > 0 ? <>
      <svg className="network-svg" viewBox="0 0 350 250" role="img" aria-label={`Schematic of ${model.name}. Select a node using the control below.`}>
        <defs><pattern id="network-grid" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#cad5d2" /></pattern><marker id="flow-arrow" markerWidth="5" markerHeight="5" refX="9" refY="2.5" orient="auto"><path d="M0,0L5,2.5L0,5" fill="#78908b" /></marker></defs>
        <rect x="0" y="0" width="350" height="250" fill="url(#network-grid)" />
        {(model.links ?? []).map(link => { const a = nodes.find(n => n.id === link.from); const b = nodes.find(n => n.id === link.to); if (!a || !b) return null; const p = position(a), q = position(b); return <g key={link.id}><line x1={p.x} y1={p.y} x2={q.x} y2={q.y} className={`network-link ${link.id === faultAsset ? 'fault' : ''}`} markerEnd="url(#flow-arrow)" />{link.id === faultAsset && <g><rect x={(p.x + q.x) / 2 - 5} y={(p.y + q.y) / 2 - 5} width="10" height="10" rx="1" className="network-fault" transform={`rotate(45 ${(p.x + q.x) / 2} ${(p.y + q.y) / 2})`} /><text x={(p.x + q.x) / 2 + 11} y={(p.y + q.y) / 2 - 8} className="network-asset-label">{link.id}</text></g>}</g>; })}
        {nodes.map(n => { const p = position(n); return <g key={n.id} className={`network-node ${n.id === selected?.id ? 'selected' : ''}`} onClick={() => setSelectedNode(n.id)}><circle cx={p.x} cy={p.y} r={n.kind === 'outfall' ? 5 : 8} /><circle cx={p.x} cy={p.y} r="2" className="node-center" /><text x={p.x} y={p.y + 24} textAnchor="middle">{n.id}</text></g>; })}
      </svg>
      <div className="network-caption"><span className="schematic-key"><i /> Storage / junction</span><span>Benchmark schematic</span></div>
      <div className="node-inspector"><label htmlFor="inspect-node">Inspect node</label><select id="inspect-node" value={selected?.id ?? ''} onChange={e => setSelectedNode(e.target.value)}>{nodes.map(n => <option key={n.id} value={n.id}>{n.id} · {n.kind}</option>)}</select><div className="node-reading"><span>Recorded depth<small>{runCase ? `${runCase.label} at ${timeLabel(sample?.time_s)}` : 'Run an experiment to inspect water depth'}</small></span><strong>{number(selected && sample?.node_depths_m?.[selected.id], 3)} <small>m</small></strong></div></div>
    </> : <div className="network-unavailable"><GitBranch size={28} /><p>No schematic coordinates are available for this model.</p><span>Model evidence remains available in the trace and packet.</span></div>}
    <p className="network-note">Topology shows model connections, not street locations or an inundation map.</p>
  </section>;
}
