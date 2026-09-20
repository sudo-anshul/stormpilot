# Evidence and validation contract

StormPilot evaluates policies in a published simulation. A passing evidence check means the included artifacts and reported numerical claims are internally consistent. An actual simulator replay is checked separately. It does **not** establish a calibrated local flood forecast, a field diagnosis, a successful physical repair, or a general safety guarantee.

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
python3 engine/cli.py investigate --request engine/examples/reduction-request.json --output packet.json
python3 -m validation.validate_packet packet.json --root .
python3 -m validation.validate_packet packet.json --root extracted-packet --output validation-report.json
python3 engine/cli.py replay --request packet.json --output replayed-packet.json
python3 -m validation.replay packet.json replayed-packet.json --root . --output replay-report.json
```

The command exits with `0` for passed recorded checks, `1` for failed evidence, and `2` for partial evidence. Its report includes `status`, individual `checks` with `passed`, `failed` or `unperformed`, per-run `computed_metrics`, independently evaluated `claims`, `scope: "recorded_evidence"`, and `replay_status: "unperformed"`. A record check never sets a replay badge. Artifact identity is partial when no artifact root or manifest is supplied. Missing numerical diagnostics remain unperformed; supplied nonfinite diagnostics fail.

Source/interface review and field calibration are explicit unperformed categories in the automatic report, outside its arithmetic/integrity pass status. Source review by a human or separate agent must be documented independently, tied to the actual code being shipped. A producer's own validation flags and explanatory prose are not used to accept evidence.

`validation.replay.compare_replay(original, replayed, root_path)` compares a freshly executed replay against the original. It checks both packets, unchanged experiment/request/source identities, logical run IDs and treatments, all physical trace rows, recomputed metrics, and per-node flood/peak results. It ignores creation times, runtime and report CPU timings. The current replay comparator expects the same routing sample grid within timestamp tolerance. The simulator CLI re-executes all unique recorded controller/fault treatments; search declarations are retained for comparison, but the search procedure itself is not re-executed. Comparing two copied packets alone cannot establish execution.

## Joint-failure policy evaluation: phase 1

The main evaluation separates a real development improvement from an unfavorable unseen result. The protocol was pinned before the new fault screen and policy tuning: `evaluation/protocol.json`, SHA-256 `1cd92c48b91c465c9e18c0bca1c39cc112c9993c7e9e510061964f1672eb29b4`. Its full horizon is 280,800 seconds, and the primary flood limit is 100 m³ with a 1e-6 m³ tolerance.

The development pair combines a +1 m depth-reading bias at P2 during 10,800–21,600 seconds with outlet 2 stuck at setting 0.035 during 21,600–28,800 seconds. Under `constant_flow` with `target_scale=1`, clean, valve-only and sensor-only flooding are all zero; the pair produces **237.262837 m³**. The pair satisfies joint necessity for this threshold violation. The separately calculated interaction excess is also 237.262837 m³; the claim does not rest on threshold crossing alone.

The grid-selected `balanced_flow` policy (`target_scale=0.98`, `balance_gain=2`) reduces development-pair flooding to **11.580060 m³**, while passing the fixed clean/single nonregression checks and all downstream/terminal guards. These guards allow increases of at most 0.001 m³/s downstream peak, 1 m³ downstream excess volume, and 0.1 m³ terminal node-and-link storage. Candidate snapshot SHA-256: `99590e22adb316c6639f61088b246f4d4881a3497855856de2c4d60a2b99ea5b`.

That candidate **fails the complete six-transform heldout evaluation**. All 48 native policy/subset runs produced valid evidence, but paired flooding increases in aggregate from **8,461.737544 to 10,361.597851 m³**: **+1,899.860307 m³, or +22.45%**. Only one of the six paired cases meets the declared individual improvement criterion; three were required. Twelve of 24 subset comparisons fail the 1 m³ primary nonregression allowance. The valve-only comparison in h2 also increases downstream peak by 0.006222947 m³/s, exceeding the 0.001 m³/s guard. All terminal-storage guards pass.

| Fixed transform | Reference paired flood (m³) | Candidate paired flood (m³) | Candidate minus reference (m³) |
|---|---:|---:|---:|
| h1 | 0.000 | 0.000 | 0.000 |
| h2 | 451.740 | 1,162.861 | +711.122 |
| h3 | 4,361.069 | 5,034.020 | +672.951 |
| h4 | 258.297 | 57.290 | −201.007 |
| h5 | 0.000 | 0.000 | 0.000 |
| h6 | 3,390.632 | 4,107.427 | +716.795 |

The three higher-rainfall transforms also worsen flooding in their clean runs, so this failure is not confined to the chosen fault pair. A fixed lower release target and reliance on noisy or biased depth allocation are plausible contributors. The comparison changes both allocation and total target, so it does not isolate their causal contributions. These already-seen cases can only serve as explicitly labeled development/diagnostic data for subsequent policy work.

The complete phase 1 record is preserved in `evaluation/phase1-evidence.zip`, SHA-256 `33baf99ec58d5dec629cb75b58aead13cc9e54e7b229d3544cfb6b2fa192d1fd`, containing the exact engine/model/evaluator sources, frozen protocol and candidate, development proof and all six compressed heldout proofs. The original report SHA-256 is `a705049c23f2021c5d54dcb5c67810ed4c4ab4af31cd3b494f5c019d83324627`.

A separate audit extracted that archive and independently recomputed every compressed full trace against the archived source/model bytes: **56 runs, 727,771 trace rows, 1,015 passed checks, zero failures**, and 21 explicit unperformed categories (three per packet). All archived aggregate outcomes match the original report. `validation/phase1-archive-audit.json` records this audit. It is a fresh record check, not a second native simulator execution; it does not set a replay badge or revise the unfavorable policy outcome.

### Independent tuning-ledger audit

`validation/repair.py` independently checks the declared Cartesian grid, exact candidate order/coverage, sequential hydraulic calls, budget and cache accounting, all candidate comparisons, guard failures, materiality, and the final feasibility-first selection rule. The genuine production repair has **25 candidates, 104 hydraulic calls, 12 rejected candidates**, and exhausts its declared grid. Its packet passes **151 recorded checks**, with three explicit unperformed categories. The selected policy's eight proof treatments match the ledger and independently checked full traces.

The other 96 tuning calls retain compact metrics, diagnostics and trace digests; their full traces are not in this repair packet. Their ledger consistency is checked, but independent trace integration cannot be claimed for those missing traces. The original preselection request is also not embedded: its digest is syntactically checked but cannot be recomputed from the selected-policy request. These limits are explicit in `validation/production-repair-check.json`. Neither a consistent ledger nor a development improvement establishes optimizer superiority.

### Separately frozen phase 2

Before further controller development or any new-suite outcome, `evaluation/phase2/protocol.json` was frozen at **2026-09-20 15:37:21 UTC**, SHA-256 `15e373f2f634a26a9fd8013853ab6618e1b57ef79877effea7a0ddf2ae1dadd7`. It fixes the same development pair and reference policy while expanding to eight seeded stratified transforms (64 policy/subset runs), with broader rainfall, noise, duration and signed bias severity, and separate sensor/valve timing shifts. No phase 2 simulation was run while declaring those transforms.

The original per-case guards remain unchanged. Every one of the 32 subset comparisons must pass guards and flood nonregression; the paired aggregate must improve by both 80 m³ and 10%, and at least four of eight paired cases must each improve by both 10 m³ and 10%. A single new candidate is frozen before that suite executes. All earlier results stay visible. A later policy or criterion change cannot reuse either observed suite as unseen evidence.

The later controller declares `causal-depth-history-feedback-v2` instead of the protocol's `causal-depth-feedback-v1` identifier. A dated **pre-execution semantic clarification and metadata deviation** records that v2 adds isolated history of the same permitted noisy depth observations, with no additional true-state, fault, rainfall or future information. Reference and candidate share the v2 context, and state is created empty inside every run. The frozen protocol bytes, transforms and acceptance thresholds are unchanged. The clarification was recorded after controller development began and before phase 2 execution; this chronology is explicit. Its file, `evaluation/phase2/information-boundary-clarification.json`, is pinned into the candidate and report with SHA-256 `79693d55b10a98befd4351257c5920a8f25a25a9f0e244854dda7ad31b96ce6d`.

### Phase 2 result: valid evidence, rejected controller

The final `plausible_depth` candidate uses `target_scale=1`, `jump_threshold_m=0.65` and `correction_fraction=0.75`. Its development pair improves from **237.262837 to 19.361153 m³** (91.84%), while clean and valve-only outputs are exactly unchanged and all declared development guards pass. Candidate snapshot SHA-256: `742f3f43880930dbb2146bf99d1a8d901f4427df00ae5cdeb101d7c8269e3e4f`.

The complete phase 2 development ledger has **293 attempted native calls: 292 completed and one disk-exhaustion failure**, within the 512-call budget. It preserves four exact historical source versions and 11 request identities. Independent checks confirm ledger sequencing, budget, source/request hashes, finite metrics and diagnostics, and all eight selected final traces. The final 16-call default search contains three candidates; the selected proof passes 151 recorded checks. Unlike the earlier phase 1 packet, this repair includes its original request, whose content hash is independently checked. These records are in `engine/experiments/phase2-development/`; audit reports are `validation/phase2-development-ledger-audit.json` and `validation/phase2-development-proof-check.json`.

The new unseen suite **still rejects the candidate**. All 64 native runs are valid, and no subset increases flooding beyond the 1 m³ allowance. Aggregate paired flooding falls from **9,840.092953 to 9,122.721824 m³**, an improvement of **717.371129 m³ (7.2903%)**. The relative requirement was 10%. Only two paired cases meet the individual 10 m³ and 10% improvement criteria; four were required. In p2h1, paired downstream excess volume increases by **1.47113394 m³**, above the 1 m³ guard. Every other downstream/terminal guard passes.

| Fixed transform | Reference paired flood (m³) | Candidate paired flood (m³) | Candidate minus reference (m³) |
|---|---:|---:|---:|
| p2h1 | 3,243.744 | 2,822.424 | −421.320 |
| p2h2 | 0.000 | 0.000 | 0.000 |
| p2h3 | 2,289.404 | 2,289.404 | 0.000 |
| p2h4 | 412.007 | 412.007 | 0.000 |
| p2h5 | 2,727.436 | 2,727.436 | 0.000 |
| p2h6 | 0.000 | 0.000 | 0.000 |
| p2h7 | 1,167.502 | 871.451 | −296.051 |
| p2h8 | 0.000 | 0.000 | 0.000 |

The recorded report is `evaluation/phase2/report.json`, SHA-256 `757b0a7a4095a5cadc2b01ef7efdc364521bbad4d31aef3792c244472c459b98`. `evaluation/phase2-evidence.zip`, SHA-256 `8210a09aa32d5da9808b3f9f730f2c6bbbc8c5ae07b59d10899d6129131c1223`, preserves the exact evaluation sources, model, protocol, clarification, candidate, development ledger/source history, base proof and all eight complete heldout proofs. It supplements the earlier phase 1 archive; neither rejected result is replaced.

A separate extraction verified all **218 archived files** and independently recomputed **72 full runs, 933,235 trace rows and 1,311 passed checks**, with zero failures and 27 explicit unperformed categories. All aggregate results agree with the frozen report. Then the archived native sources were compiled in that separate directory, and p2h1 was actually replayed. All eight treatments and **109,088 physical trace rows** matched, with maximum observed difference zero; all 11 replay-comparison checks passed. The exact compressed replay is retained at `evaluation/phase2/p2h1-replay.json.gz`; `validation/phase2-archive-audit.json` and `validation/phase2-p2h1-replay-check.json` record these checks. This proves same-host reproduction of this case, not cross-platform equality or field validity.

After hashes, complete compact records and selected proofs were retained, 284 nonselected development scratch packets were removed to recover disk space. Their source versions, request identities, metrics, diagnostics and trace hashes remain; they are explicitly **summary-only evidence**, with no claim that their missing full traces were independently reintegrated. The final development proof, its eight individual selected traces, every heldout packet and the exact replay remain preserved. No policy tuning followed the new unseen outcomes. StormPilot's supported result is a reproducible discovery and falsification workbench, not a validated general controller.

## Earlier reduction prototype checks (superseded as the main example)

The implementation plan's process-isolated native engine, fixed policy library, shared exogenous catalog and separate validation module support the intended evidence boundary. A native engine with global state must not run competing simulations in a shared thread. Keeping all exogenous fault boundaries in every ablation's step schedule avoids a numerical step change being mistaken for the removed fault's effect.

The final frozen reduction packet (`engine/runs/final-reduction-packet.json`, experiment `1841c184f7f7d0b3fbcb`) passed **131 recorded checks**, with zero failures. Three explicitly separate categories remain unperformed by that invocation: independently executed replay, policy information-access proof, and field calibration. Source provenance, canonical forcing/settings/property hashes, model/rainfall reconstruction, all five run traces, native flood crosschecks, continuity, paired removals, fallback guards and recorded search coverage passed. The packet used five unique simulations from a budget of eight.

| Physical metric | Nominal | Reduced stressed case | All-open fallback |
|---|---:|---:|---:|
| Flood volume (m³) | 0.00 | 1,621.45 | 1,275.42 |
| Positive downstream excess volume above 0.5 m³/s (m³) | 0.00 | 0.00 | 2,661.93 |
| Peak positive downstream discharge (m³/s) | 0.49155 | 0.49009 | 6.35534 |
| Terminal node-and-link water volume (m³) | 4.65102 | 4.65102 | 4.59102 |

The declared requirement was flood volume no greater than 100 m³, with numerical tolerance 1e-6 m³. A supplied two-condition case was reduced to `f1`; the complete single-removal evidence supports **1-minimality under this model and property**, not global minimality over all timing, severities, storms or conditions. The fallback reduces flooding by approximately 346.03 m³ but fails both downstream guards. Its honest conclusion is a tradeoff.

A separate, actually executed CLI replay then reran all five recorded configurations from the frozen packet. The independent replay comparator passed all eight checks; all **63,556 physical trace rows** and recomputed metrics matched exactly on this machine. This observed equality does not imply byte-identical cross-platform results. The comparator allows the documented numerical tolerance. `validation/final-packet-check.json` and `validation/final-replay-check.json` record these checks in the local workspace.

Two additional real-engine outcome cases were executed and independently checked, with **115 passed recorded checks each** and no failures:

- `validation/cases/nominal-violation.json` deliberately sets a peak-discharge limit of zero. The nominal run already violates it, so the result is `nominal_violation` with no claimed fault witness.
- `validation/cases/no-violation.json` deliberately sets a very permissive flood-volume limit. The complete supplied one-condition envelope yields `no_violation_found`, with no witness and an accurately recorded `envelope_exhausted` stop.

These deliberately extreme limits test result handling, not operationally meaningful engineering requirements. Run either case with `python3 engine/cli.py investigate --request validation/cases/CASE.json --output case-packet.json`, followed by the record-check command above. Reports are saved locally as `validation/nominal-violation-check.json` and `validation/no-violation-check.json`.

A copy of the genuine final packet was deliberately altered by subtracting 100 m³ from its reported stressed flood volume while preserving the original trace. Independent validation rejected it; `validation/genuine-corruption-check.json` records the failed arithmetic and dependent claims. The **40 focused validator tests** also pass, covering irregular-interval arithmetic, threshold crossing, invalid timestamps/numbers and overflow, missing diagnostics, canonical-content changes, altered/missing artifacts, wrong horizons, unfair treatments, incomplete minimality evidence, hidden terminal-water regressions, inconsistent search budgets/candidates and changed replays. Small synthetic unit fixtures test evidence handling, not SWMM's equations.

Source review produced three implemented corrections before this final evidence was generated: total terminal water now includes node and link volumes; sensor “dropout” is explicitly a zero-reading failure; and timestep caps preserve adaptive routing instead of invoking the public route-step setter that silently disables it. The current `commands` interface receives perturbed observations from its own run, static geometry and policy parameters, without future rainfall or a fault catalog. That is a source review of this fixed implementation, not a proof about arbitrary uploaded controllers. Source and metric changes require new packets and checks.

## Export portability check

A fresh two-condition API export, job `cffb0edfb52c40ce`, was extracted into a new directory outside the repository. All **111 files** listed in its archive manifest matched their hashes. No native library was supplied; the exported EPA/bridge sources were compiled locally using the installed compiler. The compile command referenced only the extracted source tree, with no dependency on the original checkout.

All four commands in the archive's `REPLAY.md` succeeded: recorded packet validation, actual solver replay, replayed packet validation, and independent original/replay comparison. Both record reports passed 131 checks; the replay comparison passed eight. All five cases and 63,556 physical trace rows matched, with maximum observed difference zero. No Python package installation was required. `validation/archive-portability-check.json` records the archive SHA-256, commands and observed results in the local workspace.

This verifies an independent-directory rebuild and replay on the same macOS host with its installed Python/compiler. Linux and other host/compiler combinations remain untested here; exact cross-platform identity and field validity are not claimed. The archive review also identified two optional regression-request JSON files referenced by this document but absent from the initial archive; they should be included under `validation/cases/` in subsequent exports. The primary documented replay path was complete and passed.

## Source basis

- [EPA SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm): model scope and numerical simulation context.
- [pystorms](https://pystorms.netlify.app/): public scenarios and established fault/controller comparisons.
- [Inspected upstream instrumentation](https://github.com/kLabUM/pystorms/blob/release/2.0.0/pystorms/environment.py): per-read noise, hidden state, fault windows and mode-switch semantics.
- [Dario Amodei, Machines of Loving Grace (2024)](https://www.darioamodei.com/essay/machines-of-loving-grace): intelligence cannot replace missing observations. This is a researched application of his reasoning, not an endorsement of StormPilot.
