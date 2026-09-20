# StormPilot product acceptance and design review

Historical review of the first prototype. The improved release and current rendered checks are documented in [new-product-review.md](new-product-review.md).
Status: **implementation, desktop/narrow review and core browser interactions completed locally.** Final observations are recorded below and in `verification.md`; hosted and participant checks remain separate.

Owner: Sam advisory lens / product review. The perspective is a researched interpretation of Sam Altman's public reasoning, not his endorsement. This document records recommendations and testable acceptance, not user research or a completed accessibility audit. Root owns the interface, Andrej the engine, and Dario the evaluation contract. This review changes no code.

## The product the first working flow must deliver

A climate-planning analyst or contest judge selects a documented model, policy and test question; runs nominal and stress cases; inspects a found failure or the tested coverage; reduces a failure when possible; compares a documented fallback; and exports enough evidence to reproduce the result.

The main artifact is a **replayable evidence packet**. A network diagram helps locate the result; it is not the result. The app must make three questions answerable from actual run data:

1. **What exactly did you test?** Which model/version, policy, performance check, scenario envelope and information assumptions produced this result?
2. **What happened, where and when?** Which check was exceeded—or not exceeded in the tested cases—and which saved trace supports that statement?
3. **What does the alternative change, and can I verify it?** Show the same-conditions fallback's benefits and downsides, then export/replay the exact evidence.

The analyst is an intended user, not an interviewed customer. Review burden and usability advantages remain hypotheses until someone independently uses the workflow. The contest demonstration should show a complete software outcome; it must not claim observed flood prevention or operator savings.

## Visual direction: an analytical field notebook

Choose a task-first, light technical workbench with strong alignment and a deliberate evidence-reading order. Use pale paper-like surfaces, dark ink, thin structural rules, precise labels and restrained semantic color. The primary visual object is an annotated hydrograph aligned to the result statement. A schematic drainage network and numbered evidence markers provide subject identity without pretending to be a live city map.

Use a highly legible sans for controls and prose; tabular numbers and a restrained mono role for times, identifiers and measurements. Avoid giant marketing headlines, stock flood photos, decorative KPI cards, fake maps, always-moving water, glowing AI gradients and rounded containers for every label. These are task-fit decisions, not universal style rules.

No external site was visually inspected for this review. The direction comes from the actual information structure and the installed design guidance; there is no claim that a reference's appearance or behavior was tested.

### Desktop composition

- **Compact masthead:** StormPilot, “Simulation workspace,” active model name, current run status and evidence/history access. No decorative trust badges.
- **Stable setup rail:** model/policy/question and scenario controls, grouped by the question they change. An explicit primary run action anchors the rail.
- **Main analysis column:** one plain-language result statement; scope/source line; aligned time-series comparison; selected event and explanatory trace. This is the focal area.
- **Context and evidence inspector:** schematic network, selected node/asset and the exact evidence supporting a clicked annotation. It may be a right column when there is adequate width and a lower panel when there is not.
- **Comparison and handoff:** a compact aligned metric table and clear export/replay action at the end of the evidence flow.

The interface should still be recognizably a storm-analysis workspace in grayscale because of its schematic, hydrograph, time alignment, trace annotations and structured comparison—not merely because its accent is blue.

### Narrow composition

At narrow widths, preserve the order: setup summary/edit → result → scope → chart → selected trace → comparison → export. Collapse setup into a labeled disclosure after a run; do not hide the selected policy/question. Move the inspector into normal reading flow. Keep one page scroll; avoid nested scroll traps.

A chart may retain a two-dimensional inspection surface with explicit controls, but the summary, values and table must remain accessible without precise dragging. Horizontal overflow is confined to genuinely two-dimensional data—not the whole application. Sticky controls must not cover focus or the chart's axis labels.

## Core flow and acceptance

| Step | User-facing purpose | Required behavior | Acceptance evidence |
|---|---|---|---|
| 1. Select preset | Understand the model and ask a specific question | Model and policy have readable names, source/version and known limits. Question states metric, units, check and tested horizon. Defaults come from actual supported presets. | A first-time reader can repeat the test question without opening developer logs. Unsupported presets are absent or clearly unavailable. |
| 2. Run nominal | Establish the reference case | An explicit run creates a stable run ID and records the selected configuration. Loading reflects actual engine state. | A returned result matches the saved configuration; model failure cannot turn into a success card. |
| 3. Run stress cases | Examine the declared envelope | The test set and evaluated/completed counts are visible. Any sampled search budget is disclosed. Incomplete results remain labeled partial. | The final evaluated count equals the result manifest; excluded/failed runs do not silently count as passes. |
| 4. Inspect result | Find the supporting observation | A result sentence links to the relevant case, node/asset, time and plotted series. Clicking an event selects the same time across chart and trace. | A displayed exceedance can be located in the raw values; summary and plots use the same case/filter. |
| 5. Reduce witness | Understand which changes remain sufficient | Available only after a valid found failure. Show original conditions versus retained conditions and the reduction's exact guarantee. | Removed/retained conditions match the reducer output. Never call a local search result globally minimal. |
| 6. Compare fallback | Understand a real tradeoff | Both policies use the same case, units, horizon and exogenous streams. Show all required outcome dimensions, including downside and terminal effects. | Metric values and deltas are recomputable from the packet. No hidden future/fault information advantage. |
| 7. Export packet | Verify and communicate the conclusion | Export identifies its run and contents. Include manifest, configuration, provenance, outcomes and replay instructions. Incomplete/invalid packets are distinctly labeled. | An exported packet reproduces the displayed run; edits made afterward cannot silently alter it. |

Root and Dario should keep backend field names and evaluation semantics authoritative. This document defines the product contract; it must not create contradictory scientific metrics.

## Exact copy and result-state contract

Text in braces below must be filled from valid engine/manifest data. It is a template, not sample performance. Missing values display **“—”** or **“Not available”**, never a numeric zero.

| State | Main copy | Action and display rules |
|---|---|---|
| No run | **“Choose a policy and a question to test.”** | Explain supported preset selection. Results show no numeric tiles or fabricated hydrographs. A schematic may appear if it accurately represents the selected model. |
| Ready | **“Ready to run the nominal case.”** | Primary action: **“Run nominal case.”** Show the saved question and scope directly above/beside the action. |
| Engine unavailable | **“The model runner is unavailable. No simulation result was produced.”** | Preserve inputs. Provide **“Retry”** and **“View error details.”** Do not substitute demonstration numbers. |
| Running nominal | **“Running nominal case…”** | Show actual phase or elapsed time. No fake percentage or fabricated time remaining. Offer cancellation only if it really stops the job. |
| Nominal completed | **“Nominal case completed.”** | Show check-specific findings from the engine. Primary action: **“Run stress cases.”** Do not label the model or policy “safe.” |
| Running stress | **“Testing cases: {completed} of {scheduled}.”** | Show actual counts; partial findings are explicitly partial. Do not present a final ranking before evaluation completes. |
| Failure found | **“A check was exceeded in {failed} of {evaluated} tested cases.”** | Name the check, units and case. Primary action: **“Inspect failure.”** Number is computed, not preset. |
| No failure found | **“No violation found in {evaluated} tested cases.”** | Supporting copy: **“This result covers the test conditions shown here.”** Display the envelope and budget. Never show “Flood-proof,” “Certified safe” or “All storms passed.” |
| Run invalid | **“Run invalid. These results are excluded from the comparison.”** | Give the actual reason and retain access to diagnostic logs. Disable scientific-result claims and witness reduction for this run. |
| Reduction running | **“Reducing the failure case…”** | State actual evaluated candidates if available. Preserve the original witness. |
| Reduction completed | **“Reduced failure case: {retained} of {original} conditions retained.”** | Only if the result supports that count. Explain **“Local reduction”** or the actual supported guarantee. Primary action: **“Compare fallback.”** |
| No reduction found | **“No smaller failure case found within this search.”** | The original witness remains valid. Do not call this an engine error or proof of global minimality. |
| Fallback comparison | **“Same case. Different policy.”** | Show per-metric direction and absolute values; conclusions such as “lower overflow” only follow the computed data and defined tolerance. No automatically generated “better overall” badge. |
| No allowed improvement | **“No improvement found among the tested alternatives for this check.”** | Retain other outcome dimensions. This is bounded evidence, not proof that no real solution exists. |
| Settings changed | **“Settings changed. Showing results from {run_id}.”** | Primary action: **“Run with new settings.”** Keep old run visibly identified until a new result arrives. |
| Export available | **“Export evidence for {run_id}.”** | State file type and what is included. No generic “Download report” that hides which run it represents. |
| Export failed | **“The packet could not be created. Your run is still available.”** | Permit retry without rerunning the model, unless the underlying evidence itself is missing. |

A threshold, evaluation horizon or status must not change during an in-progress run. Editing creates a draft configuration/new run. A precomputed run is acceptable only if clearly labeled **“Recorded run”**, tied to an exact matching configuration/version, and never passed off as a fresh simulation.

## Charts, statistics and comparisons

The main analytical question is **when and where two cases diverge relative to a declared check**. Use aligned line charts for time-series behavior, direct annotation for the first relevant event, and an aligned table for cross-metric tradeoffs.

- Every chart states quantity, units and time reference. Distinguish simulation elapsed time from real-world clock time.
- Same-quantity comparisons use the same scale unless a clearly labeled alternative view is intentionally selected. A truncated axis must not exaggerate a gain.
- Pair line labels with dash/marker differences; do not require color discrimination. The selected series, policy and case remain visible outside hover.
- The threshold line is labeled with the declared check and its provenance/assumption status. It is not a generic “safe level.”
- Show missing samples as missing. Do not connect gaps in a way that invents an unobserved crossing.
- Keep terminal storage/drain-down and downstream consequences visible when required by the evaluation contract. A favorable headline metric cannot hide a transfer of harm in the model.
- Relative change is unavailable when its baseline makes that calculation undefined; display absolute difference instead of infinity or a misleading percentage.
- A “zero” must represent a valid computed zero. An excluded, failed, not-yet-run or unsupported metric remains unavailable.
- Required tooltip content also has keyboard/touch access or an equivalent selected-point table. The inspector should accept time/case selection with ordinary controls, not only pixel-perfect pointer gestures.
- Animated lines advance only for genuine execution/replay semantics. No decorative pulsing hazard markers. Respect reduced motion; the evidence remains usable without animation.

Candidate semantic roles: neutral ink for text, one stable color per compared policy, amber for unresolved/partial information, and red for an actual exceeded check or invalid run. Pair every status with text/icon/pattern. Exact colors must be checked on the rendered surfaces; naming a palette does not establish accessible contrast.

## Three judge challenges the application should survive

**“Did you invent this outcome?”** The interface answers with the model/policy source, pinned version, recorded conditions, actual run status and accessible trace. Precomputed and fresh runs are distinguished.

**“What happens when I change one condition?”** The draft/run distinction prevents stale values from masquerading as a new result. A changed condition reruns the appropriate computation or selects a clearly matching recorded case. The resulting statement may improve, worsen, tie or remain unresolved.

**“Why is this more than a wrapper?”** Show the project's specific contribution: an equal-information test contract, a reduced witness or other inspectable diagnosis artifact, trace-linked explanation, an honest fallback tradeoff and a replayable packet. Attribute the simulator and existing controllers. If those additional artifacts are not working, the interface must not imply they are.

## Critical acceptance checks before the first demo

These are concrete review tasks, not new statistical tests that merely mirror the implementation.

- Complete the actual supported flow from preset selection to packet export with one valid run; inspect that the packet matches the UI.
- Exercise engine error, invalid/excluded result, partial stress run, no-violation result, witness found, no-reduction result, fallback tradeoff and stale settings. Use real results where available; clearly labeled development fixtures may test rendering but never appear as scientific findings.
- Confirm the main conclusion is derivable from the selected trace and scenario manifest. Have the reviewer point to the exact supporting values.
- Change settings after a run and verify every relevant panel remains explicitly attached to the old run until new computation completes.
- Inspect actual desktop and narrow renders, including the bottom comparison/export area and long model/policy names.
- Complete the primary controls using the keyboard; inspect focus after running, opening/closing details, selecting cases and returning from export. Do not trap focus in charts or sticky regions.
- Confirm the graph has an equivalent list/detail route and that needed values are available without hover. Check chart legend/summary consistency under case changes.
- Inspect colors and selected/disabled/error/partial states in the actual render. Normal text contrast, meaningful non-text contrast and visible focus need direct checking; no full accessibility-conformance claim follows from a small review.

## Sam product grounding

[Before Growth](https://blog.samaltman.com/before-growth) (2016), read in the preceding Sam review, argues for establishing what users actually value before optimizing appearances of progress. Applied here: the useful job is inspecting and reproducing a plan's evidence, not accumulating graphs or agents. We have not interviewed operators or measured review-time savings.

[Hard Startups](https://blog.samaltman.com/hard-startups) (2020), also read in full, supports meaningful ambition paired with a reasonable next proof. Applied here: retain the substantial public-data analysis product and make the first completed result inspectable. No solo cap is imposed and no prize probability is invented.

## Design guidance applied and verification record

Read: installed `design-direction` skill and its foundations; `interface-design-review` and its review matrix; `interface-data-visualization-ui`. These informed task-first composition, semantic state handling, truthful chart encoding, responsive structure and the requirement to review actual renders.

| Date / phase | Evidence observed | Finding / change | Verification status |
|---|---|---|---|
| Initial build planning | Current project recommendation and workbench requirements; no running UI supplied | Replaced generic dashboard framing with question → evidence → comparison → export; defined conditional copy and no-fabricated-stats contract | Recommendations only; root implementation pending |
| First working flow | Pending | Review actual plan, run path, generated results and packet | Not yet performed |
| Desktop/narrow rendered review | Pending | Record viewport, observed state, defects, corrections and recheck evidence | Not yet performed |

Future review entries should distinguish a rendered defect, an interaction defect, a source-level finding and a product hypothesis. A simulated advisor is not a research participant. Keep this document updated with concrete observations rather than declaring a numerical design score.

## Implementation-plan review — September 20, 2026

Reviewed the implementation plan against the product acceptance and independent-validation contracts. This is a **document review**, not an executed-flow or rendered-interface review. The native engine has since compiled according to the engine lane; the earlier loading blocker is historical and must not be presented as the current product state. The three highest-value corrections are below, in priority order.

### 1. Make the experiment identity visible and immutable across the API and interface

The plan requires a versioned contract and configuration fingerprints, but the UI integration also needs an explicit distinction between **draft settings**, a **submitted experiment**, and its **completed artifacts**. Assign a run/experiment identifier when submitting the frozen configuration; attach every response, chart, selected event, comparison and export to it. Include the configuration digest and relevant model/policy/property/exogenous identities. A delayed response from an older job cannot overwrite a newer selection without a visible record change.

Acceptance: after a completed run, edit a fault or threshold. The previous chart and evidence remain labeled with the previous run and the message “Settings changed. Showing results from {run_id}.” Run the new configuration and confirm that plot, outcome vector, case inspector and export switch together. Test a failed or late job as well as a successful one. This prevents the most damaging demo mistake: presenting a real result under settings that did not produce it.

### 2. Move the first export–validation–replay round trip before broad search and polish

Keep milestone 4 for hardening, but create one complete packet as soon as the actual nominal/stress pair and shared contract work. Independently validate that packet and replay its selected run before expanding search or polishing the workbench. Use that same artifact as the frontend integration fixture, clearly labeled “Recorded run” when loaded from disk. This exposes missing trace precision, provenance, treatment definitions or controller artifacts while they are still cheap to correct.

Acceptance: one real generated packet has a validation report identifying passed, failed and unperformed checks; replay reproduces the declared metrics within recorded tolerances; changing an included artifact causes rejection. An engine completion flag cannot satisfy this gate. Until replay has executed successfully, use “Replay instructions available” rather than “Replay verified.”

### 3. Select the demo finding from the computed outcome, with explicit alternate branches

The final demonstration should follow one actual case through its evidence, instead of promising that search finds a smaller failure or that the fallback wins. Choose the recorded finding only after reviewing the full outcome vector and validation report. It may be a failure with a reduced witness, an unreduced witness, no violation within the tested budget, or a fallback tradeoff. A valid original witness remains valuable when reduction does not shrink it. An invalid run is an excluded result with useful diagnostics, not a scientific finding.

Acceptance: the four-minute script identifies the selected run/packet, replaces each numerical placeholder from that packet, names the actual tested scope, and uses only the reduction/comparison branch that the evidence supports. The fallback section preserves downstream and terminal outcomes. The close demonstrates the new search/reduction/comparison/evidence workflow, credits EPA SWMM and the model/controller sources, and claims no field flood prevention. See `demo-script.md` for the conditional sequence.

These corrections preserve the project's ambition. Their purpose is to make the ambitious result inspectable early. No new approval stage, hardware dependency, municipal-data prerequisite or solo-development cap is introduced.

| Review phase | Evidence observed | Recommendation | Verification status |
|---|---|---|---|
| Implementation-plan review | `implementation-plan.md`, `validation.md`, existing product acceptance contract; engine lane reports successful native compilation | Bind every panel/export to immutable experiment identity; bring forward the first independently checked packet and replay; script an evidence-selected finding with honest branches | Document review completed; behavioral and rendered checks pending |

## First implementation and product review — September 20, 2026

Scope: reviewed the implemented React workbench, a completed real API investigation (`da89ad0843bd436b`), the current README/pitch, and root's desktop empty-state screenshot. This is a source/API review plus an expert screenshot walkthrough. The reviewer also implemented the frontend; this is **not an independent usability study**. Root owns browser interaction verification. A fresh engine packet will govern final demonstration numbers; this integration run is not declared the final contest case.

### What the implementation now earns

The real API investigation completed with native EPA SWMM output and an independent evidence report. Its nominal policy passed the selected flooding-volume check; its stressed policy exceeded it. Its fallback improved the primary flooding metric while failing downstream non-regression guards. This is a meaningful, demonstrable result without claiming that the fallback is better overall. The API also returns the complete identities, physical outcomes, trace samples and validation limitations needed by the interface.

The frontend implements the useful sequence: configure a precise check and one or more declared faults; submit a real job; inspect aligned hydraulic traces through keyboard-accessible time controls; see original/reduced cases when supplied; compare the full outcome vector; inspect independent checks; export or replay the selected run. Submitted results retain their own configuration. Editing the draft produces a stale-settings message rather than relabeling old plots.

The design fits the subject: a drainage schematic and hydrograph supply the identity, with setup kept beside evidence. There is no invented city geography or decorative flood imagery. The empty state has no fabricated numerical result. The recorded-run label is distinct from new execution.

### The Sam product judgment

**Keep the investigation as the product, and make the negative result the memorable moment.** In the inspected integration case, a seemingly useful fallback sends more flow downstream. Showing that cost is a stronger proof of the workbench's usefulness than hiding it behind a percentage gain. The product's promise is a decision someone can inspect and reproduce, not a claim to have solved flood prevention.

Applied from [Before Growth](https://blog.samaltman.com/before-growth): a finished evidence loop matters more than the count of models, charts or agents. The next product proof is an unfamiliar reviewer answering three questions without coaching: what was tested, what exceeded its check, and what the alternative worsened. No operator interviews or measured review-time improvement have been completed here.

Applied from [Hard Startups](https://blog.samaltman.com/hard-startups): maintain the ambitious, real simulation workflow; earn each stronger claim through the next concrete artifact. Native execution, independent checks and a reduced witness are substantive work. Additional speculative features do not strengthen an unverified replay or obscure failure explanation. These are researched applications, not Sam Altman's endorsement.

### Fit against the published contest criteria

| Criterion | Evidence in the current implementation | Remaining proof for the final presentation |
|---|---|---|
| Originality | A connected workflow for declared tests, failure reduction, tradeoff inspection and replayable evidence | Show one actual removal-based finding and the emitted evidence; attribute the established simulator, models and controller methods. Do not claim invention of simulation, fault testing or delta debugging. |
| Adherence to Track | Directly investigates stormwater response and a climate-resilience planning question | Preserve the distinction between a published benchmark and a calibrated real drainage network. No avoided-flood estimate follows from this build. |
| Completion | Native jobs complete through the API; the frontend compiles and supports the end-to-end workflow | Finish actual browser run/export/replay checks, narrow layout and error-state verification. A wired button is not executed proof. |
| Learning | The implementation integrates hydraulic simulation, control, bounded experiments, native builds and evidence validation | The builder must describe their own actual learning. The feature list cannot establish what was new to them. |
| Design | Task-first workspace with model context, aligned traces, conditional outcomes and accessible time controls | Verify actual full-result and narrow renders, focus behavior, threshold labels and long records. |
| Technology | Actual EPA SWMM output, declared treatments, subset search, recorded removal checks and independent metric validation | Demonstrate replay/corruption rejection and explain what the project's new orchestration adds to upstream tools. |

The official criteria publish no numerical weights. This is a qualitative product review, not a predicted rank or prize probability. The current README and earlier verdict still contain historical execution-status prose; root should update those before presenting them as the current state.

### Rendered observations and resulting changes

Root supplied `work/stormpilot-empty-desktop.png`, an actual 1440-pixel-wide desktop capture. The available screenshot shows a cohesive, legible main composition: the experiment rail, large task statement and benchmark schematic are distinct. The setup rail's primary run button lies below the initial 1000-pixel viewport, making the first action unnecessarily hard to find. A prominent **“Investigate current plan”** submit button has now been added to the empty-state introduction. This uses the same form and native input validation; it is not a second experiment path. Its corrected render still requires root's recheck.

The inspection also led to these source-level corrections, pending full browser exercise:

- Only an actual `no_violation` result uses the green check treatment. A nominal failure, incomplete investigation and unverified evidence receive explicit non-passing copy and cannot acquire a verified reduction badge.
- The search budget is labeled **simulator calls**, since nominal, comparison and reduction runs consume the budget. Search status and stopping reason are visible when supplied.
- When a reduced case exists, it is the selected witness and the basis of the fallback comparison. Original stress remains separately visible; the comparison labels which fault set is shared.
- Fallback improvement/guard wording comes from independent claim checks, not a guessed tolerance over displayed deltas. Failed validation suppresses the positive verdict.
- Numerous included-file hash checks move into a disclosure so model/numerical checks, replay status and limitations remain readable. All individual hash outcomes remain available.
- Model changes clear now-inapplicable additional fault selections. Missing node depths and results remain unavailable.

| Review phase | Evidence observed | Finding / correction | Verification status |
|---|---|---|---|
| First source/API integration | Completed native investigation `da89ad0843bd436b`; production frontend build | Data contract matched; actual fallback tradeoff exposed; stale result identity and multi-fault configuration supported | API result inspected; TypeScript/Vite build passed |
| Desktop empty state | Root's 1440-pixel-wide screenshot | Main composition coherent; primary run action was below the initial viewport; introduction CTA added | Original render inspected; changed CTA awaiting rendered recheck |
| Result/narrow/keyboard/export/replay | Root reviewing the live preview | Findings and corrections to be appended from actual observations | Pending; no claim of full accessibility conformance or user validation |

Root subsequently found a real blocking form defect: a duration input with `min=0.01` and `step=0.1` rejected the default value of five hours. All time/duration controls now use `step="any"`, matching the backend's supported decimal inputs. Duration bounds depend on the start time and model horizon; associated invalid-state messaging is provided for exceeding that horizon. The production build passes after the correction. Root's browser recheck, rather than source inspection alone, governs closure of this defect.

The engine and validation lanes have now supplied frozen experiment `1841c184f7f7d0b3fbcb`, with a two-to-one fault reduction and an actual local replay of all five configurations. `demo-narration.md` pins that packet and its separate record-check/replay reports. Its central demo moment is the evidenced fallback tradeoff. This supersedes the earlier integration run as the intended narration source; the numerical findings must not be mixed between run identities.

## Desktop, narrow layout and live flow review

Inspected root's actual `work/stormpilot-result-desktop.png` (1440 × 2457) and `work/stormpilot-result-mobile.png` (390 × 2999). The screenshots show the actual three-case result, not a design mockup. The reviewer did not independently operate these browser sessions; root performed and reported the interaction checks below.

The result composition is coherent on both widths: finding and scope precede the trace, network context supports the selected time, and the complete metric comparison precedes export. The fallback tradeoff is visibly stated, including the two failed downstream guards. At 390 pixels, the form collapses into a labeled setup control and comparison/export remain in the normal page flow. Root also checked 320 pixels and reported no page overflow, with fields remaining inside the viewport.

Two shortcomings were visible. The full 78-hour graph compresses the important early storm into a small portion of the plot. The narrow chart/table can scroll within their panels, but the original render does not explain that interaction and initially shows only the nominal table column. The final source changes add:

- **Full horizon / Focus on fault** controls, with an explicit elapsed-hour range and a visible-range y scale. Focus uses the selected witness's actual fault window, with a selector when more than one window is available. All outcome metrics continue to cover the entire experiment horizon.
- A keyboard-focusable chart and comparison scroll region, narrow-screen horizontal-scroll hints, and a sticky first outcome column so a value retains its metric label while scrolling.
- The API's declared-condition list with retained/removed/unresolved status and actual fault timings. A disclosure shows recorded removal outcomes, unique run IDs, active fault sets and whether each check was exceeded. Reused run IDs are deduplicated in the table; the simulator-call budget is reported separately.

The remaining final recheck is to inspect those additions in the browser. They were type-checked and built successfully; this source verification is not substituted for a rendered check.

| Live check | Root-reported result | Review implication |
|---|---|---|
| Default submit after duration-step fix | Fresh browser simulation completed | The blocking native-form validation defect is resolved in the exercised default path. |
| Evidence dialog | Focus enters dialog; Escape closes; focus returns | Core modal keyboard behavior passed in the reviewed browser. |
| Time and node inspection | Slider arrow keys and node selector worked | Essential trace/context values have a keyboard route. |
| Export and replay | Real download and real replay completed | Core handoff actions are exercised, beyond their source-level wiring. |
| Stale settings and bounded no-violation | At 390 pixels, changed threshold to 100,000 m³; stale state appeared, then a fresh no-violation result | Old evidence remained separate from the changed experiment; a favorable outcome used the bounded no-violation state. |
| Responsive bounds | 320 and 390 pixels, no page overflow | Page reflow passed the exercised widths; chart/table scrolling still needed the explicit hints now added. |

These checks cover the exercised browser and scenarios. They are not a full accessibility conformance audit, usability study, field validation or cross-platform guarantee.

The tracked contest fixture is now `fixtures/demo-packet.json.gz`, experiment `a3fd3abf0ac0fe120dcb`, using fault IDs `outlet-1` and `outlet-2`. It has the same declared timing and hydraulic outcomes as the earlier `f1`/`f2` development packet but a different identity. The narration is being pinned to the tracked fixture; development packet identities must not be presented as its evidence.

## Final root browser recheck

The final production build was inspected at 1440×1000, 390×844 and 320×800.
The default native run, exported archive and actual simulator replay succeeded.
The tracked recorded fixture's own replay returned `matched`. Its fault-focused
chart shows 0–7 hours with matching slider bounds, while the full 78-hour flooding
total remains 1,621.45 m³. The condition list identifies outlet 1 as retained and
outlet 2 as removed; the four unique recorded test rows show their actual outcomes.

Changing draft settings preserves the old experiment label. A high flooding
threshold returns no violation. A fresh Gamma run reports that its nominal policy
already fails the low threshold, rather than attributing that failure only to the
fault. The duration-step bug is closed by an actual successful browser submit;
end-after-horizon input produces an associated invalid-state message.

Keyboard checks covered time arrows, node selection, dialog focus/Escape return,
and horizontal table scrolling. The page has no accidental overflow at 320 or
390 pixels. Data regions now expose scroll hints and keyboard focus. Text colors
that measured below the intended contrast on pale surfaces were darkened. No
screen-reader execution or user research is claimed. See `verification.md` for
precise scope, screenshots, reported limitations and delivery status.
