import copy
import unittest
from pathlib import Path

from validation.metrics import EvidenceError
from .core import assess_campaign, assess_table, holdout_request, load_protocol


class PredeclaredEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.protocol, self.digest = load_protocol(Path(__file__).with_name("protocol.json"))
        self.snapshot = dict(request=dict(
            scenario_id="theta", rainfall_multiplier=1, noise_std_m=0, seed=42,
            faults=[dict(id="a", type="valve_stuck", asset="1", start_s=0, end_s=3600, setting=0.1),
                    dict(id="b", type="sensor_bias", asset="P2", start_s=3600, end_s=7200, bias_m=1)],
            test_contract=self.protocol["primary_contract"]),
            reference=dict(controller_id="constant_flow", parameters=dict(target_scale=1)),
            candidate=dict(controller_id="balanced_flow", parameters=dict(target_scale=1, balance_gain=1)))
        self.table = {}
        for policy in ("reference", "candidate"):
            for subset, flood in dict(empty=0, a=20, b=30, ab=200 if policy == "reference" else 100).items():
                self.table[f"{policy}:{subset}"] = dict(flood_volume_m3=flood, downstream_excess_volume_m3=0,
                                                       peak_downstream_flow_m3s=0.4, terminal_storage_m3=5)
        self.cases = [dict(case_id=t["id"], status="completed", request=holdout_request(self.snapshot, t, self.protocol),
                           table=copy.deepcopy(self.table)) for t in self.protocol["holdout_cases"]]

    def test_protocol_digest_is_pinned(self):
        self.assertEqual(self.digest, "1cd92c48b91c465c9e18c0bca1c39cc112c9993c7e9e510061964f1672eb29b4")

    def test_second_protocol_is_separate_and_pinned_before_new_development(self):
        protocol, digest = load_protocol(Path(__file__).with_name("phase2") / "protocol.json")
        self.assertEqual(digest, "15e373f2f634a26a9fd8013853ab6618e1b57ef79877effea7a0ddf2ae1dadd7")
        self.assertEqual(len(protocol["holdout_cases"]), 8)
        self.assertEqual(protocol["holdout_transform_protocol"]["expected_policy_run_count"], 64)
        self.assertEqual(protocol["prior_phase"]["protocol_sha256"], self.digest)

    def test_type_specific_time_shift_is_applied_without_changing_other_fault(self):
        transform = copy.deepcopy(self.protocol["holdout_cases"][0])
        transform["fault_time_shift_s"] = {"sensor_bias": -300}
        result = holdout_request(self.snapshot, transform, self.protocol)
        self.assertEqual(result["faults"][0]["start_s"], 300)
        self.assertEqual(result["faults"][1]["start_s"], 3300)

    def test_true_pair_and_guarded_mitigation_meet_declared_criteria(self):
        result = assess_table(self.table, self.protocol)
        self.assertTrue(result["joint_failure"])
        self.assertEqual(result["interaction_excess_m3"], 150)
        self.assertTrue(result["mitigation_passes"])

    def test_single_failure_cannot_be_presented_as_joint_necessity(self):
        self.table["reference:a"]["flood_volume_m3"] = 101
        self.assertFalse(assess_table(self.table, self.protocol)["joint_failure"])

    def test_joint_threshold_crossing_does_not_imply_nonlinear_synergy(self):
        self.table["reference:a"]["flood_volume_m3"] = 70
        self.table["reference:b"]["flood_volume_m3"] = 70
        self.table["reference:ab"]["flood_volume_m3"] = 140
        result = assess_table(self.table, self.protocol)
        self.assertTrue(result["joint_failure"])
        self.assertFalse(result["material_superadditivity"])

    def test_complete_improving_suite_passes_predeclared_outcome(self):
        result = assess_campaign(self.cases, self.snapshot, self.protocol)
        self.assertTrue(result["heldout_usefulness_passes"])
        self.assertEqual(result["joint_aggregate_flood_reduction_m3"], 600)

    def test_missing_bad_case_cannot_claim_success(self):
        with self.assertRaisesRegex(EvidenceError, "omits"):
            assess_campaign(self.cases[:-1], self.snapshot, self.protocol)

    def test_duplicate_good_case_cannot_replace_another_case(self):
        self.cases[-1] = copy.deepcopy(self.cases[0])
        with self.assertRaisesRegex(EvidenceError, "duplicated"):
            assess_campaign(self.cases, self.snapshot, self.protocol)

    def test_changed_heldout_seed_is_rejected(self):
        self.cases[0]["request"]["seed"] = 42
        with self.assertRaisesRegex(EvidenceError, "frozen request"):
            assess_campaign(self.cases, self.snapshot, self.protocol)

    def test_good_primary_metric_cannot_hide_downstream_regression(self):
        self.cases[0]["table"]["candidate:ab"]["peak_downstream_flow_m3s"] += 0.01
        result = assess_campaign(self.cases, self.snapshot, self.protocol)
        self.assertFalse(result["all_case_guards_pass"])
        self.assertFalse(result["heldout_usefulness_passes"])

    def test_unfavorable_record_cannot_be_overridden_by_claim_flags(self):
        self.cases[0]["table"]["candidate:ab"]["flood_volume_m3"] = 250
        self.cases[0]["outcome"] = dict(heldout_usefulness_passes=True, verified=True)
        result = assess_campaign(self.cases, self.snapshot, self.protocol)
        self.assertFalse(result["heldout_usefulness_passes"])

    def test_invalid_simulation_prevents_complete_success(self):
        self.cases[0]["status"] = "failed"
        result = assess_campaign(self.cases, self.snapshot, self.protocol)
        self.assertFalse(result["heldout_usefulness_passes"])
        self.assertEqual(result["invalid_cases"], ["h1"])


if __name__ == "__main__":
    unittest.main()
