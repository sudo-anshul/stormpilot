"""Run an immutable recorded alternative through the declared robustness suite."""
import sys
import traceback

from service.common import JOBS, read_json, write_json


def execute(job_id):
    folder = JOBS / job_id
    request = read_json(folder / "request.json")
    state = read_json(folder / "status.json")
    try:
        from evaluation.declared import evaluate_declared_suite
        state.update(status="running", phase="Testing robustness", message="Evaluating both recorded policies across the declared rainfall, timing and sensor-noise transformations.")
        write_json(folder / "status.json", state)
        report_path = folder / "report.json"
        evaluate_declared_suite(JOBS / request["source_job_id"] / "packet.json", request["reference_run_id"],
                                request["candidate_run_id"], request["pair_ids"], folder / "suite", report_path)
        if not report_path.is_file():
            raise RuntimeError("The evaluator did not produce a decision report.")
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
