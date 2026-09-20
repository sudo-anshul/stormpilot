# StormPilot — demonstration narration

Use the actual app at https://stormpilot.vercel.app. The recorded welcome discovery is UI job **6174a80795372955**, experiment **9df1ca1d7273778d8e7c**. Decompressed packet SHA-256: `4c14e2a1c82d14d96b6c1e4812e6b4af64a1ddd7a401add53438ca51bba460d4`. The final video must identify saved results as recorded. Only show an operation as successful after its actual completion.

Target: about three minutes, with pauses for the evidence. Screen directions are not spoken.

## 0:00–0:25 — the missed failure

Screen: opening recorded discovery and the four-condition evidence.

“StormPilot helps stormwater modelers test a proposed controller before recommending it. A sensor fault passes. A valve fault passes. Together, they cause a flood. This recorded experiment comes from the actual EPA hydraulic solver, with evidence available to inspect and replay in the live workbench.”

## 0:25–0:55 — the mechanism

Screen: discovery grid, fault windows, sensor-only and valve-only results.

“This is Theta, a published two-basin benchmark, simulated over seventy-eight hours. A sensor reads one metre high from hour three to six. Later, outlet two is restricted from hour six to eight. Neither fault alone produces flooding. Together, they produce two hundred thirty-seven cubic metres, above our fixed limit of one hundred cubic metres. At hour six, the biased-sensor case already holds about four hundred seventy extra cubic metres of water.”

## 0:55–1:20 — a real experiment

Screen: native call counts and traces; briefly open setup/import or the declared grid.

“The search checked nine declared fault pairs using twenty-one native simulations. Five full-proof cases preserve the normal, individual, joint and alternative outcomes. The grid, budget and stopping condition are visible. You can edit the faults or import a supported SWMM model with an explicit downstream mapping, then execute a fresh investigation.”

## 1:20–1:55 — the tempting response

Screen: actual completed plausible-depth response, parameters, sensor inspector at hour 3.

“We also search candidate responses under flooding, downstream and terminal-storage guards. This candidate checks abrupt changes in past sensor readings and cautiously adjusts the depth used for control. It does not see hidden fault flags, true simulator depth or future rainfall. Here, observed depth and estimated control depth are separate. The estimated sensor offset is a hypothesis. On the development case, flooding falls from two hundred thirty-seven to nineteen point three-six cubic metres: a ninety-one point eight percent reduction.”

## 1:55–2:35 — the result that matters

Screen: Phase 2 frozen evaluation, rejection headline, aggregate and guard failure; Phase 1 briefly if time.

“We froze the candidate and tested eight unseen transformations. All sixty-four simulations were valid. The aggregate flooding reduction was seven point two-nine percent, below our ten-percent requirement. Only two cases improved materially, and one downstream-excess guard failed. StormPilot rejects the candidate. It also preserves the earlier candidate that made the reserved suite twenty-two percent worse. The final decision follows every declared criterion.”

## 2:35–3:05 — reproducibility and contribution

Screen: decision report and actual source evidence download; return to full workflow.

“The decision report states the criteria, complete results and limits. The evidence archive includes exact models, sources, traces and replay commands. The independent checker recomputes the physical metrics; an actual replay is a separate action. EPA SWMM supplies the hydraulics, and pystorms supplies the public benchmarks. StormPilot adds the connected discovery, response testing and evidence workflow. These are benchmark results, not a field flood-prevention claim. The contribution is finding a hidden failure—and refusing a response the evidence does not support.”

## Recording checklist

- Show real results at normal playback speed; identify recorded results.
- Include the failed Phase 2 verdict, not just the 91.84% development reduction.
- Keep units and the 78-hour horizon visible when discussing outcomes.
- Do not describe sampled display traces as the complete physical evidence.
- A successful download is not a successful replay. Show each only if executed.
- Keep personal account details and private environment credentials out of frame.
