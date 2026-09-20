# StormPilot simulation engine

This engine runs **EPA SWMM 5.2.4**, compiled from the official C source. It does not approximate hydraulics with a replacement model. Python uses only its standard library. A system C compiler is required for the first run; macOS clang and Linux cc/clang are supported by the build script. The native solver has process-global state: use separate CLI worker processes for concurrent jobs.

From the repository root:

```sh
python3 engine/cli.py catalog
python3 engine/cli.py run --request engine/examples/default-request.json --output engine/runs/packet.json
python3 engine/cli.py investigate --request engine/examples/default-request.json --output engine/runs/investigation.json
python3 engine/cli.py replay --request engine/runs/investigation.json --output engine/runs/replayed.json
python3 -m unittest discover -s engine/tests -v
python3 -m validation.validate_packet engine/runs/investigation.json --root .
```

Without `--request`/`--output`, the CLI reads JSON from stdin and writes JSON to stdout. Build diagnostics go to stderr. Errors return nonzero with a structured JSON error on stderr. `catalog` does not compile or execute the solver. Outputs and compiled libraries belong in ignored `engine/runs` and `engine/build` directories.

## Model and code provenance

- EPA source: [official v5.2.4](https://github.com/USEPA/Stormwater-Management-Model/tree/7952ca837988b1c32f791812eccc9fd64547e093), commit `7952ca837988b1c32f791812eccc9fd64547e093`. The upstream README states that the C source is public domain and supplies its disclaimer. Vendored source is unmodified. `native_bridge.c` adds read-only access to elapsed time, native cumulative flooding, hydraulic link/node volume and signed link flow.
- Theta and Gamma inputs: [pystorms release/2.0.0](https://github.com/kLabUM/pystorms/tree/20cc6086433449df99177d4f9103940639ef3af0), commit `20cc6086433449df99177d4f9103940639ef3af0`. Exact `.inp` bytes are retained under `data/`, with the repository's GPL-3.0 license in `data/PYSTORMS-LICENSE`.
- Theta is an idealized two-basin benchmark, in CMS, with a 78-hour modeled horizon. Gamma is the published eleven-basin network, in CFS, with a 156-hour modeled horizon. These are the original supplied inputs, not pystorms' rewritten version-2 models. Gamma's actual rain-gauge reference is `DESIGN_10YR12HR_ALT`; the upstream class's different storm label is not used as evidence.
- `constant_flow` and `equal_filling` are documented adaptations of established orifice-control baselines. Theta constant targets use the published v1 parameter values. The equal-filling adaptation uses perturbed measurements consistently; it does not use hidden true depth for balancing. Gamma uses a simple 4 CFS target per outlet, not the published optimized v2 parameters. No manuscript-score reproduction or algorithmic novelty is claimed.
- The source contribution here is the causal experiment boundary, independent exogenous streams, evidence protocol, bounded condition-subset search, checked local reduction and replay workflow.

## Request and evidence contract

Use the example request or `catalog.default_request`. Choose `theta`/`gamma`; `constant_flow`, `equal_filling` or `uncontrolled`; and an explicit array of faults. All time values are seconds since model start. A stuck valve uses a fixed `setting` in `[0,1]`, or freezes that run's actual setting at onset if omitted. A sensor dropout means a **zero-reading failure**, not a missing-data token. Bias is additive meters. Fault windows are half-open: `start_s <= time < end_s`.

The controller reads its own current perturbed depth measurements every five minutes, together with static model geometry and fixed parameters. It receives neither future realized rainfall nor the fault catalogue. Rainfall multiplier is a declared scenario transformation, not a live forecast. Sensor noise comes from a SHA-256 keyed Box–Muller draw indexed by seed, asset and control timestamp. Extra diagnostics cannot change it. Each run applies the same exogenous draws to its **own evolving true hydraulic state**. Paired policies must not share a fixed full observation trace.

Control and fault boundaries clip the maximum routing step; all ablations retain the entire envelope's boundary grid. Every actual routing step is recorded, including time zero and the terminal state. `display_trace` is a separate five-minute view containing basin depths, held observations, command/actual valve settings and the observation timestamp.

Evidence uses `schema_version: stormpilot.evidence.v1`. A packet contains model topology, normalized request, source artifacts/hashes, a frozen absolute upper-bound test contract, common experiment context and runs. Runs identify policy/parameters, active fault IDs, trace, physical metrics, native continuity diagnostics and source report. Canonical JSON SHA-256 fingerprints use sorted keys and compact separators. Effective rainfall hashes bind the parsed rain gauges and referenced rainfall rows; effective model hashes bind the transformed input text. Artifact hashes bind actual source bytes.

## Units and metric limitations

All reported physical values use SI. The solver's internal hydraulic flows/volumes are in feet units. The read-only bridge converts these with the exact factor `1 ft³ = 0.028316846592 m³`. This avoids the public API's rounded CMS factor of `0.02832` causing a superficial mismatch with native cumulative statistics. SWMM's internal equations and input conversion are unchanged.

- `flood_volume_m3`: right-rectangle integration of total positive node overflow over each actual routing interval. `native_flood_volume_m3` independently reads cumulative `NodeStats.volFlooded` and is cross-checked.
- `downstream_flow_m3s`: **positive downstream discharge** at the declared link. Signed flow is also retained in `signed_downstream_flow_m3s`; the positive-discharge metric does not measure net flow.
- `downstream_excess_volume_m3`: integrated positive discharge above the declared benchmark threshold, separate from flooded volume.
- `terminal_storage_m3`: water retained throughout the hydraulic network's nodes **and links** at the fixed horizon. It is not all watershed soil/surface water.
- `peak_downstream_flow_m3s`: maximum positive discharge over routing samples. Traces are numerical model results, not continuous-time mathematical bounds.

The mixed upstream benchmark penalty is never mislabeled as volume. Continuity diagnostics and numerical tolerances remain visible. A source/model trace check establishes recorded consistency, not calibration for a city, a safe operating policy, measured damage prevention or an independently executed replay.

## Search and reduction

`investigate` searches only subsets of the declared fault conditions. The budget (3–40, default 8) includes actual nominal, candidate, ablation and fallback simulations; identical configurations may be reused from a local cache. One call is reserved for the fallback. If the nominal policy already violates the contract, the output says `nominal_violation` and does not manufacture a newly discovered fault failure.

The supplied stress is tested first. If it passes, smaller subsets are swept because hydraulic effects can be nonmonotonic. A found failure is reduced by removing one condition and rerunning. `1-minimal` means **every single deletion of the final condition set was evaluated and did not retain this violation**. It does not mean the globally smallest or least severe failure. Severity, duration, arbitrary fault types and all possible storms are not exhaustively searched. Every tested removal and its actual run remain in the packet. Budget exhaustion and no violation are valid results.

The fallback uses the same exogenous conditions and its own state. All four physical metrics are compared, including guards against shifting harm into peak discharge or terminal storage. Lower overflow alone never becomes a claim of a safe or universally improved policy.

`replay` re-executes each recorded unique policy/active-condition configuration and preserves logical run IDs. It does not rerun the search algorithm; original investigation declarations are retained for the independent comparator. Creation time, runtime and report CPU timing are not numerical replay criteria.
