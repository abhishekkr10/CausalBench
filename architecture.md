# Architecture and contracts

## Data flow

Generated scenario or HTTP device -> versioned trace -> validator -> baseline and guarded replay -> comparison -> sealed evidence -> SQLite -> HTTP API -> browser.

Python standard library plus SQLite keeps setup small and deterministic. Browser JavaScript supplies the interactive timeline; it is not the authority for replay results. The server creates decisions and verifies evidence on reads. The dashboard inserts imported text using `textContent`.

## Trace schema v1

A trace is an object with integer `schema_version: 1`, mode `simulation` or `captured-input`, and 1..10000 events. Canonical UTF-8 JSON is limited to 2 MB. Event `time_ms` is an integer in 0..86400000 and strictly increases. Capture order is preserved. Sample timestamps may go backwards, which is a fault for the guarded controller rather than a reason to sort the trace.

An observation has an ID (1..100 characters), sample time, and integer `distance_mm` in 0..10000. A Boolean `valid: false` permits an invalid/partial value; optional `raw` preserves the malformed reading. Valid observations reject booleans masquerading as integers. Sample time must not be in the future. Optional device/session IDs, sequence, and units are validated when present; units must be mm. Minimal older v1 traces remain importable without richer metadata. Duplicate IDs are intentional possible input, not globally rejected.

Generated traces include device, session, sequence, receive time, capture sequence, seed, and simulation clock description. Capture traces preserve raw device JSON, boot identity, device sequence, device uptime when present, host request-start and receive times, errors, and request duration.

## Clock domains

Simulation time is exact relative milliseconds. Capture uses host monotonic elapsed milliseconds. Device uptime is retained in its own unsynchronized clock domain. Controller sample age uses host request-start as a conservative sampling estimate, not a synchronized source timestamp. Request duration brackets uncertainty only when the endpoint actually samples during the request. Cached or buffered device samples break that assumption. The final missing interval has no known end and is excluded from missing-duration metrics.

## Controller contracts

Replay receives the trace and policy identity, with time injected through each event. It never sleeps, reads hardware, uses network, or draws random numbers. Fixture truth is used only after a decision to evaluate illustrative outcome metrics. State consists of ACTIVE/IDLE, seen observation IDs, and latest accepted sample time. Baseline repeats its command on missing input. Guarded holds on missing, invalid, duplicate, stale, or out-of-order input; rejection resets ACTIVE. Invalid observations are safely rejected by both policies because numeric comparison cannot operate on partial values.

Default configuration is version 1, enter threshold 100 mm, exit threshold 120 mm, max age 300 ms. Enter and exit comparisons are strict `<`; age exactly 300 ms is accepted. Both use enter threshold; only guarded uses exit hysteresis while ACTIVE. No cooldown is added because PULSE is an event-level command demonstration, not a physical single-shot mechanism. Trace `controller_config` can supply all four fields; exit must be >= enter. For example:

```json
{"version":1,"enter_mm":100,"exit_mm":120,"max_age_ms":300}
```

Controller identity, effective configuration, policy digest, engine version, and engine source SHA-256 are recorded. Source provenance uses retained loaded-source digests and installed descriptors/artifact digests, not a signed build or full environment attestation.

## Actuator and experiment scope

The dashboard maps HOLD to a horizontal gate and PULSE to a raised gate. It models commands only, with no motion, torque, collision, settling, or feedback physics. `actuators.py` defines an adapter protocol and rejects physical activation until an implementation is written. No physical output code is reachable from the dashboard.

Open-loop replay holds all inputs fixed. Closed-loop simulation in plant.py feeds each controller's outputs into a separate gate/queue model to generate later observations; see the 2.0 section below. Physical rerun requires actual hardware and fresh measured inputs; this is not implemented.

## Evidence and persistence

SHA-256 uses sorted-key compact JSON, rejecting NaN/Infinity. Event records form an indexed previous-hash chain. The manifest includes the trace, comparison, records, and chain head; a digest covers the whole manifest. Verification reconstructs the chain and seal and validates the trace. Decision recomputation is additionally performed when recorded source provenance matches the current engine. Older-source bundles receive consistency verification only: their old decisions are not claimed to be validated by the new implementation.

A party who controls the entire bundle can change it and recompute its hashes. Preserve a trusted digest outside the bundle for external anchoring. No signature, secret key, sensor authenticity, or truth proof is offered. SQLite stores each immutable experiment as canonical bundle JSON, with a UUID and UTC creation time. Reads verify it before delivery; a corrupted run returns 409.

## API

GET `/api/health`, `/api/runs`, `/api/runs/{id}`; POST `/api/runs` with `{scenario: name}` or `{trace: object}`; POST `/api/verify` with a bundle. History returns the latest 100 metadata entries. Static files are served from an explicit allowlist. Errors: 400 invalid input, 403 cross-origin mutation, 404 unknown resource, 415 non-JSON, 409 stored integrity failure. Body limit 2 MB. No authentication: intended for a trusted local machine, not hosted service. Browser Origin checks and CSP reduce accidental cross-origin browser interactions; they do not defend against local malware.


## Version 2.0 components and extensions

- faults.py composes seeded transformations and validates auxiliary streams/configuration. Channels share paired random draws across sweeps.
- controllers.py discovers trusted local rule/native descriptors, implements corroboration, adapts the compiled process protocol and summarizes controller outcomes. Native outputs undergo two identical-input invocations and contract validation.
- studies.py performs batches, grid scans, bounded delta debugging and regression assertions; lab_cli.py supplies headless/CI entry points.
- plant.py generates separate controller-dependent gate/queue trajectories. It is never passed off as identical-input replay.
- capture.py owns a background rolling recorder, explicit errors, count/byte limits and snapshots. It does not enable physical output.
- jobs.py bounds concurrent analysis workers and persists successful results.
- packages.py creates/inspects versioned inventories and archives. Imported code is never installed/executed. Offline reproductions use archived runner literals rather than the current runner template.
- provenance.py retains Python source at import. File edits do not relabel an already loaded implementation.
- web/lab.js adds research tools to the original interface and uses existing API/replay functions.

Optional v1 trace extensions: controllers (2..4 distinct IDs), controller_configs (per-policy configuration), fault_settings, generator_version, streams, applied_faults, source_kind and capture metadata. Minimal legacy traces remain valid. Auxiliary units are explicit: mm, milliC, milli_g or bool; missing is null and invalid uses valid=false.

SQLite additions: artifacts stores immutable payload plus digest; source_sets stores deduplicated zipped source plus blob hash; run_sources and artifact_sources associate results with their captured implementation. Reads verify bundles, artifacts and source blobs. This is local consistency, not external authentication. Existing tables are retained and migrated additively.

Current-source decision validation requires matching loaded engine/adapter/implementation provenance, including installed descriptors. Historical-source bundles still receive structural/hash consistency checks; exact historic reproduction uses the archived source package. API binds loopback, validates Host and browser Origin, caps inputs and static filenames, and supports two bounded background workers.

New routes: controllers, profiles, regressions/check, capture/start/stop/snapshot/status, jobs/status, artifacts, experiment packages and analysis packages. Exact request examples and resource bounds are documented in EXPERIMENT_WORKFLOWS.md. Trace bodies remain <=2 MB canonically; sealed evidence can be larger and has a separate verification limit. No runtime network or wall-clock input enters the built-in controller logic; live capture and native process launch are separate adapters.
