# StormPilot — four-minute narration

This take is grounded in tracked experiment **`a3fd3abf0ac0fe120dcb`**, recorded in `fixtures/demo-packet.json.gz`. Decompressed packet SHA-256: `22f140ab59c1655cb9713872c3501f5b636491a44a4420502410d7e79409e00a`. Compressed fixture SHA-256: `c5ef377198382d18942900bb682bda30e88180b22bec4774873a4ac5c046922d`. The reviewed UI job is `67e33999ffac61fa`; the experiment ID and fixture hash are the scientific artifact identity.

Use the actual matching recorded experiment in the interface. If the browser generates a fresh experiment, check its configuration, metrics, witness and report before reusing this narration; do not silently attach these numbers to another run. Screen directions are not spoken. The spoken text is about 465 words, leaving room for inspection and export in a measured four-minute take.

## 0:00–0:25 — the question

**Screen:** Show the selected experiment and Recorded run label.

“StormPilot crash-tests a stormwater control plan and gives you an experiment you can inspect and replay. We ask a specific question: does this policy still satisfy its declared check when an outlet fails? Then we isolate the failure and examine what an alternative policy changes. This is a recorded result from the actual hydraulic solver.”

## 0:25–0:55 — the experiment

**Screen:** Show Theta, constant-flow control, the 100 m³ flooding check and the two fault windows.

“This is Theta, a published two-basin benchmark, running EPA SWMM over its full seventy-eight-hour horizon. The requirement is at most one hundred cubic metres of modeled flooding. Constant-flow control produces zero flooding without faults. We then close outlet one from hour one to six, and outlet two from hour thirty to thirty-one. Both conditions are recorded before evaluation.”

## 0:55–1:25 — the observed failure

**Screen:** Select the original stressed trace, use “Focus on fault,” inspect the early fault window, then show its full-horizon flooding total.

“Together, those faults produce one thousand six hundred twenty-one point four-five cubic metres of flooding. The chart and time inspector expose the hydraulic response behind that total. The displayed total comes from the full simulation evidence, not an estimate from this simplified plot. Every panel belongs to this experiment, so changing a setting cannot relabel the old result.”

## 1:25–2:05 — the reduced witness

**Screen:** Show two original conditions becoming one retained condition; select the reduced case. Open “Inspect tested removals” to show the recorded ablation outcomes. The rows identify actual runs and deduplicate cached reuse.

“The reducer removes conditions and reruns the model. Removing the later outlet-two fault leaves the same flooding total. Keeping only that later fault produces zero flooding. The early outlet-one fault is sufficient, and removing it eliminates the violation. That earns a one-minimal witness over these declared faults. It does not prove global minimality over all possible storms or fault timings. This investigation used five actual simulations and one cached reuse, within an eight-call budget.”

## 2:05–2:55 — the alternative's cost

**Screen:** Compare the reduced witness with the outlets-open fallback. Select Downstream flow; keep the full outcome table visible.

“Now the outlets-open fallback faces the same remaining fault, weather and horizon. Flooding falls to one thousand two hundred seventy-five point four-two cubic metres. But peak downstream flow rises from zero point four-nine-zero to six point three-five-five cubic metres per second. Discharge above the declared zero point five flow threshold totals two thousand six hundred sixty-one point nine-three cubic metres. Terminal storage changes from four point six-five-one to four point five-nine-one cubic metres. The fallback still fails the flooding check and worsens two downstream guards. This is a tradeoff, not an overall improvement.”

## 2:55–3:35 — verification

**Screen:** Export the actual packet. Show the selected run’s record-check report and `validation/archive-portability-check.json`, or their accurately integrated UI equivalents. The archive report covers the same experiment/configuration; exact packet-byte differences are documented below.

“The packet carries the model, policy definitions, realized inputs, complete traces, removal records and hashes. Its record checker passes one hundred thirty-one checks and lists its limits. We independently replayed this experiment from an exported source bundle, in a separate directory on this Mac. All five configurations and sixty-three thousand five hundred fifty-six physical trace rows matched. That verifies local reproduction, not field calibration or cross-platform identity.”

## 3:35–4:00 — the contribution

**Screen:** Return to the reduced witness, tradeoff and export link.

“EPA SWMM supplies the solver; pystorms supplies the public model and the foundation for the control methods. StormPilot adds the bounded investigation, removal-based witness, matched comparison, trace inspection and reproducible evidence workflow. The useful result is a precise weakness someone else can check. We have demonstrated that in a published simulation, without claiming that a real neighborhood is protected.”

## Recording reference

| Case | Flooding, m³ | Peak downstream flow, m³/s | Downstream excess above 0.5 m³/s, m³ | Terminal storage, m³ |
|---|---:|---:|---:|---:|
| Nominal, no faults | 0 | 0.4915465632 | 0 | 4.6510187280 |
| Original, both faults | 1,621.4521074470 | 0.4900879261 | 0 | 4.6717427777 |
| Later fault alone | 0 | 0.4915465632 | 0 | 4.6717431344 |
| Reduced, early fault alone | 1,621.4521074470 | 0.4900879261 | 0 | 4.6510183919 |
| Fallback, early fault alone | 1,275.4179973493 | 6.3553446998 | 2,661.9254749096 | 4.5910228942 |

Source model revision: `20cc6086433449df99177d4f9103940639ef3af0`. EPA SWMM 5.2.4 source revision: `7952ca837988b1c32f791812eccc9fd64547e093`. Flooding threshold tolerance: `1e-6 m³`. Downstream non-regression guards permit zero increase within the specified tolerance; terminal storage is also checked.

The record checker and simulator replay have different scopes. The archived record check reports 131 passed checks and three explicit unperformed categories. Its own replay status is unperformed because reading a packet is not simulator execution. The separately executed replay check reports eight passed checks. `validation/archive-portability-check.json` records the source-bundle reconstruction: 111 manifest hashes checked, native binary built from archived source in a separate directory, all four documented commands succeeded, five recorded configurations and 63,556 physical trace rows matched with zero maximum difference. This was on the same Mac using its installed Python and C compiler; another operating system was not tested. The replay reproduced recorded cases, not a fresh search.

That archive report belongs to API job `cffb0edfb52c40ce`, archive SHA-256 `1e4c720794a623cedf418fe6165019d0cd5f081a10d96867a1a05f28b37e3565`, whose `packet.json` SHA-256 is `be281fa3aa02fe55fee9c4f982312d9e41202e7a70ff7594488fa30e646b118d`. It and the tracked fixture share experiment ID `a3fd3abf0ac0fe120dcb`. A direct comparison confirmed equal request, provenance, experiment declaration, every run's metrics, full physical traces and display traces. Their packet bytes differ, so the archive report is described as replay of the same experiment, not verification of the fixture's exact file hash. The fixture's own file hashes are pinned at the top. Do not substitute the earlier development reports for the differently identified `f1`/`f2` experiment.

The archive audit found two optional example JSON files absent from that earlier export; root was notified to include them in subsequent archives. The main documented build/validation/replay commands still passed. Do not collapse these reports into a claim that all imaginable checks passed.

If the UI or selected result changes, use the conditional branches in `demo-script.md`. Do not claim successful export, fresh browser execution or corrupted-packet rejection unless those actions are actually shown or independently recorded. The final recording itself remains to be made.
