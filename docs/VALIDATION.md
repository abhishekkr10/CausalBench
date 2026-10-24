# CausalBench 2.0 validation — 13 October 2026

> Historical implementation notes are retained below. For the current UI and feature
> inventory, see [current status](../current_status.md) and [roadmap](ROADMAP.md).
> Earlier sage/cream layouts and chart screenshots describe superseded UI versions.

Latest complete command: `python -m unittest discover -s tests -v` (captured with PowerShell Tee-Object to `data/validation-v2-tests.txt`). Result: **91 tests passed, 20.575 seconds**, Windows/Python 3.13.7. `python -m compileall -q causalbench` also completed successfully.

Actual C++ build: `g++ -std=c++17 -O2 -static controllers/native_guarded.cpp -o controllers/native_guarded.exe`; compiler g++ 15.2.0. The 2,958,985-byte Windows artifact and source/build digests are recorded in `controllers/build_manifest.json`. This is host C++ execution, not ESP32 firmware compilation/flashing.

The original 44 tests remain. Added checks cover composed-fault determinism and unchanged inputs, zero-delay behavior, actual prior-sample delay values, fault/config validation, independent auxiliary observations, fusion missing-corroboration/IMU veto, fixture-label separation for every policy, native/Python command parity across seven scenarios, native invalid/nondeterministic output, a separately installed native plugin, paired-seed studies, minimization and timestamp preservation, pass/fail/unknown regressions, command-sequence regressions, grid boundaries, feedback-dependent trajectories, source freezing, archive tampering/traversal, all analysis reproductions, count/byte capture limits, malformed nonfinite JSON, actual HTTP stand-in recording/sequence gaps, API jobs/errors, profiles/restarts, artifact tampering, package routes/imports and large sealed-evidence verification. Foreign Host and cross-Origin browser requests are rejected.

Offline reproduction tests extract trusted generated archives into new temporary directories and invoke `python reproduce.py` as a separate process. Experiment replay includes four policies and the compiled adapter. Batch, frontier, minimization, regression and closed-loop analysis runners independently return REPRODUCED.

## Actual headless examples

Executed successfully:

```powershell
python -m causalbench.lab_cli experiment --input examples/sensor-corroboration.json --output data/corroboration.bundle.json
python -m causalbench.lab_cli batch --input examples/batch.json --output data/example-batch.json
python -m causalbench.lab_cli frontier --input examples/boundary.json --output data/example-boundary.json
python -m causalbench.lab_cli plant --input examples/plant.json --output data/example-plant.json
python -m causalbench.lab_cli regressions --input examples/regressions.json --output data/example-regressions.json
```

The regression command has tested exit codes: all-pass 0, failure 1; an empty suite errors. A hosted CI service was not exercised.

## Actual browser journey

At http://127.0.0.1:8767: ran the four-policy stale experiment; baseline six pulses/one incorrect fixture pulse, guarded/fusion/native five pulses/zero incorrect fixture pulses. First divergence stayed at 1200 ms with input age 600 ms. Inspected independent current proximity (false) alongside the stale primary distance (70 mm).

Saved a named controller configuration; minimized 12 events to one at 1200 ms with seven evaluations and a 1-minimality certificate; saved and ran a stale regression with PASS. Ran two paired seeds across four delay variations with all four controllers. Isolated a normal-operation delay grid 0/100/300/600: first observed reference failure at setting 100 ms, with no continuous threshold claim.

Started live synthetic capture at a requested 50 ms gap with capacity 10, observed evictions, snapshotted into a stored experiment, then stopped. Snapshot outcome metrics were Unknown. Ran a three-controller feedback model, inspected separate trajectories/metrics and scrubbed its model timeline. Downloaded experiment and analysis source ZIPs.

On the final restarted service, four-policy comparison, source export, batch study and experiment/analysis ZIP imports were repeated. Experiment import verified 22 archive files and replayed with installed controllers; analysis import verified 21 files and retained archived results without executing source or claiming a rerun. Browser console returned no warnings/errors. Final desktop (1440×1050) and mobile (390×844) checks found no page-level horizontal overflow. Saved profile loading restored an edited enter threshold from 80 to 100. Screenshots: docs/dashboard-v2.jpg and docs/research-tools-v2.jpg.

Downloaded final ZIPs `causalbench-0d9cce06.zip` and `causalbench-analysis-0617463a.zip` were additionally inspected using the package module, extracted to checked temporary paths under CausalBench/data, and independently run. Both inspection results were valid, process exit code 0, output REPRODUCED.

## Boundaries

No actual sensor board, servo, firmware build/flash, electrical measurement, physical latency, endurance study, cross-platform native run, or hosted CI was exercised. The HTTP device test uses an actual loopback HTTP stand-in. The plant is a discrete model; native coupling is open-loop only. Reduced-motion support remains in CSS; preference emulation and a full accessibility/browser matrix were not performed. Current screenshots are saved under docs. The earlier records below are historical phases, not the current feature list.

---

# Validation record — 13 October 2026

Environment: Windows, Python 3.13.7, local SQLite, Codex in-app browser. Hardware absent; no firmware compile, upload, sensor measurement, or physical actuator test performed.

## Automated checks

Executed from C:\CausalBench:

```powershell
python -m unittest discover -s tests -v
python -m causalbench.cli run --scenario stale --output data/demo.bundle.json
python -m causalbench.cli verify data/demo.bundle.json
```

Final automated result: 44 tests, all passed, 4.862 seconds. Raw output: `data/validation-tests.txt`. CLI result: divergence `[1200]`, evidence saved, verification `VALID`.

19 engine tests cover deterministic replay, unchanged inputs, fixture truth separation, exact freshness boundary, validation, fault scenarios, bundle verification, modified decisions, modified traces, and truncation. 16 extended tests cover ordering, invalid observations, seeds, hysteresis boundaries, missing duration, JSON round trip, rehashed wrong current-engine decisions, units, mocked capture metadata/errors/recovery/partial readings/non-object JSON, configurable thresholds, invalid configuration, Boolean schema, and disabled actuator output. Nine server tests exercise actual local HTTP requests, SQLite reconstruction across Store instances, corrupted storage reads, API errors, cross-origin rejection, static allowlist, health, and verification. Store re-instantiation verifies persistence; an OS reboot was not tested.

## Scenario results

All fixtures have 12 events at 200 ms intervals. Seed 42 for noise.

| Scenario | Divergence times (ms) | Baseline incorrect fixture pulses | Guarded incorrect fixture pulses |
|---|---|---:|---:|
| normal | none | 0 | 0 |
| stale | 1200 | 1 | 0 |
| duplicate | 1200 | 1 | 0 |
| disconnect | 1000, 1200, 1400 | 2 | 0 |
| out-of-order | 1200 | 1 | 0 |
| noise | none | 0 | 0 |
| invalid | none | 0 | 0 |

The noise fixture is reproducible, but the default seed does not force a visible improvement. Independent tests verify hysteresis. Both controllers safely reject malformed values, so invalid does not force divergence. Disconnection includes one missing event while fixture presence remains true; the correctness metric counts only absent-object pulses, not all differing commands.

## Browser checks

Executed the actual dashboard at http://127.0.0.1:8767. Ran all seven scenarios and inspected rendered metrics. Verified stale First divergence at 1200 ms, baseline PULSE, guarded HOLD, age 600 ms, state transitions, and explanation. Exercised Step, Play, automatic completion, verification VALID, modified-copy INVALID, and download controls. Evidence and Markdown report downloaded into the user's Downloads directory. Imported that exported evidence through the native file chooser; a new experiment was persisted. Layout was inspected at a desktop viewport and the browser's narrow viewport and adjusted to wrap controls and fit the gate indicator. Captured screenshot under `docs/dashboard.jpg`.

Browser checks were interactive tool-driven checks, not an added automated browser regression suite. Dedicated screen-reader, keyboard-only audit, full browser matrix, and reduced-motion preference emulation were not performed. CSS includes focus-visible styles, responsive rules, and reduced-motion transitions. No physical latency, reliability, sensor accuracy, servo dynamics, or closed-loop outcome is claimed.

## Dashboard redesign — 13 October 2026

The dashboard now takes visual direction from the user's portfolio: sage background, cream surfaces, dark technical panels, large typography, and moving signal paths. Added seven selectable scenario cards, distance/sample-age SVG plot with separate axes, synchronized plot cursor and event markers, decision inspector, rejection distribution, filtered clickable ledger, and dated history entries.

Animations include entry/reveal transitions, moving packets and orbit lines, sensor rings, command-driven gate arms, metric count-up, and rejection bar transitions. The gate animation is presentation only, not a settling-time simulation. `prefers-reduced-motion` disables CSS animations/transitions and the JavaScript count-up/reveal behavior. Large traces use a sampled event-button strip plus selected divergence markers; the scrubber and plot still address every event.

Browser verification: all seven scenarios rendered 12 event markers and matching rejection counts; stale plot selection navigated to event 7 at 1200 ms; First divergence, marker selection, ledger filtering, play/pause, valid/tampered evidence, and report download succeeded. Inspected responsive layouts at 1440×1050 and 390×844. Browser console returned no warnings or errors. Reduced-motion support was inspected in source; preference emulation was not performed. This change did not alter controller or backend logic.

Additional redesign checks: imported a trace with no fixture truth; outcome metrics remained Unknown. Keyboard Enter on a filtered ledger row selected the 1200 ms divergence. Inspected computed packet animation and gate transition styles. Desktop page had no horizontal overflow. Preview images: `docs/dashboard-redesign.jpg` and `docs/dashboard-signals.jpg`.

## Repository readiness — 24 October 2026

Reran `python -m unittest discover -s tests -v`: **91 tests passed in 22.286 seconds**
on the local Windows environment. `node --check web/app.js` and
`node --check web/lab.js` both passed. Raw test output remains local at
`data/github-validation.txt` and is intentionally excluded from Git.

Verified the supplied native executable and C++ source against the SHA-256 values
in `controllers/build_manifest.json`. Repository line-ending rules preserve LF
source bytes on checkout, with CRLF for the Windows command launcher. Reviewed
staged file paths and checked common credential patterns; no matches were found.
Only placeholder Wi-Fi credentials are included. This is a publication-readiness
check, not a full security audit.

Recent interactive browser checks (20–21 October) verified light/dark switching,
theme persistence across reload, larger typography and mobile layout, reduced-motion
preference persistence, experiment creation, saved-run loading and first divergence.
The background launcher's readiness and same-server reuse were also verified.
Those are historical interactive checks, not a hosted CI or browser test suite.

The current UI has a numbered event strip. The trace chart and guided walkthrough
remain pending; the older redesign section above describes a superseded version.
