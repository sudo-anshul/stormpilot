# StormPilot: make the next investigation useful

Status: product critique, implemented interface and recorded browser verification for the authorized improvement phase. This is a researched Sam advisory application and design review, not Sam Altman's endorsement or operator research. Root owns the service; Andrej owns search and policy behavior; Dario owns scientific claim acceptance. This lane owns the frontend, rendered review and this document.

## The strongest criticism of the current product

The workbench has earned real execution, traceable outcomes, a fair comparison and source-bundle replay. Its main weakness is **the user arrives after the important question has effectively been chosen for them**. A prepared public benchmark, fixed policies and a known early outlet fault make a credible engineering demonstration, but provide limited evidence that a new user can investigate their own policy.

The current two-to-one reduction removes a late fault with no material effect on the headline flooding outcome. That proves the reducer operates, but it is a weak discovery story: the interesting condition was already supplied. A stronger result would establish an interaction that the evaluated individual faults do not reveal, with every necessary comparison actually run. If the search finds no such interaction, the interface must show that bounded outcome instead of reframing an arbitrary large failure as a compound insight.

The existing all-open fallback exposes a real downstream cost. That is valuable evidence, but it ends at “this alternative also has a problem.” A useful decision workflow should let the user propose a documented policy-parameter change and see whether it survives a separately declared evaluation suite. It may fail. The useful endpoint is an inspectable candidate assessment, not an automatically endorsed mitigation.

The most valuable new work therefore connects **a user-owned model and requirement** to **a discovered interaction** and **a candidate decision with reserved evaluation evidence**. More models, more charts or a larger language model do not independently solve that product problem.

## The user job and the visible result

Target task: an analyst, researcher or technically curious judge has a supported SWMM model and a candidate control policy. They want to know which tested combinations defeat their declared requirement and whether a concrete parameter change improves that result without moving the problem downstream or beyond the horizon.

The user finishes with a decision report that states:

1. The exact model, mapping, policy, parameters and performance requirements.
2. What the discovery campaign actually evaluated, including its call budget and stopping condition.
3. The evidence for any claimed compound interaction, including nominal, individual and combined cases.
4. How a selected candidate performed on the declared comparison suite and the separately reserved evaluation cases, including regressions and missing runs.
5. The source bundle, trace references and commands needed to reproduce those claims.

This is the product promise to earn: **“Bring a stormwater model. Find a control failure that individual checks may miss. Evaluate a response, and export the evidence behind the decision.”** The middle sentence remains conditional until a valid compound example exists. No real-world protection or prize likelihood is implied.

## A guided investigation inside the existing workbench

Keep the hydrology field-notebook direction. The evidence remains the visual focal point; there is no separate large marketing page. The opening should give a judge two concrete starting points: **Use a published example** and **Import a supported model**. A worked example is explicitly recorded; a newly launched campaign is a new execution.

Use a compact three-stage investigation strip with clear completion and stale states:

```text
Define the test          Discover a failure          Evaluate a response
model + mapping         compound envelope           candidate + frozen suite
policy + requirement    budget + evidence           decision + reproduction

Setup rail              Active question + execution state
                        Evidence appropriate to the current stage
                        Full outcome comparison and export
```

This is a sequence of user decisions, so step numbers are meaningful. A stage cannot look completed because the user clicked Next. Its status follows the model validation, actual campaign or evaluation artifact. Editing an earlier stage creates a new draft and visibly leaves completed artifacts attached to their old identity.

### Define the test

The imported model first goes through inspection. Show the file name and hash, native flow units, converted display units, horizon, discovered control links, available observation nodes and downstream outlets. Present structural errors and unsupported features at the actual affected input. A structurally accepted model is not labeled calibrated or valid for field forecasting.

Use explicit mapping controls where the controller needs an observation node for an actuator, or the property needs a downstream outlet. Show extracted suggestions as suggestions. Save a model only after the required mapping is internally consistent. Invalid, external-file-dependent or unsupported models should explain the unsupported requirement and offer the published example as a working route. No fake import success and no unrestricted uploaded controller code.

Policy controls should come from a service-provided parameter schema. Each field has a name, units, supported range and a short explanation. Keep the common policy settings visible and place detailed per-asset overrides in a disclosure or compact table. Do not expose arbitrary implementation variables as if they were meaningful planning choices.

The requirement states a physical metric, threshold, tolerance and horizon. Non-regression guards for downstream and terminal behavior are explicit before interpreting a candidate. The current question is visible as plain language, for example, “Does constant-flow control keep total flooding within this limit under the declared fault combinations?”

### Discover a failure

The user declares an admissible envelope: supported assets/fault kinds, timing and duration ranges, rainfall transformations where actually supported, and a simulator-call budget. A bounded preset can help the judge start, but its bounds remain inspectable. Search does not silently introduce faults outside that envelope.

Show actual phases and counts: nominal check, individual checks, compound search and witness reduction. A nominal failure has its own outcome; it is not attributed to the introduced compound faults. Exhausted budgets and invalid/excluded runs are explicit.

For the selected compound case, use an evidence block before the detailed hydrograph:

| Evidence row | What it answers |
|---|---|
| Nominal | Did the policy satisfy the declared requirement before these faults? |
| Fault A only | Was A alone enough to violate it? |
| Fault B only | Was B alone enough to violate it? |
| A + B | What actually happened together? |

Only a checked result may say **“Each tested individual fault passed; their combination failed.”** A missing individual run leaves that claim unverified. A numerical interaction measure is displayed only with the engine/validator's definition and units; the interface does not invent a “synergy score.” Conditions, removal outcomes and all plotted data link to actual run identities.

### Evaluate a response

Let the user select or configure a supported candidate policy/parameter set. Clearly distinguish a manual candidate from a candidate selected using discovery results. Record how it was selected and freeze its parameters before reserved evaluation.

The evaluation view is a case matrix, not a single favorable average. Group discovery/selection cases separately from reserved evaluation cases. Each row shows reference and candidate outcomes, violation status, downstream and terminal guards, completeness and a link to its paired traces. Include nominal behavior and a worst evaluated case when supplied; a favorable mean cannot hide a failed guard.

Use **held out** only if those cases were actually withheld from candidate selection under the evaluation contract. If a user repeatedly adjusts a policy after seeing them, they have become observed evaluation cases; the interface must not continue to imply a pristine holdout. Root/Dario should specify how a fresh evaluation split is created or how reuse is labeled. The UI does not claim blindness on the basis of a different colored section.

Decision language follows the evidence:

- “Improves the primary metric and passes the specified guards on this evaluated suite.”
- “Primary improvement with downstream or terminal regression.”
- “Fails the reserved evaluation check.”
- “No allowed improvement found among these tested candidates.”
- “Evaluation incomplete; no decision claim available.”

The export action identifies the selected campaign and candidate. Its decision report should be useful without opening the application: clear question, scope, result, counterevidence, limitations and reproduction pointers. A source archive alone is a reproducibility artifact; the report explains the decision it supports.

## Proposed service seams

The names below are a proposal, not a backend contract. Final types follow root's actual API.

| Seam | Minimum information needed by the frontend |
|---|---|
| Inspect model import | Temporary import ID; file/hash; supported status; native units; horizon; assets/nodes/outfalls; required mappings; structured issues with severity |
| Confirm model mapping | Import ID plus explicit control/observation and downstream mappings; returned stable model ID, mapping digest and origin |
| Policy catalog | Policy ID/name/description; parameter schema with defaults, units and supported bounds; optional per-asset entries |
| Launch campaign | Frozen model/mapping, policy/parameters, property/guards, disturbance envelope, budget, seed and suite/split declaration |
| Campaign status | Stable campaign/job ID; phase; actual completed/scheduled calls; stopping reason; errors; available result artifacts |
| Discovery result | Coverage; actual candidate cases; compound evidence classification; individual and joint runs; reduced witness; existing `InvestigationView` or equivalent for a selected case |
| Candidate evaluation | Candidate identity/parameters and selection basis; suite manifest; discovery versus reserved membership; paired outcomes; guard results; completeness and verified claims |
| Export | Campaign/config digest; report artifact; source/replay packet; separate verification and replay statuses |

JSON text upload is acceptable for a bounded `.inp` size and simpler than multipart parsing in a small standard-library service. The UI should send the actual selected file content, not a fabricated filename. Backend validation defines supported SWMM features, file limits and mapping invariants. Unsupported external rainfall/time-series dependencies must be resolved explicitly, not silently dropped.

The API must distinguish absence from zero and invalid runs from passes. Artifact responses need immutable identities; the current draft settings cannot mutate completed campaigns or evaluation reports. An old/late job response cannot overwrite the newly selected campaign without a visible selection change.

## The novelty story to earn

Stormwater simulation, fault injection, parameter search, delta debugging and holdout evaluation already exist. Claiming a new invention in any of those areas without evidence would weaken the entry. The original contribution to demonstrate is their **usable, auditable connection around a planning decision**: ingest a supported model, discover and isolate a genuine interaction, evaluate a bounded response under the same conditions, expose its reserved-case limits, and hand off a replayable report.

Applied from [Before Growth](https://blog.samaltman.com/before-growth), the test of usefulness is whether a new reviewer can complete this decision without the author narrating every step. Applied from [Hard Startups](https://blog.samaltman.com/hard-startups), keep the ambitious end-to-end result while earning the next claim with a concrete artifact. No solo-development cap is introduced. These public-reasoning applications do not substitute for interviews, operator adoption or field validation.

For NextStep's published criteria, the strongest improvement is simultaneous: Completion gains a user-owned end-to-end workflow; Technology gains a real compound experiment and candidate evaluation; Design gains an understandable decision; Originality gains a more specific integration to demonstrate. Earth Forward fit remains direct through stormwater resilience. Learning must still be reported by the actual builder. No numerical rubric weights or probability of winning are invented.

## Acceptance before the improved demo

1. A judge can import a genuinely supported model, see detected units and mappings, correct a mapping and run it. A deliberately unsupported import fails with a recoverable explanation.
2. A policy parameter change affects a real submitted configuration and completed result. Old plots retain their original policy/configuration identity.
3. The advertised compound interaction has nominal, individual and combined evidence under matching exogenous conditions. If it is not found, the no-finding branch works.
4. A candidate's selection and evaluation split are explicit. The reserved suite is genuinely separate under the implemented protocol; no hidden repeat-tuning claim remains.
5. The paired comparison exposes every required metric and guard, including regressions, incomplete runs and failed nominal cases.
6. A decision report downloads and identifies the same campaign, candidate and suite visible in the UI. Replay verifies the numerical claims through the documented path.
7. Root reviews actual desktop/narrow layouts, new empty/loading/error states, keyboard mapping controls, campaign progress and the selected evidence/report flow.

This is the current proposal. Implementation decisions and actual verification will be appended as the service contract and results arrive.

## Implemented workflow and browser evidence — 20 September 2026

The workbench now has a compact four-stage navigation: Define test, Discover failure, Find response and Evaluate. These are navigation links, not completion badges. It supports a real `.inp` inspection/import flow, fault-type-aware inputs, supported policy parameters, rainfall/noise transformations, a declared compound-search grid, a response-search ledger, and an evaluation decision report. The existing trace explorer, immutable evidence, scientific checks, export and replay remain part of the same investigation.

### User-model path

- Selected the actual `engine/data/theta.inp` through the browser file input, named it “Theta import — interface check,” inspected its CMS units, 78-hour horizon, two outlet assets and six nodes, explicitly chose downstream link 8, and set target discharges to 0.2 and 0.3 m³/s. Registration returned `custom_4da5e795b9ea40d762f87516` and the model appeared in the selector.
- Running that imported model produced an actual fresh result: nominal flooding 0 and stressed flooding 1,970.498 m³. This proves interface integration with the imported input; it is not calibration or a contest claim.
- An input containing a `[FILES]` external dependency was rejected with the service's explanation. The dialog remained recoverable and the error panel received keyboard focus. A subsequent file can be selected without dismissing the dialog.
- A real submitted request used sensor P2, +0.5 m reading bias during hours 3–6, outlet 2 stuck at 0.035 during hours 6–8, and constant-flow target scale 0.98. Sensor choices were P1/P2 rather than outlet IDs. The fresh result was 49.554 m³ flooding with no error. Normalized backend defaults no longer cause a false “settings changed” message.

### Discovery and response path

Browser-run discovery `1b9821e9fcfb4404` used the declared 3×3 grid at basin P2/outlet 2, with three sensor offsets, three outlet openings and explicit five-minute-aligned windows. It completed 21 of 40 allowed simulator calls and screened all nine declared pairs. The retained reference, sensor-only and valve-only cases each produced 0 m³ flooding; the pair produced 237.263 m³. The UI displays the arithmetic interaction statistic and all five retained trace cases, while explicitly limiting independent trace validation to the retained proof rather than the screening ledger.

The “Find a guarded response” action then created real job `de5245d943a04a87`. It evaluated 25 of 25 candidates in 104 of 120 allowed simulator calls. Twelve candidates were rejected. The selected balanced-flow parameters were target scale 0.98 and balance gain 2, producing 11.580 m³ of joint flooding, a reduction of 225.683 m³ or 95.1% on this development case. The nominal and each-single-condition evidence remain visible after the response search, with all eight retained reference/candidate traces available.

The interface highlights a tempting rejected candidate from actual data: target scale 1, balance gain 2 produced 0 m³ joint flooding but raised the condition-A-only downstream peak by 0.002862 m³/s, above the declared 0.001 m³/s allowance. The complete candidate ledger preserves every tested candidate and each rejection reason. This explains why selecting only the smallest flooding number would give the wrong decision under the stated criteria.

### Evaluation and failure evidence

The user-triggered evaluation action posts the recorded job ID, not editable draft settings. Evaluation `6bbfa73789b84a86` was accepted, then failed with the explicit message “Recorded evidence or source identity is invalid. Run a fresh experiment before evaluating this suite.” Engine/source work was ongoing. The UI exposed that failure without substituting a report or counting it as a pass. A successful fresh user-triggered suite remains to be verified after hydraulic source changes settle.

The separately loaded recorded phase-one benchmark report is real and unfavorable. All 48 policy runs completed, but aggregate joint flooding increased from 8,461.74 to 10,361.60 m³: +1,899.86 m³ or +22.45%. Only one of six perturbations met the individual material-improvement criterion. Twelve of 24 condition subsets exceeded the primary non-regression allowance, and one condition subset failed a downstream guard. The UI leads with “Not all declared criteria met,” shows the aggregate regression explicitly, separates the two passing development criteria from failed suite usefulness, and opens adverse case tables automatically.

Report rendering takes case/run counts from the report rather than assuming six cases. Independently shifted sensor/valve timing in a future phase-two protocol is displayed from `fault_time_shift_s`, including nested transform details. User-triggered results are called a “Declared robustness suite”; the recorded benchmark is separately labeled as a frozen evaluation. A later passing candidate must not erase phase one's rejected result.

The browser downloaded a real self-contained HTML decision report and the complete report JSON. The HTML had one header row and all 24 condition-subset rows; the JSON retained six cases, 24 subsets and `acceptance.overall=false`. The HTML contains the decision, numerical aggregate, policies, complete outcome table, declared transforms, limitations and source identities. The server also provides the evaluation evidence bundle. Local `file:` navigation is unavailable through the browser tool, so standalone downloaded-HTML rendering has not been claimed; the equivalent report data was rendered and inspected in the application.

### Rendered and interaction review

- `npm run build` passed after the new workflow modules and integration edits.
- Actual desktop (1440×1000) and narrow (390×844) screenshots were inspected for import, discovery, response and evaluation. The page stayed at 390 px width on the narrow viewport; tables scroll within labeled, keyboard-focusable regions. No horizontal page overflow was measured.
- Narrow response layout preserves the selected parameters, reduction, rejected zero-flood candidate and scope. Evaluation keeps the failure headline and 22.45% regression readable before detailed cases.
- Browser reload restored the selected response via `?run=de5245d943a04a87` and its recorded benchmark report via `evaluation=benchmark`. No JavaScript page error was observed during that restoration. Unknown or unavailable run IDs show a visible recovery message.
- New jobs clear the previous job's phase before awaiting the response, so a long-running hosted POST displays a genuine preparing state instead of an old “Complete” phase. Retry repeats the operation that failed, including response search or export.
- Sensor-bias input, valve-opening input and policy parameters match current service bounds. Import errors, discovery-list errors and invalid windows are associated with their controls. Chart lines include the individual-condition and candidate-treatment roles.

Remaining verification: a successful fresh declared evaluation and evaluation-bundle download after source stabilization; rendered review of any new phase-two policy/report; hosted Vercel behavior once deployed. No field efficacy, all-storm robustness, optimizer superiority, independent screening-ledger trace validation or cross-platform replay claim is added by this UI work.

## Superseding verification after source stabilization — 20 September 2026

The successful declared evaluation and phase-two rendered review below resolve the corresponding outstanding checks above. The earlier source-identity error and rejected phase-one result remain historical evidence; neither is reclassified as a pass. Final hosted behavior remains the release owner's separate check.

### Sensor-plausibility candidate and visible mechanism

The browser created response job `dde2386543384d65` from the recorded compound discovery. Its explicit grid used `plausible_depth`, target scale 1, a 0.65 m jump threshold and correction fractions 0.25, 0.5 and 0.75, with a 120-call budget. Three candidates consumed 16 simulator calls. The selected correction fraction was 0.75. Joint flooding was 19.361 m³, a reduction of 217.902 m³ or 91.8% on the development pair, and all development-search criteria passed.

The new sensor inspector exposes the mechanism instead of treating the policy as a black box. At hour 3 for P2, the physical depth was 0.236 m, the supplied sensor reading 1.236 m and the policy control input 0.487 m. The recorded estimated offset was 0.9986 m, with one threshold crossing and an aggregate command-cap scale of 1×. The interface calls that offset a hypothesis; it does not claim general fault-detection accuracy or that this reconstruction is available to a real operator as ground truth.

The inspection action selects the actual candidate trace and its first nonzero recorded offset. A response-search fallback is labeled “Candidate response,” preserving the meaning of the original fallback elsewhere. “Focus on fault” considers both active windows: the sensor fault at hours 3–6 and valve fault at hours 6–8 give a plotted interval of hours 2–9. The full 78-hour trace remains available. Eight trace readouts arrange in two rows of four on desktop.

### Successful declared suite and evidence export

User-triggered declared evaluation `1f552c0dbb6046cd` completed from response `dde2386543384d65`. All 48 required runs completed across six visible, reusable transformations. All declared criteria passed; aggregate joint flooding decreased by 1,413.60 m³ or 16.71%, and four of six cases met the individual material-improvement criterion. This is a **declared robustness suite**, not an unseen holdout. Passing it does not override the separately frozen phase-two rejection below.

The actual browser download `stormpilot-robustness-1f552c0dbb6046cd.zip` contained 29,191,936 bytes, 161 entries and seven compressed full packets, including the source, requests, report and suite cases. `ZipFile.testzip()` returned `None`, confirming archive integrity. Both redundant downloaded copies were deleted after this check to conserve disk space; the service's original export remained available for release persistence.

### Phase-two rejection remains the decision

The separately frozen phase-two benchmark completed 64 valid runs over eight transformations and 32 condition-subset comparisons. Aggregate joint flooding fell from 9,840.09 to 9,122.72 m³: 717.37 m³ or 7.29%. Two of eight cases met the individual material criterion, and no condition subset increased primary flooding. The candidate nevertheless failed the frozen criteria for three explicit reasons:

1. The aggregate reduction was below the required 10%.
2. Only two cases met the material criterion; at least four were required.
3. P2H1/AB downstream excess increased by 1.471134 m³, above the 1 m³ allowance.

The rendered decision leads with **“Candidate rejected by these criteria.”** It shows all three reasons and their thresholds before the full case tables. Better aggregate flooding and primary non-regression are visible evidence, but they do not change the rejection.

The phase-two report also carries an information-boundary clarification: isolated history of the same observations used v2 while frozen protocol metadata said v1. The clarification states that transformations and acceptance rules did not change. It is visible in limitations and preserved in JSON and HTML exports. Its `content` is structured data, not a string; a discovered React runtime error from rendering the object directly was fixed by explicitly converting it to readable text while retaining the raw object in JSON.

### Final rendered checks

The response, sensor inspector and phase-two report were inspected at 1440×1000 and 390×844. No horizontal page overflow was measured; outcome tables scroll inside labeled, focusable regions. The rejection reasons and acceptance thresholds remain readable on the narrow viewport. A final reload of `?run=dde2386543384d65&evaluation=phase2`, sensor-inspection action and fault-focus action produced zero browser console errors. Duplicate sibling keys were also corrected by giving sensor and response trace items distinct prefixes.

The phase-two HTML and JSON downloads retain the decision, complete case evidence and information-boundary clarification. Standalone HTML rendering is still unverified because the browser tool blocks local `file:` navigation; the corresponding application view and exported contents were checked. The browser was handed back to the release owner for demo recording after these checks. No further simulations or duplicate large downloads were needed for the frontend review.
