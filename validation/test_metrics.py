import unittest

from .metrics import EvidenceError, compute_metrics
from .properties import compare_fallback, evaluate_property


def sample(t, flood, flow, storage=0):
    return dict(time_s=t, total_flooding_m3s=flood,
                downstream_flow_m3s=flow, total_storage_m3=storage)


class TraceArithmeticTests(unittest.TestCase):
    def test_irregular_intervals_have_physical_units(self):
        # 2 m3/s for 3 s followed by 4 m3/s for 7 s is 34 m3.
        trace = [sample(0, 0, 0), sample(3, 2, 3), sample(10, 4, 1, 9)]
        result = compute_metrics(trace, integration="right_rectangle", downstream_threshold_m3s=2)
        self.assertEqual(result, dict(flood_volume_m3=34, downstream_excess_volume_m3=3,
                                     peak_downstream_flow_m3s=3, terminal_storage_m3=9))

    def test_threshold_crossing_linear_integral(self):
        # Flow crosses 2 m3/s at 5 s; excess is a triangle of area 5 m3.
        result = compute_metrics([sample(0, 0, 0), sample(10, 0, 4)],
                                 integration="linear", downstream_threshold_m3s=2)
        self.assertEqual(result["downstream_excess_volume_m3"], 5)

    def test_reverse_flow_is_not_counted_as_positive_excess(self):
        result = compute_metrics([sample(0, 0, 0), sample(10, 0, -4)],
                                 integration="right_rectangle", downstream_threshold_m3s=2)
        self.assertEqual(result["downstream_excess_volume_m3"], 0)

    def test_invalid_times_or_nonfinite_values_are_rejected(self):
        invalid = [
            [sample(0, 0, 0)],
            [sample(0, 0, 0), sample(0, 0, 0)],
            [sample(2, 0, 0), sample(1, 0, 0)],
            [sample(0, 0, 0), sample(2, float("nan"), 0)],
            [sample(0, 0, 0), sample(2, 0, float("inf"))],
            [sample(0, 0, 0), sample(2, -1, 0)],
            [sample(0, 0, 0), sample(2, 0, 0, -1)],
            [sample(False, 0, 0), sample(2, 0, 0)],
        ]
        for trace in invalid:
            with self.subTest(trace=trace), self.assertRaises(EvidenceError):
                compute_metrics(trace, integration="right_rectangle", downstream_threshold_m3s=2)

    def test_incomplete_horizon_is_rejected(self):
        with self.assertRaisesRegex(EvidenceError, "end time"):
            compute_metrics([sample(0, 0, 0), sample(5, 0, 0)], integration="right_rectangle",
                            downstream_threshold_m3s=2, start_s=0, end_s=10)

    def test_finite_samples_that_overflow_integral_are_rejected(self):
        with self.assertRaises(EvidenceError):
            compute_metrics([sample(0, 0, 0), sample(1, 1e308, 0), sample(2, 1e308, 0)],
                            integration="right_rectangle", downstream_threshold_m3s=2)


class PropertyTests(unittest.TestCase):
    def test_material_increase_uses_declared_reference(self):
        prop = dict(metric="flood_volume_m3", unit="m3", mode="increase", direction="above",
                    bound=10, tolerance=0.1)
        self.assertFalse(evaluate_property(prop, {"flood_volume_m3": 30.1},
                                           {"flood_volume_m3": 20})["violated"])
        self.assertTrue(evaluate_property(prop, {"flood_volume_m3": 31},
                                          {"flood_volume_m3": 20})["violated"])

    def test_primary_improvement_does_not_hide_terminal_storage_regression(self):
        stressed = dict(flood_volume_m3=10, downstream_excess_volume_m3=1,
                        peak_downstream_flow_m3s=2, terminal_storage_m3=100)
        fallback = dict(stressed, flood_volume_m3=5, terminal_storage_m3=200)
        comparison = compare_fallback(stressed, fallback, dict(
            primary_metric="flood_volume_m3", minimum_improvement=0, tolerance=0.01,
            maximum_increase={key: 0 for key in stressed if key != "flood_volume_m3"}))
        self.assertTrue(comparison["primary_improved"])
        self.assertFalse(comparison["guarded_improvement"])
        self.assertFalse(comparison["changes"]["terminal_storage_m3"]["guard_passed"])

    def test_missing_guard_withholds_nonregression_claim(self):
        metrics = dict(flood_volume_m3=10, downstream_excess_volume_m3=1,
                       peak_downstream_flow_m3s=2, terminal_storage_m3=100)
        comparison = compare_fallback(metrics, dict(metrics, flood_volume_m3=5), dict(
            primary_metric="flood_volume_m3", minimum_improvement=0, tolerance=0.01,
            maximum_increase={"peak_downstream_flow_m3s": 0}))
        self.assertTrue(comparison["primary_improved"])
        self.assertFalse(comparison["guarded_improvement"])
        self.assertIn("terminal_storage_m3", comparison["missing_guards"])


if __name__ == "__main__":
    unittest.main()
