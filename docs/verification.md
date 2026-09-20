# Executed verification

Date: September 20, 2026. Local environment: macOS, Python 3.14.3, Node 22.20,
clang, Chromium controlled through Playwright. These are development checks;
no field validation, operator study or accessibility-conformance claim follows.

## Engine, evidence and service

`npm test` passed **60 tests**: 7 real native-engine behavioral tests, 40
independent validation/negative tests and 13 HTTP/service tests. The service tests
were rerun after the final trace payload and compression changes; all 13 passed.
`npm run build` passed on the final frontend.

The genuine two-fault experiment reduces to one retained condition. Independent
recorded checks pass, and a fresh replay of all five recorded configurations
matches on this Mac. The exact welcome fixture has a separate executed replay:

- [Recorded evidence report](evidence/welcome-validation.json)
- [Actual replay comparison](evidence/welcome-replay.json)

Two independent development lanes also extracted a downloaded archive outside
the project, rebuilt the native library from included source, ran every case and
passed the independent comparison. The archive requires no GitHub access or
third-party Python packages. Native source/model hashes, trace integrals and
condition identities are checked. Corrupted metrics and source bytes are rejected.

## Browser tasks actually exercised

| Task/state | Observed result |
|---|---|
| Empty state → default run | Native simulation completes and all result panels attach to the returned job. A duration-step mismatch initially blocked submit; fixed and rechecked. |
| Recorded two-fault case | Correct recorded label, 5-call count, original and reduced traces, 2→1 condition list and actual removal outcomes. |
| Fault focus | Chart changes from 0–78 h to 0–7 h, range/visible-scale labels update, slider bounds match; full-horizon total stays 1,621.45 m³. |
| Export | Browser downloads a real source-complete ZIP for the selected job. |
| Replay | A new native job completes; dialog changes replay status from Unperformed to Matched. |
| Draft edits | Existing result keeps its original run identity with a visible settings-changed message. |
| High-threshold Theta | Fresh run returns No violation found; no failure witness is claimed. |
| Gamma, low threshold | Fresh 156-hour run reports the nominal plan already exceeds the check; no fault-only discovery is claimed. |
| Invalid duration | Associated `aria-invalid`/alert message identifies a fault ending after the model horizon. |
| 1440×1000 desktop | Opening, graph, removal evidence, comparison and export inspected. |
| 390×844 and 320×800 | No page overflow in closed/open setup and result states; chart/table scrolling is contained and labeled. |
| Keyboard | Slider arrows change time; node select works; comparison region scrolls horizontally with ArrowRight; dialog opens on its close control and Escape restores focus to the trigger. |
| Text spacing at 320 px | Specified line/letter/word/paragraph spacing applied together; document width remains 320 px and setup fields remain available. |
| Console | Final production navigation has zero console errors or warnings. |

Muted text pairs initially measured below 4.5:1 on their rendered pale surfaces.
Text and axis colors were darkened while preserving the palette. This scoped
inspection does not establish all state/contrast combinations. Actual screen-reader
use and 200% browser text enlargement have not been exercised.

Screenshots: [desktop](images/workbench-desktop.png),
[initial viewport](images/workbench-preview.png), [320 px](images/workbench-mobile.png).
Full-page captures were repeated from scroll position zero to avoid a misleading
sticky-sidebar capture. Ordinary viewport inspection confirmed the live layout.

## Delivery checks still separate

The private GitHub repository and milestone pushes are verified. Both the first
push and an explicit workflow dispatch stopped before any jobs with
`startup_failure`. The signed-in GitHub run page exposed the cause: an account
billing banner and the annotation, “The job was not started because recent
account payments have failed or your spending limit needs to be increased.”
The workflow parses and is registered active. No Ubuntu pass is claimed and no
payment/account settings were changed. Billing resolution is a user account step.

The local Docker daemon was unavailable, so the provided Dockerfile has not yet
been built locally. The hosting account has not been selected in this session.
Public deployment, final video recording, judge invitations and Devpost submission
have not been performed.
