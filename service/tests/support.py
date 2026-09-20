from functools import lru_cache
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@lru_cache(maxsize=1)
def genuine_packet():
    """Generate the small published case; never depend on a tracked giant fixture."""
    with tempfile.TemporaryDirectory(prefix="engine-evidence-") as temp:
        output = Path(temp) / "packet.json"
        subprocess.run([sys.executable, str(ROOT / "engine/cli.py"), "investigate",
                        "--request", str(ROOT / "engine/examples/reduction-request.json"),
                        "--output", str(output)], cwd=ROOT, check=True, capture_output=True, timeout=90)
        return json.loads(output.read_text())


def presentation_request():
    from service.present import normalize_config
    return {"id": "0123456789abcdef", "created_at": "2026-09-20T00:00:00+00:00",
            "config": normalize_config({"additional_faults": [
                {"asset": "2", "start_hour": 30, "duration_hours": 1}]})}
