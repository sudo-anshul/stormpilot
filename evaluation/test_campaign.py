"""Execution-boundary regression tests without native hydraulic simulation."""
import contextlib
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation.metrics import EvidenceError
from .core import load_protocol
from .run_campaign import run_holdout


class CampaignBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.protocol, self.protocol_hash = load_protocol(Path(__file__).with_name("protocol.json"))

    def test_rejected_full_packets_are_retained_with_failure_labels(self):
        snapshot = dict(reference={}, candidate={})
        raw = b'{"deliberately_invalid_packet":true}'

        def worker(command, **kwargs):
            Path(command[command.index("--output")+1]).write_bytes(raw)
            return type("Completed", (), {"returncode":0})()

        def report(cases, snapshot, protocol, protocol_hash, snapshot_hash, retained, suite_type):
            self.assertTrue(all(c["status"] == "failed" for c in cases))
            self.assertEqual(len(retained),6)
            self.assertTrue(all(c["validation_status"] == "failed" for c in retained))
            return dict(status="completed_with_invalid_cases", acceptance=dict(overall=False), retained_packets=retained)

        with patch("evaluation.run_campaign._load_snapshot", return_value=(snapshot,"a"*64)), \
             patch("evaluation.run_campaign.check_sources"), \
             patch("evaluation.run_campaign.holdout_request", return_value={}), \
             patch("evaluation.run_campaign.subprocess.run", side_effect=worker), \
             patch("evaluation.run_campaign.assess_case", side_effect=EvidenceError("Invalid trace")), \
             patch("evaluation.run_campaign.make_report", side_effect=report), contextlib.redirect_stdout(io.StringIO()):
            result = run_holdout(self.root/"unused.json",Path(__file__).with_name("protocol.json"),self.root/"cases",self.root/"report.json")
        self.assertFalse(result["acceptance"]["overall"])
        self.assertEqual(len(list((self.root/"cases").glob("*-packet.json.gz"))),6)
        for path in (self.root/"cases").glob("*-packet.json.gz"):
            self.assertEqual(gzip.decompress(path.read_bytes()),raw)
        self.assertFalse(list((self.root/"cases").glob("*-packet.json")))
        records=json.loads((self.root/"cases/case-records.json").read_text())
        self.assertTrue(all(c["error"] == "Invalid trace" for c in records))

    def test_source_change_is_rejected_before_any_worker_executes(self):
        with patch("evaluation.run_campaign._load_snapshot", return_value=({},"a"*64)), \
             patch("evaluation.run_campaign.check_sources", side_effect=EvidenceError("Frozen source changed")), \
             patch("evaluation.run_campaign.subprocess.run") as worker:
            with self.assertRaisesRegex(EvidenceError,"source changed"):
                run_holdout(self.root/"unused.json",Path(__file__).with_name("protocol.json"),self.root/"cases")
            worker.assert_not_called()
        self.assertFalse((self.root/"cases").exists())


if __name__ == "__main__":
    unittest.main()
