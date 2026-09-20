"""Pinned public benchmark inputs and explicit unit/topology metadata."""
from pathlib import Path
from datetime import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parent
PYSTORMS_COMMIT = "20cc6086433449df99177d4f9103940639ef3af0"
EPA_COMMIT = "7952ca837988b1c32f791812eccc9fd64547e093"
SCENARIOS = {
    "theta": {"label": "Theta · two connected basins", "description": "Published idealized stormwater benchmark; not a calibrated city model.",
              "downstream_link": "8", "threshold_m3s": 0.5,
              "targets_m3s": [0.243551408837705, 0.2734532846977572],
              "model_kind": "idealized public benchmark"},
    "gamma": {"label": "Gamma · eleven-basin network", "description": "Published network inspired by a real system; supplied design rainfall, no field-protection claim.",
              "downstream_link": "O1", "threshold_m3s": 4 * 0.028316846592,
              "targets_m3s": [4 * 0.028316846592] * 11,
              "model_kind": "published design-storm benchmark"},
}


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def sections(text):
    result, current = {}, None
    for line in text.splitlines():
        clean = line.split(";", 1)[0].strip()
        if clean.startswith("["):
            current = clean.upper()
            result[current] = []
        elif clean and current:
            result[current].append(clean.split())
    return result


def metadata(scenario_id):
    if scenario_id not in SCENARIOS:
        raise ValueError("Unsupported scenario_id; choose theta or gamma.")
    path = ROOT / "data" / f"{scenario_id}.inp"
    data = path.read_bytes()
    parsed = sections(data.decode())
    options = {r[0]: r[1] for r in parsed["[OPTIONS]"]}
    length_factor = 0.3048 if options["FLOW_UNITS"] == "CFS" else 1.0
    coords = {r[0]: (float(r[1]), float(r[2])) for r in parsed.get("[COORDINATES]", [])}
    nodes, links, assets = [], [], []
    for section, kind in [("[STORAGE]", "basin"), ("[JUNCTIONS]", "junction"), ("[OUTFALLS]", "outfall"), ("[DIVIDERS]", "junction")]:
        for row in parsed.get(section, []):
            x, y = coords.get(row[0], (0, 0))
            nodes.append({"id": row[0], "label": "Basin " + row[0] if kind == "basin" else row[0],
                          "type": kind, "x": x, "y": y,
                          "max_depth_m": float(row[2]) * length_factor if kind == "basin" else None})
    xsections = {r[0]: r for r in parsed["[XSECTIONS]"]}
    for section, kind in [("[CONDUITS]", "conduit"), ("[ORIFICES]", "orifice")]:
        for row in parsed.get(section, []):
            links.append({"id": row[0], "source": row[1], "target": row[2], "type": kind,
                          "controllable": kind == "orifice"})
            if kind == "orifice":
                xs = xsections[row[0]]
                if xs[1] != "RECT_CLOSED":
                    raise ValueError("Only curated rectangular bottom orifices are supported by these controllers.")
                assets.append({"id": row[0], "node_id": row[1], "area_m2": float(xs[2]) * float(xs[3]) * length_factor**2,
                               "discharge_coefficient": float(row[5])})
    # Stable natural order matches the published baseline parameter ordering.
    assets.sort(key=lambda a: int("".join(c for c in a["id"] if c.isdigit())))
    start = datetime.strptime(options["START_DATE"] + " " + options["START_TIME"], "%m/%d/%Y %H:%M:%S")
    end = datetime.strptime(options["END_DATE"] + " " + options["END_TIME"], "%m/%d/%Y %H:%M:%S")
    meta = {"id": scenario_id, **SCENARIOS[scenario_id], "nodes": nodes, "links": links, "assets": assets,
            "horizon_s": (end-start).total_seconds(), "start_datetime": start.isoformat(),
            "input_units": options["FLOW_UNITS"], "base_model_sha256": digest(data),
            "source_url": f"https://github.com/kLabUM/pystorms/blob/{PYSTORMS_COMMIT}/pystorms/networks/{scenario_id}.inp",
            "license": "GPL-3.0-only (pystorms repository)", "coordinates_kind": "model schematic; not a geographic flood map"}
    return meta


def rainfall_model(scenario_id, multiplier):
    """Scale only time series referenced by the input's rain gauges."""
    text = (ROOT / "data" / f"{scenario_id}.inp").read_text()
    parsed = sections(text)
    names = {r[r.index("TIMESERIES") + 1] for r in parsed["[RAINGAGES]"] if "TIMESERIES" in r}
    output, rainfall_rows, in_timeseries = [], [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_timeseries = stripped.upper() == "[TIMESERIES]"
        fields = line.split(";", 1)[0].split()
        if in_timeseries and fields and fields[0] in names:
            fields[-1] = format(float(fields[-1]) * multiplier, ".12g")
            line = " ".join(fields)
            rainfall_rows.append(fields)
        output.append(line)
    return "\n".join(output) + "\n", digest({"rain_gauges": parsed["[RAINGAGES]"], "rows": rainfall_rows})
