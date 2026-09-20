from pathlib import Path
import sys
import unittest

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

from controllers import commands, normalize_parameters, plausible_observations


class SensorPlausibilityTests(unittest.TestCase):
    def setUp(self):
        self.parameters = normalize_parameters("plausible_depth", {"correction_fraction": 0.5})

    def test_smooth_physical_rise_passes_through(self):
        state = {}
        for depth in [0.2, 0.23, 0.27, 0.32, 0.36, 0.4]:
            self.assertEqual(plausible_observations({"basin": depth}, self.parameters, state)["basin"], depth)
        self.assertEqual(state["basin"]["events"], 0)

    def test_positive_step_is_persistent_and_opposite_step_releases(self):
        state = {}
        for depth in [0.2, 0.23, 0.26, 0.29]:
            plausible_observations({"basin": depth}, self.parameters, state)
        corrected = plausible_observations({"basin": 1.32}, self.parameters, state)["basin"]
        self.assertAlmostEqual(corrected, 0.82)
        self.assertAlmostEqual(plausible_observations({"basin": 1.35}, self.parameters, state)["basin"], 0.85)
        self.assertAlmostEqual(plausible_observations({"basin": 0.38}, self.parameters, state)["basin"], 0.38)
        self.assertEqual(state["basin"]["offset"], 0)

    def test_negative_step_and_return_do_not_create_false_positive_bias(self):
        state = {}
        for depth in [1.0, 1.03, 1.06, 0.09, 0.12, 1.15]:
            self.assertAlmostEqual(plausible_observations({"basin": depth}, self.parameters, state)["basin"], depth)
        self.assertEqual(state["basin"]["offset"], 0)

    def test_runs_and_sensors_do_not_share_memory(self):
        first, second = {}, {}
        plausible_observations({"a": 0.2, "b": 0.2}, self.parameters, first)
        plausible_observations({"a": 1.2, "b": 0.2}, self.parameters, first)
        self.assertEqual(first["b"]["offset"], 0)
        result = plausible_observations({"a": 1.2, "b": 0.2}, self.parameters, second)
        self.assertEqual(result["a"], 1.2)

    def test_state_is_required_and_commands_remain_bounded(self):
        assets = [{"id": "outlet", "node_id": "basin", "area_m2": 1, "discharge_coefficient": 1}]
        parameters = {**self.parameters, "targets_m3s": [0.2]}
        with self.assertRaises(ValueError):
            commands("plausible_depth", {"basin": 0.2}, assets, {"basin": 2}, parameters)
        state = {}
        for depth in [0.2, 1.2, -2, 0, 5]:
            result = commands("plausible_depth", {"basin": depth}, assets, {"basin": 2}, parameters, state)
            self.assertGreaterEqual(result["outlet"], 0)
            self.assertLessEqual(result["outlet"], 1)

    def test_history_cap_stops_an_unrelated_low_reading_adding_flow(self):
        assets = [{"id": n, "node_id": n, "area_m2": 1, "discharge_coefficient": 1} for n in ("a", "b")]
        parameters = {**self.parameters, "targets_m3s": [0.2, 0.2]}
        state = {}
        for measured in [{"a": 0.5, "b": 0.5}] * 3 + [{"a": 0.5, "b": 1.5}]:
            commands("plausible_depth", measured, assets, {"a": 2, "b": 2}, parameters, state)
        result = commands("plausible_depth", {"a": 0.05, "b": 1.5}, assets, {"a": 2, "b": 2}, parameters, state)
        self.assertLess(state["a"]["aggregate_cap_scale"], 1)
        self.assertLess(result["a"], 0.2 / (2 * 9.81 * 0.05) ** 0.5)
        commands("plausible_depth", {"a": 0.5, "b": 0.5}, assets, {"a": 2, "b": 2}, parameters, state)
        self.assertEqual(state["b"]["aggregate_cap_scale"], 1)


if __name__ == "__main__":
    unittest.main()
