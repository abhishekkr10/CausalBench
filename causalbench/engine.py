"""Pure replay engine. Time and observations come from the input trace."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import hashlib
import json
import random
import subprocess
from pathlib import Path

SCHEMA = 1
POLICIES = ("baseline-v1", "guarded-v1")
SCENARIOS = ("normal", "stale", "duplicate", "disconnect", "out-of-order", "noise", "invalid")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def make_trace(scenario, seed=42):
    integer(seed, "seed", 0, 4294967295)
    rng = random.Random(seed)
    if scenario not in SCENARIOS:
        raise ValueError("Unknown scenario")
    events = []
    for tick in range(12):
        now = tick * 200
        # Fixture ground truth is explanatory only; controllers never receive it.
        present = tick in (3, 4, 5, 8, 9)
        obs = {"id": f"sensor-{tick}", "sample_ms": now,
               "distance_mm": 70 if present else 250}
        if scenario == "stale" and tick == 6:
            obs = {"id": "delayed-3", "sample_ms": 600, "distance_mm": 70}
        if scenario == "duplicate" and tick == 6:
            obs = {"id": "sensor-3", "sample_ms": 1200, "distance_mm": 70}
        if scenario == "disconnect" and tick in (5, 6, 7):
            obs = None
        if scenario == "out-of-order" and tick == 6:
            obs = {"id": "late-5", "sample_ms": 900, "distance_mm": 70}
        if scenario == "noise":
            obs["distance_mm"] = (95 if present else 125) + rng.randint(-12, 12)
        if scenario == "invalid" and tick == 6:
            obs.update(valid=False, distance_mm=None, raw={"distance_mm": "sensor-error"})
        obs_metadata = {"device_id": "sim-sensor", "session_id": "fixture", "sequence": tick,
                        "source_timestamp_ms": obs["sample_ms"] if obs else None, "units": "mm"}
        if obs is not None:
            obs.update(obs_metadata)
        events.append({"capture_sequence": tick, "receive_ms": now, "time_ms": now, "observation": obs,
                       "fixture_present": present})
    trace = {"schema_version": SCHEMA, "mode": "simulation",
             "scenario": scenario, "seed": seed, "clock": "simulation milliseconds; zero synchronization uncertainty", "events": events}
    validate_trace(trace)
    return trace


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Invalid {name}")


def validate_trace(trace):
    if not isinstance(trace, dict) or type(trace.get("schema_version")) is not int or trace.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported trace schema")
    if len(canonical(trace).encode()) > 2000000:
        raise ValueError("Trace exceeds 2 MB")
    if trace.get("mode") not in ("simulation", "captured-input"):
        raise ValueError("Invalid trace mode")
    events = trace.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= 10000:
        raise ValueError("Trace needs 1..10000 events")
    cfg = trace.get("controller_config", {"version": 1, "enter_mm": 100, "exit_mm": 120, "max_age_ms": 300})
    if not isinstance(cfg, dict) or type(cfg.get('version')) is not int or cfg.get("version") != 1:
        raise ValueError("Unsupported controller configuration")
    for name, bound in (("enter_mm", 10000), ("exit_mm", 10000), ("max_age_ms", 86400000)):
        integer(cfg.get(name), name, 0, bound)
    if cfg["exit_mm"] < cfg["enter_mm"]:
        raise ValueError("exit_mm must be >= enter_mm")
    if 'controller_configs' in trace:
        from .faults import configuration
        configs=trace['controller_configs']
        if not isinstance(configs,dict) or len(configs)>16:
            raise ValueError('Invalid controller configuration map')
        for identity,value in configs.items():
            if not isinstance(identity,str) or not 1<=len(identity)<=60:
                raise ValueError('Invalid controller configuration identity')
            configuration(value)
    previous = -1
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Invalid event")
        integer(event.get("time_ms"), "time_ms", 0, 86400000)
        if event["time_ms"] <= previous:
            raise ValueError("Event times must strictly increase")
        previous = event["time_ms"]
        if "fixture_present" in event and type(event["fixture_present"]) is not bool:
            raise ValueError("Invalid fixture ground truth")
        if 'streams' in event:
            from .faults import validate_streams
            validate_streams(event)
        obs = event.get("observation")
        if obs is not None:
            if not isinstance(obs, dict):
                raise ValueError("Invalid observation")
            if not isinstance(obs.get("id"), str) or not 1 <= len(obs["id"]) <= 100:
                raise ValueError("Invalid observation id")
            integer(obs.get("sample_ms"), "sample_ms", 0, 86400000)
            if "valid" in obs and type(obs["valid"]) is not bool:
                raise ValueError("Invalid validity flag")
            if obs.get("valid", True):
                integer(obs.get("distance_mm"), "distance_mm", 0, 10000)
            for field in ("device_id", "session_id"):
                if field in obs and (not isinstance(obs[field], str) or not 1 <= len(obs[field]) <= 100):
                    raise ValueError("Invalid " + field)
            if "sequence" in obs:
                integer(obs["sequence"], "sequence", 0, 4294967295)
            if obs.get("units", "mm") != "mm":
                raise ValueError("Distance units must be mm")
            if obs["sample_ms"] > event["time_ms"]:
                raise ValueError("Observation cannot come from the future")


def replay(trace, policy):
    validate_trace(trace)
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    cfg = trace.get("controller_config", {"version": 1, "enter_mm": 100, "exit_mm": 120, "max_age_ms": 300})
    seen = set()
    rows = []
    latest_sample = -1
    active = False
    missing_since = None
    for event in trace["events"]:
        now, obs = event["time_ms"], event.get("observation")
        before = "ACTIVE" if active else "IDLE"
        command = "HOLD"
        reason = "No observation; hold simulated actuator"
        if obs is not None:
            age = now - obs["sample_ms"]
            missing_since = None
            if not obs.get("valid", True):
                reason = "Invalid or partial observation rejected"
            elif policy == "guarded-v1" and obs["id"] in seen:
                reason = "Duplicate observation rejected"
            elif policy == "guarded-v1" and age > cfg["max_age_ms"]:
                reason = f"Stale observation rejected (age > {cfg['max_age_ms']} ms)"
            elif policy == "guarded-v1" and obs["sample_ms"] <= latest_sample:
                reason = "Out-of-order sample rejected"
            else:
                threshold = cfg["exit_mm"] if policy == "guarded-v1" and active else cfg["enter_mm"]
                command = "PULSE" if obs["distance_mm"] < threshold else "HOLD"
                latest_sample = max(latest_sample, obs["sample_ms"])
                active = command == "PULSE"
                reason = f"Distance {obs['distance_mm']} mm < {threshold} mm; simulated pulse" if command == "PULSE" else f"Distance outside {threshold} mm threshold"
            seen.add(obs["id"])
            if command == "HOLD":
                active = False
        else:
            age = None
            active = False
            if missing_since is None:
                missing_since = now
            if policy == "baseline-v1" and rows:
                command = rows[-1]["command"]
                active = command == 'PULSE'
                reason = "Missing observation; repeat last command"
        row = {"time_ms": now, "observation_id": obs["id"] if obs else None,
               "sample_age_ms": age, "command": command, "reason": reason,
               "state_before": before, "state_after": "ACTIVE" if active else "IDLE"}
        if "fixture_present" in event:
            row["fixture_present"] = event["fixture_present"]
            row["unsafe_fixture_pulse"] = command == "PULSE" and not event["fixture_present"]
        rows.append(row)
    return {"policy": policy, "policy_digest": digest({"name": policy, "engine": "2.0.0", "configuration": cfg}),
            "provenance": {"engine_source_sha256": hashlib.sha256(_LOADED_SOURCE).hexdigest(),
                           "engine_version": "2.0.0"},
            "configuration": {**cfg, "exit_mm": cfg["exit_mm"] if policy == "guarded-v1" else cfg["enter_mm"]},
            "trace_digest": digest(trace), "rows": rows,
            "metrics": {"pulses": sum(r["command"] == "PULSE" for r in rows),
                        "unsafe_fixture_pulses": sum(r.get("unsafe_fixture_pulse", False) for r in rows) if all("fixture_present" in r for r in rows) else None,
                        "rejected_stale": sum("Stale" in r["reason"] for r in rows),
                        "rejected_duplicate": sum("Duplicate" in r["reason"] for r in rows),
                        "rejected_invalid": sum("Invalid" in r["reason"] for r in rows),
                        "rejected_out_of_order": sum("Out-of-order" in r["reason"] for r in rows),
                        "missing_observation_duration_ms": sum(trace["events"][i+1]["time_ms"] - e["time_ms"] for i,e in enumerate(trace["events"][:-1]) if e.get("observation") is None),
                        "events": len(rows)}}


def compare(trace):
    if 'controllers' in trace or 'controller_configs' in trace:
        from .controllers import comparison
        validate_trace(trace)
        return comparison(trace)
    baseline, guarded = (replay(trace, p) for p in POLICIES)
    divergences = [a["time_ms"] for a, b in zip(baseline["rows"], guarded["rows"])
                   if a["command"] != b["command"]]
    return {"baseline": baseline, "guarded": guarded, "divergence_times_ms": divergences,
            "scope": "Open-loop replay of identical inputs; no physical outcome or counterfactual sensor trajectory is proven."}


def seal(trace, comparison):
    records = []
    previous = "0" * 64
    for index, event in enumerate(trace["events"]):
        payload = {"index": index, "event": event, "previous": previous}
        previous = digest(payload)
        records.append({**payload, "hash": previous})
    manifest = {"schema_version": SCHEMA, "trace": trace, "comparison": comparison,
                "records": records, "head": previous}
    return {"manifest": manifest, "manifest_digest": digest(manifest)}


def verify(bundle):
    try:
        manifest = bundle["manifest"]
        if digest(manifest) != bundle["manifest_digest"]:
            return False
        validate_trace(manifest["trace"])
        source = manifest["comparison"].get("guarded", {}).get("provenance", {}).get("engine_source_sha256")
        adapter = manifest['comparison'].get('guarded', {}).get('provenance', {}).get('controller_adapter_sha256')
        adapter_matches = adapter is None or adapter == hashlib.sha256(loaded_source(Path(__file__).with_name('controllers.py'))).hexdigest()
        implementation = manifest['comparison'].get('guarded',{}).get('provenance',{}).get('implementation_digest')
        if implementation is not None:
            from .controllers import implementation_digest
            adapter_matches = adapter_matches and implementation==implementation_digest()
        if source == hashlib.sha256(_LOADED_SOURCE).hexdigest() and adapter_matches and manifest["comparison"] != compare(manifest["trace"]):
            return False
        return seal(manifest["trace"], manifest["comparison"]) == bundle
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return False
