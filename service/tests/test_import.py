import copy
from pathlib import Path
import tempfile
import unittest
import json
import subprocess
import sys
import zipfile
from unittest.mock import patch

from engine.models import ROOT, custom_model_id, inspect_input, metadata, normalize_custom_model
from service import models
from service.present import engine_request, normalize_config
from service.common import write_json
from service.archive import build_archive
from validation.validate_packet import validate_packet


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "data/theta.inp").read_text()

    def payload(self):
        return {"name": "Imported network", "inp_text": self.text, "downstream_link": "8",
                "downstream_threshold_m3s": 0.5, "targets_m3s": [0.24, 0.26]}

    def test_inspection_preserves_input_and_requires_explicit_mapping(self):
        payload = self.payload()
        self.assertEqual(inspect_input(payload["name"], self.text)["duration_hours"], 78)
        normalized = normalize_custom_model(payload)
        self.assertEqual(normalized["inp_text"], self.text)
        model = metadata(custom_model_id(normalized), normalized)
        self.assertEqual(model["targets_m3s"], [0.24, 0.26])
        self.assertEqual(model["origin"], "imported")
        for changes in ({"downstream_link": "missing"}, {"targets_m3s": [0.2]},
                        {"targets_m3s": [float("nan"), 1]}, {"downstream_threshold_m3s": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_custom_model({**payload, **changes})

    def test_external_files_and_ambiguous_sections_never_reach_swmm(self):
        malicious = [
            self.text + "\n[FILES]\nUSE HOTSTART /etc/passwd\n",
            self.text + "\n[TEMPERATURE]\nFILE /etc/passwd\n",
            self.text.replace("[TIMESERIES]", "[TIMESERIES]\nforeign FILE /etc/passwd"),
            self.text.replace("[OPTIONS]", "[OPTIONS]\nTEMPDIR /tmp/elsewhere"),
            self.text.replace("[OPTIONS]", "[OPTIONS]\nTEM /tmp/elsewhere"),
            self.text + "\n[CONTROLS]\nRULE hidden\n",
            self.text + "\n[OPTIONS]\nFLOW_UNITS CMS\n",
            self.text + "\x00",
        ]
        for text in malicious:
            with self.subTest(suffix=text[-90:]), self.assertRaises(ValueError):
                inspect_input("test", text)

    def test_import_scope_and_native_units_are_checked(self):
        for text in ("x" * 262145, self.text.replace("DYNWAVE", "KINWAVE"),
                     self.text.replace("BOTTOM", "SIDE"), self.text.replace("RECT_CLOSED", "CIRCULAR")):
            with self.assertRaises(ValueError):
                inspect_input("test", text)
        imperial = self.text.replace("CMS", "GPM")
        custom = normalize_custom_model({**self.payload(), "inp_text": imperial})
        model = metadata(custom_model_id(custom), custom)
        self.assertAlmostEqual(model["nodes"][0]["max_depth_m"], 0.6096)

    def test_registration_identity_and_fresh_requests_are_portable(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(models, "REGISTRY", Path(directory)):
            inspected = models.inspect_model({"name": "Own catchment", "inp_text": self.text})
            model = models.register_model({"token": inspected["token"], "downstream_link": "8", "downstream_threshold_m3s": 0.5})
            self.assertEqual(model["targets_m3s"], [0.25, 0.25])
            config = normalize_config({"model_id": model["id"]})
            native = engine_request(config)
            self.assertEqual(native["custom_model"]["inp_text"], self.text)
            before = copy.deepcopy(native["custom_model"])
            before["downstream_threshold_m3s"] = 0.6
            with self.assertRaises(ValueError):
                metadata(model["id"], before)
            with self.assertRaises(ValueError):
                models.resolve_model("../../private")

    def test_imported_model_executes_and_exports_its_exact_input(self):
        custom = normalize_custom_model(self.payload())
        native = {"scenario_id": custom_model_id(custom), "custom_model": custom,
                  "controller_id": "constant_flow", "fallback_controller_id": "balanced_flow",
                  "fallback_controller_parameters": {"target_scale": 0.98, "balance_gain": 2},
                  "faults": [{"id": "biased-level", "type": "sensor_bias", "asset": "P2", "bias_m": 1,
                              "start_s": 10800, "end_s": 21600}]}
        with tempfile.TemporaryDirectory(prefix="stormpilot-import-test-") as directory:
            folder = Path(directory)
            write_json(folder / "engine-request.json", native)
            completed = subprocess.run([sys.executable, "engine/cli.py", "run", "--request", str(folder / "engine-request.json"),
                                        "--output", str(folder / "packet.json")], cwd=ROOT.parent, capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            packet = json.loads((folder / "packet.json").read_text())
            validation = validate_packet(packet, root_path=ROOT.parent)
            self.assertEqual(validation["status"], "passed", [c for c in validation["checks"] if c["status"] != "passed"])
            write_json(folder / "validation.json", validation)
            archive = build_archive(folder)
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(bundle.read(packet["provenance"]["model_path"]), self.text.encode())
                self.assertEqual(json.loads(bundle.read("packet.json"))["request"]["custom_model"], custom)


if __name__ == "__main__":
    unittest.main()
