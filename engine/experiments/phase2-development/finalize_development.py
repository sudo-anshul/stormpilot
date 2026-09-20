"""Final default-search proof; records every physical call in the complete ledger."""
from pathlib import Path
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"engine"))
sys.path.insert(0,str(ROOT))
from models import digest
import repair as repair_module
from validation.validate_packet import validate_packet

ledger_path=WORK/"ledger.jsonl"
rows=[json.loads(line) for line in ledger_path.read_text().splitlines()]
source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/"engine").glob("*.py"))}
source_id=digest(source)
snapshot=WORK/"sources"/source_id
snapshot.mkdir(parents=True,exist_ok=True)
for name in source:
    (snapshot/Path(name).name).write_bytes((ROOT/name).read_bytes())
(snapshot/"manifest.json").write_text(json.dumps(source,indent=2)+"\n")
native=repair_module.run_simulation

def recorded(request,role,controller,active_ids,parameters):
    if len(rows)>=512:
        raise RuntimeError("Frozen phase2 development budget exhausted")
    ids=[f["id"] for f in request["faults"]]
    subset=next(s for s,v in {"empty":[],"a":ids[:1],"b":ids[1:],"ab":ids}.items() if v==active_ids)
    row={"call":len(rows)+1,"case_id":"original-final","purpose":"final_default_repair_proof",
         "request_sha256":digest(request),"controller_id":controller,"parameters":parameters,
         "subset":subset,"source_sha256":source_id,"created_at":datetime.now(timezone.utc).isoformat()}
    try:
        run=native(request,role,controller,active_ids,parameters)
        file=WORK/("run-%04d.json.gz"%row["call"])
        with gzip.open(file,"wt") as output:
            json.dump(run,output,separators=(",",":"))
        row.update(status="completed",run_id=run["run_id"],metrics=run["metrics"],continuity=run["continuity"],
                   controller=run["controller"],trace_sha256=digest(run["trace"]),routing_steps=run["routing_steps"],
                   full_run_file=file.name,full_run_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
    except Exception as error:
        row.update(status="failed",error=type(error).__name__+": "+str(error))
    rows.append(row)
    with ledger_path.open("a") as output:
        output.write(json.dumps(row,separators=(",",":"))+"\n")
        output.flush()
    if row["status"]!="completed":
        raise RuntimeError(row["error"])
    return run

repair_module.run_simulation=recorded
request=json.loads((ROOT/"evaluation/candidate.json").read_text())["request"]
(WORK/"final-request.json").write_text(json.dumps(request,indent=2)+"\n")
plan={"created_at":datetime.now(timezone.utc).isoformat(),"source_sha256":source_id,"request":request,
      "default_search":repair_module.normalize_repair(request)[2],"global_call_budget":512,
      "purpose":"Generate final default-search proof after development; no phase2 heldout access."}
(WORK/"final-proof-plan.json").write_text(json.dumps(plan,indent=2)+"\n")
packet=repair_module.repair(request)
with gzip.open(WORK/"final-proof.json.gz","wt") as output:
    json.dump(packet,output,separators=(",",":"))
checked=validate_packet(packet,ROOT)
(WORK/"final-validation.json").write_text(json.dumps(checked,indent=2)+"\n")
spec={"controller_id":packet["repair"]["selected"]["controller_id"],
      "parameters":packet["repair"]["selected"]["parameters"],
      "development_ledger_calls":len(rows),"source_sha256":source_id,
      "controller_source_sha256":source["engine/controllers.py"],
      "selected":packet["repair"]["selected"]}
(WORK/"final-spec.json").write_text(json.dumps(spec,indent=2)+"\n")
print(json.dumps({"validation":checked["status"],"parameters":spec["parameters"],
                  "eligible":spec["selected"]["eligible"],"development_ledger_calls":len(rows),
                  "controller_source_sha256":spec["controller_source_sha256"]}),flush=True)
if checked["status"]!="passed":
    print(json.dumps([x for x in checked["checks"] if x["required"] and x["status"]!="passed"]),flush=True)
