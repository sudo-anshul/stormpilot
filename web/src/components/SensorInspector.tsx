import { useState } from 'react';
import { ArrowRight, Eye, Info } from 'lucide-react';
import type { InvestigationView } from '../types';
import { nearestPoint, number, caseRoleLabel, timeLabel } from '../types';

export default function SensorInspector({ view, selectedCase, setSelectedCase, time, setTime }: { view: InvestigationView; selectedCase: string; setSelectedCase: (id: string) => void; time: number; setTime: (time: number) => void }) {
  const [node, setNode] = useState('');
  const diagnosticCases = view.cases.filter(run => run.trace.some(point => point.controller_diagnostics && Object.keys(point.controller_diagnostics).length));
  if (!diagnosticCases.length) return null;
  const active = view.cases.find(run => run.id === selectedCase) ?? view.cases[0];
  const sample = active ? nearestPoint(active.trace, time) : undefined;
  const sensorFault = view.cases.flatMap(run => run.faults).find(fault => String(fault.type).startsWith('sensor_'));
  const sensors = view.model.nodes.filter(item => ['basin', 'storage'].includes(item.kind));
  const selectedNode = sensors.find(item => item.id === node)?.id ?? sensors.find(item => item.id === sensorFault?.asset)?.id ?? sensors[0]?.id ?? '';
  const diagnostic = sample?.controller_diagnostics?.[selectedNode];
  const physical = sample?.node_depths_m?.[selectedNode];
  const observed = sample?.observed_depth_m?.[selectedNode];
  const exampleCase = diagnosticCases.find(run => run.role === 'fallback') ?? diagnosticCases[0];
  const examplePoint = exampleCase.trace.find(point => Math.abs(point.controller_diagnostics?.[selectedNode]?.estimated_offset_m ?? 0) > .000001);
  function inspectExample() { setSelectedCase(exampleCase.id); setTime(examplePoint?.time_s ?? exampleCase.trace[0]?.time_s ?? 0); }
  return <section className="sensor-inspector panel" aria-labelledby="sensor-title"><div className="section-heading"><div><div className="section-index"><Eye size={15} />Observation and control</div><h2 id="sensor-title">What the sensor says. What the policy uses.</h2></div><button className="text-button" onClick={inspectExample}>{examplePoint ? 'Inspect an offset hypothesis' : 'Inspect controller state'} <ArrowRight size={14} /></button></div><p className="section-description">Read the physical model state, the supplied sensor reading and the policy’s control input at the same retained sample. The policy sees observations and their recent history; physical depth is shown here for inspection.</p>
    <div className="sensor-inspector-controls"><div className="field"><label htmlFor="sensor-inspection-node">Observed basin</label><select id="sensor-inspection-node" value={selectedNode} onChange={event => setNode(event.target.value)}>{sensors.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}</select></div><div className="field"><label htmlFor="sensor-inspection-case">Policy trace</label><select id="sensor-inspection-case" value={active?.id ?? ''} onChange={event => setSelectedCase(event.target.value)}>{view.cases.map(run => <option key={run.id} value={run.id}>{caseRoleLabel(run.role, Boolean(view.repair))} · {run.controller_id === 'plausible_depth' ? 'sensor plausibility control' : run.controller_id.replaceAll('_', ' ')}</option>)}</select></div><p>Sample at <strong>{timeLabel(sample?.time_s)}</strong><span>Use the trace explorer’s time control to inspect another point.</span></p></div>
    <div className="sensor-reading-grid"><div><span>Simulated physical depth</span><strong>{number(physical, 4)} <small>m</small></strong><p>Inspection reference</p></div><div><span>Supplied sensor reading</span><strong>{number(observed, 4)} <small>m</small></strong><p>May include the declared fault and noise</p></div><div><span>Depth used by policy</span><strong>{number(diagnostic?.control_depth_m, 4)} <small>m</small></strong><p>{diagnostic ? 'After the policy’s partial offset correction' : 'No offset diagnostic recorded for this policy'}</p></div></div>
    {diagnostic ? <div className="sensor-hypothesis"><Info size={17} /><div><strong>Estimated offset hypothesis: {number(diagnostic.estimated_offset_m, 4)} m</strong><p>{number(diagnostic.detected_jumps, 0)} threshold crossing{diagnostic.detected_jumps === 1 ? '' : 's'} recorded · aggregate command cap scale {number(diagnostic.aggregate_cap_scale, 4)}×.</p><p>The estimate is internal controller state, not a confirmed sensor diagnosis or a measure of detection accuracy. The command cap uses estimated heads; it does not guarantee an actual downstream-flow limit.</p></div></div> : <div className="sensor-hypothesis"><Info size={17} /><div><strong>This selected trace has no offset-correction diagnostics.</strong><p>Choose a sensor-plausibility trace or use “Inspect an offset hypothesis” to inspect the available controller state.</p></div></div>}
  </section>;
}
