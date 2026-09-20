# Evidence and validation contract

StormPilot evaluates policies in a published simulation. A passing evidence check means the recorded experiment is reproducible and the reported numerical claims follow from its artifacts. It does **not** establish a calibrated local flood forecast, a field diagnosis, a successful physical repair, or a general safety guarantee.

This contract is coordinated with the engine interface. The independent validator lives in `validation/`; the simulator and experiment generation remain in `engine/`.

## Experimental unit

An experiment pins one model, one engine revision, one rainfall/event artifact, an evaluation horizon, a fault/noise realization, controller definitions, and the property to test. Each run changes only an explicitly listed treatment: controller selection and/or selected fault set. The experiment includes unchanged control, a stressed policy, any counterfactual ablations, and any proposed fallback.

Required provenance consists of cryptographic digests of the exact artifacts used, not a label such as “SWMM latest.” The model source URL identifies origin; the digest identifies the bytes actually evaluated. A random seed identifies a generation request but does not by itself identify the realized exogenous stream.

## Fairness

1. All paired runs use the same base model, rainfall, initial condition, evaluation horizon, solver settings and external fault/noise realization. Allowed differences are explicit treatments.
2. Faults/noise are indexed by asset and simulation time. The same perturbation is applied to each run's **own** physical state. Fairness does not require identical numerical state observations after policies cause different trajectories.
3. An ablation disables only its named faults. A fallback faces the same active faults as the stressed run. A clean baseline is an explicit reference condition, not an unlabeled switch to all-knowing control.
4. The acting policy sees only its timestamped observation history and an explicitly declared forecast. It cannot see hidden fault schedules, future realized rainfall, noise-free evaluation state, or post-run metrics. An offline auditor may inspect completed trajectories to find and explain a witness; that hindsight cannot be presented as operational foresight.
5. Additional reads cannot redraw the environment's ordinary noise. `pystorms.state(level="1")` reveals the entire true state, while `step(level="1")` bypasses actuator faults; neither is a selective field inspection or repair.
6. Baselines receive the same information and simulation budget. A controller is not handicapped to manufacture an improvement.

The validator can check recorded artifact identities and treatment consistency. It cannot establish that arbitrary controller code never accessed undeclared information. That requires source review or a separate process exposing only the observation interface; the result must state which was done.

## Trace and metric protocol

The engine normalizes physical quantities to SI. The evidence trace must identify its sampling/integration protocol and cover the complete common horizon. A timestamp is simulation time, not wall-clock time. All numbers are finite; time increases strictly; flooding rates and stored volumes cannot be negative beyond declared numerical tolerance.

The first interface targets are total flooding rate (m³/s), positive downstream discharge (m³/s), and total stored water (m³), together with time (s). Total stored water must include nodes **and links**, including conduit water. Where the engine supplies full routing-step samples, the independent checker recomputes trace-integrated flooding and downstream excess volumes, peak downstream discharge and terminal storage. Native solver cumulative volumes are retained separately. An approximate integral over coarse display samples must not be silently substituted for the native solver total.

A threshold exceedance volume is the time integral of `max(flow − threshold, 0)`, not the full discharged volume. A peak flow is m³/s, never m³. A percentage change requires the named reference and a nonzero reference value; if the reference is near zero, report the absolute change.

The upstream benchmark score is retained only as its published objective. It is not renamed “flood damage,” “people protected” or “water saved.” Separate outcomes cover flooding, relevant downstream discharge and terminal storage or a common drain-down requirement. This prevents a plan from appearing better merely because it shifts water to an unscored node or beyond the evaluation window. Engine runoff/routing continuity errors are included with their units and interpretation.

## Claim acceptance

### Baseline reproduction

- Pin executable source and model bytes; state the exact scenario/version.
- Run unchanged control under a declared exogenous realization.
- Verify complete traces, numerical integrity, continuity diagnostics and metric recomputation.
- Compare an upstream reference only when engine, scenario, objective, step schedule and fault generation actually match. Otherwise call it a new baseline run, not a reproduction of published figures.

### Failure witness

- State a numerical property before interpreting the result: metric, reference run, direction, materiality threshold and numerical tolerance.
- The stressed run must violate that property by more than tolerance under the recorded horizon.
- A witness is the exact replayable tuple of model, policy, rainfall, faults/noise and property. An attractive frame or a changed scalar score alone is insufficient.

### Paired fault ablation

- Retain the same exogenous catalog and remove only the named fault IDs.
- Replay the same controller and horizon; independently recompute the property.
- Attribute a difference only within this model and treatment set. A removed model fault is not evidence that a field maintenance action will succeed.

### Reduced witness

- The reduced fault set is a subset of the original witness and still violates the declared property.
- “Verified 1-minimal” requires a replay removing each remaining fault in turn, with every such removal eliminating the violation.
- If some removals were not tested, use “reduced witness.” Neither status implies globally minimal severity, duration or fault count.

### Fallback comparison

- The fallback faces the same faults, weather, horizon and information as the stressed policy.
- Report absolute values and changes for each guard metric, not only the preferred metric.
- “Improves the primary metric” and “passes all specified non-regression guards” are different claims. If the fallback shifts harm downstream or retains water beyond the terminal limit, present a tradeoff rather than a clean improvement.
- No observed violation means only no violation in the tested cases. It is not a safety certificate.

### Replay packet

- Include the model, exogenous realization, controller definitions, experiment declaration, complete evaluation traces and numerical results or unambiguous references to their included files.
- Hash each included artifact and reject altered or missing files.
- Independent replay checks use the same declared numerical tolerances. Byte-identical floating-point results across platforms are not assumed.
- Export a validation report listing passed, failed and unperformed checks. No run becomes “verified” merely because the producer set a Boolean.

## Required negative checks

The checker must reject or withhold the relevant claim for a changed rainfall artifact, mismatched horizon, nonfinite or out-of-order trace, materially incorrect reported integral, ablation that adds a fault, fallback evaluated on fewer faults, absent single-removal evidence behind a minimality claim, a favorable primary metric with hidden downstream/terminal regression, or a modified packet artifact.

These tests verify the evidence contract. They do not rerun the simulator's own equations or prove hydraulic calibration. Numerical verification, empirical validation and real-world effect remain separate.

## Implemented JSON interface

The fixed packet version is `stormpilot.evidence.v1`. `validation.validate_packet.validate_run(run, experiment)` checks one run; `validate_packet(packet, root_path=None)` checks the complete evidence and relationships. The validator imports no engine module. It requires only the Python standard library.

| Field | Required contents |
|---|---|
| `packet.schema_version` | `stormpilot.evidence.v1` |
| `packet.experiment` | Shared context plus `scenario_id`, `threshold_m3s`, `metric_protocol`, `test_contract`, full `exogenous`, full `solver_settings`, and `faults` catalog |
| Shared context | `base_model_sha256`, `effective_model_sha256`, `rainfall_sha256`, `exogenous_sha256`, `solver_settings_sha256`, `horizon_s`, `information_boundary_id` |
| `experiment.metric_protocol` | `routing-step-right-rectangle-v1` |
| `experiment.test_contract` | `metric`, `threshold`, `tolerance`, `units`, `horizon_s`, `mode: "absolute"`, `direction: "above"`; an optional `increase` mode requires `reference_run_id` |
| `packet.test_contract_sha256` | Canonical digest of the full test contract |
| `packet.runs` | Nonempty list of uniquely named completed runs |
| Each run | `run_id`, `role`, `context`, `controller`, `active_fault_ids`, `units`, `trace`, `routing_steps`, `metrics`, `continuity` |
| `run.controller` | `id`, `source_sha256`, `parameters`; descriptions may also be included |
| `run.units` | `{"time":"s","flow":"m3/s","volume":"m3","depth":"m"}` |
| Each trace row | `time_s`, `total_flooding_m3s`, `downstream_flow_m3s`, `total_storage_m3` |
| `run.metrics` | `flood_volume_m3`, `downstream_excess_volume_m3`, `peak_downstream_flow_m3s`, `terminal_storage_m3`, `native_flood_volume_m3` |
| `run.continuity` | `runoff_error_pct`, `routing_error_pct`; other native diagnostics may also be present |
| `packet.artifacts` | List of `{"path":"relative/included/path","sha256":"…"}`; absolute, parent-traversing and escaping paths are rejected |
| `packet.provenance` | Base model digest/path, runner source digest, solver/bridge source bundle digest, pinned upstream references |
| `packet.request` | The replay request, including the rainfall multiplier |

The trace starts at zero and ends at `horizon_s`; `routing_steps` equals the number of intervals, which is one less than the trace row count. `display_trace` can be downsampled for the interface, but it is never the validator's integration input. Right-end rates are integrated over each preceding actual routing interval. Native cumulative flooding is independently compared with that sum. Physical flow and volume conversions use the exact internal cubic-foot conversion, `0.028316846592`, consistently; rounded public API unit factors must not be mixed into the same comparison.

Default numerical comparison tolerances are absolute `1e-6`, relative `1e-8`, timestamp `1e-6` seconds, and an absolute native runoff/routing continuity diagnostic bound of `1.0%`. `experiment.numerical_tolerances` can state these explicitly. The diagnostic bound is a screening choice, not proof of model accuracy. The test property's materiality threshold and tolerance are separate from arithmetic tolerances. A tiny `1e-12` relative/absolute roundoff allowance prevents a binary floating-point boundary from being reported as a strict property violation.

Canonical JSON means Python-compatible `json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)` encoded as UTF-8. The checker reconstructs the exogenous/settings/property digests from the actual included objects. It also reconstructs the declared rainfall transform from the base model and requested multiplier, and checks the effective model digest. Source bundle hashing includes each sorted solver-source path relative to `engine/`, a null byte, then its exact bytes, followed by `native_bridge.c` in the same format. These checks detect stale or changed evidence; they do not authenticate who originally produced the packet.

Optional relationship records use these shapes:

```json
{
  "ablations": [
    {"source_run_id": "stress-id", "run_id": "removed-id", "removed_fault_ids": ["fault-id"]}
  ],
  "witness": {
    "run_id": "reduced-id",
    "original_run_id": "stress-id",
    "claim": "1-minimal",
    "single_removals": [{"fault_id": "fault-id", "run_id": "removed-id"}]
  },
  "fallback": {
    "stressed_run_id": "stress-id",
    "fallback_run_id": "fallback-id",
    "primary_metric": "flood_volume_m3",
    "minimum_improvement": 0,
    "tolerance": 0.000001,
    "maximum_increase": {
      "downstream_excess_volume_m3": 0,
      "peak_downstream_flow_m3s": 0,
      "terminal_storage_m3": 0
    }
  }
}
```

This is an interface example, not observed evidence. Every referenced run must actually be included. A `reduced` witness can retain unsuccessful single-removal attempts; a `1-minimal` witness cannot. A fallback report always includes all four metric changes. Missing guards withhold the aggregate guarded-improvement claim. An explicitly claimed `guarded_improvement` that violates a guard fails validation; an honestly recorded tradeoff remains valid evidence.

## Commands and report semantics

Run these commands from the repository root:

```sh
python3 -m unittest discover -s validation -t . -v
python3 -m validation.validate_packet engine/runs/first-packet.json --root .
python3 -m validation.validate_packet packet.json --root extracted-packet --output validation-report.json
```

The command exits with `0` for passed recorded checks, `1` for failed evidence, and `2` for partial evidence. Its report includes `status`, individual `checks` with `passed`, `failed` or `unperformed`, per-run `computed_metrics`, independently evaluated `claims`, `scope: "recorded_evidence"`, and `replay_status: "unperformed"`. A record check never sets a replay badge. Artifact identity is partial when no artifact root or manifest is supplied. Missing numerical diagnostics remain unperformed; supplied nonfinite diagnostics fail.

Source/interface review and field calibration are explicit unperformed categories in the automatic report, outside its arithmetic/integrity pass status. Source review by a human or separate agent must be documented independently, tied to the actual code being shipped. A producer's own validation flags and explanatory prose are not used to accept evidence.

## Architecture review and observed checks

The implementation plan's process-isolated native engine, fixed policy library, shared exogenous catalog and separate validation module support the intended evidence boundary. A native engine with global state must not run competing simulations in a shared thread. Keeping all exogenous fault boundaries in every ablation's step schedule avoids a numerical step change being mistaken for the removed fault's effect.

The first stable native packet was checked against three complete 9,361-row traces. All independently recomputed metrics, native flooding crosschecks, common contexts, horizon coverage and continuity bounds passed. Its artifact manifest was not yet included, so the recorded report was partial and replay was unperformed. The result showed 0 m³ nominal flooding, approximately 1,618.64 m³ under the stressed policy, and approximately 1,267.83 m³ under the all-open fallback. The fallback increased positive downstream excess volume from 0 to approximately 2,649.28 m³ and peak downstream discharge from approximately 0.4901 to 6.2656 m³/s. This supports a tradeoff, not an unqualified improvement.

Source review identified two presentation/correctness issues before integration: terminal water originally counted nodes only and must also include link water; sensor “dropout” is implemented as a zero reading, so it must be described as a zero-reading sensor failure. The current `commands` interface receives perturbed observations from its own run, static geometry and policy parameters; the call does not expose future rainfall or the fault catalog. That is a source review of this implementation, not a proof about arbitrary uploaded controllers.

The 31 focused validator tests currently cover independent irregular-interval arithmetic, threshold crossing, invalid timestamps/numbers, missing diagnostics, canonical-content changes, altered/missing artifacts, changed horizons, unfair ablation/fallback treatments, incomplete minimality evidence and hidden terminal-water regressions. Their small synthetic fixtures test evidence handling, not SWMM's hydraulic equations. Corrected final packets must be regenerated and rechecked after source or metric changes.

## Source basis

- [EPA SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm): model scope and numerical simulation context.
- [pystorms](https://pystorms.netlify.app/): public scenarios and established fault/controller comparisons.
- [Inspected instrumentation source](https://github.com/kLabUM/pystorms/blob/release/2.0.0/pystorms/environment.py): per-read noise, hidden state, fault windows and mode-switch semantics; pin the actual revision used.
- [Dario Amodei, Machines of Loving Grace (2024)](https://www.darioamodei.com/essay/machines-of-loving-grace): intelligence cannot replace missing observations. This is a researched application of his reasoning, not an endorsement of StormPilot.
