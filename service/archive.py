"""Self-contained evidence archives with the exact recorded solver sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from service.common import ROOT, read_json

REPLAY_GUIDE = """# Replay this StormPilot investigation

This archive contains recorded evidence, the pinned EPA solver source, public
benchmark inputs and the independent validator. Extract it to a new directory.
Use Python 3.10+ and a C compiler (clang or GCC), on macOS or Linux. No Python
packages, network connection or GitHub access are required for replay.

From the extracted directory, run:

```sh
python3 -m validation.validate_packet packet.json --root . --output recorded-check.json
python3 engine/cli.py replay --request packet.json --output replayed-packet.json
python3 -m validation.validate_packet replayed-packet.json --root . --output replayed-check.json
python3 -m validation.replay packet.json replayed-packet.json --root . --output replay-check.json
```

Replay executes every recorded case, including condition-removal tests. It does
not rerun or expand the original search. The comparison independently checks the
fresh traces, inputs and conclusions against the original packet. The supplied
validation.json is the report at export; the commands above produce fresh checks.

MANIFEST.json lists SHA-256 hashes of the included files. Model, controller and
solver identities are also checked against packet provenance. Native binaries
are rebuilt locally. Small platform differences are assessed using the explicit
tolerances in the independent validator; exact cross-platform equality is not
assumed.

The results describe public benchmark simulations. They do not certify field
performance or flood protection. See LICENSE and engine/data/PYSTORMS-LICENSE
for licensing, and engine/README.md for the experiment protocol.
"""


def build_archive(folder: Path) -> Path:
    packet = read_json(folder / "packet.json")
    files: dict[str, bytes] = {}
    for artifact in packet.get("artifacts", []):
        relative = artifact["path"]
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or Path(relative).is_absolute():
            raise ValueError("A recorded artifact has an invalid path.")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact["sha256"]:
            raise ValueError("Source files changed since this run. Start a fresh experiment before exporting.")
        files[relative] = content
    for pattern in ("validation/*.py", "validation/cases/*.json", "engine/data/*", "engine/examples/*.json"):
        for path in ROOT.glob(pattern):
            if path.is_file():
                files[str(path.relative_to(ROOT))] = path.read_bytes()
    for relative in ("LICENSE", "engine/README.md", "docs/validation.md"):
        files[relative] = (ROOT / relative).read_bytes()
    for name in ("packet.json", "validation.json", "request.json", "engine-request.json", "replay.json"):
        if (folder / name).exists():
            files[name] = (folder / name).read_bytes()
    files["REPLAY.md"] = REPLAY_GUIDE.encode()
    files["MANIFEST.json"] = json.dumps({"schema_version": "stormpilot.archive.v1", "files": [
        {"path": name, "sha256": hashlib.sha256(content).hexdigest()}
        for name, content in sorted(files.items())
    ]}, indent=2).encode()
    archive = folder / "evidence.zip"
    temporary = folder / "evidence.zip.tmp"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, content in sorted(files.items()):
            bundle.writestr(name, content)
    temporary.replace(archive)
    return archive


def build_evaluation_archive(folder: Path, source_folder: Path) -> Path:
    """Export the recorded source investigation and every retained suite proof."""
    archive = folder / "evidence.zip"
    source = source_folder / "evidence.zip"
    if not source.exists():
        source = build_archive(source_folder)
    files = {}
    with zipfile.ZipFile(source) as original:
        for name in original.namelist():
            if name != "MANIFEST.json":
                files[name] = original.read(name)
    for base in (folder / "suite", folder / "evaluator-source"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".gz", ".sha256"}:
                name = str(path.relative_to(base)) if base.name == "evaluator-source" else "suite/" + str(path.relative_to(base))
                files[name] = path.read_bytes()
    files["robustness-report.json"] = (folder / "report.json").read_bytes()
    files["robustness-request.json"] = (folder / "request.json").read_bytes()
    request = read_json(folder / "request.json")
    args = " ".join("--pair-id " + key for key in request["pair_ids"])
    files["ROBUSTNESS.md"] = (
        "# Recorded robustness evaluation\n\nThis export contains the source investigation, full retained suite packets, "
        "the declared protocol, policies and all outcomes, including rejected cases.\n\n"
        "These transforms are visible and reusable. Re-execution is a declared suite, not a new held-out evaluation.\n\n"
        "Replay the source investigation using REPLAY.md. To rerun the declared robustness suite in a new directory:\n\n"
        "```sh\npython3 -m evaluation.declared --packet packet.json "
        f"--reference-run-id {request['reference_run_id']} --candidate-run-id {request['candidate_run_id']} "
        f"{args} --output-dir fresh-suite --report fresh-robustness-report.json\n```\n"
    ).encode()
    files["MANIFEST.json"] = json.dumps({"schema_version": "stormpilot.robustness-archive.v1", "files": [
        {"path": name, "sha256": hashlib.sha256(content).hexdigest()} for name, content in sorted(files.items())
    ]}, indent=2).encode()
    temporary = folder / "evidence.zip.tmp"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, content in sorted(files.items()):
            bundle.writestr(name, content)
    temporary.replace(archive)
    return archive
