# Current status — 3 November 2026

CausalBench 2.0 is a local Python/SQLite experiment laboratory with simulated
actuation. No physical sensor or actuator is required.

## Available

- Deterministic generated/imported traces; controller comparisons, replay,
  synchronized trace chart, event inspector and decision ledger.
- Composed seeded faults, controller tuning and named profiles.
- Paired-seed studies, explicit-grid robustness scans, bounded minimization,
  regression assertions and headless checks.
- Declarative/native C++ controllers, auxiliary streams and corroboration rules.
- Bounded synthetic/HTTP recording, diagnostics and experiment snapshots.
- A separate closed-loop gate model and inspectable trajectories.
- Saved experiment comparisons, evidence verification, archives, source snapshots,
  imports and offline reproduction.
- Guided first-experiment walkthrough with actual API results and retry states.
- Supplied Figma design integrated with real data: paper/charcoal themes, orange
  actions, local Manrope/IBM Plex Mono fonts, selected-event inspection, 100–400%
  chart zoom and an expanded dialog. Responsive navigation retains every view.
- Subtle hover, blur and dialog effects, with system/saved reduced-motion support.
- MIT licensing, named demo requests and a three-platform CI configuration.

## Verified locally

93 Python tests and 13 Edge browser workflows passed. Tests exercise research,
recording, feedback models, imports/exports, comparisons, chart interaction,
mobile navigation and evidence preservation. See docs/VALIDATION.md.
The server runs locally at http://127.0.0.1:8767/.

## Deferred or unverified

Physical sensors, ESP32 compilation/flashing and actuator operation are deferred
at the owner's request. PhysicalActuator remains disabled/unimplemented.
Hosted CI, Linux and macOS execution remain unverified. The current server is a
trusted local application, not a public multiuser service.

Disagreement alone is not failure. Unknown fixture truth stays Unknown. Feedback
results depend on the model. Hashes establish consistency, not authenticity.
Imported archive source is inspected rather than automatically executed.
ROS/MCAP interoperability, MCU emulation and signed evidence remain future work.

Refined Figma export: real request-driven empty/loading/error/completed states,
complete mobile navigation drawer and larger touch targets are integrated.

Visible motion effects include card/text hover emphasis, glowing graph lines,
cursor-following spotlight, enlarged nearest-event points and scroll blur
entrances. Effects preserve recorded values and respect reduced motion.

Cursor movement now selects the nearest recorded event and updates the inspector,
controller explanations, replay position and ledger without clicking. This also
works with reduced motion.
