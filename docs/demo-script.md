# StormPilot — conditional four-minute demonstration

Status: conditional fallback template. Use `demo-narration.md` for the current compound-discovery recording and its exact artifact identity; this document supplies alternative branches if a newly selected experiment differs.

## Recording contract

Choose one genuine completed experiment as the main demonstration. Record its experiment/run ID, packet digest, model and engine versions, controller definitions, declared property, horizon and validation report in the recording notes. Replace every bracketed field below directly from that packet. Remove all unresolved placeholders before recording. Numerical rounding must preserve units, direction and whether the stated tolerance was exceeded.

Use the branch supported by the evidence; do not arrange the narration around an assumed failure, reduction or improvement. The spoken spine below, with one branch per section, is approximately four minutes at a measured pace. Screen directions are not spoken. Rehearse against the actual UI; if a control or verification action does not exist, fix it or state the limitation instead of miming it.

If computation exceeds the demonstration window, open a real saved experiment visibly labeled **Recorded run**, say that it is recorded, and show its exact configuration. A short fresh run may demonstrate editability separately. Never label the recorded result as the outcome of an unfinished fresh job. When editing inputs, retain the old result's run identity until the replacement completes.

## 0:00–0:25 — the decision

**Screen:** Open directly to the experiment workspace, with selected model and run status visible.

**Say:** “StormPilot asks a specific planning question: under these modeled conditions, where does a stormwater control policy break its declared check, and what does another policy change? It turns a simulation into an inspectable test: the conditions, the trace, the explanation and a packet someone else can replay.”

## 0:25–0:55 — exactly what is being tested

**Screen:** Show model/source, policy, property, horizon and fault configuration. If using saved output, show the Recorded run label and run ID.

**Say:** “This is [model], from [source], run with EPA SWMM [version]. We test [policy] against [property in plain language, including units and threshold] over [horizon]. These are [actual supported disturbances]. The controller receives [declared observations]. It cannot inspect hidden fault schedules or future realized rainfall. [This is a recorded experiment / I am starting this experiment now]; its inputs and result share this identifier.”

**Action:** If showing a fresh run, invoke the real run control and wait for actual completion or clearly distinguish its in-progress status from the selected recorded result. Do not narrate fabricated progress.

## 0:55–1:45 — the finding and its supporting trace

**Screen:** Show nominal and stress cases, tested count/budget, aligned chart and selected event/time inspector. Select the actual series and time cited.

**Failure branch:** “The nominal reference is [actual outcome]. Across [evaluated] tested cases, [failed] exceeded this check. Here is one witness: [short fault description]. At [elapsed simulation time], this trace shows [value and unit] against [check]. You can inspect the recorded values behind the chart. This is a failure of this policy under this model, property and test envelope.”

**No-violation branch:** “No violation was found in [evaluated] tested cases within this envelope. Here is the closest tested case according to [declared metric], with [value and unit] against [check]. The recorded trace supports that bounded conclusion. It does not establish behavior outside these conditions.”

**Invalid branch:** “This run is invalid because [actual diagnostic]. It is excluded from the comparison. The app preserves its inputs and logs and makes the missing evidence explicit.” Then show an already valid experiment if available. If none exists, present a truthful implementation-status demonstration; do not claim a completed scientific result.

## 1:45–2:20 — isolate what the evidence supports

**Screen:** Show original and retained fault sets, with actual removal records. If no failure exists, show tested coverage instead of a reduction action.

**Verified 1-minimal branch:** “Starting with [original count] conditions, the reducer retained [retained count]. We replayed every single removal from this final set, and each removed the violation. This supports 1-minimality over these named faults. It is not global minimality over all possible faults or severities.”

**Reduced-witness branch:** “The violation remains with [retained count] of the original [original count] conditions. These are the removals we actually tested. We call it a reduced witness; the untested removals remain unverified.”

**No-reduction branch:** “The search found no smaller failure within [actual budget]. The original witness still reproduces. These records show what was tried and why the stronger minimality claim is unavailable.”

**No-violation branch:** “There is no failure witness to reduce. Instead, this view records [tested dimensions and budget], including incomplete or excluded cases separately.”

## 2:20–3:00 — compare the alternative fairly

**Screen:** Show the paired fallback and full outcome table: flooding, downstream excess/peak, terminal storage or the declared drain-down metric. Keep names, units and horizon visible.

**Say:** “Now we compare [fallback] under the same weather, initial conditions and active faults. Each policy evolves its own hydraulic state. The primary metric changes from [A] to [B]. Downstream [metric] changes from [C] to [D], and terminal [metric] from [E] to [F].”

Choose one supported close:

- **Improvement and all guards pass:** “The primary metric improves by [absolute delta], and every specified non-regression guard passes within its recorded tolerance.”
- **Tradeoff:** “The primary metric improves, but [specific guard] worsens beyond its limit. This is a tradeoff, not an overall improvement.”
- **Tie or worsening:** “This alternative [ties/worsens] the primary metric within the declared tolerance. The packet keeps that result; the comparison does not promise a winning policy.”
- **Incomplete comparison:** “This comparison is incomplete because [reason]. The missing result is unavailable, and no superiority claim is made.”

## 3:00–3:40 — make the claim reproducible

**Screen:** Export the selected run's real packet; show the included configuration, artifacts and independent validation report. Execute the documented replay command if its duration permits. Otherwise show its recorded, identifiable execution result and state that fact.

**Say:** “This export belongs to [run ID]. It contains the model and controller definitions, realized external inputs, complete evaluation traces, metrics and reduction records, plus a hash manifest. The independent checker reports [actual passed, failed and unperformed checks]. [The replay just reproduced these values within the declared tolerance / This recorded replay reproduced these values within the declared tolerance / Replay instructions are included; replay has not yet been verified].”

Only if actually tested: “Changing [specific artifact] causes the packet check to fail.” Show the genuine rejected-copy result; preserve the original packet.

## 3:40–4:00 — contribution and boundary

**Screen:** Return to the finding with its packet and source links visible.

**Say:** “EPA SWMM supplies the hydraulic solver; [upstream source] supplies [model/controller contributions actually used]. StormPilot adds [only implemented search, reduction, fair comparison, trace-linked inspection and reproducible evidence capabilities]. The result is a testable claim about a published simulation. It is not a local flood forecast or a field safety certificate. The next reviewer can inspect the same evidence and rerun the same question.”

## Final take checklist

- The spoken finding matches one identified packet and its complete validation report.
- Every visible number is real; missing or excluded values are unavailable, never zero.
- Fresh and recorded execution are distinguished; draft settings cannot silently relabel old evidence.
- Primary improvement, guard outcomes and completeness are spoken separately.
- Minimality wording matches the actual single-removal evidence; no global claim appears.
- The recording shows actual supported interactions and includes a real export.
- Replay language matches executed evidence, including any platform or tolerance limits.
- Public source attribution and original implementation are accurate. No physical deployment, flood prevention, municipal adoption, review-time saving or prize outcome is invented.

Product review basis: the Sam advisory lens favors a concrete useful result before presentation polish. This is an application of published reasoning, not a consultation or endorsement by Sam Altman.
