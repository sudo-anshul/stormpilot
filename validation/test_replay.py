import copy
import unittest

from .replay import compare_replay
from . import test_packet


class ReplayEvidenceTests(unittest.TestCase):
    def setUp(self):
        fixture = test_packet.PacketEvidenceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.original = fixture.packet
        self.replayed = copy.deepcopy(self.original)
        self.root = fixture.root

    def test_runtime_and_creation_time_do_not_affect_numerical_comparison(self):
        self.replayed["created_at"] = "a later timestamp"
        self.replayed["runs"][0]["runtime_s"] = 999
        report = compare_replay(self.original, self.replayed, self.root)
        self.assertEqual(report["status"], "passed", report)

    def test_consistent_but_different_replay_metric_is_rejected(self):
        changed = self.replayed["runs"][1]
        changed["trace"][1]["total_flooding_m3s"] = 2.01
        changed["metrics"]["flood_volume_m3"] = changed["metrics"]["native_flood_volume_m3"] = 20.1
        report = compare_replay(self.original, self.replayed, self.root)
        self.assertEqual(report["status"], "failed", report)
        self.assertIn("differs beyond tolerance", report["checks"][-1]["message"])

    def test_changed_policy_treatment_is_rejected(self):
        self.replayed["runs"][3]["controller"]["parameters"] = dict(target=10)
        report = compare_replay(self.original, self.replayed, self.root)
        self.assertEqual(report["status"], "failed", report)
        self.assertIn("controller parameters", report["checks"][-1]["message"])

    def test_missing_logical_run_is_rejected(self):
        self.replayed["runs"][0]["run_id"] = "renamed"
        report = compare_replay(self.original, self.replayed, self.root)
        self.assertEqual(report["status"], "failed", report)
        self.assertIn("logical run IDs", report["checks"][-1]["message"])


if __name__ == "__main__":
    unittest.main()
