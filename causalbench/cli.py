"""Headless experiments, verification, and optional ESP32 HTTP capture."""
from .provenance import loaded_source, register_source
_LOADED_SOURCE=register_source(__file__)
import argparse
import json
import time
import urllib.request
from pathlib import Path
from .engine import SCENARIOS, compare, make_trace, seal, validate_trace, verify


def capture(url, count, interval_ms):
    origin = time.monotonic_ns()
    events = []
    for _ in range(count):
        start = (time.monotonic_ns() - origin) // 1000000
        obs = None
        error = None
        reading = None
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                raw = response.read(4097)
            if len(raw) > 4096:
                raise ValueError("Device response exceeds 4096 bytes")
            reading = json.loads(raw)
            if not isinstance(reading, dict):
                raise ValueError("Device response must be an object")
            if reading.get("valid") is True:
                distance = reading["distance_mm"]
                sequence = reading["sequence"]
                if type(distance) is not int or not 0 <= distance <= 10000:
                    raise ValueError("Invalid device distance")
                if type(sequence) is not int or not 0 <= sequence <= 4294967295:
                    raise ValueError("Invalid device sequence")
                obs = {"id": f"{reading['boot_id']}:{sequence}",
                       "sample_ms": start, "distance_mm": distance,
                       "device_id": "esp32-http", "session_id": str(reading['boot_id'])[:100],
                       "sequence": sequence, "source_timestamp_ms": reading.get("uptime_ms"),
                       "units": "mm", "source_clock": "device uptime; unsynchronized"}
            else:
                error = "Device reported sensor invalid"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            error = str(exc)[:200]
        arrival = (time.monotonic_ns() - origin) // 1000000
        now = max(arrival, events[-1]["time_ms"] + 1 if events else 0)
        events.append({"time_ms": now, "observation": obs, "capture_error": error,
                       "capture_sequence": len(events), "raw_observation": reading,
                       "request_start_ms": start, "receive_ms": arrival, "uncertainty_ms": arrival-start})
        time.sleep(interval_ms / 1000)
    trace = {"schema_version": 1, "mode": "captured-input", "scenario": "esp32-http",
             "timestamp_scope": "sample_ms is host request-start estimate; not device clock synchronization",
             "events": events}
    validate_trace(trace)
    return trace


def main():
    parser = argparse.ArgumentParser(description="CausalBench reproducible experiment CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--scenario", choices=SCENARIOS, default="stale")
    run.add_argument("--trace", type=Path)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("bundle", type=Path)
    collect = sub.add_parser("capture")
    collect.add_argument("--url", required=True)
    collect.add_argument("--count", type=int, default=30)
    collect.add_argument("--interval-ms", type=int, default=200)
    collect.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        valid = verify(json.loads(args.bundle.read_text(encoding="utf-8")))
        print("VALID" if valid else "INVALID")
        raise SystemExit(0 if valid else 1)
    if args.command == "capture":
        if not 1 <= args.count <= 10000 or not 1 <= args.interval_ms <= 60000:
            parser.error("count must be 1..10000 and interval-ms 1..60000")
        result = capture(args.url, args.count, args.interval_ms)
    else:
        trace = json.loads(args.trace.read_text(encoding="utf-8")) if args.trace else make_trace(args.scenario, args.seed)
        result = seal(trace, compare(trace))
        print(json.dumps(result["manifest"]["comparison"]["divergence_times_ms"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
