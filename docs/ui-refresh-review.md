# UI refresh — executed review

September 20, 2026. This pass changes the interface, navigation and derived presentation of existing evidence. It does not change the hydraulic engine, controllers, acceptance criteria or recorded scientific conclusions.

## Design

The Alina and design-direction skills informed three compared approaches: a technical field notebook, an instrument workbench and a guided experiment wizard. The selected workbench distinguishes configuration, measurement, plotting and evaluation through composition, type and surface treatment. [The direction record](alina-direction.md) includes the alternatives, tokens and independent visual review.

The result has a compact teal masthead, sage configuration rail, prominent measurement strip, active section navigation, legible evidence tables, and a full-width sticky run action. Mobile configuration collapses above the investigation. A timing ruler uses actual selected fault windows and explicitly distinguishes its detail range from the full simulation horizon. The measurement meter is derived from the displayed metric and declared threshold; text remains authoritative.

## Browser verification

Chromium through Playwright, against the local Vite preview with the existing production API. These are executed checks, not a participant study.

| Check | Observed outcome |
| --- | --- |
| Reflow | At 320, 390, 768, 900, 920, 1280 and 1440px the document had no horizontal overflow. The final 900/920/320/1440 boundary check waited two animation frames after each resize: rail widths were respectively 900/268/320/294px. |
| Sticky navigation | Trace received focus and cleared the sticky navigation. Active section tracking and horizontal visibility of the mobile Evaluation item worked. Ordinary and reduced-motion navigation were exercised. |
| Configure | Narrow setup expanded and focused the model input. The desktop action shelf covers the rail's lower and side edges; the initial exposed-field defect was corrected and rechecked. |
| Chart | Fault focus selected the 2–9h display window; stored-water selection worked. Full-horizon headline metrics remained unchanged. |
| Draft settings | Editing the threshold from 100 to 110 showed the stale-result notice and preserved the recorded metric. The value was restored before execution. |
| Fresh discovery | Job `0d2ef506570e4be1` completed through the redesigned form: 21 simulator calls; 0 m³ nominal, sensor-only and valve-only; 237.262837 m³ jointly. Evidence status passed. |
| Frozen evaluation | Phase 2 loaded from the API and preserved the rejected verdict and all three reasons: 7.29% aggregate reduction below 10%, 2 of 8 material improvements below 4, and downstream excess +1.471134 m³ above the 1 m³ allowance. |
| Evidence dialog | Tab remained inside the native dialog. Escape closed it and restored focus to its trigger. |
| Import | An actual Theta input was inspected successfully, with focus on downstream mapping. At 390px, the 356px dialog had equal 354px client/scroll widths; mapping and footer remained reachable by vertical scrolling. Escape restored trigger focus. This inspection did not register another model. |
| Contrast | Alina's final review corrected the small amber pending-status label from 3.95:1 to 5.57:1 on white. Other measured token pairs are listed in the direction record. |
| Clean reload | Final local Phase 2 reload reported zero console errors or warnings. Earlier in the session, a local proxy origin mismatch caused a recoverable 403; the preview proxy was corrected without changing production origin protection. |

Screenshots: [desktop](images/ui-refresh-desktop.jpg), [390px opening](images/ui-refresh-mobile.jpg), [frozen evaluation](images/ui-refresh-evaluation.jpg). They show the final local interface; the evaluation capture deliberately retains the rejected result.

## Build and limits

The final local TypeScript check and Vite production build passed, including the final contrast correction. To respect severe local disk pressure, the preview reused existing installed packages: Vite 8.3.0, React 19.3.0 and plugin-react 6.1.1 matched the project; TypeScript 5.9.3 and lucide-react 0.577.0 were local substitutions. All 31 imported icons resolved. Vercel's production Docker build uses the exact package-lock versions, including TypeScript 7.0.2 and lucide-react 1.47.0. No dependency or lockfile change is part of this refresh.

The earlier release's 141 Python and four Node tests remain recorded in [verification.md](verification.md). The native suite was not repeated for this interface pass. A fresh native discovery was executed as described above. No screen-reader test, full accessibility conformance, operator study, or field validation is claimed. The existing demonstration video predates the UI refresh; its scientific results are unchanged.
