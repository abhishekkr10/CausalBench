# CausalBench 2.0: experiment workflows

All ten research additions run locally. Use the sidebar to reach Experiment builder, Research studies, Live recording, Feedback model and Evidence & archives. The overview contains scenario controls and replay. These implementations were written for this project; no comparator repository was cloned or copied. The use of established techniques such as seeded trials and delta debugging is deliberate; this is not a claim of scientific novelty.

## 1. Configure and combine faults

Choose a preset at the top. Open Composed fault settings in Experiment builder. Select seed, event count, active time window, noise amplitude, and probabilities for delay/drop/duplicate/reorder/invalid input. Multiple fault channels can fire at one event. Choose Normal operation when you want to isolate additional faults from an existing preset.

Every channel draws a random value on every tick, even outside its active window. That preserves common random numbers across parameter sweeps: changing a rate does not shift all subsequent RNG draws. Delay chooses the most recent actual sampled value at or before the requested past time; it does not fabricate a near reading by changing its timestamp. It adds a distinct delivery identity to make freshness/order faults independently inspectable. Duplicate injection preserves an earlier identity. Capture order is not sorted away. `applied_faults` identifies composed transformations; preset faults are described by the trace scenario.

The simulation samples at 200 ms. Requested delays therefore select discrete prior samples. A 100 ms requested delay can select a sample 200 ms old. Boundary values are generator settings, not precisely measured physical delays. Generated events are capped at 1000; probabilities are 0..1; noise amplitude <=2000 mm and requested delay <=60000 ms.

## 2. Tune controllers and save profiles

Select reference and candidate controller IDs. The candidate editor sets enter threshold, exit threshold, and maximum age. Reference has a separate enter threshold. Additional fusion/native comparisons use the candidate configuration. A named configuration saves immutable values in SQLite; loading a profile applies them to the next run. Existing recordings and comparisons do not change.

Configuration schema version 1: enter/exit integers 0..10000 mm, exit >= enter, max age 0..86400000 ms. Baseline effectively uses enter for both thresholds. Guarded uses exit while active. Age exactly at the maximum is accepted; comparisons with thresholds are strict `<`.

## 3. Batch studies

Supply comma-separated seeds and choose current settings, a delay sweep, or a candidate-freshness sweep. Each variation uses the same supplied seeds. The result table reports run counts, mean command divergences, mean incorrect fixture pulses, runs with an incorrect pulse, missed-present events, rejection counts and rejection fractions.

Incorrect fixture pulse = PULSE while supplied simulation presence is false. Missed-present event = HOLD while supplied presence is true. Neither is a physical accident or measured latency. Rejection fraction uses all replay events as denominator; missing observations are tracked separately. Repeated seeds remain repeated cases, not independent statistical samples. No confidence interval or hardware reliability estimate is claimed.

Limits: 1..30 seeds, 1..12 variations, at most 120 paired trials. The CLI accepts explicit variation maps for more configuration/fault combinations. `examples/batch.json` demonstrates noise sweeps.

## 4. Regression assertions and CI

Save the current trace with either an incorrect-fixture-pulse limit or an exact candidate command sequence. Cases retain trace digest, configuration, controller IDs and saved policy digests. Run an individual case or all saved cases against installed controllers. Unknown outcome truth is an UNKNOWN/failing assertion, never a successful safety check.

```powershell
python -m causalbench.lab_cli regressions --input examples/regressions.json --output data/check.json
python -m causalbench.lab_cli regressions --database data/experiments.sqlite --output data/saved-checks.json
```

Exit 0 means all checked assertions passed; exit 1 means a failing/unknown assertion. An empty suite is an error. These are CI entry points; hosted CI has not been run and nothing has been published. Assertions describe recorded-input behavior, not a physical safety certification.

## 5. Failure minimization

Select command divergence or an incorrect fixture pulse in the reference/candidate. The minimizer deletes chunks, then individual events, without renumbering IDs or shifting absolute timestamps. Every candidate rerun starts from the normal declared initial state. It preserves the selected predicate, not the original entire state history.

A successful complete search certifies 1-minimality: no one remaining event can be removed while keeping the predicate. It does not promise the globally shortest sequence. Evaluation budget is bounded to 150 from the dashboard, max 300 via the API; input <=300 events. A derived experiment receives its own evidence/source snapshot. The analysis retains the original digest, original trace and reproduction request. Inspect reduced trace to load it into the main replay view.

The default stale example reduces 12 events to one at 1200 ms. That is a useful standalone counterexample, while other state-dependent failures can retain more history.

## 6. Controller plugins

Installed controllers are discovered from local `controllers/*.controller.json`. Dashboard imports never install or execute archived plugins. Add only trusted local controller programs. Built-ins: baseline-v1, guarded-v1 and fusion-v1. The supplied `corroborated-v1` is a declarative plugin.

A rule descriptor has schema_version 1, a unique ID, kind `rule`, description, configuration and optional Boolean `require_proximity`. It reuses the validated guarded contract with the chosen thresholds, optionally requiring sensor corroboration. See the supplied descriptor.

Native descriptors use kind `native`, local executable/source filenames and optional default configuration. Files must stay inside the controllers directory. This supports separately installed C++ controllers, not just the bundled example:

```json
{"schema_version":1,"id":"my-native-v1","kind":"native","description":"My controller","executable":"my_controller.exe","source":"my_controller.cpp","configuration":{"version":1,"enter_mm":100,"exit_mm":120,"max_age_ms":300}}
```

Protocol: first stdin line is `enter_mm exit_mm max_age_ms`. Following lines contain `time_ms id_hash sample_ms distance_mm observation_present`. Hash is a stable 60-bit representation of the ID. Missing is present=0; invalid distance is -1. Exactly one stdout line per input: `PULSE reason_token` or `HOLD reason_token`. Tokens are <=80 letters/digits/underscore/hyphen. Standard reasons accepted/stale/duplicate/order/invalid/missing have diagnostic mappings; custom tokens become native explanations. Other output is rejected. Stderr is not part of the decision record.

The native adapter passes only the primary distance stream in this v1 protocol. Auxiliary fusion uses Python/declarative policies. Native input <=1000 events, timeout 5 seconds per invocation, output <=100 KB. The adapter invokes the executable twice and rejects differing results. This is a consistency check, not a sandbox or proof that arbitrary native programs never use clocks, files or randomness. The supplied C++ example does not use those dependencies. Native controllers are open-loop only in this release.

Actual build on this machine: g++ 15.2.0, `-std=c++17 -O2 -static`, Windows artifact. Build manifest includes compiler, command and digests. Linux expects a native_guarded executable without `.exe`; that platform remains unverified. Custom native runtime dependencies must be supplied by their author; they are not automatically downloaded.

## 7. Live capture and failure snapshots

Choose synthetic mock or HTTP device, polling gap and retained capacity. Start, observe status, then Snapshot buffer into experiment. Recording can continue after a snapshot. Stop terminates polling. The mock source is labelled synthetic and deliberately supplies no outcome labels, so correctness metrics remain Unknown.

The rolling buffer is bounded by 10..1000 events and approximately 1.5 MB of retained event JSON. Old events are evicted by count or bytes; status exposes counts/bytes, evictions, connection errors and observed sequence gaps. Snapshots freeze the recent lead-up to a failure and persist it in SQLite. Unsaved live data is process memory and is lost on shutdown.

HTTP accepts the existing ESP32 endpoint: valid, integer distance_mm, sequence, boot_id and optional uptime_ms. Optional `streams` can provide objects with value/unit/valid. Request timeout is 2 seconds, response cap 16 KB. Failures record missing input and diagnostics; subsequent polls recover. Non-standard NaN/Infinity JSON is retained as invalid raw text, not allowed to poison canonical exports. Interval is a pause after a request, not a promise of fixed-rate sampling.

Host receive time and request-start sampling estimate are separate from unsynchronized device uptime. Request duration is uncertainty only under the endpoint's sample-during-request assumption. Source sequence gaps are diagnostics; without a source-to-host clock mapping, replay cannot establish true device freshness for cached/buffered endpoints. Boot identity separates sequence sessions. Real hardware has not been exercised.

## 8. Multiple streams and corroboration

Generated streams: primary distance in mm; temperature in milliC; IMU in milli_g; proximity Boolean. The auxiliary transducers sample the current clean simulated scene separately from a corrupted primary reading. Proximity is an ideal binary sensor in this fixture model; it is not an independent real measurement. Disconnect an auxiliary stream to test missing corroboration. HTTP capture can ingest up to 16 named auxiliary streams with supported units and explicit invalid/missing observations.

Replay-time stream inspection shows values, units, ages and availability. Fusion-v1 accepts a primary PULSE only with fresh valid positive proximity corroboration, and vetoes a fresh IMU shock above 1500 milli_g. A veto resets active state. It is deliberately conservative: it can avoid false pulses and increase missed-present events.

`examples/sensor-corroboration.json` supplies a fresh noisy primary input with reference guarded-v1 versus candidate fusion-v1, making the additional sensor check observable. Fixture labels are used only after commands are chosen; changing those labels alone does not change decisions.

## 9. Closed-loop gate model

Choose 5..200 steps, 10..1000 ms step size, object speed and gate angular rate. Up to three built-in/declarative controllers drive separate plants with paired exogenous seeds. Their future inputs can differ because earlier commands differ. Do not interpret the resulting trajectories as fixed-input replay.

PULSE targets 90 degrees and HOLD 0. Gate movement is bounded by the specified angular rate per step. An approaching object moves at constant speed, waits at 35 mm when the gate angle is below 60 degrees, and crosses when passable. At most one object is spawned every 30 ticks when the scene is empty. Faults act on each plant's own observations.

The model records input at the beginning of a step, then applies the command, gate movement and object movement. Plant-state rows are attached to the decision's start-time key but contain end-of-step state. Metrics are discrete-step sums, not continuous-time integration: objects passed, blocked duration, and open-without-near-object duration. The latter is a model exposure indicator, not a physical accident metric. Native adapters are not coupled into this feedback model.

No collision, torque, acceleration, servo electronics or mechanical settling calibration is modelled. A physical rerun and calibrated dynamics are still future work.

## 10. Source/evidence reproduction packages

Every new dashboard experiment and completed analysis retains its source set in SQLite. Identical source sets are deduplicated. Archives include Python modules, controller descriptors/sources, native artifacts, available headers/build manifest, environment information and a reproduction script. Loaded Python source is retained in memory at import and archived from that retained version if disk files subsequently change. Runner scripts come from the archived implementation, read as AST literals without importing it.

Download source & evidence ZIP for a current run or analysis & source ZIP for a result. Import package verifies file inventory and digests without running source. Experiment imports replay the input trace with installed controllers into a new experiment. Analysis imports retain the result and archived sources without claiming a rerun. Very old runs without source snapshots must be replayed into a new run before packaging.

```powershell
python -m causalbench.packages verify data/run.zip
```

For an archive you trust, extract into a new directory and run `python reproduce.py` there. It compares a recomputed experiment or analysis with the saved result and prints REPRODUCED or MISMATCH. Use the recorded Python version and the native artifact's OS/runtime. This is not a bundled Python runtime, dependency resolver or cross-platform container. Hashes are not signatures; preserve a trusted external digest if authenticity matters.

ZIP limits: 16 MB compressed, 24 MB total uncompressed, <=100 entries, no traversal/absolute/duplicate member names. Stored experiments/artifacts and source blobs are verified on reads. Trace remains <=2 MB; evidence verification accepts larger sealed bundles up to 32 MB because decision records and hash chains duplicate some input content.

## Additional tool: observed robustness boundary

Choose delay, drop rate, duplicate rate or noise amplitude; supply grid values and paired seeds. The dashboard deliberately uses Normal operation and clears other fault channels for an isolated scan. Predicate can be reference/candidate incorrect fixture pulse or command disagreement.

All supplied grid values are tested in supplied order, with no binary-search assumption of monotonicity. The result records failed seeds and the first observed failure on that grid. It does not prove a continuous threshold, failure probability outside the selected seeds, or hardware resilience. Limits: <=20 values, <=10 seeds, <=100 evaluations. Default delay scan on the 200 ms sampler reports its first observed reference failure at grid setting 100 ms; the affected sample can actually be 200 ms old.

## Persistence, resource and verification boundaries

Two analysis workers may run concurrently; successful analyses persist independently of the browser. In-progress job state and capture buffers are not resumed after service restart. Dashboard history lists latest 100 experiments; saved analysis list displays latest 30 non-profile/non-regression artifacts. SQLite retains older data. Failed jobs report an error rather than invent a result.

Verified Windows flows and exact tests are listed in VALIDATION.md. No real board/servo test, hosted CI execution, cross-platform native run, signature service, ROS/MCAP import, or full CPU/peripheral emulator is claimed. Those comparator capabilities remain outside this implementation.
