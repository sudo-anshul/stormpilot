"""Install the genuine recorded welcome case as an exportable/replayable job."""
from __future__ import annotations

import gzip

from service.archive import build_archive
from service.common import JOBS, ROOT, read_json, write_json
from service.present import engine_request, make_view
from validation.validate_packet import validate_packet


def install_demo():
    fixture = ROOT / "fixtures"
    compressed = fixture / "demo-packet.json.gz"
    if not compressed.exists():
        return None
    request = read_json(fixture / "demo-request.json")
    folder = JOBS / request["id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "packet.json").write_bytes(gzip.decompress(compressed.read_bytes()))
    packet = read_json(folder / "packet.json")
    validation = validate_packet(packet, root_path=ROOT)
    # The saved packet is rechecked here; a fresh simulator replay requires an
    # explicit job and is never inferred from a previous machine's report.
    view = make_view(packet, validation, request, recorded=True)
    write_json(folder / "request.json", request)
    write_json(folder / "engine-request.json", engine_request(request["config"]))
    write_json(folder / "validation.json", validation)
    write_json(folder / "view.json", view)
    write_json(folder / "status.json", {"id": request["id"], "status": "completed", "phase": "Recorded experiment", "message": "Saved simulation; evidence checked against the installed sources.", "created_at": request["created_at"]})
    if validation["status"] == "passed":
        build_archive(folder)
    return view
