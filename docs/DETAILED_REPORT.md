# CausalBench: detailed engineering report

> Historical implementation notes are retained below. For the current UI and feature
> inventory, see [current status](../current_status.md) and [roadmap](ROADMAP.md).
> Earlier sage/cream layouts and chart screenshots describe superseded UI versions.

## Problem and motivation

Embedded failures often come from timing and state rather than a simple wrong threshold. A sensor reading may have been accurate when sampled but misleading when it reaches the controller. A duplicate can look like a new event. A disconnect can leave a naive controller repeating an old action. CausalBench makes these causes visible and reproducible.

The central question is: "Why did this controller make this decision, and how would another controller respond to the same recorded inputs?" A captured or generated input sequence becomes an immutable experiment. Two policies consume identical observations at identical event times. Their command differences are tied to supporting observations, ages, state transitions, and explanations.

You do not need a servo to use it. The entire experiment, replay, comparison, storage, visualization, and evidence workflow runs locally with a simulated command display. Actual sensor capture is an optional input path; even those experiments keep the actuator simulated.

## Portfolio relevance

The project complements embedded work by showing what happens between a reading and an actuator command: clock assumptions, input validation, state, and failure handling. If AeroNode demonstrates device engineering and validation discipline, this separate project demonstrates reproducible investigation of controller behavior. Its evidence chain can support the kind of traceability associated with JOCKY. This is a conceptual portfolio fit; neither project was inspected or modified during this work.

A strong interview explanation uses a concrete failure, a controlled experiment, and an honest statement of what was proved. Avoid presenting the guarded policy as a certified safety controller. This is an engineering laboratory with deliberately small, inspectable policies.

## What was built and why

The implementation uses Python's standard library, SQLite, and static HTML/CSS/JavaScript. This minimizes installation work and isolates deterministic computation from interactive playback. A loopback HTTP server is sufficient for a trusted single-machine lab. SQLite makes history survive process exits without a separate database service.

Existing CausalBench code and data were preserved and extended. Four original scenarios became seven. The dashboard gained first-divergence navigation, step, report/trace downloads, explicit input mode, state inspection, and a gate indicator. The engine gained invalid and sample-order handling, seed recording, hysteresis, versioned configuration, provenance, and richer metrics. Hardware capture gained raw observations and distinct clock metadata.

## Module-by-module explanation

`engine.py` holds pure controller execution alongside fixture and evidence helpers. `make_trace` builds a scenario using a seeded generator. `validate_trace` enforces the core contract without sorting sample timestamps. `replay` computes one policy's decision ledger. `compare` runs both policies and identifies event times with different commands. `seal` makes the manifest and event hash chain. `verify` checks the export's consistency and, for matching source provenance, recomputes its decisions.

`server.py` exposes a small JSON API and explicitly listed static files. `Store.create` validates a trace, computes comparison, seals it, and persists it under a UUID. `Store.get` verifies evidence before returning it. Independent SQLite connections and a creation lock keep the service simple. History metadata is capped at the latest 100 experiments.

`cli.py` supports run, verify, and capture. Capture polls a configurable HTTP endpoint and records successful readings, partial raw data, and connection errors. It uses host monotonic time for replay, retains device uptime separately, and never enables an actuator. It retries on the next poll after errors.

`actuators.py` defines a minimal command/time protocol, a command-only simulated response, and a physical adapter reservation that refuses activation. The dashboard implements the same command-only mapping visually. There is no claim that the gate drawing models real motion.

`web/index.html`, `app.js`, and `style.css` provide the dashboard. All decisions originate on the server. Playback only changes which recorded row is displayed; moving the scrubber cannot change the result. The ledger highlights differing commands. Imported evidence must verify before its trace is replayed into a new run. Text is inserted as text rather than interpreted as HTML.

The optional ESP32 sketch supplies `/reading` JSON with boot ID, sequence, uptime, validity, and distance. It samples per HTTP request and attempts Wi-Fi recovery. It is included for future bench work and was not compiled or flashed.

## Controller behavior

Baseline pulses whenever distance is below the enter threshold and repeats the previous command on missing input. It intentionally ignores freshness, duplicate identity, and sample ordering. Both controllers reject explicitly invalid values: malformed data cannot reasonably take part in a numeric comparison.

Guarded prioritizes invalid rejection, duplicate rejection, stale rejection, then sample-order rejection. A sample whose age exceeds 300 ms is stale by default. An equal or older sample time than the latest accepted sample is out of order. Accepted near readings enter ACTIVE below 100 mm; while ACTIVE the exit threshold is 120 mm. Rejected or missing observations produce HOLD and reset ACTIVE. Hysteresis reduces threshold chatter while observations remain valid and ordered. Configuration can be changed in trace JSON and is recorded with each policy result.

PULSE means a simulated command at that event. It does not mean a physical pulse duration, full gate open/close cycle, or single-shot actuator behavior. No cooldown is implemented. A future physical adapter must explicitly define those semantics before output is enabled.

## Fault scenarios

Normal uses fresh observations with fixture presence at selected ticks. Stale replaces the 1200 ms observation with a near reading sampled at 600 ms. Duplicate reuses a previous observation ID while preserving arrival order. Disconnect removes three observations; baseline continues its previous pulse. Out-of-order supplies a 900 ms sample after a 1000 ms sample. Noise perturbs distances with a stored seed. Invalid preserves a raw error representation with `valid: false` and a null distance.

Capture order is always the event list order. The engine requires increasing event time, while allowing old sample time. Sorting by sample time would erase the phenomenon being investigated. Synthetic fixture truth is stored separately and used only for illustrative incorrect-command metrics after the controller decides.

## Worked failure and replay example

At 600 ms an object is close and distance is 70 mm. Both controllers pulse. At 800 and 1000 ms the object remains close. At 1200 ms fixture truth says the object is absent, but a delayed 70 mm observation sampled at 600 ms arrives.

Baseline sees 70 <100 and produces PULSE. Guarded calculates 1200−600=600 ms, exceeding its 300 ms allowance, and produces HOLD with the explanation "Stale observation rejected." This is the first command divergence. The ledger shows the same observation and age for both policies. Baseline has one incorrect fixture pulse, guarded zero.

This proves that the guarded policy responds differently to this fixed input sequence. It does not prove that a real gate would avoid an accident, nor that the recorded future observations would remain the same after a changed physical command. A physical rerun or a specified plant model is required for those claims.

## Metrics and assumptions

Command divergence count is the number of paired events whose commands differ. Pulse count counts PULSE rows, not gate cycles. Rejection counts use the primary explanation; a reading that is both stale and out of order is counted under the first applicable reason. Missing-observation duration sums the intervals following missing events up to the next event, excluding the final unbounded interval.

Incorrect fixture pulses count PULSE when generated fixture presence is false. This is an illustrative command-level error, not physical safety measurement. Captured traces without fixture truth report the metric as unknown. If a trace supplies truth for only some events, aggregate correctness remains unknown. No measured physical latency or response-time claim is made.

Simulation time has exact millisecond semantics. Captured source timestamps are unsynchronized. Host request-start is a sampling estimate with request-duration uncertainty and depends on the endpoint really sampling during the request. A buffered sensor protocol would need a stronger clock mapping. Browser playback caps display waits at two seconds, but recorded decision times remain unchanged.

## Evidence integrity

Canonical JSON and SHA-256 provide stable trace and manifest digests. An indexed event chain detects changes and truncation relative to its recorded head; the manifest digest also covers decisions and provenance. Stored evidence is verified before viewing, and report download requests verification first. The tamper demonstration changes a copy, preserving the stored experiment.

Hash consistency is distinct from authenticity. An editor can recompute a self-contained digest. Keep a trusted digest elsewhere if you want a reference that cannot be replaced together with the export. No signature or sensor attestation is implemented. Matching source provenance allows decision recomputation; old-source exports receive consistency checks only. A historical implementation would be needed to reproduce historical decisions exactly.

## Tests and observed results

44 Python tests passed on Python 3.13.7. They cover deterministic replay, unchanged inputs, truth separation, freshness and hysteresis boundaries, fault behavior, configuration, imports/exports, tampering/truncation, mocked sensor errors and recovery, physical output refusal, SQLite persistence, and actual HTTP requests. The browser was exercised across all seven scenarios, including first divergence, step/play, import, evidence/report downloads, and integrity controls. Exact commands and results are in `VALIDATION.md`; raw output is saved under data.

Default-seed noise and invalid scenarios show no divergence. This is intentional honest reporting: not every fault necessarily changes the commands. The stale, duplicate, and out-of-order fixtures each produce one divergence; disconnect produces three.

## Hardware integration and limits

See `HARDWARE_GUIDE.md` for the example ESP32/HC-SR04 profile, configurable pins and endpoint, level compatibility, capture command, and future servo contract. The original exact board inventory is unknown. Firmware compilation, flashing, and physical tests remain unverified. Credentials stay in an ignored local header. No other project's firmware was overwritten.

The local application has no account system, distributed clock synchronization, signed evidence, or real servo driver. Version 2.0 adds rolling sensor capture and a deliberately simplified gate model. Trace limits bound experiments to 10000 events, 2 MB, and a 24-hour relative clock. Rich metadata is optional to preserve useful existing v1 inputs. Source provenance hashes the engine file rather than the whole repository or runtime environment.

## Future milestones and interview talking points

First, validate sensor firmware on the actual board and measure clock uncertainty and sensor accuracy. Next, calibrate the implemented closed-loop model against real observations. Then implement explicitly enabled servo output with power planning, mechanical limits, stop behavior, and measured settling. Finally, consider signed evidence and wider browser regression testing.

Useful talking points: why arrival order matters; why time must be injected; why duplicate IDs are not new samples; what hysteresis trades off; how known fixture truth differs from unknown hardware truth; what a hash can establish; and why open-loop comparison does not establish counterfactual physical behavior. These are the decisions that make the project credible beyond its dashboard.


## Version 2.0: from demonstration to experiment workflow

All ten proposed software additions have been implemented. The original dashboard structure/theme is preserved; Research tools follow its history panel. Read EXPERIMENT_WORKFLOWS.md for exact use, schemas and limits.

The main engineering change is the path from a composed fault, through paired controller/seed studies, to an isolated counterexample, a saved regression, and an archived implementation that can reproduce it later. Grid search exposes observed robustness boundaries without assuming monotonic behavior. Common random draws reduce confounding from changing the random sequence between sweep values. The source-retention layer prevents edited files from silently changing the provenance of code already running in memory.

Native controller comparison is actual host C++ execution, not a second Python policy labelled native. The g++ example was compiled and independently checked across all seven original scenarios. A separately installed native descriptor/executable is also tested. The corroboration controller consumes separately sampled proximity/IMU inputs; it never reads fixture truth for decisions. Its conservative veto can reduce incorrect pulses while increasing missed detections. That tradeoff is displayed rather than treating every disagreement as an improvement.

Live mock/HTTP capture now supports snapshots of a bounded recent buffer. Device time and host estimates remain distinct; cached endpoints cannot yield proven physical freshness without synchronization. A real HTTP stand-in exercises network capture, but no actual ESP32 hardware is claimed.

The gate model feeds outputs back into motion and subsequent sensing. It records independent trajectories, discrete blocked/exposure metrics and its assumptions. It models no torque/collision/acceleration and is not hardware validation. Native adapters remain open-loop only.

Experiment and analysis ZIPs contain retained sources, controller artifacts, environment description and an offline runner. Imports inspect code without executing it. Offline tests unpack trusted generated archives into temporary directories and independently reproduce comparisons, studies, scans, minimized traces, regressions and plant runs. This establishes reproducibility under the captured implementation/environment, not authenticity or sensor truth.

The latest suite has 91 passing tests; exact commands and browser checks are in VALIDATION.md. C++ host compilation succeeded; microcontroller firmware compilation/flashing remain unverified. Future work should measure the real sensor/clock path and calibrate the model, followed by explicitly enabled physical output, rather than adding another decorative dashboard redesign.
