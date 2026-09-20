#!/usr/bin/env python3
"""Stable JSON CLI: catalog, run and investigate. No third-party Python packages."""
import argparse
import json
import sys
from pathlib import Path
from controllers import POLICIES
from models import metadata
from runner import FAULT_TYPES, packet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["catalog", "run", "investigate", "discover", "repair", "replay"])
    parser.add_argument("--request", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "catalog":
            result = {"schema_version": "stormpilot.catalog.v1", "engine": "EPA SWMM 5.2.4",
                      "scenarios": [metadata("theta"), metadata("gamma")], "policies": POLICIES,
                      "fault_types": FAULT_TYPES,
                      "default_request": {"scenario_id": "theta", "controller_id": "constant_flow",
                          "fallback_controller_id": "uncontrolled", "seed": 42, "rainfall_multiplier": 1,
                          "noise_std_m": 0, "faults": [{"id": "f1", "type": "valve_stuck", "asset": "1", "start_s": 3600,
                                                      "end_s": 21600, "setting": 0}],
                          "test_contract": {"metric": "flood_volume_m3", "threshold": 100, "tolerance": 1e-6}}}
        else:
            request = json.loads(args.request.read_text() if args.request else sys.stdin.read())
            if args.command == "replay":
                from replay import replay
                result = replay(request)
            elif args.command == "discover":
                from campaign import discover
                result = discover(request)
            elif args.command == "repair":
                from repair import repair
                result = repair(request)
            elif args.command == "investigate":
                from investigate import investigate
                result = investigate(request)
            else:
                result = packet(request)
        output = json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output)
        else:
            sys.stdout.write(output)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        sys.stderr.write(json.dumps({"error": str(exc), "type": type(exc).__name__}) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
