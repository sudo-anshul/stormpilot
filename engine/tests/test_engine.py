import copy
import json
from pathlib import Path
import sys
import unittest

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
from investigate import investigate
from models import metadata
from replay import replay
from runner import normal_draw, packet, prepare, run_simulation


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads((ENGINE / "examples/default-request.json").read_text())

    def test_native_run_replay_and_trace_integral(self):
        request = {**self.request, "noise_std_m": 0.03}
        first = run_simulation(request)
        second = run_simulation(request)
        self.assertEqual(first["trace"], second["trace"])
        self.assertEqual(first["display_trace"], second["display_trace"])
        self.assertEqual(first["trace"][0]["time_s"], 0)
        self.assertEqual(first["trace"][-1]["time_s"], metadata("theta")["horizon_s"])
        integrated = sum(b["total_flooding_m3s"]*(b["time_s"]-a["time_s"])
                         for a,b in zip(first["trace"],first["trace"][1:]))
        self.assertAlmostEqual(integrated, first["metrics"]["native_flood_volume_m3"], places=6)

    def test_perturbation_and_fallback_tradeoff(self):
        result = packet(self.request)
        nominal, stress, fallback = result["runs"]
        self.assertEqual(nominal["metrics"]["flood_volume_m3"], 0)
        self.assertGreater(stress["metrics"]["flood_volume_m3"], 1500)
        self.assertLess(fallback["metrics"]["flood_volume_m3"], stress["metrics"]["flood_volume_m3"])
        self.assertGreater(fallback["metrics"]["peak_downstream_flow_m3s"], stress["metrics"]["peak_downstream_flow_m3s"])
        self.assertEqual(nominal["context"], stress["context"])
        self.assertEqual(stress["context"], fallback["context"])
        self.assertNotEqual(stress["trace"], fallback["trace"])

    def test_exogenous_noise_is_call_order_independent(self):
        expected = normal_draw(42,"P1",300)
        for t in [900,0,600,300]:
            normal_draw(42,"P2",t)
        self.assertEqual(expected, normal_draw(42,"P1",300))
        self.assertNotEqual(expected, normal_draw(43,"P1",300))

    def test_declared_two_condition_reduction_and_budget(self):
        request = copy.deepcopy(self.request)
        request["faults"].append({"id":"f2","type":"valve_stuck","asset":"2","start_s":108000,"end_s":111600,"setting":0})
        result = investigate(request)
        witness = next(r for r in result["runs"] if r["run_id"] == result["witness"]["run_id"])
        self.assertEqual(witness["active_fault_ids"], ["f1"])
        self.assertEqual(result["witness"]["claim"], "1-minimal")
        self.assertLessEqual(result["search"]["simulator_calls"], request["search_budget"])
        self.assertTrue(result["search"]["nominal_passes"])
        self.assertFalse(result["search"]["global_minimality_claimed"])
        replayed = replay(result)
        by_id = {r["run_id"]: r for r in replayed["runs"]}
        for run in result["runs"]:
            self.assertEqual(run["trace"], by_id[run["run_id"]]["trace"])

    def test_empty_stress_and_nominal_violation_are_honest(self):
        request = {**self.request, "faults": []}
        result = investigate(request)
        self.assertEqual(result["search"]["status"], "no_violation_found")
        self.assertIsNone(result["witness"])
        request = {**self.request, "controller_id":"uncontrolled", "test_contract":{"metric":"peak_downstream_flow_m3s","threshold":0.1}}
        result = investigate(request)
        self.assertEqual(result["search"]["status"], "nominal_violation")
        self.assertIsNone(result["witness"])

    def test_input_bounds_and_fault_identity(self):
        for patch in [{"noise_std_m": float("nan")}, {"scenario_id":"../../x"}, {"controller_id":"unknown"},
                      {"rainfall_multiplier": 100}, {"seed": True},
                      {"faults":[{"id":"x","type":"sensor_dropout","asset":"missing"}]}]:
            with self.assertRaises(ValueError):
                prepare({**self.request, **patch})

    def test_gamma_real_model_si_conversion(self):
        result = run_simulation({"scenario_id":"gamma","controller_id":"uncontrolled","faults":[]})
        self.assertEqual(result["trace"][-1]["time_s"], 561600)
        self.assertAlmostEqual(result["metrics"]["flood_volume_m3"],result["metrics"]["native_flood_volume_m3"],places=5)
        self.assertLess(abs(result["continuity"]["routing_error_pct"]),1.0)


if __name__ == "__main__":
    unittest.main()
