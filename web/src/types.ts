export type MetricId = 'flood_volume_m3' | 'peak_downstream_flow_m3s' | 'downstream_excess_volume_m3' | 'terminal_storage_m3';
export type FaultKind = 'stuck_closed' | 'valve_stuck' | 'sensor_bias' | 'sensor_dropout';
export interface FaultConfig { asset: string; start_hour: number; duration_hours: number; kind?: FaultKind; setting?: number; bias_m?: number }

export interface ExperimentConfig {
  mode?: 'investigate' | 'discover' | 'run';
  discovery?: DiscoveryConfig | null;
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
  additional_faults?: FaultConfig[];
  fault_setting?: number;
  sensor_bias_m?: number;
  rainfall_multiplier?: number;
  noise_std_m?: number;
  controller_parameters?: Record<string, number>;
  fallback_controller_parameters?: Record<string, number>;
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
  origin?: string;
  flow_units?: string;
  sha256?: string;
  downstream_link?: string;
  downstream_threshold_m3s?: number;
  targets_m3s?: number[];
}

export interface PolicyParameter { id?: string; key?: string; name?: string; label?: string; description?: string; default: number; min: number; max: number; unit?: string }
export interface Policy { id: string; name: string; description: string; parameters?: PolicyParameter[] | Record<string, Omit<PolicyParameter, 'id'>> }
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
  observed_depth_m?: Record<string, number>;
  controller_diagnostics?: Record<string, { estimated_offset_m: number; control_depth_m: number; detected_jumps: number; aggregate_cap_scale: number }>;
}

export type CaseRole = 'nominal' | 'stress' | 'reduced' | 'fallback' | 'single_a' | 'single_b' | 'single_sensor' | 'single_valve' | 'mitigation_empty' | 'mitigation_a' | 'mitigation_b';
export interface RunCase {
  id: string;
  role: CaseRole;
  label: string;
  controller_id: string;
  controller_parameters?: Record<string, number>;
  faults: Record<string, unknown>[];
  metrics: Record<MetricId, number | null>;
  trace: TracePoint[];
}

export interface InvestigationView {
  id: string;
  created_at: string;
  recorded: boolean;
  discovery?: DiscoveryResult | null;
  repair?: RepairResult | null;
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
  single_a: 'Condition A only', single_b: 'Condition B only', single_sensor: 'Sensor only', single_valve: 'Valve only',
  mitigation_empty: 'Candidate · nominal', mitigation_a: 'Candidate · A only', mitigation_b: 'Candidate · B only',
};
export function caseRoleLabel(role: CaseRole, hasResponseSearch = false): string { return role === 'fallback' && hasResponseSearch ? 'Candidate response' : ROLE_LABELS[role]; }

export interface DiscoveryConfig {
  sensor_asset: string;
  valve_asset: string;
  bias_values_m: number[];
  sensor_windows_s: [number, number][];
  valve_settings: number[];
  valve_windows_s: [number, number][];
  budget: number;
}
export interface DiscoveryResult {
  status: 'baseline_failed' | 'interaction_found' | 'no_interaction_found';
  budget: number; simulator_calls: number; screening_calls: number; proof_simulator_calls: number;
  declared_grid: DiscoveryConfig; grid_sha256: string; declared_sensor_variants: number; declared_valve_variants: number;
  declared_pairs: number; screened_singles: number; screened_pairs: number; eligible_interactions_found: number;
  grid_exhausted: boolean; stopping_reason: string; selection_rule: string; joint_proof_verified_by_engine: boolean;
  interaction_values: { nominal: number; sensor_only: number; valve_only: number; joint: number; interaction_excess: number } | null;
  coverage_note: string; verification_scope: string;
}
export interface CandidateFailure {
  subset: string; criterion: string; increase?: number; allowance?: number;
  absolute_reduction_m3?: number; relative_reduction?: number; minimum_absolute_m3?: number; minimum_relative?: number;
}
export interface RepairCandidate {
  candidate_id: string; controller_id: string; parameters: Record<string, number>; eligible: boolean;
  failures: CandidateFailure[]; flood_reduction_m3: number; relative_flood_reduction: number | null;
  comparisons: Record<string, { reference: Record<MetricId, number>; candidate: Record<MetricId, number>; changes: Record<MetricId, number>; guards: Record<string, boolean> }>;
}
export interface RepairResult {
  status: 'reference_not_joint_failure' | 'candidate_found' | 'no_qualifying_candidate';
  budget: number; simulator_calls: number; proof_simulator_calls: number; cache_hits: number;
  declared_grid: RepairSearchConfig; grid_sha256: string;
  declared_candidates: number; evaluated_candidates: number; grid_exhausted: boolean; stopping_reason: string;
  selected: RepairCandidate | null; candidates: RepairCandidate[];
  selection_rule: string; information_boundary: string; verification_scope: string;
  acceptance: { minimum_absolute_flood_reduction_m3: number; minimum_relative_flood_reduction: number; guard_maximum_increase: Record<string, number>; other_subsets_flood_increase_allowance_m3: number; arithmetic_tolerance: number };
}
export interface RepairSearchConfig {
  controller_id?: 'balanced_flow' | 'plausible_depth'; target_scales: number[]; balance_gains?: number[];
  jump_thresholds_m?: number[]; correction_fractions?: number[]; budget: number;
}
export interface EvaluationSubset {
  subset: string; active_fault_ids: string[];
  reference_metrics: Record<MetricId, number>; candidate_metrics: Record<MetricId, number>; changes: Record<MetricId, number>;
  guards: Record<string, boolean>; all_guards_pass: boolean; material_flood_improvement: boolean;
  flood_reduction_m3: number; relative_flood_reduction: number | null;
}
export interface EvaluationReport {
  schema_version: string; suite_type: 'heldout_benchmark' | 'declared_robustness'; status: string;
  completed_at_utc: string; protocol: { id: string; sha256: string; frozen_at_utc: string };
  candidate_snapshot_sha256: string;
  information_boundary_clarification?: { path: string; sha256: string; content: string | Record<string, unknown> };
  matching_identity: { development_request_sha256: string; base_model_sha256: string; controller_source_sha256: string; engine_source_sha256: string; runner_source_sha256: string };
  reference: { controller_id: string; parameters: Record<string, number> };
  candidate: { controller_id: string; parameters: Record<string, number> };
  acceptance: { overall: boolean; development_joint_failure: boolean; development_mitigation: boolean; heldout_usefulness?: boolean; suite_usefulness?: boolean };
  conclusion: string; limitations: string[];
  holdout: {
    case_count: number; policy_run_count: number; expected_policy_run_count: number;
    guard_allowances: Record<string, number>; criteria: Record<string, unknown>; aggregate_metrics: Record<string, unknown>;
    cases: { case_id: string; status: string; error?: string; transform: Record<string, unknown>; subsets: EvaluationSubset[]; validation_counts?: Record<string, number>; trace_records?: unknown }[];
  };
}

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
