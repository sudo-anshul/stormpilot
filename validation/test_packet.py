"""Small synthetic records exercise evidence rejection, not hydraulic physics."""

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from .validate_packet import canonical_sha256, validate_packet


class PacketEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        files = {
            "engine/data/test.inp": "[RAINGAGES]\nR INTENSITY 0:05 1 TIMESERIES rain\n[TIMESERIES]\nrain 0 1\n",
            "engine/controllers.py": "# synthetic controller fixture\n",
            "engine/runner.py": "# synthetic producer fixture\n",
            "engine/native_bridge.c": "/* synthetic bridge fixture */\n",
            "engine/vendor/epa-swmm/src/solver/test.c": "/* synthetic solver fixture */\n",
        }
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        hashes = {name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()}
        self.model_rel = "engine/data/test.inp"
        base_hash = hashes[self.model_rel]
        rain_hash = canonical_sha256(dict(rain_gauges=[["R", "INTENSITY", "0:05", "1", "TIMESERIES", "rain"]], rows=[["rain", "0", "1"]]))
        exogenous = dict(seed=42, noise_std_m=0, noise_protocol="synthetic-test",
                         rainfall_sha256=rain_hash, faults=[dict(id="f1")])
        settings = dict(control_interval_s=10, fixture=True)
        context = dict(base_model_sha256=base_hash, effective_model_sha256=base_hash,
                       rainfall_sha256=rain_hash, exogenous_sha256=canonical_sha256(exogenous),
                       solver_settings_sha256=canonical_sha256(settings), horizon_s=10,
                       information_boundary_id="synthetic-test")
        contract = dict(metric="flood_volume_m3", threshold=10, tolerance=1e-6, units="m3",
                        horizon_s=10, mode="absolute", direction="above")
        self.packet = dict(
            schema_version="stormpilot.evidence.v1",
            experiment=dict(context, scenario_id="synthetic-test", metric_protocol="routing-step-right-rectangle-v1",
                            threshold_m3s=1, test_contract=contract, exogenous=exogenous,
                            solver_settings=settings, faults=exogenous["faults"]),
            request=dict(rainfall_multiplier=1, seed=42, noise_std_m=0, faults=exogenous["faults"],
                         test_contract=contract, scenario_id="synthetic-test"), test_contract_sha256=canonical_sha256(contract),
            provenance=dict(base_model_sha256=base_hash, model_path=self.model_rel,
                            runner_source_sha256=hashes["engine/runner.py"]),
            artifacts=[dict(path=p, sha256=h) for p, h in hashes.items()], runs=[],
        )
        bundle = hashlib.sha256()
        for name in ["vendor/epa-swmm/src/solver/test.c", "native_bridge.c"]:
            bundle.update(name.encode() + b"\0" + files["engine/" + name].encode())
        self.packet["provenance"]["engine_source_sha256"] = bundle.hexdigest()
        controller = dict(id="test-policy", source_sha256=hashes["engine/controllers.py"], parameters={})
        self.packet["runs"] = [
            self.make_run("nominal", [], controller, context, 0),
            self.make_run("stress", ["f1"], controller, context, 2),
            self.make_run("removed", [], controller, context, 0),
            self.make_run("fallback", ["f1"], dict(controller, id="test-fallback"), context, 0.5),
        ]
        self.packet["ablations"] = [dict(source_run_id="stress", run_id="removed", removed_fault_ids=["f1"])]
        self.packet["witness"] = dict(run_id="stress", original_run_id="stress", claim="1-minimal",
                                      single_removals=[dict(fault_id="f1", run_id="removed")])
        self.packet["fallback"] = dict(stressed_run_id="stress", fallback_run_id="fallback",
                                       primary_metric="flood_volume_m3", minimum_improvement=0,
                                       tolerance=1e-6, maximum_increase=dict(downstream_excess_volume_m3=0,
                                       peak_downstream_flow_m3s=0, terminal_storage_m3=0),
                                       claim="guarded_improvement")

    @staticmethod
    def make_run(identifier, faults, controller, context, rate):
        return dict(run_id=identifier, role=identifier, context=copy.deepcopy(context),
                    controller=copy.deepcopy(controller), active_fault_ids=faults,
                    units=dict(time="s", flow="m3/s", volume="m3", depth="m"), routing_steps=1,
                    trace=[dict(time_s=0, total_flooding_m3s=0, total_storage_m3=0, downstream_flow_m3s=0),
                           dict(time_s=10, total_flooding_m3s=rate, total_storage_m3=5, downstream_flow_m3s=1)],
                    metrics=dict(flood_volume_m3=rate*10, native_flood_volume_m3=rate*10,
                                 downstream_excess_volume_m3=0, peak_downstream_flow_m3s=1, terminal_storage_m3=5),
                    continuity=dict(runoff_error_pct=0, routing_error_pct=0))

    def report(self):
        return validate_packet(self.packet, self.root)

    def assert_failed_check(self, part):
        report = self.report()
        self.assertEqual(report["status"], "failed", report)
        self.assertTrue(any(part in c["id"] and c["status"] == "failed" for c in report["checks"]), report)

    def test_complete_synthetic_packet_passes_recorded_checks_only(self):
        report = self.report()
        self.assertEqual(report["status"], "passed", report)
        self.assertEqual(report["replay_status"], "unperformed")
        self.assertEqual(report["scope"], "recorded_evidence")
        self.assertTrue(report["claims"]["fallback"]["guarded_improvement"])

    def test_changed_rain_identity_fails_fairness(self):
        self.packet["runs"][1]["context"]["rainfall_sha256"] = "f" * 64
        self.assert_failed_check("shared_context")

    def test_changed_exogenous_content_fails_even_if_run_hashes_match(self):
        self.packet["experiment"]["exogenous"]["seed"] = 100
        self.assert_failed_check("canonical_fingerprints")

    def test_rewritten_all_rain_hashes_still_fails_against_artifact(self):
        new = "f" * 64
        self.packet["experiment"]["rainfall_sha256"] = new
        self.packet["experiment"]["exogenous"]["rainfall_sha256"] = new
        digest = canonical_sha256(self.packet["experiment"]["exogenous"])
        self.packet["experiment"]["exogenous_sha256"] = digest
        for run in self.packet["runs"]:
            run["context"]["rainfall_sha256"] = new
            run["context"]["exogenous_sha256"] = digest
        self.assert_failed_check("rainfall_provenance")

    def test_wrong_horizon_fails(self):
        self.packet["runs"][1]["context"]["horizon_s"] = 11
        self.assert_failed_check("shared_context")

    def test_changed_contract_requires_new_fingerprint(self):
        self.packet["experiment"]["test_contract"]["threshold"] = 200
        self.assert_failed_check("canonical_fingerprints")

    def test_incorrect_replay_request_fails(self):
        self.packet["request"]["seed"] = 300
        self.assert_failed_check("canonical_fingerprints")

    def add_search_record(self):
        self.packet["request"]["controller_id"] = "test-policy"
        self.packet["search"] = dict(
            budget=3, simulator_calls=3, envelope_fault_ids=["f1"], global_minimality_claimed=False,
            candidates=[dict(run_id="nominal", active_fault_ids=[], violated=False, metric="flood_volume_m3", units="m3", value=0),
                        dict(run_id="stress", active_fault_ids=["f1"], violated=True, metric="flood_volume_m3", units="m3", value=20)],
            nominal_passes=True, status="witness_found", stopping_reason="single_deletion_neighborhood_complete",
        )

    def test_recorded_search_coverage_passes(self):
        self.add_search_record()
        self.assertEqual(self.report()["status"], "passed")

    def test_false_search_budget_accounting_fails(self):
        self.add_search_record()
        self.packet["search"]["simulator_calls"] = 2
        self.assert_failed_check("search_consistency")

    def test_false_search_candidate_conclusion_fails(self):
        self.add_search_record()
        self.packet["search"]["candidates"][1]["violated"] = False
        self.assert_failed_check("search_consistency")

    def test_false_reported_integral_fails(self):
        self.packet["runs"][1]["metrics"]["flood_volume_m3"] = 2
        self.assert_failed_check("trace_metrics")

    def test_duplicate_timestamp_fails(self):
        self.packet["runs"][1]["trace"][1]["time_s"] = 0
        self.assert_failed_check("trace_metrics")

    def test_nonfinite_trace_fails(self):
        self.packet["runs"][1]["trace"][1]["total_flooding_m3s"] = float("nan")
        self.assert_failed_check("trace_metrics")

    def test_nonfinite_diagnostic_fails(self):
        self.packet["runs"][1]["continuity"]["routing_error_pct"] = float("inf")
        self.assert_failed_check("continuity")

    def test_missing_diagnostic_is_explicitly_unperformed(self):
        del self.packet["runs"][1]["continuity"]
        report = self.report()
        self.assertEqual(report["status"], "partial", report)
        self.assertTrue(any(c["id"] == "stress:continuity" and c["status"] == "unperformed" for c in report["checks"]))

    def test_ablation_cannot_add_a_fault(self):
        self.packet["runs"][2]["active_fault_ids"] = ["other"]
        self.assert_failed_check("ablation")

    def test_ablation_cannot_change_policy(self):
        self.packet["runs"][2]["controller"]["id"] = "other-policy"
        self.assert_failed_check("ablation")

    def test_fallback_cannot_receive_fewer_faults(self):
        self.packet["runs"][3]["active_fault_ids"] = []
        self.assert_failed_check("fallback_comparison")

    def test_minimality_requires_single_removal_evidence(self):
        self.packet["witness"]["single_removals"] = []
        self.assert_failed_check("witness")

    def test_fake_verified_boolean_cannot_support_minimality(self):
        self.packet["verified"] = True
        self.packet["witness"]["verified"] = True
        self.packet["witness"]["single_removals"] = []
        self.assert_failed_check("witness")

    def test_single_removal_that_still_fails_disproves_minimality(self):
        run = self.packet["runs"][2]
        run["trace"][1]["total_flooding_m3s"] = 1.5
        run["metrics"]["flood_volume_m3"] = run["metrics"]["native_flood_volume_m3"] = 15
        self.assert_failed_check("witness")

    def test_primary_improvement_cannot_hide_terminal_regression(self):
        run = self.packet["runs"][3]
        run["trace"][1]["total_storage_m3"] = 100
        run["metrics"]["terminal_storage_m3"] = 100
        self.assert_failed_check("fallback_claim")

    def test_changed_artifact_fails(self):
        (self.root / self.model_rel).write_text("altered\n")
        self.assert_failed_check("artifact:")

    def test_missing_artifact_fails(self):
        (self.root / "engine/controllers.py").unlink()
        self.assert_failed_check("artifact:")

    def test_artifact_path_cannot_escape_root(self):
        self.packet["artifacts"][0]["path"] = "../outside"
        self.assert_failed_check("artifact:")

    def test_invalid_optional_relation_type_reports_failure(self):
        self.packet["ablations"] = 7
        self.assert_failed_check("ablations")

    def test_absent_artifact_root_is_partial(self):
        report = validate_packet(self.packet)
        self.assertEqual(report["status"], "partial", report)

    def add_imported_model(self):
        old_path = self.root / self.model_rel
        custom = dict(name="Synthetic imported fixture", inp_text=old_path.read_text(), downstream_link="out",
                      downstream_threshold_m3s=1.0, targets_m3s=[0.5])
        scenario = "custom_" + canonical_sha256(custom)[:24]
        new_rel = f"engine/data/imports/{scenario}.inp"
        new_path = self.root / new_rel
        new_path.parent.mkdir(parents=True)
        old_path.rename(new_path)
        self.packet["request"].update(custom_model=custom, scenario_id=scenario)
        self.packet["experiment"]["scenario_id"] = scenario
        self.packet["provenance"]["model_path"] = new_rel
        self.packet["model"] = dict(id=scenario, origin="imported", base_model_sha256=self.packet["experiment"]["base_model_sha256"],
                                     downstream_link="out", threshold_m3s=1.0, targets_m3s=[0.5],
                                     mapping_sha256=canonical_sha256({k: v for k, v in custom.items() if k != "inp_text"}))
        for artifact in self.packet["artifacts"]:
            if artifact["path"] == self.model_rel:
                artifact["path"] = new_rel
        self.model_rel = new_rel

    def test_complete_imported_identity_passes(self):
        self.add_imported_model()
        self.assertEqual(self.report()["status"], "passed")

    def test_imported_mapping_change_is_rejected(self):
        self.add_imported_model()
        self.packet["model"]["downstream_link"] = "different-link"
        self.assert_failed_check("custom_model_identity")

    def test_imported_text_change_is_rejected(self):
        self.add_imported_model()
        self.packet["request"]["custom_model"]["inp_text"] += "; new bytes\n"
        self.assert_failed_check("custom_model_identity")

    def test_imported_payload_cannot_be_omitted(self):
        self.add_imported_model()
        del self.packet["request"]["custom_model"]
        self.assert_failed_check("custom_model_identity")


if __name__ == "__main__":
    unittest.main()
