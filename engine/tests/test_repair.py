from pathlib import Path
import sys
import unittest

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ENGINE.parent))

from repair import normalize_repair, repair
from validation.validate_packet import validate_packet


class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = {"scenario_id": "theta", "controller_id": "constant_flow",
                       "controller_parameters": {"target_scale": 1},
                       "faults": [{"id": "a", "type": "sensor_bias", "asset": "P2", "bias_m": 1,
                                   "start_s": 10800, "end_s": 21600},
                                  {"id": "b", "type": "valve_stuck", "asset": "2", "setting": 0.035,
                                   "start_s": 21600, "end_s": 28800}],
                       "test_contract": {"metric": "flood_volume_m3", "threshold": 100},
                       "repair": {"target_scales": [0.98, 1], "balance_gains": [2], "budget": 12}}
        cls.result = repair(cls.request)

    def test_real_search_rejects_zero_flood_candidate_with_guard_failure(self):
        result = self.result
        search = result["repair"]
        self.assertEqual(search["simulator_calls"], 12)
        self.assertEqual(len(search["ledger"]), 12)
        self.assertEqual(len(result["runs"]), 8)
        self.assertTrue(search["grid_exhausted"])
        self.assertTrue(search["selected"]["eligible"])
        rejected = [c for c in search["candidates"] if not c["eligible"]]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["comparisons"]["ab"]["candidate"]["flood_volume_m3"], 0)
        self.assertTrue(any(f["criterion"] == "peak_downstream_flow_m3s" for f in rejected[0]["failures"]))
        self.assertGreater(search["selected"]["comparisons"]["ab"]["candidate"]["flood_volume_m3"], 0)
        self.assertEqual(validate_packet(result, ENGINE.parent)["status"], "passed")
        self.assertEqual({(r["evaluation_role"]["policy"], r["evaluation_role"]["subset"]) for r in result["runs"]},
                         {(p, s) for p in ("reference", "candidate") for s in ("empty", "a", "b", "ab")})

    def test_invalid_joint_premise_is_a_result_not_a_safety_claim(self):
        request = {**self.request, "test_contract": {"metric": "flood_volume_m3", "threshold": 1e6}}
        result = repair(request)
        self.assertEqual(result["repair"]["status"], "reference_not_joint_failure")
        self.assertEqual(result["repair"]["simulator_calls"], 4)
        self.assertEqual(result["repair"]["evaluated_candidates"], 0)
        self.assertIsNone(result["witness"])
        self.assertIsNone(result["repair"]["selected"])
        self.assertEqual(validate_packet(result, ENGINE.parent)["status"], "passed")

    def test_bounded_grid_and_contract_validation(self):
        for grid in [{"budget": True}, {"budget": 7}, {"target_scales": [1, 1]},
                     {"balance_gains": [float("nan")]}, {"balance_gains": [9]}, {"unknown": []}]:
            with self.assertRaises(ValueError):
                normalize_repair({**self.request, "repair": grid})
        with self.assertRaises(ValueError):
            normalize_repair({**self.request, "faults": []})
        with self.assertRaises(ValueError):
            normalize_repair({**self.request, "test_contract": {"metric": "terminal_storage_m3", "threshold": 100}})


if __name__ == "__main__":
    unittest.main()
