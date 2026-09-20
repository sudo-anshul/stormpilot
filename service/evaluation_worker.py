"""Run an immutable recorded alternative through the declared robustness suite."""
import sys
import traceback
import shutil

from service.common import JOBS, ROOT, read_json, write_json
from service.archive import build_evaluation_archive


def execute(job_id):
    folder = JOBS / job_id
    request = read_json(folder / "request.json")
    state = read_json(folder / "status.json")
    try:
        from evaluation.declared import evaluate_declared_suite
        for relative in ("evaluation", "validation"):
            destination = folder / "evaluator-source" / relative
            destination.mkdir(parents=True, exist_ok=True)
            for source in (ROOT / relative).glob("*.py"):
                shutil.copy2(source, destination / source.name)
        for name in ("protocol.json", "protocol.sha256"):
            shutil.copy2(ROOT / "evaluation" / name, folder / "evaluator-source" / "evaluation" / name)
        state.update(status="running", phase="Testing robustness", message="Evaluating both recorded policies across the declared rainfall, timing and sensor-noise transformations.")
        write_json(folder / "status.json", state)
        report_path = folder / "report.json"
        evaluate_declared_suite(JOBS / request["source_job_id"] / "packet.json", request["reference_run_id"],
                                request["candidate_run_id"], request["pair_ids"], folder / "suite", report_path)
        if not report_path.is_file():
            raise RuntimeError("The evaluator did not produce a decision report.")
        state.update(phase="Packaging robustness evidence", message="Bundling the source, declared suite and all retained full proofs.")
        write_json(folder / "status.json", state)
        build_evaluation_archive(folder, JOBS / request["source_job_id"])
        state.update(status="completed", phase="Complete", message="All recorded robustness outcomes are ready.")
        write_json(folder / "status.json", state)
    except Exception as exc:
        traceback.print_exc()
        state.update(status="failed", phase="Evaluation stopped", error=str(exc)[-1200:])
        write_json(folder / "status.json", state)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1]))
