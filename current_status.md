# Current status — 24 October 2026

## Implemented

CausalBench 2.0 is a local Python/SQLite experiment laboratory with a simulated
actuator and a dependency-free browser dashboard.

- Deterministic generated and imported traces; baseline/guarded comparisons;
  replay, first disagreement, event selection, decision explanations and ledger.
- Composed seeded faults, controller settings and saved configuration profiles.
- Paired-seed batch studies, explicit-grid robustness scans, saved regressions
  and bounded failure minimization with a 1-minimality certificate when complete.
- Declarative plugins, a compiled host C++ adapter, auxiliary sensor streams
  and a corroboration controller with an IMU veto.
- Bounded live mock/HTTP recording, diagnostics and capture snapshots.
- A separate closed-loop gate model with controller-dependent observations.
- Evidence hashing, verification, experiment/analysis archives, source snapshots,
  imports and offline reproduction.
- White/blue and dark themes, larger typography, responsive layout, blur entrance
  and hover animations, keyboard focus styles, and saved reduced-motion/theme
  preferences. The system theme is used until an explicit theme is chosen.
- Windows double-click launcher that starts the loopback server in the background,
  checks readiness, reuses an existing server, and opens the dashboard.

## Pending

The latest requested feature work was interrupted before implementation:
**the sensor/freshness trace chart and guided first-experiment walkthrough are
not in the current UI.** The numbered event strip is implemented. Older validation
notes describe a chart from a superseded UI; they are historical, not evidence
that the current dashboard contains it.

See [ROADMAP.md](docs/ROADMAP.md) for implementation order and acceptance criteria.

## Verification and boundaries

On 24 October 2026, all 91 Python tests passed in 22.286 seconds and both browser
JavaScript files passed syntax checks. See [VALIDATION.md](docs/VALIDATION.md)
for automated results and dated browser
checks. Windows is the exercised platform; other operating systems need validation.
Native plugins are trusted host executables, not flashed firmware. Their repeated
runs check consistency but do not prove arbitrary code deterministic.

No real sensor, microcontroller or servo has been exercised. ESP32 compilation,
flashing, wiring, clock uncertainty and physical timing remain unverified.
PhysicalActuator is disabled/unimplemented. Closed-loop output describes the
stated simplified model, not real-world reliability.

Open-loop disagreement alone is not failure. Captures without fixture truth have
unknown outcome error counts. Hashes establish internal consistency, not signed
authenticity. Imported archive code is inspected, not automatically executed.

ROS/MCAP interoperability, process scheduling emulation, full microcontroller
emulation, cryptographic signing, hosted multiuser deployment, automated browser
regressions and hosted CI are not implemented.
