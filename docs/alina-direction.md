# Alina design implementation

StormPilot is an investigation workbench for a hydraulic modeler, with a first-time hackathon judge as a secondary reader. Its primary job is to make a declared experiment, inspect the resulting failure, compare a candidate response, and retrieve the evidence. The design must never make a passed development case look like a passed frozen evaluation.

## Direction selected

Three compositions were considered with the same factual material:

| Direction | Opening and reading path | Useful property | Cost for this product |
| --- | --- | --- | --- |
| Technical field notebook | A narrative finding, followed by sequential sections and disclosure details | Careful reading and provenance | The previous implementation made most surfaces look equivalent; tiny type and repeated cards made the working state hard to scan. |
| Hydraulic instrument workbench | Active result and measured values first; traces and controls on white instrument surfaces; decisions and evidence presented as a flatter ledger | Fast orientation between experiment, measurement, and decision | Needs discipline around density, so configuration collapses at narrow widths and detail remains available on demand. |
| Guided experiment wizard | Model, faults, run, response, evaluation as separate screens | More guidance for an unfamiliar user | Hides comparisons and requires repeated transitions when a modeler iterates on an investigation. |

The instrument workbench is the chosen direction. This is a compositional decision, not a palette swap: the setup rail is distinct from the measurement strip; charts and inspectors retain bounded interaction surfaces; proof and evaluation become structured documents with ruled comparisons instead of another stack of identical cards. Existing Manrope and IBM Plex Mono fonts, teal/sage identity, real model graphics, and all scientific wording remain the base.

## Implemented visual contract

- A compact deep-teal masthead establishes identity. The pale-sage setup rail visually separates configuration from results.
- The result heading, full-horizon measurement, nominal comparison, and simulator-call accounting form the opening hierarchy. A single instrument-style outcome strip holds these values. Its small meter is redundant with the explicit value and declared threshold; it does not introduce a safety claim.
- In-page navigation reads as location rather than completion. The active section receives an underline; the masthead and section navigation remain sticky during long evidence reports. Target headings have explicit scroll clearance, and compact navigation scrolls horizontally on narrow layouts.
- The four-case compound proof remains visibly comparable. The actual fault windows appear in a small timing ruler with explicit text labels; the ruler is a detail view, not the full simulation timeline.
- Charts receive a white plotting surface, stronger series strokes, legible controls and readings, and retained line patterns. Network diagrams remain schematics from the actual model.
- Response and evaluation sections use clear typography, tabular values, quiet rules, and stronger rejection contrast. All rejection reasons remain alongside the outcome. Evidence links are visually distinct from status.
- The setup action remains in a sticky action area; desktop configuration has its own bounded scrolling region beneath the masthead, and settings collapse below 900px. Main content uses shrinkable tracks, and tables deliberately retain their horizontal scrolling region. Narrow form inputs use 16px type to avoid focus zoom in iOS browsers.
- Focus indicators, hover/disabled states, reduced-motion behavior, dialogs, errors, provenance, and import states follow the same shared system. No animation, imagery, icons, claims, or additional dependencies were introduced for decoration.

## Semantic tokens

| Role | Value |
| --- | --- |
| Workspace background | `#f3f6f4` |
| Instrument surface | `#ffffff` |
| Configuration surface | `#e9f0eb` |
| Primary text | `#183c38` |
| Secondary text | `#526b64` |
| Action teal | `#124f48` |
| Measurement surface | `#174e46` |
| Failure / caution | `#a74f20` / `#a0362c` |
| Positive criterion | `#27664d` |
| Focus | `#1c78b0`, with a light ring in the dark masthead/measurement region |

Core copy is 12–14px; supporting IDs and plot units remain compact. Headings use Manrope; tabular measurements, source IDs and plotting labels use IBM Plex Mono where that assists comparison. The implementation uses the existing component CSS as a baseline, followed by one documented workbench layer; no new rendering library is required.

## Evidence and review boundary

The starting point was inspected in `docs/images/release-opening.png`, supported by the current component source and the installed Alina, design-direction, frontend-design and interface-design-review guides. The observed old opening had a large amount of equivalent pale-green framing and compact copy; the remedy above is a design hypothesis being checked in the actual browser, not participant research.

The new layer has balanced CSS braces. Opaque sRGB calculations checked the declared token pairs: primary text 11.08:1, secondary workspace text 5.29:1, secondary rail text 4.97:1, light measurement text 6.68:1, rejection body text 6.04:1, and positive criterion text 6.82:1. The focus ring on white is 4.81:1; timing bars against their track are 3.64:1 and 3.81:1. These verify the listed opaque pairs, not every composited or interactive state. The root implementation task is carrying out rendered desktop/narrow and interaction verification and records those results with the release evidence. No screen-reader, WCAG conformance, or usability-study claim follows from this design pass.


Rendered checkpoint: the implemented 1440×960 opening in `work/alina-desktop-initial.jpg` was visually inspected. The result, measurement strip and four-case proof form distinct levels, and the values remain readable together. This inspection identified a real lower-edge defect in the sticky configuration action shelf: underlying fields showed through its side and bottom padding. The CSS was corrected to cover the full rail width and remove the scrollport bottom gap; the subsequent desktop trace and evaluation captures show the shelf covering the bottom and side edges without the leaked fields.

Additional rendered review inspected `work/alina-mobile-initial.jpg`, `work/alina-trace.jpg`, `work/alina-evaluation.jpg`, and `work/alina-mobile-evaluation.jpg` at the captured 390px and 1440px widths. The trace heading clears the sticky navigation; readings and controls remain legible. The narrow opening retains the full measurement and export action through ordinary page scrolling. Desktop and narrow evaluation views visibly preserve the rejected verdict and all three failure reasons. This is screenshot inspection; functional keyboard, import, navigation, and production checks are recorded separately by the root task. No participant study or screen-reader test was performed in this design pass.


Final review also inspected `work/alina-320.jpg`, `work/alina-validation.jpg`, and `work/alina-mobile-import.jpg`. The 320px opening preserves the measurement, threshold, reference values and export action without clipped text in the captured state. The scrolled validation dialog shows legible check rows, an explicit distinction between passed and unperformed checks, a visible artifact-disclosure focus ring and reachable footer actions. The narrow import dialog shows the downstream-mapping focus ring entirely inside the overlay, legible model caveats, wrapping SHA content, and the disabled registration action before a downstream choice is made.

One final measured defect was corrected: the small pending validation status used the inherited `#9a7c37` on white, only 3.95:1. The scoped `.check-list > li.pending` color is now `#856222`, which calculates to 5.57:1 on white. Amber meaning and the text “Unperformed” are retained; no status changed.

A source review of the 900px boundary confirmed the explicit layout switch: 901–1280px uses the 268px desktop configuration rail and a three-column measurement strip with the export action in a full-width row; at 900px the rail becomes an expandable inline section, its scroll limit is removed, and the masthead/anchor clearance changes together from 72px to 66px. The root task separately reports actual browser checks at 320, 390, 768, 900, 920, 1280 and 1440px with no document overflow, target top 138px below a 115px navigation bottom, corrected rail bottom at 960px, Escape focus return, and a successful real model-input inspection. Those are root browser observations, not additional interactions performed by this visual reviewer.
