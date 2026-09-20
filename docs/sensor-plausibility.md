# Causal sensor-plausibility experiment

`plausible_depth` is a candidate controller for a simulator experiment. It is
not a field-certified flood-control policy. A valid evidence packet and a
useful controller are separate outcomes.

The initial balanced-flow candidate failed its independent phase 1 evaluation.
That rejection and its exact source are preserved in
`evaluation/phase1-evidence.zip`. Phase 1 outcomes subsequently became disclosed
development data. A separate phase 2 protocol was frozen before this controller
was developed; its individual cases must remain unseen until candidate freeze.

## Mechanism

The reference constant-flow policy computes a valve command from measured basin
depth and a configured discharge target. A positive step bias makes a basin
appear deeper and can cause that policy to close its outlet too far.

The candidate keeps each original target at its configured scale. It estimates
a sensor's normal change from the median of its three preceding increments. An
innovation beyond `jump_threshold_m` updates a persistent offset hypothesis.
An opposite jump can cancel that hypothesis. It corrects only a fraction of an
inferred positive offset. Negative offsets are tracked so their return to normal
is not mistaken for a new positive fault; they do not cause extra throttling.

While a positive offset is active, it also estimates outlet discharge using the
larger of current control depth and a three-sample median. If estimated aggregate
discharge exceeds the configured total, it proportionally caps commands. This
addresses the observed development failure where correcting one basin added
flow during a noisy low reading in the other basin. The cap is an estimate from
measurements, not a guarantee about actual hydraulic flow.

Each run creates its own state dictionary. The policy receives only current and
past corrupted depth observations, declared outlet geometry and controller
parameters. It receives no fault flags, true hydraulic state, rain forecast,
future observation, active fault IDs or evaluation outcome. Audit traces record
the inferred offset, control depth, jump count and aggregate command scale.

## Bounded search API

An empty `repair` object selects `plausible_depth` and searches:

```json
{
  "controller_id": "plausible_depth",
  "target_scales": [1.0],
  "jump_thresholds_m": [0.65],
  "correction_fractions": [0.25, 0.5, 0.75],
  "budget": 120
}
```

Each candidate runs on clean, A-only, B-only and joint conditions. The fixed
downstream peak, excess volume, terminal storage and other-subset flooding
guards are checked before flood reduction is ranked. The default grid costs
four reference calls plus three groups of four candidate calls: 16 calls.

The explicit legacy `balanced_flow` family accepts `target_scales` and
`balance_gains`. For backward compatibility, a request that omits `controller_id`
but supplies either legacy array still selects `balanced_flow`. Family-specific
arrays cannot be mixed. Each array contains at most eight unique values; the
global call budget bounds the evaluated Cartesian product.

Only the current best candidate's full traces remain in search memory. Every
candidate's metrics and rejection reason remain in the compact search ledger.
The original normalized reference request is retained alongside its hash.

## Limits

Step detection assumes real basin depth changes smoothly at the 300-second
control interval. Rapid legitimate hydraulic transitions, noisy jumps, gradual
sensor drift, incomplete bias recovery and overlapping faults can violate that
assumption. Corrections can increase downstream flow. A basin's actual actuator
position is not available to the policy, and a stuck valve can invalidate its
discharge estimate. Guard failures reject candidates rather than being traded
for greater flood reduction. Passing development examples is not evidence of
generalization; report the complete independent evaluation, including failures.
