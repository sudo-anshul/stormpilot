# Predeclared evaluation

`protocol.json` is the fixed benchmark protocol. Its exact bytes are pinned by `protocol.sha256`; do not edit it after inspecting results. The primary requirement is the existing 100 m³ flood-volume limit. A pair is a joint failure only when clean, A alone and B alone pass while A+B fails. All four outcomes must be shown. The statistic `L(AB) − L(A) − L(B) + L(empty)` is reported separately, so ordinary threshold crossing is not mislabeled nonlinear synergy.

The fixed development policy must reduce paired flooding by at least 10 m³ **and** 10%. It must also preserve the clean/single cases within 1 m³ and keep increases within the stated guards: 0.001 m³/s peak downstream discharge, 1 m³ downstream excess volume, and 0.1 m³ terminal node-and-link storage. These are explicit allowances, not a literal zero-change or safety claim.

Six fixed rainfall/timing/noise/severity transforms are applied to all four fault subsets and both frozen policies: **48 heldout runs**. Their outcomes are not inspected during development. One final evaluation starts only after the selected pair, parameters and complete source artifacts are frozen. A later policy change cannot reuse this suite as unseen evidence. All unfavorable or invalid outcomes remain in the table.

## Fixed benchmark commands

Create the eight-run development proof using the selected request and policy specification:

```sh
python3 evaluation/worker.py --request selected-request.json --spec selected-policy.json --output development-packet.json
python3 -m evaluation.run_campaign freeze --packet development-packet.json --spec selected-policy.json
python3 -m evaluation.run_campaign holdout
```

The specification contains `reference` and `candidate`, each with a recorded `controller_id` and normalized `parameters`. The worker executes each policy on `empty`, `a`, `b` and `ab` under one complete external fault catalog. The independent parent process checks actual full routing traces using `validation.validate_packet`; it does not accept a producer's validation Boolean.

The freeze step writes an immutable `candidate.json` and digest. The evaluation refuses changed sources, a changed protocol, or a reused output directory with an existing execution lock. `report.json` distinguishes evidence completeness from meeting the declared usefulness criteria. A valid unfavorable result stays unfavorable.

## Recorded user models

User-triggered evaluations use the **declared robustness suite** label. The transforms are visible and reusable; these runs must never be presented as held out.

```sh
python3 -m evaluation.declared \
  --packet recorded-packet.json \
  --reference-run-id RECORDED_REFERENCE_ID \
  --candidate-run-id RECORDED_CANDIDATE_ID \
  --pair-id RECORDED_SENSOR_FAULT_ID \
  --pair-id RECORDED_VALVE_FAULT_ID \
  --output-dir NEW_OUTPUT_DIRECTORY \
  --report REPORT_PATH
```

The equivalent callable is:

```python
from evaluation.declared import evaluate_declared_suite

evaluate_declared_suite(
    packet_path, reference_run_id, candidate_run_id,
    pair_ids, output_dir, report_path,
)
```

The model, exact imported input, policies and effective parameters come from completed recorded runs. The selected pair must contain one sensor condition and one valve condition on valid model assets. The first implementation supports flood-volume requirements. The original model horizon and declared flood limit are retained; it is not silently converted into the Theta benchmark.

Time transforms follow the predeclared formula: scale the original duration, cap it at the model horizon, shift the start, then clip the whole window into the horizon while preserving that scaled duration. This makes behavior explicit for short imported models. Rainfall multipliers apply to the model's original rainfall. A user model is still a supplied simulation, with no inference of calibration or field validity.

## Complete evidence with bounded storage

Every complete trace is independently checked during execution. Compact records retain all cases, policy/subset metrics, guards, failures, exact configurations and trace hashes. After disk space became available, retaining **all six compressed case packets and the base proof** was authorized before any heldout outcome. This is additive storage only; the frozen protocol and acceptance criteria are unchanged. The predeclared highest-reference-flood and largest guard-regression cases are highlighted, while every complete case remains available for independent recomputation.

`report.json` includes the protocol/candidate/source identities, all 24 paired case rows, the accepted and rejected criteria, aggregate values and retained evidence paths. Its `suite_type` distinguishes the fixed `heldout_benchmark` from repeated `declared_robustness` evaluations. A report belongs only to its matching request/model/controller identities; it does not validate an unrelated draft experiment.

No optimizer superiority is claimed merely because a grid finds a useful policy. The protocol requires a complete equal-budget simple-baseline comparison before that claim. The product can establish a useful bounded policy comparison without establishing a new optimization algorithm.

## Phase 1 rejection and new protocol

The first frozen candidate passed the original joint-failure development proof, then failed its complete unseen suite: paired aggregate flooding increased by 22.45%. `phase1-evidence.zip` retains the exact original source tree, protocol, candidate, report, base proof and all six complete case packets. `validation/phase1-archive-audit.json` records an independent recheck of all 56 runs and 727,771 trace rows from that archive. Its unfavorable result remains unchanged.

`phase2/protocol.json` was frozen before new controller development at 15:37:21 UTC on 2026-09-20 (SHA-256 `15e373f2f634a26a9fd8013853ab6618e1b57ef79877effea7a0ddf2ae1dadd7`). The development pair and reference remain fixed. Eight new seeded stratified transforms require 64 policy/subset runs and include separate sensor/valve onset shifts. All 32 subset comparisons must preserve the original guards and primary nonregression; aggregate paired improvement must reach both 80 m³ and 10%, with at least four individually material paired improvements. Original phase 1 cases may be used as declared development diagnostics but cannot be reused as unseen evidence.

Keep phase 2 output paths separate:

```sh
python3 -m evaluation.run_campaign freeze --packet phase2-development-packet.json --spec phase2-policy.json --development-ledger complete-development-ledger.jsonl.gz --protocol evaluation/phase2/protocol.json --output evaluation/phase2/candidate.json
python3 -m evaluation.run_campaign holdout --protocol evaluation/phase2/protocol.json --snapshot evaluation/phase2/candidate.json --output-dir evaluation/phase2/heldout --report evaluation/phase2/report.json
```

The evaluator preserves complete invalid packets too, labeled with their failed validation status, so a rejected trace remains inspectable. An invalid case still prevents a complete-success claim.

The phase 2 controller uses the new `causal-depth-history-feedback-v2` metadata identifier. A dated pre-execution clarification records that its memory contains only earlier instances of the same permitted depth observations, with state reset for each run. The protocol's exact bytes remain unchanged; this identifier deviation is explicit in `phase2/information-boundary-clarification.json`, the candidate snapshot, report and exported evidence. No perturbation or acceptance criterion changed.

## Verification

```sh
python3 -m unittest discover -s evaluation -t .
python3 -m unittest discover -s validation -t .
```

The tests cover missing/duplicated cases, changed transforms, false claims, hidden guard regressions, invalid runs, threshold crossing versus superadditivity, recorded-policy provenance, invalid asset pairs, and deterministic short-horizon handling. They test evidence logic, not the hydraulic equations or field calibration.
