# StormPilot — submission copy

Prepared copy; no Devpost entry has been submitted.

**Tagline:** Find the stormwater failures that individual fault tests miss.
**Track:** Earth Forward
**Live demo:** https://stormpilot.vercel.app
**Private source:** https://github.com/sudo-anshul/stormpilot
**Intended user:** A stormwater modeler testing a proposed controller before recommending it.

## Inspiration

A sensor fault can pass a test. A restricted valve can pass a test. Their combination can still cause a flood. And a response that looks excellent in one storm can make a different storm worse. We wanted a stormwater planning tool that exposes both mistakes before a controller is trusted.

## What it does

StormPilot helps stormwater modelers test proposed controllers before recommending them. Import a supported SWMM model or use a published benchmark. Declare the performance requirement, sensor and valve faults, timing and search budget. StormPilot runs the real EPA SWMM solver, finds interacting failures, checks each condition separately, searches bounded control responses and tests the selected candidate against declared physical guards.

The workbench connects the decision to the evidence: complete outcomes, individual and joint traces, sensor observations versus estimated control depth, every tested candidate, rejection reasons, independent evaluation reports, and a source-complete replay archive. A judge can change the inputs and execute a new experiment on the hosted app.

## The result we can prove

In Theta, a published two-basin benchmark, the no-fault case produces zero flooding. A +1 m sensor bias at basin P2 during hours 3–6 also produces zero. A valve fixed at 0.035 opening during hours 6–8 produces zero alone. Together they produce **237.263 m³**, violating the fixed 100 m³ check. At hour 6, the biased-sensor case already holds **469.544 m³ more water** than the no-fault case. The faults act at different times; the earlier disturbance changes storage before the valve restriction arrives.

The bounded grid uses 21 native calls, including five retained full-proof simulations. A causal sensor-plausibility candidate reduces the development case to **19.361 m³**, a **91.84% reduction**.

We then tried to disprove that apparent success. In a separately frozen eight-case evaluation, all 64 simulations were valid and no flood subset worsened beyond tolerance. But the aggregate improvement was only **7.29%**, below the required 10%; only two of eight cases improved materially, and one downstream guard failed. **The candidate was rejected.** An earlier candidate also failed its own evaluation, increasing aggregate flooding by 22.45%. Both results remain visible and downloadable.

The achievement is an inspectable discovery and an evidence-based rejection—not a claim that an unvalidated controller protects a real neighborhood.

## How we built it

Pinned EPA SWMM 5.2.4 C source runs through a small Python bridge with isolated native processes. Deterministic fault search and paired subset experiments establish the interaction. Parameter search evaluates all declared physical guards. A separately implemented validator recomputes physical quantities from full routing-step traces and checks source, input, pairing, budget and claim integrity.

React, TypeScript and SVG form the workbench. A bounded `.inp` import flow preserves exact input bytes, SI mappings and provenance. Vercel builds and runs the Linux native solver in a container. Private Blob storage preserves evidence across instance loss and serves source ZIPs through expiring signed URLs.

## Implementation lessons

Three concrete lessons shaped the implementation. First, a timestep API disabled adaptive routing, and a second benchmark exposed the continuity error; preserving the solver's adaptive behavior became an explicit requirement. Second, independent recomputation caught omitted link storage and inconsistent native-unit conversions, so complete routing traces and native cumulative totals are now checked separately. Third, minimizing flood volume alone selected misleading responses: a zero-flood candidate worsened downstream flow, and reserved evaluation rejected two candidates that improved the development case.

The resulting workbench retains failed experiments, frozen protocols and exact sources. Its output is a decision another reviewer can challenge and reproduce, including an explicit rejection when the criteria fail.

Development used AI coding assistance and parallel technical/product reviews. Advisor-named skills supplied interpretations of public reasoning; the named people did not review or endorse the project. These are documented implementation lessons, without a claim about the entrant's prior experience or personal learning.

## What is original, and what is next

EPA SWMM supplies the established hydraulic solver. Pystorms supplies public benchmark networks and control foundations. Fault injection, ablation, parameter search and evaluation are established techniques. Our contribution is connecting them into a working stormwater decision workflow with editable models, causal inspection, explicit rejection and portable evidence.

The next evidence needed is an operator study on a calibrated partner network: can a planning analyst find a missed interaction and reject a bad response faster than their current workflow? We have not measured that yet. We also do not claim field calibration, real avoided flooding, a universal controller, or a winning probability.

## Submission handoff

Deadline previously verified: September 20, 2026, 17:00 EDT / September 21, 02:30 IST. Confirm the current contest page before submitting.

The live app is available. The repository stays private. [SOURCE-ACCESS.md](../SOURCE-ACCESS.md) explains how to share the local full-app code ZIP with judges or grant repository access explicitly. An experiment replay archive supports numerical reproduction but is not a substitute for access to the complete app code. Upload the finished demonstration video to an account you control, complete eligibility/team details accurately, and submit through Devpost. No code-sharing invitation or Devpost submission has been sent by this workspace.
