import copy
from pathlib import Path
import sys
import unittest

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ENGINE.parent))

from campaign import discover, normalize_discovery
from replay import replay
from runner import prepare, run_simulation
from validation.validate_packet import validate_packet


class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = {"scenario_id": "theta", "controller_id": "constant_flow",
                       "controller_parameters": {"target_scale": 1}, "fallback_controller_id": "balanced_flow",
                       "fallback_controller_parameters": {"target_scale": 0.98, "balance_gain": 2},
                       "test_contract": {"metric": "flood_volume_m3", "threshold": 100}, "faults": []}

    def test_real_joint_discovery_budget_evidence_and_parameter_replay(self):
        evidence = discover(self.request)
        discovery = evidence["discovery"]
        self.assertEqual(discovery["simulator_calls"], len(discovery["ledger"]))
        self.assertLessEqual(discovery["simulator_calls"], discovery["budget"])
        self.assertEqual(discovery["status"], "interaction_found")
        self.assertEqual(discovery["interaction_values"]["nominal"], 0)
        self.assertEqual(discovery["interaction_values"]["sensor_only"], 0)
        self.assertEqual(discovery["interaction_values"]["valve_only"], 0)
        self.assertGreater(discovery["interaction_values"]["joint"], 100)
        self.assertEqual(len(evidence["runs"]), 5)
        self.assertEqual(evidence["witness"]["claim"], "1-minimal")
        self.assertEqual(validate_packet(evidence, ENGINE.parent)["status"], "passed")
        replayed = replay(evidence)
        for first, second in zip(evidence["runs"], replayed["runs"]):
            self.assertEqual(first["trace"], second["trace"])
            self.assertEqual(first["controller"]["parameters"], second["controller"]["parameters"])

    def test_budget_exhaustion_does_not_claim_a_complete_grid(self):
        evidence = discover({**self.request, "discovery": {"budget": 9}})
        self.assertEqual(evidence["discovery"]["status"], "no_interaction_found")
        self.assertEqual(evidence["discovery"]["stopping_reason"], "screening_budget_exhausted")
        self.assertFalse(evidence["discovery"]["grid_exhausted"])
        self.assertIsNone(evidence["witness"])
        self.assertLessEqual(evidence["discovery"]["simulator_calls"], 9)
        self.assertEqual(validate_packet(evidence, ENGINE.parent)["status"], "passed")

    def test_same_controller_distinct_parameters_are_replayed_separately(self):
        from runner import packet
        request = copy.deepcopy(self.request)
        first = run_simulation(request, "nominal", "constant_flow", [], {"target_scale": 1})
        second = run_simulation(request, "fallback", "constant_flow", [], {"target_scale": 0.8})
        self.assertNotEqual(first["trace"], second["trace"])
        replayed = replay(packet(request, [first, second]))
        self.assertEqual(replayed["replay"]["unique_simulator_calls"], 2)
        self.assertEqual(second["trace"], replayed["runs"][1]["trace"])

    def test_parameters_and_discovery_grid_reject_ambiguous_values(self):
        invalid = [{"controller_parameters": {"target_scale": True}},
                   {"controller_parameters": {"typo": 1}},
                   {"fallback_controller_parameters": {"balance_gain": float("nan")}}]
        for update in invalid:
            with self.assertRaises(ValueError):
                prepare({**self.request, **update})
        for grid in [{"budget": True}, {"bias_values_m": [0.5, 0.5]},
                     {"sensor_windows_s": [[301, 1800]]}, {"sensor_asset": "absent"}, {"valve_settings": [2]}]:
            with self.assertRaises(ValueError):
                normalize_discovery({**self.request, "discovery": grid})


if __name__ == "__main__":
    unittest.main()
