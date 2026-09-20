export type MetricId = 'flood_volume_m3' | 'peak_downstream_flow_m3s' | 'downstream_excess_volume_m3' | 'terminal_storage_m3';

export interface ExperimentConfig {
  model_id: string;
  controller_id: string;
  fallback_controller_id: string;
  metric: MetricId;
  threshold: number;
  fault_asset: string;
  fault_kind: string;
  start_hour: number;
  duration_hours: number;
  budget: number;
  additional_faults?: { asset: string; start_hour: number; duration_hours: number }[];
  [key: string]: unknown;
}

export interface Model {
  id: string;
  name: string;
  description: string;
  source: string;
  asset_ids: string[];
  nodes: { id: string; x: number; y: number; kind: string }[];
  links: { id: string; from: string; to: string }[];
  duration_hours: number;
}

export interface Policy { id: string; name: string; description: string }
export interface Catalog {
  models: Model[];
  policies: Policy[];
  defaults: ExperimentConfig;
  engine: { status: string; version: string };
}

export interface TracePoint {
  time_s: number;
  total_flooding_m3s: number;
  total_storage_m3: number;
  downstream_flow_m3s: number;
  node_depths_m?: Record<string, number>;
}

export type CaseRole = 'nominal' | 'stress' | 'reduced' | 'fallback';
export interface RunCase {
  id: string;
  role: CaseRole;
  label: string;
  controller_id: string;
  faults: Record<string, unknown>[];
  metrics: Record<MetricId, number | null>;
  trace: TracePoint[];
}

export interface InvestigationView {
  id: string;
  created_at: string;
  recorded: boolean;
  config: ExperimentConfig;
  model: Model;
  cases: RunCase[];
  finding: {
    status: 'violation' | 'no_violation' | 'baseline_failure' | 'incomplete' | 'unverified';
    title: string;
    description: string;
    metric: string;
    threshold: number;
    unit: string;
    first_time_s: number | null;
  };
  search: {
    status?: string;
    stopping_reason?: string;
    metric?: MetricId;
    unit?: string;
    conditions?: { id: string; asset: string; start_hour: number; duration_hours: number; retained: boolean | null }[];
    tests?: { id: string; phase: string; active_fault_ids: string[]; value: number | null; violated: boolean | null }[];
    evaluated: number;
    budget: number;
    method: string;
    reduced_from: number;
    reduced_to: number;
    claim: string;
    coverage: string | string[];
  };
  validation: {
    status: string;
    checks: { id: string; status: string; message: string }[];
    limitations: string[];
    replay_status?: string;
    claims?: {
      witness?: { claim?: string; active_fault_ids?: string[]; tested_removals?: string[]; globally_minimal?: boolean };
      fallback?: {
        primary_improved: boolean;
        all_specified_guards_pass: boolean;
        guarded_improvement: boolean;
        conclusion: string;
        changes: Partial<Record<MetricId, { change: number; guard_passed: boolean | null; maximum_increase: number | null }>>;
      };
    };
  };
  provenance: {
    engine_version: string;
    model_sha256: string;
    source_url: string;
    model_name: string;
    units: string;
    run_seconds: number;
  };
}

export interface Job {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase: string;
  message: string;
  error?: string;
}

export const METRICS: Record<MetricId, { label: string; unit: string; description: string }> = {
  flood_volume_m3: { label: 'Flooding volume', unit: 'm³', description: 'Total modeled water leaving the drainage system as flooding.' },
  peak_downstream_flow_m3s: { label: 'Peak downstream flow', unit: 'm³/s', description: 'Highest modeled flow at the downstream outlet.' },
  downstream_excess_volume_m3: { label: 'Downstream excess volume', unit: 'm³', description: 'Discharge integrated above the declared downstream flow limit.' },
  terminal_storage_m3: { label: 'Terminal storage', unit: 'm³', description: 'Water remaining in storage at the end of the common horizon.' },
};

export const ROLE_LABELS: Record<CaseRole, string> = {
  nominal: 'Nominal', stress: 'Stressed', reduced: 'Reduced witness', fallback: 'Fallback',
};

export function number(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en', { maximumFractionDigits: digits }).format(value);
}

export function timeLabel(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return '—';
  return `${number(seconds / 3600, 2)} h`;
}

export function nearestPoint(trace: TracePoint[], time: number): TracePoint | undefined {
  if (!trace.length) return undefined;
  let low = 0;
  let high = trace.length - 1;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (trace[mid].time_s < time) low = mid + 1;
    else high = mid;
  }
  const after = trace[low];
  const before = trace[Math.max(0, low - 1)];
  return Math.abs(after.time_s - time) < Math.abs(before.time_s - time) ? after : before;
}
