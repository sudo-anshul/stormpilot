# StormPilot implementation plan

Status: improved implementation deployed to Vercel, September 20, 2026; final release verification and demonstration assets in progress. The contest deadline previously verified is September 20, 2026, 17:00 EDT / September 21, 02:30 IST.

## Product result and scope

### Execution status — improved release

| Milestone | Actual result |
|---|---|
| Repository | Private `sudo-anshul/stormpilot`; milestone commits and pushes. |
| Native engine | Pinned EPA SWMM 5.2.4 executes on macOS and the Vercel Linux container. |
| Discovery | 3×3 bounded grid; 21 calls; selected faults produce 0 m³ alone and 237.263 m³ together. |
| User workflow | Supported `.inp` import, SI mapping, sensor/valve controls, policy parameters, search/rejection ledger and causal sensor inspection. |
| Candidate development | Sensor plausibility reduces the compound development case to 19.361 m³; 293 attempted development calls are disclosed. |
| Independent evaluation | Phase 1 rejected (+22.45% aggregate flooding); Phase 2 rejected (−7.29%, one downstream guard failure). All 112 reserved runs valid. Exact protocols, sources and full proofs preserved. |
| Evidence | Separate record validation, actual replay, portable source ZIPs, decision reports and declared user-triggered robustness suites. |
| Hosting | Live at https://stormpilot.vercel.app with a Linux native container and private Blob persistence. Final cloud regression checks and demo recording are recorded in the verification document. |

The stronger welcome discovery is UI job `6174a80795372955`, experiment `9df1ca1d7273778d8e7c`. Neither evaluated response is recommended for field use. No score or winning guarantee follows from these milestones.

The plan below retains milestone acceptance and technical rationale. A planned
capability is not an executed result unless marked above or in the decision log.

Build a complete workbench that answers: **under the tested conditions, where does this stormwater control plan fail, what causes the failure in the model, and what does another policy change?**

The primary user is a planning analyst, researcher or learner investigating a supplied model. The hackathon judge must be able to change a permitted condition, obtain an actual simulation-backed result, inspect its explanation and download the experiment. We will not rely on real repair hardware or unprovided municipal data. Solo participation does not constrain the ambition; verified milestones organize execution.

The first complete vertical path is: curated public model → nominal simulation → declared instrumentation stress → failure property → reduction through reruns → matched fallback comparison → independently checked evidence export. A second model and broader search follow once that path works. No results are fabricated to fit the intended demonstration.

### Required capabilities

- Published model/source provenance, clear units and a documented control policy.
- A native EPA SWMM engine executing actual hydraulic calculations.
- Explicit asset/time-indexed exogenous faults, with deterministic replay.
- A bounded search over supported faults and a transparent search budget.
- Physical metrics independently recomputed from traces where meaningful.
- A reduced failure example with the exact reduction guarantee stated.
- Fair fallback comparisons with paired external conditions, each run retaining its own hydraulic state.
- A responsive analyst workbench with meaningful empty, pending, completed, partial and error states.
- An evidence packet, replay command and independent verification result.
- A private GitHub repository and pushed commits after major milestones.

### Excluded from the initial claim

Field diagnosis, actual maintenance prescriptions/cost savings, accurate street-level flood maps, residents protected, novel hydraulic physics, a guarantee of safety, and a guarantee of winning. Arbitrary user code execution and unrestricted uploaded models are unnecessary for the first complete entry. Published benchmark facts and our new contribution will be distinguished in the README and demonstration.

## Architecture and file ownership

Keep the runtime small enough to reproduce without a large machine-learning environment.

| Layer | Initial implementation | Owner |
|---|---|---|
| Hydraulic engine | Official EPA SWMM source compiled locally if packaged native library cannot load; thin Python standard-library bridge/CLI | Andrej implementation lane |
| Curated scenarios | Exact public input files, source hashes, license notices, documented units and reference settings | Andrej implementation lane |
| Experiment logic | Fixed policy library, fault schedule, physical trace, search and reduction calls | Engine lane with root integration |
| Independent verification | Packet schema, provenance checks, trace metric recomputation, comparison invariants and reduction checks | Dario validation lane |
| API/service | Python standard-library HTTP service; process isolation for native engine jobs; bounded inputs and job polling | Root |
| Interface | React + TypeScript + Vite; SVG charts and hydraulic network diagram; semantic tokens and responsive layout | Root, Sam product review |
| Evidence/export | Versioned JSON plus model/source references and replayable run configuration; archive download | Root + validation lane |
| Delivery | Repeatable setup script, tests, production frontend build, CI, private repository, demo instructions | Root |

The native solver may use global state. Run experiments in isolated worker processes, not concurrently in Python threads sharing one native model. The HTTP layer can remain responsive while it polls job status. Reject unsupported network/policy/fault IDs and cap candidate counts. A failed worker must produce an explicit error without corrupting prior results.

Build the interface around a versioned JSON contract, not direct native-engine objects. Engine results provide model metadata, units, policy, time series, metric values, event summaries, provenance and status. The validator adds a separate validation report; the UI must not derive a validation badge from an engine success flag alone.

## Milestone 0 — repository, plan and evidence contract

1. Create the private repository under the authenticated user's account.
2. Commit this plan, README, ignore rules, design direction and advisor responsibilities.
3. Agree the engine CLI and evidence contract with the technical and validation lanes.
4. Record the important existing limitations: packaged SWMM loading terminated before model initialization; full dependency setup previously ran out of disk space; public models are not calibrated local city models.

Acceptance: remote visibility verified private; no credentials, local environments or unrelated research files committed; all lanes have bounded ownership and compatible interfaces.

Commit: `chore: establish StormPilot project and implementation plan`.

## Milestone 1 — actual engine proof

1. Resolve engine loading without silently replacing SWMM with toy hydraulics. Try a source build from a pinned official EPA revision with installed clang if necessary.
2. Run a small curated published model to completion and preserve the input hash and engine version.
3. Capture every routing step, terminal state and simulator diagnostics. Preserve native calculation precision; convert units explicitly for display. Downsample only the display trace, never the independent integration evidence.
4. Repeat the baseline with identical external inputs and compare results within stated numeric tolerances.
5. Apply one supported controlled perturbation and show that the result is produced by the native model.
6. Ask Andrej to review runtime, units and baseline, and Dario to review the information boundary and physical metrics.

Acceptance: complete baseline and repeat; actual traces; controlled perturbation; no placeholder numerical output. A crash must remain visible as a failed experiment. If native loading remains blocked, resolve execution before claiming the demonstration works.

Commit: `feat: run reproducible SWMM benchmark experiments`.

## Milestone 2 — experiments, failure discovery and reduction

1. Freeze a supported fault grammar (for example sensor bias/dropout and stuck outlet with bounded asset, onset and duration).
2. Precompute rainfall/fault/noise inputs indexed by asset and time. Extra diagnostic reads cannot alter later disturbances.
3. State each checked property with units, horizon and source or user-provided threshold. Separate a benchmark's aggregate reward from physical overflow or flow.
4. Run no-fault, stress and established reference policies under equivalent settings. Keep hidden physical truth and future realized rainfall away from the online policy.
5. Implement deterministic enumeration/search with an explicit call budget, cached identical configurations and cancellation boundaries. Use a simple method first; an agent search must earn its computational cost against that baseline.
6. When a case fails, remove conditions and rerun. Record every tested removal and its result. Label locally reduced cases accurately; do not imply exhaustive global minimality.
7. Compare an existing fallback under the same exogenous stream. If it worsens another metric, preserve that result.
8. Record source/seed/configuration fingerprints so independently replayed output can be checked.

Acceptance: a failure or meaningful tested tradeoff is genuinely observed; replay confirms it; removing a claimed necessary condition is evaluated; the fallback does not benefit from hidden information; unsuccessful searches report exactly what was tested.

Commit: `feat: discover and reduce policy failure cases`.

## Milestone 3 — analyst workbench

The interface is a technical field notebook. It opens directly into a useful experiment rather than a marketing landing page.

- Masthead: StormPilot identity, model context, run state and evidence access.
- Setup rail: scenario, policy, test requirement, supported stress controls and run action.
- Primary result: one plain-language conclusion from actual run state, relevant physical measurements and a clear next action.
- Main chart: aligned nominal/stress/fallback time series with a keyboard-accessible time inspector and fault windows.
- Network context: topological model view, selected asset and recorded state. It is not a street inundation map.
- Evidence inspector: selected event, units, source, time and comparison result.
- Investigation: candidate progress, search coverage, selected/reduced witness and fallback tradeoffs.
- Export: downloadable evidence and replay instructions, enabled only for a completed appropriate artifact.

All controls must work. Before results arrive, show unavailable measurements as unavailable rather than zero. During jobs, show actual progress or a clear indeterminate state. Worker errors remain legible and retryable. A precomputed welcome case, if included, must be an actual saved engine result explicitly identified as a replay.

Responsive behavior: on narrow screens the setup rail becomes a compact top section, the result remains first, charts scroll or adapt without clipping, and evidence opens below the relevant visualization. Keyboard focus, non-color status markers and reduced motion are required.

Ask Sam to critique the first working user journey. Inspect rendered desktop and narrow layouts using the design-direction and interface-design-review skills. Fix the flow before decorative polish.

Acceptance: a fresh input can run, results match the backend, time/asset selection works, search/reduction and fallback are reachable, the archive downloads, and primary flows work with keyboard and narrow layout.

Commit: `feat: add interactive stormwater investigation workbench`.

## Milestone 4 — evidence, replay and meaningful verification

1. Package configuration, provenance, permitted perturbations, timestamps, metrics, result traces and comparison/reduction records.
2. Independently recompute supported physical metrics and verify finite values, monotonic time, units and shared exogenous inputs.
3. Verify reduction claims from evaluated neighbors and compare fallback on all declared metrics.
4. Provide a clean replay command that uses the same pinned engine/model and validates its output within documented tolerance.
5. Test negative cases: wrong model hash, missing trace, changed fault stream, nonfinite numbers, unsupported policy, worker crash and interrupted job. Use behavioral tests that exercise meaningful risks.
6. Separate benchmark correctness, explanation fidelity, UI usability and field validity. Only completed evidence checks support a corresponding badge.

Acceptance: a generated packet passes independent validation; a deliberately corrupted packet fails; a replay reproduces the result; the UI accurately reports incomplete/error evidence.

Commit: `feat: export and independently verify replayable evidence`.

## Milestone 5 — polish and submission readiness

1. Production frontend build, backend health check and full primary flow using the real engine.
2. Rendered desktop/narrow review, empty/loading/error states, control semantics and contrast review.
3. Clean environment setup and CI where feasible; document verified commands and platform-specific engine requirements.
4. Final advisor feedback: Sam checks judge clarity, Andrej checks the technical contribution/baselines, Dario checks claims and evidence boundaries. Resolve material objections and record decisions.
5. Prepare a four-minute demo script around the best actual result. Preserve failed or tied comparisons when they explain the finding.
6. Document upstream code/data and original work, build steps, known limits and actual learning. The repository remains private as requested; judge access or public release is a separate action.
7. Provide a working local preview and a deployment path. If a public preview can be deployed through available authorized infrastructure, verify it before presenting it as live.

Acceptance: implementation and verification claims match executed evidence; fresh run and export work; no fake impact quantities; all major milestones are committed and pushed; remaining submission/account actions are explicit.

Commit: `docs: prepare verified demo and submission materials` plus scoped fixes as needed.

## Review cadence and decision log

The named advisor skills are researched interpretations of public work, not real consultations. They will review substantive decisions and results throughout implementation, not merely approve the initial pitch.

| Review point | Questions | Required response |
|---|---|---|
| Architecture/contract | Is the task fully specified? Are actions and claims supported? | Resolve engine/validator/API fields and scope before integration. |
| Engine proof | Are units, exogenous pairing and metrics valid? | Replay and independently recompute the result. |
| First full UI | Can a judge identify what was tested, what failed and why? | Fix unclear flow and unsupported copy. |
| Evidence export | Can someone reproduce the same conclusion? | Pass valid packet, reject corrupted packet and run replay. |
| Final demo | Is the new contribution clear and the stated impact honest? | Apply material feedback and record remaining limits. |

Initial decision: keep the project; make failure investigation the core. Existing tools already provide simulation and faults. Our contribution must be the complete search/reduction/comparison/evidence workflow and its usable presentation.

## Progress log

- Plan initialized; repository creation and engine source-build investigation in progress.
- Sam review requested for workflow and rendered-review acceptance; Dario review requested for independent evidence contract; Andrej implementation assigned actual engine proof.
- Private repository created and verified: `sudo-anshul/stormpilot`; initial plan pushed at `49a1ea8`.
- Official EPA SWMM 5.2.4 source builds with installed clang and loads successfully, resolving the previous native-wheel blocker. A complete theta run and controlled stuck-outlet run have produced real traces.
- Sam architecture feedback accepted: freeze an immutable Test Contract/run identity; pull independent packet validation and replay into the first engine proof; ensure no-violation, tied fallback and no-reduction outcomes remain complete user journeys.
- Andrej feedback accepted: retain full routing-step samples for independent numerical checks and downsample only for presentation.
