"""Build the vendored public-domain EPA solver with the system C compiler."""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "vendor/epa-swmm/src/solver"
LIBRARY = ROOT / "build" / ("libswmm5.dylib" if sys.platform == "darwin" else "libswmm5.so")


def source_hash():
    digest = hashlib.sha256()
    paths = sorted(p for p in SOURCE.rglob("*") if p.is_file()) + [ROOT / "native_bridge.c"]
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def build(force=False):
    manifest_path = ROOT / "build/build.json"
    signature = source_hash()
    if not force and LIBRARY.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("source_sha256") == signature:
            return LIBRARY
    compiler = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
    if not compiler:
        raise RuntimeError("A C compiler is required to build the real EPA SWMM engine.")
    LIBRARY.parent.mkdir(exist_ok=True)
    command = [compiler, "-O2", "-fPIC", "-dynamiclib" if sys.platform == "darwin" else "-shared",
               "-I" + str(SOURCE / "include"), "-I" + str(SOURCE)]
    command += [str(p) for p in sorted(SOURCE.glob("*.c"))]
    command += [str(ROOT / "native_bridge.c"), "-o", str(LIBRARY), "-lm"]
    subprocess.run(command, check=True, stdout=sys.stderr, stderr=sys.stderr)
    manifest = {"source_sha256": signature, "epa_tag": "v5.2.4",
                "epa_commit": "7952ca837988b1c32f791812eccc9fd64547e093",
                "platform": platform.platform(), "command": command}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return LIBRARY


if __name__ == "__main__":
    print(build("--force" in sys.argv))
