"""Declared phase2 development only; never reads the new phase2 evaluation cases."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import copy
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))
from models import digest
from runner import run_simulation, prepare
from repair import assess_candidate

parser = argparse.ArgumentParser()
parser.add_argument("--fractions", type=float, nargs="+", default=[.25, .5, .75, 1.])
parser.add_argument("--threshold", type=float, default=.5)
parser.add_argument("--cases", nargs="+", default=["original", "h1", "h2", "h3", "h4", "h5", "h6"])
args = parser.parse_args()
ledger_path = WORK / "ledger.jsonl"
ledger = [json.loads(line) for line in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
source = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted((ROOT / "engine").glob("*.py"))}
source_id = digest(source)
snapshot = WORK / "sources" / source_id
snapshot.mkdir(parents=True, exist_ok=True)
for name in source:
    destination = snapshot / Path(name).name
    destination.write_bytes((ROOT / name).read_bytes())
(snapshot / "manifest.json").write_text(json.dumps(source, indent=2)+"\n")

requests = {}
requests["original"] = json.loads((ROOT / "evaluation" / "candidate.json").read_text())["request"]
for case in args.cases:
    if case.startswith("noise"):
        request=copy.deepcopy(requests["original"])
        extra={"noise-positive":(1.,1001,1.),"noise-heavy-positive":(1.35,1002,1.),
               "noise-negative":(1.,1003,-1.),"noise-heavy-negative":(1.35,1004,-1.)}
        rain,seed,bias=extra[case]
        request.update(rainfall_multiplier=rain,seed=seed,noise_std_m=.08)
        for fault in request["faults"]:
            if fault["type"]=="sensor_bias":
                fault["bias_m"]=bias
        requests[case]=request
    elif case != "original":
        requests[case] = json.loads((ROOT / "evaluation" / "heldout" / (case+"-request.json")).read_text())
requests = {key: prepare(requests[key])[0] for key in args.cases}
specs = [{"target_scale": 1., "jump_threshold_m": args.threshold, "correction_fraction": f} for f in args.fractions]
plan = {"created_at": datetime.now(timezone.utc).isoformat(), "source_sha256": source_id,
        "development_data": "Original phase1 witness plus now-disclosed phase1 heldout cases; phase2 heldout remains unseen.",
        "requests": requests, "candidates": specs, "global_call_budget": 512}
(WORK / ("plan-"+digest(plan)[:12]+".json")).write_text(json.dumps(plan, indent=2)+"\n")
cache = {(x["request_sha256"],x["controller_id"],digest(x["parameters"]),x["subset"],x["source_sha256"]):x
         for x in ledger if x["status"]=="completed"}

def execute(case, controller, parameters, subset):
    request = requests[case]
    key = (digest(request),controller,digest(parameters),subset,source_id)
    if key in cache:
        return cache[key]
    if len(ledger) >= 512:
        raise RuntimeError("Frozen phase2 development budget exhausted")
    ids = [f["id"] for f in request["faults"]]
    subsets = {"empty": [], "a": ids[:1], "b": ids[1:], "ab": ids}
    row = {"call": len(ledger)+1, "case_id": case, "request_sha256": digest(request),
           "controller_id": controller, "parameters": parameters, "subset": subset,
           "source_sha256": source_id, "created_at": datetime.now(timezone.utc).isoformat()}
    try:
        run = run_simulation(request, "development_"+case+"_"+subset, controller, subsets[subset], parameters)
        file = WORK / ("run-%04d.json.gz" % row["call"])
        with gzip.open(file, "wt") as output:
            json.dump(run, output, separators=(",", ":"))
        row.update(status="completed", run_id=run["run_id"], metrics=run["metrics"],
                   continuity=run["continuity"], controller=run["controller"],
                   trace_sha256=digest(run["trace"]), routing_steps=run["routing_steps"],
                   full_run_file=file.name, full_run_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
    except Exception as error:
        row.update(status="failed", error=type(error).__name__+": "+str(error))
    ledger.append(row)
    with ledger_path.open("a") as output:
        output.write(json.dumps(row,separators=(",", ":"))+"\n")
        output.flush()
    if row["status"]!="completed":
        raise RuntimeError(row["error"])
    cache[key]=row
    return row

reference={case:{subset:execute(case,"constant_flow",{"target_scale":1.},subset)
                 for subset in ("empty","a","b","ab")} for case in requests}
print("Reference calls complete; total ledger calls",len(ledger),flush=True)
summaries=[]
for spec in specs:
    outcomes={}
    for case in requests:
        candidate={subset:execute(case,"plausible_depth",spec,subset) for subset in ("empty","a","b","ab")}
        outcomes[case]=assess_candidate(reference[case],candidate)
    summary={"source_sha256":source_id,"parameters":spec,"outcomes":outcomes}
    summaries.append(summary)
    (WORK/("summary-"+digest(summary)[:12]+".json")).write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({"parameters":spec,"ledger_calls":len(ledger),"cases":{
        case:{"reduction":round(o["flood_reduction_m3"],4),"relative":o["relative_flood_reduction"],
              "failures":o["failures"]} for case,o in outcomes.items()}}),flush=True)
