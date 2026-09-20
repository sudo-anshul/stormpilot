import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from service.present import compact_trace, engine_request, make_view, normalize_config
from service.tests.support import genuine_packet, presentation_request


class NormalizerTests(unittest.TestCase):
    def test_rejects_invalid_settings_before_a_job_is_created(self):
        invalid = [
            {"budget": 2}, {"budget": 25}, {"budget": 3.5}, {"budget": True},
            {"seed": 0.5}, {"seed": True}, {"seed": -1}, {"seed": 2**31},
            {"threshold": float("nan")}, {"threshold": float("inf")}, {"threshold": -1},
            {"model_id": "../../private"}, {"controller_id": "unknown"},
            {"fallback_controller_id": "unknown"}, {"metric": "unsupported"},
            {"fault_asset": "missing"}, {"fault_kind": "unsupported"},
            {"start_hour": 78}, {"start_hour": 77, "duration_hours": 2},
            {"duration_hours": 0}, {"mode": "unrestricted-code"},
            {"additional_faults": {}}, {"additional_faults": [{"asset":"missing", "start_hour":1,"duration_hours":1}]},
            {"additional_faults": [{"asset":"2","start_hour":77,"duration_hours":2}]},
        ]
        for config in invalid:
            with self.subTest(config=config), self.assertRaises((ValueError, TypeError)):
                normalize_config(config)

    def test_rejects_overlapping_conditions_on_the_same_outlet(self):
        # This combination is also rejected by the engine. It should not first
        # enter the work queue and fail as an expensive simulation job.
        with self.assertRaises(ValueError):
            normalize_config({"additional_faults":[{"asset":"1","start_hour":2,"duration_hours":1}]})

    def test_normalization_preserves_input_and_converts_hours_to_declared_seconds(self):
        supplied = {"budget":"3", "seed":"42", "start_hour":1.5, "duration_hours":2,
                    "additional_faults":[{"asset":"2","start_hour":30,"duration_hours":1}]}
        before = copy.deepcopy(supplied)
        normalized = normalize_config(supplied)
        self.assertEqual(supplied, before)
        self.assertEqual(normalized["budget"],3)
        self.assertEqual(normalized["seed"],42)
        request = engine_request(normalized)
        self.assertEqual(request["faults"][0]["start_s"],5400)
        self.assertEqual(request["faults"][0]["end_s"],12600)
        self.assertEqual(request["faults"][1]["start_s"],108000)
        self.assertEqual(request["faults"][1]["end_s"],111600)
        self.assertEqual(request["search_budget"],3)


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = genuine_packet()
        cls.request = presentation_request()

    def test_original_and_reduced_cases_remain_distinct_and_use_actual_metrics(self):
        view = make_view(self.packet, {"status":"passed"}, self.request)
        by_role = {case["role"]:case for case in view["cases"]}
        self.assertEqual(set(by_role), {"nominal","stress","reduced","fallback"})
        self.assertEqual(len(by_role["stress"]["faults"]),2)
        self.assertEqual(len(by_role["reduced"]["faults"]),1)
        native_witness = next(r for r in self.packet["runs"] if r["run_id"] == self.packet["witness"]["run_id"])
        self.assertEqual(by_role["reduced"]["metrics"],native_witness["metrics"])
        self.assertEqual(view["search"]["evaluated"],self.packet["search"]["simulator_calls"])
        self.assertEqual(view["search"]["reduced_from"],2)
        self.assertEqual(view["search"]["reduced_to"],1)
        self.assertEqual(view["finding"]["status"],"violation")
        self.assertIsNotNone(view["finding"]["first_time_s"])

    def test_rendered_trace_retains_measured_discharge_and_overflow_peaks(self):
        for run in self.packet["runs"]:
            with self.subTest(run=run["run_id"]):
                compact = compact_trace(run)
                self.assertEqual(compact[0]["time_s"],0)
                self.assertEqual(compact[-1]["time_s"],run["trace"][-1]["time_s"])
                self.assertEqual(max(r["downstream_flow_m3s"] for r in compact),run["metrics"]["peak_downstream_flow_m3s"])
                self.assertEqual(max(r["total_flooding_m3s"] for r in compact),max(r["total_flooding_m3s"] for r in run["trace"]))

    def test_absent_witness_and_high_threshold_do_not_crash_or_claim_a_failure(self):
        packet = {**self.packet,"witness":None,"search":{"status":"no_violation_found","stopping_reason":"envelope_exhausted"}}
        request = copy.deepcopy(self.request)
        request["config"]["threshold"] = 1e8
        view = make_view(packet,{"status":"passed"},request)
        self.assertEqual(view["finding"]["status"],"no_violation")
        self.assertIsNone(view["finding"]["first_time_s"])
        self.assertIn("No reduction claim",view["search"]["claim"])

    def test_nominal_failure_is_not_attributed_only_to_the_fault(self):
        request = copy.deepcopy(self.request)
        request["config"].update(metric="peak_downstream_flow_m3s",threshold=0)
        view = make_view({**self.packet,"witness":None},{"status":"passed"},request)
        self.assertEqual(view["finding"]["status"],"baseline_failure")
        self.assertIn("not a failure introduced only",view["finding"]["description"])

    def test_failed_evidence_has_priority_over_a_numerical_violation(self):
        view = make_view(self.packet,{"status":"failed"},self.request)
        self.assertEqual(view["finding"]["status"],"unverified")
        self.assertIn("Required evidence checks failed",view["finding"]["description"])

    def test_missing_metrics_and_budget_limited_pass_remain_incomplete(self):
        packet = {**self.packet,"witness":None,"runs":[],"search":{}}
        self.assertEqual(make_view(packet,{"status":"partial"},self.request)["finding"]["status"],"incomplete")
        request = copy.deepcopy(self.request)
        request["config"]["threshold"] = 1e8
        packet = {**self.packet,"witness":None,"search":{"stopping_reason":"budget_exhausted"}}
        self.assertEqual(make_view(packet,{"status":"passed"},request)["finding"]["status"],"incomplete")


if __name__ == "__main__":
    unittest.main()
