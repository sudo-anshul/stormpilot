# StormPilot — submission draft

Prepared copy; no entry has been submitted.

**Tagline:** Crash-test a stormwater control plan before relying on it.  
**Track:** Earth Forward  
**Private code:** https://github.com/sudo-anshul/stormpilot

## Inspiration

A control plan can satisfy its checks under normal conditions and fail when an
outlet sticks. An apparently helpful fallback can shift the problem downstream.
Planning needs an experiment whose assumptions and tradeoffs can be inspected.

## What it does

StormPilot runs published stormwater benchmarks with the actual EPA SWMM engine.
The user declares a policy, performance check and outlet faults. It tests the
nominal plan, searches within the supplied conditions, removes conditions through
reruns and compares another policy under the same external conditions. The
workbench links conclusions to traces, fault windows, node depths, removal tests
and complete physical outcomes.

The downloaded archive includes source and evidence. Another user can compile
the included solver, replay every case and independently compare the result.

## Demonstrated finding

The included Theta nominal policy produces zero flooding. Two declared faults
produce 1,621.45 m³. Removing the later fault leaves the violation; the early
outlet-1 fault is a 1-minimal witness. Five native simulations and one cached
reuse establish the finding.

The outlets-open fallback reduces flooding to 1,275.42 m³ but raises peak
downstream flow from 0.49009 to 6.35534 m³/s and causes 2,661.93 m³ of excess
discharge above the declared 0.5 m³/s threshold. It still fails the 100 m³
flooding check. That tradeoff is visible and reproducible.

## How it was built

Pinned EPA C source is compiled and called through a Python bridge. Native
processes isolate solver state. Deterministic bounded subset search and deletion
experiments produce a witness. A separate checker recomputes physical metrics
and checks source hashes, matched conditions, search accounting and claims.

React, TypeScript and original SVG charts/schematics distinguish draft settings,
recorded results, fresh execution, partial findings and verified replay. Numerical
outcomes come from the native solver.

## Challenges and implementation lessons

- The packaged library failed to load; compiling official source restored
  reproducible execution.
- A timestep API silently disabled adaptive routing. Testing Gamma exposed a
  severe continuity error. Preserving adaptive stepping fixed it without
  relaxing the acceptance threshold.
- Independent checks exposed an incomplete stored-water total and native-unit
  conversion errors that a plausible chart would not reveal.
- Primary-metric improvement concealed downstream regressions. The full outcome
  vector and explicit guards became central to the product.

The entrant should adapt this section to their own learning and disclose AI
assistance accurately where the submission asks for it.

## Attribution and scope

EPA SWMM supplies established hydraulics; pystorms supplies public models and
control foundations. Fault testing and deletion are established methods.
StormPilot contributes the complete investigation, reduction, paired comparison,
inspection and replayable evidence workflow. No field flood prevention, calibrated
city performance, operator savings or actual deployment is claimed.

## Delivery handoff

Deadline previously verified: September 20, 2026, 17:00 EDT / September 21,
02:30 IST. Recheck the contest page before submitting.

- Arrange judge access while preserving the requested private repository.
- Deploy the Docker app to a Python/container-capable host and verify a fresh
  run, export and replay there. A static-only host is insufficient.
- Record the four-minute demonstration using `demo-narration.md`, preserving
  the selected packet identity and record-check/replay distinction.
- Complete eligibility/team information accurately and submit through Devpost.
  This workspace has not sent an entry, invited judges or published the repo.
