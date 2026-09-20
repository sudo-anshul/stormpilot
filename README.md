# StormPilot

**Crash-test a stormwater control plan before relying on it.**

StormPilot runs a published drainage model, introduces declared outlet faults,
isolates a failure by removing conditions and rerunning the solver, and compares
another policy under the same conditions. The result is an inspectable experiment
with a self-contained source and replay archive.

Built for NextStep Hacks 2026, **Earth Forward**. This repository is private.

## Run locally

Requirements: **Python 3.10+**, **Node.js 22.12+**, and **clang or GCC** on macOS
or Linux. Python uses the standard library. No API keys are needed.

```sh
npm ci
npm run build
python3 server.py --port 8787
```

Open **http://127.0.0.1:8787**. The welcome investigation is a genuine recorded
simulation, labeled as such. Click **Investigate plan** to execute a new one.
The first fresh run compiles the vendored EPA source if necessary.

For interface development, keep the Python server running and use `npm run dev`
in another terminal. Vite proxies `/api` to port 8787.

## Try the complete investigation

1. Keep the recorded Theta benchmark and constant-flow policy. Its declared
   flooding limit is 100 m³ over 78 hours.
2. Investigate the two stuck-closed outlets: outlet 1 during hours 1–6 and
   outlet 2 during hours 30–31.
3. Inspect original and reduced traces. **Focus on fault** enlarges the selected
   disturbance window without changing the full-horizon metrics.
4. Read which conditions remain and inspect the actual removal tests.
5. Compare the reduced witness with the outlets-open fallback and its
   downstream costs.
6. **Export evidence packet** downloads inputs, complete physical traces, exact
   engine/model sources, validator and executable replay instructions.
   **Replay run** executes all recorded configurations before comparing them.

Change the flooding threshold to 100,000 m³ and rerun for a valid no-violation
outcome. Previous results retain their original settings until the new run ends.
Gamma supplies a second public 11-basin benchmark with a 156-hour horizon.

## The recorded result

These are simulated outcomes for the included Theta experiment, not estimates
of real-world flood protection.

| Case | Flooding (m³) | Peak downstream flow (m³/s) | Excess above 0.5 m³/s (m³) |
|---|---:|---:|---:|
| Nominal, no faults | 0 | 0.49155 | 0 |
| Both declared faults | 1,621.45 | 0.49009 | 0 |
| Reduced: early outlet-1 fault | 1,621.45 | 0.49009 | 0 |
| Alternative: outlets open, same remaining fault | 1,275.42 | 6.35534 | 2,661.93 |

Five native simulations and one cached reuse establish a **1-minimal witness**:
no single remaining condition can be deleted while preserving the violation.
The later outlet-2 fault alone produces zero flooding. This does not establish
global minimality across other storms, timings or faults.

The alternative reduces flooding by 346.03 m³ but still exceeds the 100 m³
check and increases downstream flow and excess discharge. The interface
preserves the tradeoff, including terminal storage.

## Verify and replay

```sh
npm test
npm run build
```

The suite has **60 tests**: 7 native-engine behavioral tests, 40 independent
validation/negative tests, and 13 service/API tests. It includes a real HTTP
investigation, export, fresh source compilation from an extracted archive and
actual replay. GitHub Actions is configured for Ubuntu; see the
[executed verification record](docs/verification.md) for CI and platform status.

Engine-only commands:

```sh
python3 engine/cli.py catalog
python3 engine/cli.py investigate --request engine/examples/reduction-request.json --output runtime/packet.json
python3 -m validation.validate_packet runtime/packet.json --root . --output runtime/check.json
python3 engine/cli.py replay --request runtime/packet.json --output runtime/replayed.json
python3 -m validation.replay runtime/packet.json runtime/replayed.json --root . --output runtime/replay-check.json
```

Record validation and fresh simulator replay have different scopes. Only an
executed, matching replay produces `replay_status: matched`. Complete routing-step
traces remain in the packet; only the displayed plot is sampled.

To intentionally regenerate the tracked welcome fixture after an engine change,
run `python3 scripts/record_demo.py` and restart the server. Saved evidence is
tied to its original sources and must not be relabeled after edits.

## Architecture and original contribution

- **Engine:** official EPA SWMM 5.2.4 pinned C source and a Python/ctypes bridge.
  Adaptive routing is preserved while steps align with policy/fault boundaries.
  Separate native processes isolate solver state.
- **Investigation:** deterministic, bounded subset search and condition deletion
  over explicitly supplied faults. Native calls count toward the budget;
  identical cases are cached and fallback reserves its required call.
- **Independent checks:** a separate package recomputes SI metrics and checks
  horizon, continuity, native flooding, hashes, exogenous pairing, search
  accounting, removals and comparison claims.
- **Workbench:** React, TypeScript, SVG traces/schematic, fault/time inspection,
  conditional results, responsive comparison, exports and actual replay.

EPA SWMM supplies established hydraulics. Public benchmarks and control
foundations come from pystorms. StormPilot contributes the connected
investigation, reduction, comparison, inspection and evidence workflow.

## Limits and delivery

The models are published idealized benchmarks, not calibrated city networks.
Schematics are not inundation maps. Source/input checks cannot certify arbitrary
third-party policies. No field deployment, operator study or avoided-flood
estimate is claimed.

The HTTP service allows two concurrent workers, four queued/running jobs, bounded
inputs and execution time limits. It is a prototype with local file storage.
Runtime files remain in `runtime/`; use persistent storage when retention matters.

The Dockerfile targets a host supporting a persistent Python process. A static
frontend host alone cannot execute the native solver. Hosted preview, video and
judge access are separate delivery steps; the source repo remains private.

## Documentation and attribution

- [Implementation plan and advisor decisions](docs/implementation-plan.md)
- [Engine protocol and sources](engine/README.md)
- [Independent validation and executed checks](docs/validation.md)
- [Product and rendered review](docs/product-review.md)
- [Four-minute demo narration](docs/demo-narration.md)
- [Submission draft](docs/submission-draft.md)
- [EPA SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm)
- [pystorms](https://github.com/kLabUM/pystorms), revision `20cc6086433449df99177d4f9103940639ef3af0`

EPA solver source retains its public-domain notices. Included pystorms material
retains its GPLv3 license; this project uses GPLv3. See [LICENSE](LICENSE) and
[the model license](engine/data/PYSTORMS-LICENSE).
