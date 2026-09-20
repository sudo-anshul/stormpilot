"""Independent recorded-evidence checks. Run from the project root:

    python3 -m validation.validate_packet packet.json --root .

This module never imports the engine and never trusts producer validation flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .metrics import EvidenceError, METRIC_UNITS, close_enough, compute_metrics, finite_number
from .properties import compare_fallback, evaluate_property


SCHEMA_VERSION = "stormpilot.evidence.v1"
CONTEXT_FIELDS = (
    "base_model_sha256", "effective_model_sha256", "rainfall_sha256", "exogenous_sha256", "solver_settings_sha256",
    "horizon_s", "information_boundary_id",
)
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_UNITS = {"time": "s", "flow": "m3/s", "volume": "m3", "depth": "m"}
LIMITATIONS = [
    "Checks establish consistency of recorded evidence, not hydraulic calibration or field outcomes.",
    "Matching declared context cannot prove that arbitrary policy code lacked hidden information.",
    "A passing packet check is not an independently executed simulator replay or safety certificate.",
]


def _check(report: dict, identifier: str, status: str, message: str, *, required=True, **data):
    item = dict(id=identifier, status=status, message=message, required=required)
    if data:
        item["details"] = data
    report["checks"].append(item)


def _finish(report: dict) -> dict:
    statuses = [c["status"] for c in report["checks"] if c["required"]]
    report["status"] = "failed" if "failed" in statuses else (
        "partial" if "unperformed" in statuses else "passed"
    )
    report["scope"] = "recorded_evidence"
    report["replay_status"] = "unperformed"
    return report


def _object(value: Any, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise EvidenceError(f"{label} must be an object")
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise EvidenceError(f"{label} must be a lowercase SHA-256 digest")
    return value


def canonical_sha256(value: Any) -> str:
    """Declared canonical-JSON encoding; no simulator utility is imported."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def _faults(value: Any, label: str) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
        raise EvidenceError(f"{label} must be a list of nonempty fault IDs")
    if len(set(value)) != len(value):
        raise EvidenceError(f"{label} contains duplicate fault IDs")
    return set(value)


def _tolerances(experiment: Mapping) -> dict[str, float]:
    supplied = _object(experiment.get("numerical_tolerances", {}), "numerical_tolerances")
    defaults = dict(absolute=1e-6, relative=1e-8, time_s=1e-6, continuity_pct=1.0)
    for name, default in defaults.items():
        value = finite_number(supplied.get(name, default), f"tolerance {name}")
        if value < 0:
            raise EvidenceError(f"tolerance {name} must be nonnegative")
        defaults[name] = value
    # Evidence arithmetic cannot be made meaningless with a producer's huge tolerance.
    if defaults["relative"] > 1e-3 or defaults["absolute"] > 1e-2 or defaults["time_s"] > 0.1:
        raise EvidenceError("numerical tolerance exceeds supported evidence-check bounds")
    return defaults


def property_declaration(experiment: Mapping) -> dict:
    contract = _object(experiment.get("test_contract"), "test_contract")
    horizon = finite_number(contract.get("horizon_s"), "test contract horizon")
    if horizon != finite_number(experiment.get("horizon_s"), "experiment horizon"):
        raise EvidenceError("test contract and experiment horizons differ")
    return dict(metric=contract.get("metric"), unit=contract.get("units"),
                mode=contract.get("mode", "absolute"), direction=contract.get("direction", "above"),
                bound=contract.get("threshold"), tolerance=contract.get("tolerance"))


def validate_run(run: Mapping[str, Any], experiment: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one completed run against explicit shared experiment metadata."""
    report: dict[str, Any] = dict(run_id=run.get("run_id") if isinstance(run, Mapping) else None,
                                 checks=[], computed_metrics={}, limitations=list(LIMITATIONS))
    try:
        run = _object(run, "run")
        experiment = _object(experiment, "experiment")
        if not isinstance(run.get("run_id"), str) or not run["run_id"]:
            raise EvidenceError("run_id is required")
        if not isinstance(run.get("role"), str) or not run["role"]:
            raise EvidenceError("run role is required")
        controller = _object(run.get("controller"), "controller")
        if not isinstance(controller.get("id"), str) or not controller["id"]:
            raise EvidenceError("controller ID is required")
        _hash(controller.get("source_sha256"), "controller source hash")
        _object(controller.get("parameters"), "controller parameters")
        _faults(run.get("active_fault_ids"), "active faults")
        _check(report, "run_identity", "passed", "Run, controller and fault identities are explicit.")
    except (EvidenceError, TypeError) as exc:
        _check(report, "run_identity", "failed", str(exc))
        return _finish(report)

    try:
        context = _object(run.get("context"), "run context")
        for field in CONTEXT_FIELDS:
            if field not in context or field not in experiment:
                raise EvidenceError(f"missing common identity: {field}")
            if context[field] != experiment[field]:
                raise EvidenceError(f"run context differs from experiment: {field}")
            if field.endswith("sha256"):
                _hash(context[field], field)
        if not isinstance(context["information_boundary_id"], str) or not context["information_boundary_id"]:
            raise EvidenceError("information boundary must be a nonempty identifier")
        _check(report, "shared_context", "passed", "Declared model, weather, exogenous stream, settings, horizon and information boundary match.")
    except EvidenceError as exc:
        _check(report, "shared_context", "failed", str(exc))

    try:
        tolerance = _tolerances(experiment)
        if run.get("units") != EXPECTED_UNITS:
            raise EvidenceError("run must explicitly declare SI time, flow, volume and depth units")
        if experiment.get("metric_protocol") != "routing-step-right-rectangle-v1":
            raise EvidenceError("unsupported or missing metric protocol")
        horizon = finite_number(experiment.get("horizon_s"), "horizon")
        if horizon <= 0:
            raise EvidenceError("horizon must be positive")
        result = compute_metrics(run.get("trace"), integration="right_rectangle",
                                 downstream_threshold_m3s=experiment.get("threshold_m3s"),
                                 start_s=0, end_s=horizon, time_tolerance_s=tolerance["time_s"])
        reported = _object(run.get("metrics"), "reported metrics")
        mismatches = []
        for name, value in result.items():
            if not close_enough(reported.get(name), value,
                                absolute=tolerance["absolute"], relative=tolerance["relative"]):
                mismatches.append(name)
        report["computed_metrics"] = result
        _check(report, "trace_metrics", "failed" if mismatches else "passed",
               "Reported metric differs from independently integrated trace." if mismatches else
               "SI metrics recomputed from a strictly ordered trace covering the full horizon.",
               mismatches=mismatches, sample_count=len(run["trace"]), tolerances=tolerance)
        steps = run.get("routing_steps")
        if steps is None:
            _check(report, "routing_step_coverage", "unperformed", "Routing-step count absent; full native-step coverage not established.")
        elif isinstance(steps, bool) or not isinstance(steps, int) or steps != len(run["trace"]) - 1:
            _check(report, "routing_step_coverage", "failed", "Routing-step count differs from trace interval count.")
        else:
            _check(report, "routing_step_coverage", "passed", "Recorded routing-step count matches trace interval count.")
        native = reported.get("native_flood_volume_m3", run.get("native_flood_volume_m3"))
        if native is None:
            _check(report, "native_flood_crosscheck", "unperformed", "Native cumulative flood total absent.")
        else:
            native = finite_number(native, "native flood volume")
            if native < 0:
                raise EvidenceError("native flood volume is negative")
            matched = close_enough(native, result["flood_volume_m3"],
                                   absolute=tolerance["absolute"], relative=tolerance["relative"])
            _check(report, "native_flood_crosscheck", "passed" if matched else "failed",
                   "Native cumulative flooding and integrated trace agree." if matched else
                   "Native cumulative flooding and integrated trace disagree; investigate units or sampling.",
                   native_flood_volume_m3=native, trace_flood_volume_m3=result["flood_volume_m3"])
    except (EvidenceError, TypeError) as exc:
        _check(report, "trace_metrics", "failed", str(exc))

    try:
        tolerance = _tolerances(experiment)
        continuity = _object(run.get("continuity"), "native continuity diagnostics")
        values = {name: finite_number(continuity.get(name), name)
                  for name in ("runoff_error_pct", "routing_error_pct")}
        exceeded = [name for name, value in values.items() if abs(value) > tolerance["continuity_pct"]]
        _check(report, "continuity", "failed" if exceeded else "passed",
               "Native continuity error exceeds the declared diagnostic bound." if exceeded else
               "Native runoff and routing continuity diagnostics are finite and within the declared bound.",
               values=values, absolute_limit_pct=tolerance["continuity_pct"])
    except EvidenceError as exc:
        missing = not isinstance(run.get("continuity"), Mapping) or any(
            run.get("continuity", {}).get(key) is None for key in ("runoff_error_pct", "routing_error_pct")
        )
        _check(report, "continuity", "unperformed" if missing else "failed", str(exc))
    return _finish(report)


def _verify_artifacts(packet: Mapping, root_path: Path | None, report: dict):
    artifacts = packet.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        _check(report, "artifact_integrity", "unperformed", "No included-artifact manifest was supplied.")
        return
    if root_path is None:
        _check(report, "artifact_integrity", "unperformed", "Artifact root was not supplied; included bytes were not checked.")
        return
    root = root_path.resolve()
    seen: set[str] = set()
    for i, item in enumerate(artifacts):
        try:
            item = _object(item, f"artifact {i}")
            rel = item.get("path")
            if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise EvidenceError("artifact path must be a contained relative path")
            if rel in seen:
                raise EvidenceError("duplicate artifact path")
            seen.add(rel)
            expected = _hash(item.get("sha256"), "artifact hash")
            path = (root / rel).resolve()
            if not path.is_relative_to(root):
                raise EvidenceError("artifact path escapes the packet root")
            if not path.is_file():
                raise EvidenceError(f"missing artifact: {rel}")
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(65536), b""):
                    digest.update(block)
            actual = digest.hexdigest()
            _check(report, f"artifact:{rel}", "passed" if actual == expected else "failed",
                   "Included bytes match the manifest." if actual == expected else "Included bytes do not match the manifest.")
        except (EvidenceError, OSError, ValueError) as exc:
            _check(report, f"artifact:{i}", "failed", str(exc))


def _verify_fingerprints(packet: Mapping, root_path: Path | None, report: dict):
    experiment = packet["experiment"]
    try:
        for field in ("exogenous", "solver_settings"):
            value = _object(experiment.get(field), field)
            expected = _hash(experiment.get(field + "_sha256"), field + " digest")
            if canonical_sha256(value) != expected:
                raise EvidenceError(f"canonical {field} content does not match its digest")
        if canonical_sha256(experiment.get("test_contract")) != _hash(packet.get("test_contract_sha256"), "test-contract digest"):
            raise EvidenceError("test-contract digest differs from the declared property")
        exogenous = experiment["exogenous"]
        request = _object(packet.get("request"), "replay request")
        for key in ("seed", "noise_std_m", "faults"):
            if key not in request or request[key] != exogenous.get(key):
                raise EvidenceError(f"replay request and exogenous catalog differ: {key}")
        if request.get("test_contract") != experiment.get("test_contract"):
            raise EvidenceError("replay request differs from the declared test contract")
        if request.get("scenario_id") != experiment.get("scenario_id"):
            raise EvidenceError("replay request differs from the declared scenario")
        if exogenous.get("rainfall_sha256") != experiment.get("rainfall_sha256"):
            raise EvidenceError("exogenous rainfall identity differs from the experiment")
        faults = exogenous.get("faults")
        if not isinstance(faults, list) or faults != experiment.get("faults"):
            raise EvidenceError("experiment fault catalog differs from its hashed exogenous catalog")
        ids = _faults([_object(f, "fault").get("id") for f in faults], "fault catalog IDs")
        for run in packet["runs"]:
            if not _faults(run.get("active_fault_ids"), "active faults") <= ids:
                raise EvidenceError("run activates a fault outside the hashed catalog")
            if run.get("role") == "nominal" and run["active_fault_ids"]:
                raise EvidenceError("a nominal run cannot activate stress faults")
        _check(report, "canonical_fingerprints", "passed", "Exogenous stream, solver settings and test contract match canonical content hashes; active faults belong to that catalog.")
    except (EvidenceError, ValueError, TypeError) as exc:
        _check(report, "canonical_fingerprints", "failed", str(exc))

    if root_path is None:
        _check(report, "source_provenance", "unperformed", "Artifact root not supplied; local model and source identities were not checked.")
        return
    try:
        root = root_path.resolve()
        provenance = _object(packet.get("provenance"), "provenance")
        rel = provenance.get("model_path")
        if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise EvidenceError("model path must be contained and relative")
        model_path = (root / rel).resolve()
        if not model_path.is_relative_to(root) or not model_path.is_file():
            raise EvidenceError("base model artifact is absent or outside the root")
        actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if actual != experiment.get("base_model_sha256") or actual != provenance.get("base_model_sha256"):
            raise EvidenceError("base model bytes do not match experiment and provenance")
        controller_path = root / "engine/controllers.py"
        controller_digest = hashlib.sha256(controller_path.read_bytes()).hexdigest()
        if any(run["controller"]["source_sha256"] != controller_digest for run in packet["runs"]):
            raise EvidenceError("controller bytes differ from a run's source digest")
        runner_digest = hashlib.sha256((root / "engine/runner.py").read_bytes()).hexdigest()
        if runner_digest != provenance.get("runner_source_sha256"):
            raise EvidenceError("runner bytes differ from provenance")
        engine_root = root / "engine"
        solver_root = engine_root / "vendor/epa-swmm/src/solver"
        sources = sorted(p for p in solver_root.rglob("*") if p.is_file())
        if not sources:
            raise EvidenceError("pinned solver source is absent")
        sources += [engine_root / "native_bridge.c"]
        digest = hashlib.sha256()
        for path in sources:
            if not path.resolve().is_relative_to(root):
                raise EvidenceError("solver source escapes artifact root")
            digest.update(str(path.relative_to(engine_root)).encode() + b"\0")
            digest.update(path.read_bytes())
        if digest.hexdigest() != provenance.get("engine_source_sha256"):
            raise EvidenceError("solver/bridge source bundle differs from provenance")
        _check(report, "source_provenance", "passed", "Exact base model, controller, runner and solver/bridge source bytes match recorded provenance.")
        _verify_rainfall(packet, model_path.read_text(), report)
    except (EvidenceError, OSError, KeyError, TypeError) as exc:
        _check(report, "source_provenance", "failed", str(exc))


def _verify_rainfall(packet: Mapping, base_text: str, report: dict):
    """Reconstruct the documented curated-model rainfall transform from bytes."""
    try:
        experiment = packet["experiment"]
        request = _object(packet.get("request"), "replay request")
        multiplier = finite_number(request.get("rainfall_multiplier"), "rainfall multiplier")
        sections: dict[str, list[list[str]]] = {}
        section = None
        for line in base_text.splitlines():
            clean = line.split(";", 1)[0].strip()
            if clean.startswith("["):
                section = clean.upper()
                sections[section] = []
            elif clean and section is not None:
                sections[section].append(clean.split())
        gauges = sections.get("[RAINGAGES]", [])
        if not gauges:
            raise EvidenceError("base model has no declared rainfall gauges")
        names = set()
        for row in gauges:
            if "TIMESERIES" not in row:
                raise EvidenceError("validator supports curated inline rainfall time series only")
            index = row.index("TIMESERIES") + 1
            names.add(row[index])
        output, rain_rows = [], []
        in_series = False
        for line in base_text.splitlines():
            if line.strip().startswith("["):
                in_series = line.strip().upper() == "[TIMESERIES]"
            fields = line.split(";", 1)[0].split()
            if in_series and fields and fields[0] in names:
                fields[-1] = format(float(fields[-1]) * multiplier, ".12g")
                line = " ".join(fields)
                rain_rows.append(fields)
            output.append(line)
        rain_hash = canonical_sha256(dict(rain_gauges=gauges, rows=rain_rows))
        effective_hash = hashlib.sha256(("\n".join(output) + "\n").encode()).hexdigest()
        if rain_hash != experiment.get("rainfall_sha256"):
            raise EvidenceError("rainfall identity does not match base-model rows and requested multiplier")
        if effective_hash != experiment.get("effective_model_sha256"):
            raise EvidenceError("effective model identity does not match the declared rainfall transform")
        _check(report, "rainfall_provenance", "passed", "Rainfall and effective-model hashes independently reconstructed from base bytes and the declared multiplier.")
    except (EvidenceError, IndexError, ValueError) as exc:
        _check(report, "rainfall_provenance", "failed", str(exc))


def _same_policy(a: Mapping, b: Mapping):
    if a["controller"] != b["controller"]:
        raise EvidenceError("ablation must use the same controller source and parameters")


def validate_packet(packet: Mapping[str, Any], root_path: str | Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = dict(checks=[], runs={}, claims={}, limitations=list(LIMITATIONS))
    try:
        packet = _object(packet, "packet")
        if packet.get("schema_version") != SCHEMA_VERSION:
            raise EvidenceError(f"expected packet schema_version {SCHEMA_VERSION}")
        experiment = _object(packet.get("experiment"), "experiment")
        runs = packet.get("runs")
        if not isinstance(runs, list) or not runs:
            raise EvidenceError("packet requires completed runs")
        by_id: dict[str, Mapping] = {}
        for run in runs:
            run = _object(run, "run")
            identifier = run.get("run_id")
            if not isinstance(identifier, str) or not identifier or identifier in by_id:
                raise EvidenceError("run IDs must be nonempty and unique")
            by_id[identifier] = run
        _check(report, "packet_schema", "passed", "Versioned packet has uniquely identified runs.")
    except EvidenceError as exc:
        _check(report, "packet_schema", "failed", str(exc))
        return _finish(report)

    for identifier, run in by_id.items():
        checked = validate_run(run, experiment)
        report["runs"][identifier] = checked
        for item in checked["checks"]:
            report["checks"].append(dict(item, id=f"{identifier}:{item['id']}"))

    _verify_artifacts(packet, Path(root_path) if root_path is not None else None, report)
    _verify_fingerprints(packet, Path(root_path) if root_path is not None else None, report)
    valid_metrics = {identifier: r["computed_metrics"] for identifier, r in report["runs"].items()
                     if r["computed_metrics"] and r["status"] != "failed"}
    try:
        declaration = property_declaration(experiment)
        reference_id = experiment["test_contract"].get("reference_run_id")
        reference = valid_metrics.get(reference_id)
        property_results = {identifier: evaluate_property(declaration, metrics, reference)
                            for identifier, metrics in valid_metrics.items()}
        # Also validate the declaration if every trace has failed.
        if not property_results:
            evaluate_property(declaration, {key: 0 for key in METRIC_UNITS},
                              {key: 0 for key in METRIC_UNITS} if reference_id else None)
        report["claims"]["properties"] = property_results
        _check(report, "property_declaration", "passed", "Explicit physical property evaluated from independently recomputed metrics.")
    except (EvidenceError, TypeError) as exc:
        property_results = {}
        _check(report, "property_declaration", "failed", str(exc))

    ablations = packet.get("ablations", [])
    if not isinstance(ablations, list):
        _check(report, "ablations", "failed", "Ablations must be a list.")
        ablations = []
    for i, relation in enumerate(ablations):
        try:
            relation = _object(relation, "ablation")
            source = by_id[relation["source_run_id"]]
            ablated = by_id[relation["run_id"]]
            removed = _faults(relation.get("removed_fault_ids"), "removed faults")
            original = _faults(source["active_fault_ids"], "source faults")
            actual = _faults(ablated["active_fault_ids"], "ablation faults")
            if not removed or not removed <= original or actual != original - removed:
                raise EvidenceError("ablation must remove exactly the named existing faults")
            _same_policy(source, ablated)
            if source["run_id"] not in valid_metrics or ablated["run_id"] not in valid_metrics:
                raise EvidenceError("ablation depends on invalid run evidence")
            _check(report, f"ablation:{i}", "passed", "Only the named faults were removed with policy and context held fixed.")
        except (EvidenceError, KeyError, TypeError) as exc:
            _check(report, f"ablation:{i}", "failed", str(exc))

    witness = packet.get("witness")
    if witness is not None:
        try:
            witness = _object(witness, "witness")
            run = by_id[witness["run_id"]]
            faults = _faults(run["active_fault_ids"], "witness faults")
            if not property_results.get(run["run_id"], {}).get("violated"):
                raise EvidenceError("witness run does not establish the declared violation")
            original_id = witness.get("original_run_id", run["run_id"])
            original = by_id[original_id]
            if not faults <= _faults(original["active_fault_ids"], "original faults"):
                raise EvidenceError("reduced witness adds faults to the original")
            _same_policy(original, run)
            if not property_results.get(original_id, {}).get("violated"):
                raise EvidenceError("original witness lacks a validated violation")
            claim = witness.get("claim", "reduced")
            if claim not in {"reduced", "1-minimal"}:
                raise EvidenceError("supported witness claims are reduced and 1-minimal")
            removals = witness.get("single_removals", [])
            if not isinstance(removals, list):
                raise EvidenceError("single removals must be a list")
            tested = set()
            necessary = set()
            for removal in removals:
                removal = _object(removal, "single removal")
                fault = removal["fault_id"]
                neighbor = by_id[removal["run_id"]]
                if fault not in faults or fault in tested:
                    raise EvidenceError("single removal must name each retained fault at most once")
                if _faults(neighbor["active_fault_ids"], "neighbor faults") != faults - {fault}:
                    raise EvidenceError("single removal changed more than its named fault")
                _same_policy(run, neighbor)
                if neighbor["run_id"] not in property_results:
                    raise EvidenceError("single-removal run has no valid property evaluation")
                if not property_results[neighbor["run_id"]]["violated"]:
                    necessary.add(fault)
                tested.add(fault)
            if claim == "1-minimal" and tested != faults:
                raise EvidenceError("1-minimal claim lacks every retained fault's single-removal replay")
            if claim == "1-minimal" and necessary != faults:
                raise EvidenceError("single removal still violates the property; witness is not 1-minimal")
            result = dict(run_id=run["run_id"], claim=claim, active_fault_ids=sorted(faults),
                          tested_removals=sorted(tested), necessary_faults=sorted(necessary), globally_minimal=False)
            report["claims"]["witness"] = result
            _check(report, "witness", "passed", "Violation and the declared reduction guarantee are supported.", **result)
        except (EvidenceError, KeyError, TypeError) as exc:
            _check(report, "witness", "failed", str(exc))

    fallback = packet.get("fallback")
    if fallback is not None:
        try:
            fallback = _object(fallback, "fallback")
            stressed_id = fallback["stressed_run_id"]
            fallback_id = fallback["fallback_run_id"]
            stressed = by_id[stressed_id]
            alternative = by_id[fallback_id]
            if _faults(stressed["active_fault_ids"], "stressed faults") != _faults(alternative["active_fault_ids"], "fallback faults"):
                raise EvidenceError("fallback must face exactly the same active faults")
            if stressed_id not in valid_metrics or fallback_id not in valid_metrics:
                raise EvidenceError("fallback comparison depends on invalid run evidence")
            result = compare_fallback(valid_metrics[stressed_id], valid_metrics[fallback_id], fallback)
            report["claims"]["fallback"] = result
            _check(report, "fallback_comparison", "passed", "Fallback uses matched faults and reports every physical metric.", conclusion=result["conclusion"])
            if fallback.get("claim") == "guarded_improvement" and not result["guarded_improvement"]:
                _check(report, "fallback_claim", "failed", "Claimed guarded improvement is unsupported; primary benefit may conceal tradeoffs.")
        except (EvidenceError, KeyError, TypeError) as exc:
            _check(report, "fallback_comparison", "failed", str(exc))

    _check(report, "independent_replay", "unperformed", "This invocation checks records; it does not execute the hydraulic engine.", required=False)
    _check(report, "controller_information_access", "unperformed", "Recorded information boundaries require separate source/interface review.", required=False)
    _check(report, "field_calibration", "unperformed", "No site calibration or real-world impact is established.", required=False)
    return _finish(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--root", type=Path, help="Root containing included artifact paths")
    parser.add_argument("--output", type=Path, help="Write report to this path instead of stdout")
    args = parser.parse_args()
    try:
        packet = json.loads(args.packet.read_text())
        report = validate_packet(packet, args.root)
    except (OSError, ValueError) as exc:
        report = _finish(dict(checks=[dict(id="packet_read", status="failed", required=True,
                                           message=str(exc))], runs={}, claims={}, limitations=list(LIMITATIONS)))
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 1 if report["status"] == "failed" else (2 if report["status"] == "partial" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
