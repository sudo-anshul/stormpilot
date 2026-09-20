"""Synthetic negative tests for policy-search accounting, not hydraulics."""
import copy
import unittest

from .metrics import EvidenceError
from .repair import ACCEPTANCE, GUARDS, SUBSETS, audit_repair, digest


def fixture():
    base_metrics = dict(flood_volume_m3=0.0, peak_downstream_flow_m3s=0.4,
                        downstream_excess_volume_m3=0.0, terminal_storage_m3=5.0,
                        native_flood_volume_m3=0.0)
    contract = dict(metric="flood_volume_m3", threshold=100.0, tolerance=1e-6,
                    units="m3", mode="absolute", direction="above", horizon_s=10.0)
    packet = dict(request=dict(controller_id="constant_flow", controller_parameters=dict(target_scale=1.0),
                  fallback_controller_id="balanced_flow", fallback_controller_parameters=dict(target_scale=0.98, balance_gain=2.0),
                  faults=[dict(id="a"), dict(id="b")], test_contract=contract),
                  model=dict(targets_m3s=[0.2, 0.3]), artifacts=[dict(path="engine/controllers.py", sha256="1"*64)],
                  experiment=dict(solver_settings=dict(control_interval_s=300)), runs=[])
    ledger, generated, verified = [], {}, {}
    subsets = dict(empty=[], a=["a"], b=["b"], ab=["a", "b"])

    def run(policy, subset, parameters, candidate_id, flood, peak):
        metrics = dict(base_metrics, flood_volume_m3=flood, native_flood_volume_m3=flood, peak_downstream_flow_m3s=peak)
        controller = dict(id="constant_flow" if policy == "reference" else "balanced_flow", source_sha256="1"*64,
                          parameters=dict(targets_m3s=[x*parameters["target_scale"] for x in packet["model"]["targets_m3s"]],
                                          control_interval_s=300, **parameters))
        trace = [dict(time_s=0, total_flooding_m3s=0, downstream_flow_m3s=0, total_storage_m3=0),
                 dict(time_s=10, total_flooding_m3s=flood/10, downstream_flow_m3s=peak, total_storage_m3=5)]
        record = dict(call=len(ledger)+1, policy=policy, subset=subset, candidate_id=candidate_id,
                      run_id=f"run-{len(ledger)+1}", controller=controller, active_fault_ids=subsets[subset], metrics=metrics,
                      contract_result=dict(violated=flood > 100.000001, metric="flood_volume_m3", value=flood,
                                           threshold=100.0, tolerance=1e-6, units="m3"),
                      continuity=dict(runoff_error_pct=0, routing_error_pct=0), trace_sha256=digest(trace), routing_steps=1, runtime_s=0.1)
        ledger.append(record)
        generated[record["run_id"]] = dict(record, trace=trace, evaluation_role=dict(policy=policy, subset=subset))
        verified[record["run_id"]] = dict(status="passed", computed_metrics={k:v for k,v in metrics.items() if k != "native_flood_volume_m3"})
        return record

    reference = {s: run("reference", s, dict(target_scale=1.0), None, 200.0 if s == "ab" else 0.0, 0.4) for s in SUBSETS}
    entries, rows = [], []
    for scale, flood, peak in ((0.98, 50.0, 0.4), (1.0, 10.0, 0.41)):
        parameters = dict(target_scale=scale, balance_gain=2.0)
        identifier = "policy-"+digest(parameters)[:12]
        candidate = {s: run("candidate", s, parameters, identifier, flood if s == "ab" else 0.0, peak) for s in SUBSETS}
        comparisons, failures = {}, []
        for subset in SUBSETS:
            changes = dict(flood_volume_m3=(flood-200 if subset == "ab" else 0.0), peak_downstream_flow_m3s=peak-0.4,
                           downstream_excess_volume_m3=0.0, terminal_storage_m3=0.0)
            guards = dict(peak_downstream_flow_m3s=peak == 0.4, downstream_excess_volume_m3=True, terminal_storage_m3=True)
            comparisons[subset] = dict(reference=reference[subset]["metrics"], candidate=candidate[subset]["metrics"], changes=changes, guards=guards)
            if peak != 0.4:
                failures.append(dict(subset=subset, criterion="peak_downstream_flow_m3s", increase=peak-0.4, allowance=0.001))
        entries.append(dict(candidate_id=identifier, controller_id="balanced_flow", parameters=parameters,
                            call_numbers=[candidate[s]["call"] for s in SUBSETS], eligible=not failures, failures=failures,
                            comparisons=comparisons, flood_reduction_m3=200-flood, relative_flood_reduction=(200-flood)/200))
        rows.append(candidate)
    config = dict(target_scales=[0.98,1.0], balance_gains=[2.0], budget=12)
    packet["repair"] = dict(schema_version="stormpilot.repair.v1", method="guard-first-causal-parameter-grid-v1",
                  acceptance=copy.deepcopy(ACCEPTANCE), budget=12, simulator_calls=12, proof_simulator_calls=8, cache_hits=0,
                  declared_grid=config, grid_sha256=digest(config), reference_request_sha256="2"*64,
                  declared_candidates=2, evaluated_candidates=2, candidates=entries, ledger=ledger,
                  grid_exhausted=True, stopping_reason="declared_grid_exhausted", status="candidate_found", selected=copy.deepcopy(entries[0]))
    packet["runs"] = [generated[r["run_id"]] for r in list(reference.values())+list(rows[0].values())]
    return packet, verified


class RepairAuditTests(unittest.TestCase):
    def setUp(self):
        self.packet, self.validated = fixture()
        self.repair = self.packet["repair"]

    def use_plausibility_family(self):
        for i, entry in enumerate(self.repair["candidates"]):
            parameters = dict(target_scale=1.0, jump_threshold_m=0.5, correction_fraction=0.5 if i == 0 else 1.0)
            identifier = "policy-" + digest(parameters)[:12]
            entry.update(controller_id="plausible_depth", candidate_id=identifier, parameters=parameters)
            for row in self.repair["ledger"][4+i*4:8+i*4]:
                row["candidate_id"] = identifier
                row["controller"].update(id="plausible_depth", parameters=dict(targets_m3s=[0.2,0.3], control_interval_s=300, **parameters))
        self.repair["selected"] = copy.deepcopy(self.repair["candidates"][0])
        self.packet["request"].update(fallback_controller_id="plausible_depth", fallback_controller_parameters=self.repair["selected"]["parameters"])
        self.repair["declared_grid"] = dict(controller_id="plausible_depth",target_scales=[1.0],jump_thresholds_m=[0.5],correction_fractions=[0.5,1.0],budget=12)
        self.repair["grid_sha256"] = digest(self.repair["declared_grid"])
        self.repair["reference_request"] = copy.deepcopy(self.packet["request"])
        self.repair["reference_request_sha256"] = digest(self.repair["reference_request"])

    def test_plausibility_family_and_embedded_reference_request_are_audited(self):
        self.use_plausibility_family()
        result = audit_repair(self.packet,self.validated)
        self.assertTrue(result["original_reference_request_digest_recomputed"])
        self.assertEqual(result["candidate_count"],2)

    def test_omitted_plausibility_grid_member_is_rejected(self):
        self.use_plausibility_family()
        self.repair["candidates"][1]["parameters"]["correction_fraction"] = 0.75
        with self.assertRaisesRegex(EvidenceError,"grid entries"): audit_repair(self.packet,self.validated)

    def test_changed_original_request_cannot_be_hidden_by_rehashing(self):
        self.use_plausibility_family()
        self.repair["reference_request"]["seed"] = 999
        self.repair["reference_request_sha256"] = digest(self.repair["reference_request"])
        with self.assertRaisesRegex(EvidenceError,"original request"): audit_repair(self.packet,self.validated)

    def test_embedded_original_request_digest_must_match_content(self):
        self.use_plausibility_family()
        self.repair["reference_request_sha256"] = "f"*64
        with self.assertRaisesRegex(EvidenceError,"embedded content"): audit_repair(self.packet,self.validated)

    def test_complete_record_retains_rejected_policy_and_scopes_trace_claim(self):
        result = audit_repair(self.packet, self.validated)
        self.assertEqual(result["rejected_candidate_count"], 1)
        self.assertEqual(result["full_trace_audited_calls"], 8)
        self.assertEqual(result["compact_only_calls"], 4)
        self.assertFalse(result["original_reference_request_digest_recomputed"])

    def test_generic_replay_roles_preserve_treatment_identity_without_optional_tags(self):
        roles = ["nominal","single_a","single_b","stress","mitigation_empty","mitigation_a","mitigation_b","fallback"]
        for run,role in zip(self.packet["runs"],roles):
            del run["evaluation_role"]
            run["role"] = role
        self.assertEqual(audit_repair(self.packet,self.validated)["full_trace_audited_calls"],8)

    def test_false_replay_role_cannot_replace_actual_policy_identity(self):
        self.packet["runs"][0].pop("evaluation_role")
        self.packet["runs"][0]["role"] = "fallback"
        with self.assertRaises(EvidenceError): audit_repair(self.packet,self.validated)

    def test_guard_failure_cannot_be_changed_to_eligible(self):
        self.repair["candidates"][1]["eligible"] = True
        self.repair["candidates"][1]["failures"] = []
        with self.assertRaises(EvidenceError): audit_repair(self.packet, self.validated)

    def test_rejected_candidate_cannot_be_omitted(self):
        self.repair["candidates"].pop()
        self.repair["evaluated_candidates"] = 1
        with self.assertRaises(EvidenceError): audit_repair(self.packet, self.validated)

    def test_rejected_low_flood_candidate_cannot_replace_guarded_selection(self):
        self.repair["selected"] = copy.deepcopy(self.repair["candidates"][1])
        with self.assertRaisesRegex(EvidenceError, "selected candidate"): audit_repair(self.packet, self.validated)

    def test_changed_compact_metric_cannot_escape_comparison_check(self):
        self.repair["ledger"][8]["metrics"]["terminal_storage_m3"] = 25
        with self.assertRaises(EvidenceError): audit_repair(self.packet, self.validated)

    def test_full_trace_digest_must_match_selected_ledger(self):
        self.packet["runs"][-1]["trace"][-1]["total_storage_m3"] = 6
        with self.assertRaisesRegex(EvidenceError, "trace digest"): audit_repair(self.packet, self.validated)

    def test_call_duplication_and_budget_forgery_fail(self):
        self.repair["ledger"][5]["call"] = 5
        with self.assertRaisesRegex(EvidenceError, "call numbers"): audit_repair(self.packet, self.validated)

    def test_distinct_calls_cannot_reuse_a_run_identity(self):
        self.repair["ledger"][5]["run_id"] = self.repair["ledger"][4]["run_id"]
        with self.assertRaisesRegex(EvidenceError, "duplicates a run ID"): audit_repair(self.packet, self.validated)

    def test_permissive_guard_declaration_is_rejected(self):
        self.repair["acceptance"]["guard_maximum_increase"]["peak_downstream_flow_m3s"] = 1
        with self.assertRaisesRegex(EvidenceError, "fixed repair acceptance"): audit_repair(self.packet, self.validated)

    def test_failed_independent_trace_check_cannot_be_ignored(self):
        self.validated[self.packet["runs"][0]["run_id"]]["status"] = "failed"
        with self.assertRaisesRegex(EvidenceError, "independent trace"): audit_repair(self.packet, self.validated)

    def test_call_bound_stopping_can_preserve_an_incomplete_grid(self):
        self.repair["candidates"] = self.repair["candidates"][:1]
        self.repair["ledger"] = self.repair["ledger"][:8]
        self.repair.update(budget=8,simulator_calls=8,evaluated_candidates=1,grid_exhausted=False,stopping_reason="candidate_budget_exhausted")
        self.repair["declared_grid"]["budget"] = 8
        self.repair["grid_sha256"] = digest(self.repair["declared_grid"])
        self.assertFalse(audit_repair(self.packet,self.validated)["grid_exhausted"])

    def test_changed_grid_digest_is_rejected(self):
        self.repair["declared_grid"]["target_scales"][0] = 0.95
        with self.assertRaisesRegex(EvidenceError,"grid digest"): audit_repair(self.packet,self.validated)


if __name__ == "__main__":
    unittest.main()
