# Discover a joint failure, then test a controller change

The new demonstration asks a stricter question than identifying one blocked outlet: can two conditions each pass a declared flooding contract while their combination fails it, and can a causal controller improve that case without shifting an unacceptable burden downstream?

The primary requirement is fixed at **100 m³ of modeled surface flooding over Theta's full 78-hour horizon**. The stricter 1 m³ check is secondary. Neither threshold is a municipal regulation. They were fixed before fault screening and controller tuning.

## Reproduce the complete development workflow

From the repository root:

```sh
python3 engine/cli.py discover --request engine/examples/discovery-request.json --output runtime/discovered.json
python3 engine/cli.py repair --request engine/examples/repair-request.json --output runtime/repaired.json
python3 -m validation.validate_packet runtime/repaired.json --root . --output runtime/repaired-check.json
python3 engine/cli.py replay --request runtime/repaired.json --output runtime/repaired-replay.json
```

The API derives a repair request from the immutable completed discovery result. The example repair request makes that same selected pair explicit for standalone CLI use. Editing the current UI draft does not redefine an already completed experiment.

Discovery supports declared sensor-bias values, partial valve positions, assets and time windows. Windows align to the 300-second control interval so cached single-condition screens use the same routing boundaries as joint cases. Every native run counts against the campaign budget. Screening retains metrics and trace hashes; the final clean/sensor/valve/joint comparison and fallback retain full traces. The default 3-by-3 pair grid executes **16 screening calls and 5 retained-proof calls**.

The selected public Theta case is:

| Conditions | Surface flooding (m³) |
|---|---:|
| Neither | 0 |
| P2 sensor reads 1 m high during hours 3–6 | 0 |
| Outlet 2 fixed at 0.035 during hours 6–8 | 0 |
| Both, in sequence | 237.262837 |

The early measurement error reduces release and consumes storage headroom. The later partial restriction then causes overflow. The interaction excess, `joint − sensor − valve + neither`, is also 237.262837 m³. Removing either condition prevents this violation in the tested experiment; this establishes a local, condition-deletion claim, not global minimality.

## A controller change with explicit rejection criteria

The default `plausible_depth` candidate estimates abrupt sensor offsets from its own measured-depth history, partially corrects positive offsets, and applies an estimated aggregate discharge cap. It keeps the configured per-basin targets. State is isolated per run; it receives no true-depth channel, fault flag, forecast, future hydraulic trajectory or evaluation result. See [the sensor-plausibility experiment](sensor-plausibility.md) for the causal mechanism, bounded API and limitations.

The default repair grid has three correction fractions and evaluates all four condition subsets for each candidate, plus four reference runs: **16 native calls**. A candidate must reduce joint flooding by at least 10 m³ and 10%, while meeting all of these limits on every matched subset:

| Quantity | Maximum allowed increase |
|---|---:|
| Downstream peak | 0.001 m³/s |
| Downstream excess volume | 1 m³ |
| Terminal node-plus-link storage | 0.1 m³ |
| Flooding in clean and single-condition cases | 1 m³ |

These allowances were fixed before tuning. They permit small reported changes; they do not mean every quantity is unchanged. Guards are checked before ranking eligible candidates by joint flooding. All rejected candidates remain in the ledger.

The phase 2 development candidate (`target_scale=1`, `jump_threshold_m=0.65`, `correction_fraction=0.75`) reduces the original pair's flooding to **19.361153 m³**, a **91.84%** reduction, while passing the guards. Its broader development record contains 293 attempted native calls, including one retained disk-exhaustion failure. Development improvements do not establish independent generalization.

The earlier phase 1 `balanced_flow` grid used 25 candidates and 104 calls. Its selected `target_scale=0.98, balance_gain=2` policy achieved 11.580060 m³ on the original pair but **failed independent evaluation**, increasing aggregate joint flooding. Its exact source, proof and rejection remain archived. The zero-flood `target_scale=1, balance_gain=2` variant was rejected even during development because it exceeded a downstream-peak guard. Explicit legacy grids remain available for reproduction.

## What the evidence does and does not establish

The full retained traces support independent physical metric checking and actual re-execution. The wider screening and tuning ledgers preserve requests, parameters, results and trace hashes, but their discarded traces are not independently re-integrated during packet validation. The `search` block accounts for retained proof treatments; `discovery` and `repair` separately account for all campaign calls. A successful replay re-executes recorded treatments and does not rerun either search.

The parameter grid is development work. Generalization is assessed separately by the frozen protocol and held-out campaign in `evaluation/`; consult its actual result before making a robustness claim. No search-efficiency advantage over an equal-budget comparator is claimed.

The initial Gamma constant-flow baseline already spills approximately 8,559 m³ under its supplied design storm. It cannot support a healthy-baseline interaction witness under this 100 m³ requirement. That failure is retained in the development record; the system reports a failed baseline instead of inventing a fault-induced discovery.

These are public benchmark simulations. They do not demonstrate field protection, calibrated city flood prediction, controller deployment safety, or a globally optimal search/controller.
