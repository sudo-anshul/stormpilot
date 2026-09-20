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
