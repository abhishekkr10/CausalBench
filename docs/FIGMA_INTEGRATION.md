# Figma integration — 2 November 2026

Source: the owner-provided `CausalBench Experiment Laboratory.zip`.

The export is a React visual prototype with fixed event/run data and placeholder
study, recording and evidence interactions. Its paper/charcoal palette, orange
primary actions, teal comparison color, technical typography and trace/inspector
composition were ported to the existing frontend. The existing Python APIs,
storage, controller evaluation, archives and headless commands remain authoritative.
No exported scripts, deployment plugins, AGENTS.md or CLAUDE.md were executed or
adopted as project instructions.

All existing control IDs were retained. Controller profiles, composed faults,
batches, boundary scans, minimization, regression checks, mock/HTTP recording,
feedback models, saved runs, comparisons, verification, imports and downloads are
available through the workspace navigation. The mobile navigation scrolls rather
than hiding destinations. Analysis completion opens its results view.

Added interactions:
- Selected-event timestamps, age, distance, validity and fixture truth use the
  recorded trace. Missing or unknown values are not invented.
- Zoom from 100% to 400%, reset and a native expanded trace dialog. These change
  the presentation only. The original interactive chart moves into the dialog,
  retaining event selection and keyboard behavior. Escape restores the chart
  and focus; no duplicate chart IDs are created.
- Subtle workspace blur entrances, hover/press feedback and dialog backdrop blur.
  Both system and saved reduced-motion preferences disable movement and blur.
- Manrope and IBM Plex Mono are served locally, with their bundled licenses.
  The dashboard requires no external font/CDN calls.

The supplied concept remains under ignored `data/figma-export` for reference.
Screenshots: `figma-integrated-light.png`, `figma-integrated-dark.png`,
`figma-integrated-mobile.png`.

The existing working frontend was retained rather than replacing it with the
prototype's simulated handlers. The result preserves the design direction while
supporting real variable-length traces, unknown truth and actual research results.

## Refined export integration

Reviewed `CausalBench Experiment Laboratory (1).zip`. Added explicit empty,
loading, failed and completed experiment presentation driven by real requests;
no fixed progress counters or timer-driven success states were adopted. Added a
native mobile navigation dialog exposing all seven workspaces, Escape handling,
focus restoration, larger touch targets and reduced-motion behavior. Existing
missing-data gaps, real chart zoom, evidence and research workflows remain intact.
The revised prototype still contains fixed data and illustrative actions; these
were retained only as design reference under ignored data/figma-refined.

Validation: 11 Edge browser workflows passed in 27.8 seconds, with JavaScript
syntax and whitespace checks passing. No Python backend changes were needed.

## Cursor-driven readings

Moving a mouse or pen across the recorded chart selects the nearest event and
synchronizes the right-hand readings, controller decisions, replay slider,
selected marker and ledger. The last event remains selected when the cursor
leaves. Hover selection pauses replay and works in reduced-motion mode; touch
retains tap selection and scrolling. No trace values or evidence are changed.
