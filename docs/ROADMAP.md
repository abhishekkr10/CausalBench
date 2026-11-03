# Roadmap and next steps

Updated: 3 November 2026.

## Completed software milestones

1. Interactive trace chart: separate distance/age/command tracks, missing-data
   gaps, disagreement marks, cursor-driven inspector, keyboard/touch replay,
   zoom/reset and expanded inspection.
2. Guided first experiment: real API outcomes, explanations, retries,
   restart/exit, no-disagreement handling and verified evidence export.
3. Saved-run comparisons: configuration/metrics, input identity disclosure,
   Unknown truth handling and JSON export.
4. Project quality: named examples, 13 browser workflow checks, MIT license,
   locally bundled fonts, responsive Figma-derived design, updated documentation
   and owner-supplied dashboard screenshots. A GitHub Actions matrix is configured
   for Windows, Linux and macOS; hosted results must be checked after publication.

Latest completed local verification: 93 Python tests and 13 browser workflows.
See [validation](VALIDATION.md) for the exact scope and historical results.

## Immediate follow-up

- Inspect the first hosted CI results after pushing main, resolve any failures,
  and document actual OS/compiler/browser results.
- Continue usability checks with real experiment traces and larger studies.
- Keep screenshots, status and workflow documentation aligned with releases.

## Hardware validation — deferred at the owner's request

When sensors are available: review/compile the ESP32 sketch, validate wiring and
voltage levels, and record real readings while keeping actuation simulated.
Measure clock uncertainty, polling delays and gaps; publish sanitized evidence
with device metadata. PhysicalActuator remains disabled/unimplemented.
Physical output requires a separate implementation and hardware safeguards.

## Optional distribution and research extensions

Consider a packaged desktop launcher, signed evidence, MCAP/ROS interoperability,
stronger environment reproduction and richer validated plant models. Public
multiuser hosting requires authentication, data isolation, capture network
boundaries and a native-executable policy. The existing server is loopback-only.

Disagreement alone does not establish failure. Model results do not establish
physical reliability, and evidence hashes establish consistency, not authenticity.
