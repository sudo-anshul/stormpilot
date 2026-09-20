"""Complete published theta episode and one controlled valve perturbation."""
from pathlib import Path
import json
import time
from swmm import Simulation

ROOT = Path(__file__).resolve().parent


def run(stuck=False):
    started = time.monotonic()
    name = "theta-valve-stuck" if stuck else "theta-uncontrolled"
    sim = Simulation(ROOT / "data/theta.inp", ROOT / f"runs/{name}.rpt", ROOT / f"runs/{name}.out")
    trace = []
    flood = excess = peak = 0.0
    previous = 0.0
    try:
        running = True
        while running:
            now = sim.time_s
            for asset in ["1", "2"]:
                setting = 0.0 if stuck and asset == "1" and 3600 <= now < 21600 else 1.0
                sim.set(407, sim.links[asset], setting)
            boundary = min([x for x in [3600, 21600, sim.duration_s] if x > now + 1e-7], default=sim.duration_s)
            sim.set(3, 0, min(30.0, max(0.001, boundary - now)))
            running = sim.step()
            now = sim.time_s
            current_flood = sum(max(0.0, sim.get(308, i)) for i in sim.nodes.values())
            storage = sum(sim.get(305, i) for i in sim.nodes.values())
            downstream = max(0.0, sim.get(410, sim.links["8"]))
            dt = now - previous
            flood += current_flood * dt
            excess += max(0.0, downstream - 0.5) * dt
            peak = max(peak, downstream)
            trace.append({"time_s": now, "total_flooding_m3s": current_flood,
                          "total_storage_m3": storage, "downstream_flow_m3s": downstream})
            previous = now
        native = sim.native_flood_volumes()
        continuity = sim.finish()
    finally:
        sim.close()
    return {"run_id": name, "controller": "uncontrolled", "fault": "valve 1 closed from hour 1 to 6" if stuck else None,
            "metrics": {"flood_volume_m3": flood, "native_flood_volume_m3": sum(native.values()),
                        "peak_downstream_flow_m3s": peak, "downstream_excess_volume_m3": excess,
                        "terminal_storage_m3": storage}, "continuity": continuity,
            "routing_steps": len(trace), "duration_s": previous,
            "runtime_s": time.monotonic() - started, "trace": trace}


if __name__ == "__main__":
    results = [run(False), run(True)]
    (ROOT / "runs/proof.json").write_text(json.dumps(results))
    print(json.dumps([{k:v for k,v in item.items() if k != "trace"} for item in results], indent=2))
