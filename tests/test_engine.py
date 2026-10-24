import copy
import unittest
from causalbench.engine import compare, make_trace, replay, seal, validate_trace, verify


class EngineTests(unittest.TestCase):
    def test_normal_agrees(self):
        self.assertEqual(compare(make_trace("normal"))["divergence_times_ms"], [])

    def test_stale_failure_and_fix(self):
        result = compare(make_trace("stale"))
        self.assertEqual(result["divergence_times_ms"], [1200])
        self.assertEqual(result["baseline"]["metrics"]["unsafe_fixture_pulses"], 1)
        self.assertEqual(result["guarded"]["metrics"]["unsafe_fixture_pulses"], 0)

    def test_duplicate_failure_and_fix(self):
        result = compare(make_trace("duplicate"))
        self.assertEqual(result["divergence_times_ms"], [1200])
        self.assertIn("Duplicate", result["guarded"]["rows"][6]["reason"])

    def test_disconnect_failure_and_fix(self):
        result = compare(make_trace("disconnect"))
        self.assertEqual(result["divergence_times_ms"], [1000, 1200, 1400])
        self.assertEqual(result["baseline"]["metrics"]["unsafe_fixture_pulses"], 2)
        self.assertEqual(result["guarded"]["metrics"]["unsafe_fixture_pulses"], 0)

    def test_replay_deterministic(self):
        trace = make_trace("stale")
        self.assertEqual(compare(trace), compare(copy.deepcopy(trace)))

    def test_replay_does_not_mutate_inputs(self):
        trace = make_trace("stale")
        before = copy.deepcopy(trace)
        compare(trace)
        self.assertEqual(trace, before)

    def test_fixture_truth_not_used_for_decisions(self):
        trace = make_trace("normal")
        a = replay(trace, "guarded-v1")
        for event in trace["events"]:
            event["fixture_present"] = not event["fixture_present"]
        b = replay(trace, "guarded-v1")
        self.assertEqual([r["command"] for r in a["rows"]], [r["command"] for r in b["rows"]])

    def test_exact_freshness_boundary(self):
        trace = make_trace("normal")
        trace["events"] = [{"time_ms": 300, "observation": {"id": "a", "sample_ms": 0, "distance_mm": 70}}, {"time_ms": 301, "observation": {"id": "b", "sample_ms": 0, "distance_mm": 70}}]
        self.assertEqual([r["command"] for r in replay(trace, "guarded-v1")["rows"]], ["PULSE", "HOLD"])

    def test_future_time_rejected(self):
        trace = make_trace("normal")
        trace["events"][0]["observation"]["sample_ms"] = 1
        with self.assertRaises(ValueError): validate_trace(trace)

    def test_nonmonotonic_time_rejected(self):
        trace = make_trace("normal")
        trace["events"][1]["time_ms"] = 0
        with self.assertRaises(ValueError): validate_trace(trace)

    def test_boolean_distance_rejected(self):
        trace = make_trace("normal")
        trace["events"][0]["observation"]["distance_mm"] = True
        with self.assertRaises(ValueError): validate_trace(trace)

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError): replay(make_trace("normal"), "unknown")

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError): make_trace("unknown")

    def test_bundle_verifies(self):
        trace = make_trace("stale")
        self.assertTrue(verify(seal(trace, compare(trace))))

    def test_modified_trace_detected(self):
        trace = make_trace("stale")
        bundle = seal(trace, compare(trace))
        bundle["manifest"]["trace"]["events"][0]["time_ms"] = 1
        self.assertFalse(verify(bundle))

    def test_modified_decision_detected(self):
        trace = make_trace("stale")
        bundle = seal(trace, compare(trace))
        bundle["manifest"]["comparison"]["guarded"]["rows"][0]["command"] = "PULSE"
        self.assertFalse(verify(bundle))

    def test_truncated_chain_detected(self):
        trace = make_trace("stale")
        bundle = seal(trace, compare(trace))
        bundle["manifest"]["records"].pop()
        self.assertFalse(verify(bundle))

    def test_malformed_bundle_invalid(self):
        self.assertFalse(verify({}))

    def test_capture_without_truth_has_no_invented_ground_truth(self):
        trace = make_trace("normal")
        trace["mode"] = "captured-input"
        for event in trace["events"]: del event["fixture_present"]
        self.assertNotIn("unsafe_fixture_pulse", replay(trace, "guarded-v1")["rows"][0])


if __name__ == "__main__": unittest.main()
