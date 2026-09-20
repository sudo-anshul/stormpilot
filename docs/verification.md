# Executed verification — improved release

Date: September 20, 2026. Local environment: macOS, Python 3.14.3, Node 22.20, clang and Chromium through Playwright. Production: Vercel native Linux container, Python 3.12 and compiled EPA SWMM 5.2.4. This record describes software and simulation evidence; no field validation or operator study is claimed.

## Scientific evidence

The current recorded discovery is UI job `6174a80795372955`, experiment `9df1ca1d7273778d8e7c`. Its packet passes the separate validator. The full 78-hour Theta experiment produces 0 m³ flooding without faults, 0 with either fault alone, and 237.262837 m³ with both. The 21-call declared search retains five full-proof cases. The candidate produces 19.361153 m³ on this development case.

Both frozen candidates fail their reserved evaluations. Phase 1 has 48 valid runs but increases aggregate flooding by 22.45%. Phase 2 has 64 valid runs and reduces it by 7.29%, below the required 10%; two of eight transformations improve materially, below four required; one downstream-excess guard fails. These failures are the reported conclusions, not invalid simulations.

The source-complete Phase 1 archive was independently rechecked across 56 runs and 727,771 trace rows. Phase 2's archive audit checked 218 manifest files, 72 runs, 933,235 trace rows and 1,311 checks without failures. An actual source rebuild and replay of Phase 2 case p2h1 executed eight simulations and matched 109,088 physical rows with zero observed difference. This was an isolated directory on the same Mac, not a field experiment or a guarantee of cross-platform equality. See [validation.md](validation.md), [phase2-archive-audit.json](../validation/phase2-archive-audit.json) and [phase2-p2h1-replay-check.json](../validation/phase2-p2h1-replay-check.json).

## Automated checks

The release run passed 20 native-engine behavioral tests, 62 separate validation/negative tests and 20 evaluation tests. Its initial service rerun hit local disk exhaustion while writing an extracted replay and a repair packet. Redundant task caches were reclaimed after preserving completed evidence in private Blob storage. The affected service suite then passed all **39 tests**, including 20 cloud-boundary tests; all **four Node Blob tests** also passed. The verified total is **141 Python tests and four Node tests**. `npm test` runs both groups.

Cloud failure-injection tests cover partial upload retries, immutable byte conflicts, concurrent hydration/writes, export followed by a demo action, direct import lookup beyond the first catalog page, overload before hydration, initialization cleanup, parent leases, shared deadlines, signing errors and fixed-evaluation archive publication. These mocked boundaries do not substitute for actual production tests.

The final frontend TypeScript/Vite build passed after the fixed-evidence download controls were added. Reproducible frontend dependency caches were temporarily removed to free disk space; `npm ci` restores them. Native and validation source remained unchanged during cloud work.

## Browser tasks exercised

| Workflow | Observed outcome |
|---|---|
| Model import | Actual Theta `.inp` inspected; units, controls, downstream link and targets registered; fresh native run completed. External-file-dependent input rejected with a recoverable error. |
| Editable experiment | Sensor bias, valve opening, timing and policy settings were sent in the actual request; old evidence retained its identity while draft settings changed. |
| Compound discovery | 21 calls, nine pairs, individually passing faults and the 237.263 m³ pair shown with the retained proof. |
| Guarded response | Fresh job `dde2386543384d65` selected sensor-plausibility scale 1, threshold 0.65 m, correction 0.75; eight retained cases and 19.361 m³ joint flooding. |
| Sensor inspection | At hour 3, physical depth 0.236 m, supplied reading 1.236 m and control depth 0.487 m remain distinct; inferred offset labeled as a hypothesis. |
| Declared evaluation | Job `1f552c0dbb6046cd` completed all 48 runs, with 16.71% aggregate improvement and all declared criteria passing. It is explicitly a reusable declared suite, separate from the rejected Phase 2 reserved evaluation. |
| Decision export | HTML and JSON reports downloaded. Declared evidence ZIP passed integrity with 161 entries and seven full packets. |
| Recorded evaluations | Separate Phase 1 and Phase 2 views preserve rejection; Phase 2 shows all three failure reasons and the information-boundary clarification. |
| Responsive and keyboard | Desktop and 390 px layouts inspected; no horizontal page overflow. Focused fault view spans hours 2–9 while full-horizon metrics remain unchanged. Controls and tables retain labels and keyboard access. |
| Console | Final clean reload had no console/page errors. |

See [new-product-review.md](new-product-review.md) for the executed details. Earlier screenshots/review and `docs/evidence/welcome-*` describe the first prototype, not this current fixture. Actual screen-reader use and full accessibility conformance have not been established.

## Hosting and delivery

The first Vercel deployment successfully built and executed the native solver on Linux. Production job `8490cd47a9444985` passed validation and matched the corresponding Mac example metrics. Local cloud-adapter tests separately demonstrated result restoration after deleting its local cache and a real signed private-Blob export.

The final release adds retryable immutable publication, bounded cloud deadlines, safe source leases and frozen-evaluation downloads. A fresh production discovery → response → declared evaluation → export → replay check is the final release gate; results will be recorded here and in `docs/evidence/production-release.json` after execution.

GitHub Actions is configured, but GitHub refused to start runners because recent account payments failed or the spending limit needed increasing. No GitHub-hosted CI pass is claimed and no billing settings were changed. The Vercel Linux build/run evidence is separate.

The GitHub repo remains private. A private link alone is not judge viewing access; [SOURCE-ACCESS.md](../SOURCE-ACCESS.md) describes the prepared code handoff. No judge invitations or Devpost submission have been sent. The demonstration recording and its verified duration are tracked separately in the final delivery entry.
