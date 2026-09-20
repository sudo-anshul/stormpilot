# StormPilot

**Find the stormwater failures that individual fault tests miss.**

[Open the live workbench](https://stormpilot.vercel.app) · [Submission story](docs/submission-draft.md) · [Executed verification](docs/verification.md)

StormPilot connects an actual hydraulic simulator to a decision workflow: import a supported drainage model, discover interacting failures, search candidate responses, challenge them on a separate evaluation, and export the evidence. Built for NextStep Hacks 2026, **Earth Forward**. The GitHub repository remains private; the live demo is accessible without a GitHub account.

## The finding

In the public Theta benchmark, neither a biased sensor nor a restricted valve causes flooding on its own. Together, they cause **237.263 m³** over the full 78-hour simulation. The faults do not even overlap: the sensor reads 1 m high during hours 3–6, then outlet 2 is fixed at 0.035 opening during hours 6–8. The earlier disturbance changes the storage available when the second fault arrives.

| Tested condition | Flooding (m³) |
|---|---:|
| No fault | 0 |
| Sensor bias alone | 0 |
| Valve restriction alone | 0 |
| Both faults | 237.263 |
| Both, with the candidate sensor-plausibility policy | 19.361 |

The declared 3×3 grid uses **21 native calls**: 16 screening calls and five retained full-proof calls. Screening is summary-only; the selected interaction is independently checked against complete traces. The fixed flooding contract is 100 m³. These are simulated benchmark outcomes, not real-world avoided flooding.

## The response did not pass final evaluation

The 91.84% development reduction is promising, but it is not the final verdict. StormPilot keeps the counterevidence:

| Frozen evaluation | Valid runs | Aggregate joint flooding change | Decision |
|---|---:|---:|---|
| Phase 1: balanced-flow candidate | 48 | **22.45% worse** | Rejected |
| Phase 2: sensor-plausibility candidate | 64 | **7.29% better** | Rejected |

Phase 2 required at least 10% aggregate improvement and material improvement in four of eight transformations; it achieved two. All 32 flood nonregression comparisons passed, but one downstream-excess guard failed: +1.471 m³ against a 1 m³ allowance. Candidate selection and protocols were frozen before their respective reserved suites. Those cases are now seen and cannot become a new holdout by rerunning them.

This is the useful decision: a striking development result is **not sufficient to recommend the controller**. Both phase reports, full proofs, source snapshots and rejection criteria are retained in [evaluation/](evaluation/README.md). Subsequent user-triggered tests are explicitly labeled **declared robustness suites**, not unseen evaluations.

## Try the complete workflow

1. Open the labeled recorded discovery, inspect the declared search envelope, then start a fresh **Discover interacting faults** run.
2. Compare no-fault, sensor-only, valve-only and combined traces. Inspect fault timing and the complete physical outcome table.
3. Search a guarded response. The parameter grid, call budget and every candidate rejection remain visible.
4. Inspect sensor plausibility at hour 3: physical depth, observed depth and the controller's estimated control depth are distinct. The estimated sensor offset is a hypothesis, not truth available to the policy.
5. Run a declared robustness suite or open the separate Phase 1 and Phase 2 recorded evaluations. Read the failure reasons before the detailed table.
6. Download a decision report and source-complete evidence ZIP. **Replay run** executes the recorded configurations again and compares their results.

Bring your own self-contained `.inp` model through **Import model**. Inspection exposes native units, horizon and available controls; downstream mapping and targets are explicit. The current supported envelope includes bounded DYNWAVE storage/orifice networks with inline rainfall. [Import scope and limits](docs/model-import.md) explain rejected features.

## Run locally

Requirements: **Python 3.10+**, **Node.js 22.12+**, and **clang or GCC** on macOS or Linux. The hydraulic/validation backend uses Python's standard library; the local workflow needs no API key.

```sh
npm ci
npm run build
python3 server.py --port 8787
```

Open http://127.0.0.1:8787. The first fresh run compiles pinned EPA source if needed. For frontend development, keep the server running and use `npm run dev` (Vite proxies `/api` to port 8787).

```sh
npm test
npm run build
python3 engine/cli.py discover --request engine/examples/discovery-request.json --output runtime/discovery.json
python3 -m validation.validate_packet runtime/discovery.json --root . --output runtime/check.json
python3 engine/cli.py replay --request runtime/discovery.json --output runtime/replayed.json
python3 -m validation.replay runtime/discovery.json runtime/replayed.json --root . --output runtime/replay-check.json
```

Record validation and fresh simulator replay have different scopes. Only an executed matching replay receives `replay_status: matched`. Plot sampling never replaces the complete routing-step evidence.

## Architecture and contribution

- **Hydraulics:** pinned official EPA SWMM 5.2.4 C source, compiled through a Python/ctypes bridge. Native subprocesses isolate solver state; adaptive routing and fault/control boundaries are preserved.
- **Experiments:** bounded deterministic compound search; matched ablations; parameter search with flood, downstream and terminal guards; causal sensor-history diagnostics.
- **Independent evidence:** a separate validator recomputes metrics, checks physical traces, source/input identity, paired external conditions, search accounting and claims. Frozen evaluations keep failures as results.
- **Workbench:** React, TypeScript, SVG plots/schematics, model import, fault/policy controls, immutable run links, candidate/rejection tables and report/export/replay.
- **Hosting:** Vercel native container builds the Linux solver. Private Vercel Blob stores completed jobs, source archives and imported model artifacts. Native computation runs within the active request; completed evidence survives container cache loss. Downloads use expiring signed links.

EPA SWMM supplies established hydraulics; pystorms supplies the public benchmarks and control foundations. Fault injection, parameter search and holdout evaluation are established methods. StormPilot contributes their connected, inspectable workflow around a stormwater planning decision. It does not claim novel hydraulic physics or a trained AI forecasting model.

## Limits and attribution

Theta and Gamma are idealized public benchmarks, not calibrated city networks. The network view is a schematic, not an inundation map. We have no municipal partner, operator study, measured time savings or field-protection result. The hosted app is a bounded research prototype; the selected controller failed its declared reserved evaluation. A valid simulation is not a safe deployment recommendation.

The welcome fixture is a genuine recorded discovery: UI job `6174a80795372955`, experiment `9df1ca1d7273778d8e7c`. Regenerate intentionally with `python3 scripts/record_demo.py` after an engine change; never relabel old evidence with new sources.

See [implementation decisions](docs/implementation-plan.md), [interaction discovery](docs/interaction-discovery.md), [sensor plausibility](docs/sensor-plausibility.md), [validation](docs/validation.md), [deployment](docs/deployment.md) and [demo narration](docs/demo-narration.md).

[EPA SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm) retains its public-domain notices. Included [pystorms](https://github.com/kLabUM/pystorms) material is pinned to revision `20cc6086433449df99177d4f9103940639ef3af0` and retains GPLv3. This project uses [GPLv3](LICENSE); see [the model license](engine/data/PYSTORMS-LICENSE).
