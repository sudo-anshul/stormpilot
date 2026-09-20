import copy
import unittest
from pathlib import Path

from validation.metrics import EvidenceError
from .core import holdout_request, load_protocol
from .declared import prepare_declared_suite


class DeclaredSuiteTests(unittest.TestCase):
    def setUp(self):
        self.protocol, _ = load_protocol(Path(__file__).with_name("protocol.json"))
        self.packet = dict(
            request=dict(scenario_id="custom_test", rainfall_multiplier=1, noise_std_m=0, seed=42,
                         faults=[dict(id="sensor", type="sensor_bias", asset="basin", start_s=0, end_s=400, bias_m=1),
                                 dict(id="valve", type="valve_stuck", asset="outlet", start_s=400, end_s=700, setting=0.1)]),
            experiment=dict(horizon_s=900, test_contract=dict(metric="flood_volume_m3", units="m3", mode="absolute",
                                                            direction="above", threshold=50, tolerance=1e-6, horizon_s=900)),
            model=dict(assets=[dict(id="outlet")], nodes=[dict(id="basin", type="basin")]),
            runs=[dict(run_id="reference", controller=dict(id="constant_flow", parameters=dict(target_scale=1, targets_m3s=[0.2], control_interval_s=300))),
                  dict(run_id="candidate", controller=dict(id="balanced_flow", parameters=dict(target_scale=0.98, balance_gain=2, targets_m3s=[0.196], control_interval_s=300)))],
        )

    def test_derived_suite_preserves_recorded_model_horizon_and_policies(self):
        request, spec, protocol = prepare_declared_suite(self.packet, "reference", "candidate", ["sensor", "valve"], self.protocol)
        self.assertEqual(protocol["scenario_id"], "custom_test")
        self.assertEqual(protocol["horizon_s"], 900)
        self.assertEqual(protocol["primary_contract"]["threshold"], 50)
        self.assertEqual(spec["candidate"]["parameters"], dict(target_scale=0.98, balance_gain=2))
        self.assertIn("not_heldout", protocol["status"])
        changed = holdout_request(dict(request=request), protocol["holdout_cases"][-1], protocol)
        self.assertTrue(all(0 <= f["start_s"] < f["end_s"] <= 900 for f in changed["faults"]))

    def test_unrecorded_policy_run_is_rejected(self):
        with self.assertRaisesRegex(EvidenceError, "recorded runs"):
            prepare_declared_suite(self.packet, "reference", "invented", ["sensor", "valve"], self.protocol)

    def test_two_valve_conditions_are_not_sensor_valve_suite(self):
        self.packet["request"]["faults"][0].update(type="valve_stuck", asset="outlet")
        with self.assertRaisesRegex(EvidenceError, "one recorded sensor"):
            prepare_declared_suite(self.packet, "reference", "candidate", ["sensor", "valve"], self.protocol)

    def test_sensor_asset_must_exist_in_recorded_model(self):
        self.packet["request"]["faults"][0]["asset"] = "other-basin"
        with self.assertRaisesRegex(EvidenceError, "assets"):
            prepare_declared_suite(self.packet, "reference", "candidate", ["sensor", "valve"], self.protocol)

    def test_nonflood_contract_is_explicitly_unsupported(self):
        self.packet["experiment"]["test_contract"]["metric"] = "peak_downstream_flow_m3s"
        with self.assertRaisesRegex(EvidenceError, "flood-volume"):
            prepare_declared_suite(self.packet, "reference", "candidate", ["sensor", "valve"], self.protocol)


if __name__ == "__main__":
    unittest.main()
