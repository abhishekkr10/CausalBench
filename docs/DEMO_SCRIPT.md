# Interview demonstration

> Historical implementation notes are retained below. For the current UI and feature
> inventory, see [current status](../current_status.md) and [roadmap](ROADMAP.md).
> Earlier sage/cream layouts and chart screenshots describe superseded UI versions.

## 90 seconds

0–15 s: Open the dashboard. Say: "This compares two controllers against exactly the same observations. The gate is simulated, so no servo is needed."

15–35 s: Select Delayed sensor reading and Run experiment. Point to 12 events, one divergence, baseline one incorrect fixture pulse, guarded zero.

35–55 s: Click First divergence. At 1200 ms the delayed sample is from 600 ms. Baseline sees 70 mm and pulses; guarded rejects age >300 ms. Fixture presence is false, but neither controller uses that truth to choose a command.

55–75 s: Step, then Play and Pause. Point to input age, state transitions, and ledger. Explain that replay time is injected and independent of browser playback speed.

75–90 s: Verify bundle, then Test a modified copy. Show VALID then INVALID. Export evidence. Say: "The hashes check consistency against a trusted digest; they do not prove sensor truth. Open-loop replay compares decisions, not counterfactual physical outcomes."

## Five minutes

Run the 90-second demonstration. Then run Duplicate observation, Sensor disconnect, and Out-of-order sample; use First divergence on each. Missing input makes baseline repeat a pulse while guarded holds. Noise uses a stored seed and tests hysteresis; this particular default seed can yield no command divergence, which is an honest result. Invalid observation is rejected by both controllers.

Export trace and evidence, import the trace into a new experiment, and inspect history. Download the verified comparison report. Explain capture mode using the configurable CLI and unsynchronized clock metadata. Show the disabled physical adapter and hardware guide. Finish by outlining a future closed-loop model and a separately measured physical rerun, without claiming either exists today.


## Version 2.0 deeper demonstration

1. Keep the original stale-reading demo. In Research tools, add fusion and compiled C++ and run again. Show all four policy rows.
2. Minimize the failure: 12 observations reduce to one at 1200 ms. Explain 1-minimality, fixed timestamps, and reset initial state.
3. Save a regression and run it. Then show a paired-seed delay/configuration study and an isolated boundary scan. Distinguish tested grid values from physical timing thresholds.
4. Start mock recording, snapshot the recent buffer, and stop. Point to synthetic labeling, evictions and Unknown outcome truth.
5. Run the feedback gate model. Scrub the separate plants and explain its assumptions, independent future inputs and discrete exposure/blocked metrics.
6. Download an experiment or analysis source ZIP. Inspect, extract a trusted archive in a new directory, and run python reproduce.py. Show REPRODUCED. Explain source freezing and why archive consistency is not authenticity.

For a fresh-noise example where corroboration adds value beyond freshness/order checks, use examples/sensor-corroboration.json through the headless command, then import its bundle. Actual measured hardware behavior remains outside this demonstration.
