# Roadmap and next steps

Status: 24 October 2026. These are planned milestones, not shipped capabilities.
The first two were requested and remain the immediate implementation priorities.

## 1. Interactive trace chart

Add a chart above replay showing distance (mm), observation age (ms) and both
controller commands against the same recorded event time. Keep distinct vertical
scales and units. Highlight disagreements and synchronize chart selection with
the existing event strip, scrubber, decision explanations and ledger.

Implementation: derive all points from the selected bundle, render with native SVG
or another deliberately selected chart implementation, and hook updates into
`render`/`showFrame` in `web/app.js`. Do not change recorded data for visualization.

Acceptance criteria:
- The stale example identifies event 7 at 1200 ms, a 70 mm observation aged 600 ms,
  baseline PULSE and guarded HOLD.
- Missing or invalid observations produce gaps rather than invented zero readings.
- Single-event, long, no-disagreement and unknown-fixture traces remain usable.
- Mouse/touch selection and keyboard navigation select the same recorded event.
- Both themes, narrow screens and reduced motion work; no whole-page overflow.
- No implication that a drawn line proves continuous physical behavior.

## 2. Guided first experiment

Add an optional, restartable walkthrough: choose a fault, run a labelled example,
find its first disagreement, inspect the explanation, and preserve the evidence.
Use actual API results and keep advanced configuration available.

Acceptance criteria:
- A new user can explain the delayed-reading example without reading source code.
- Steps advance from successful results, with visible loading/error/retry states.
- Users can exit/restart; an unrelated run cannot leave stale tutorial conclusions.
- A no-disagreement example is handled honestly.
- Keyboard focus, screen-reader announcements and reduced motion are checked.

## 3. Compare saved runs

Allow selection of two saved experiments. Show configuration differences, event
counts and outcome metrics, while clearly identifying whether inputs differ.
Identical-input replay and cross-run comparisons must remain distinguishable.

Acceptance: comparisons can be exported, missing truth stays Unknown, and the
interface does not attribute an outcome change solely to a controller when the
input trace also changed.

## 4. Curated demonstration and project quality

- Build named examples for stale, duplicate, disconnection and corroboration.
- Add a small browser regression suite for run/replay/import/theme/tutorial flows.
- Configure hosted CI for Python tests and C++ build with explicit tool versions.
- Add cross-platform checks after building the native example on each platform.
- Keep documentation screenshots and feature descriptions aligned with releases.
- Select a repository license deliberately before describing the project as
  licensed open-source software; no license is currently declared.

Acceptance: a clean checkout can reproduce documented demos and tests; CI status
is based on an actual completed workflow, not assumed from local success.

## 5. Real sensor validation

Review and compile the ESP32 sketch, validate wiring and safe voltage levels,
then record real readings with the actuator still simulated. Keep Wi-Fi secrets
local. Measure timestamp uncertainty, sampling behavior, HTTP delay and gaps.

Acceptance: publish a documented, sanitized real-capture experiment with device
and clock metadata; separate measured facts from model assumptions. Only then
consider explicitly enabled physical output with appropriate hardware safeguards.

## 6. Distribution and research extensions

Consider a packaged desktop launcher, signed evidence, MCAP/ROS import/export,
stronger environment reproduction and validated richer plant models. Evaluate
hosting only after designing authentication, per-user data isolation, capture
network boundaries and native-executable policy. The current server is a trusted
loopback tool and is not ready for direct public multiuser exposure.

## Suggested next development sequence

1. Create a feature branch for the trace chart and walkthrough.
2. Inspect the current bundle schema and preserve existing replay behavior.
3. Build the chart and verify edge cases before layering on the walkthrough.
4. Run Python tests and targeted browser checks in light/dark and narrow layouts.
5. Update current status, validation and screenshots; publish the reviewed change.
