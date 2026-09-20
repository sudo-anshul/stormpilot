"""Pinned public benchmark inputs and explicit unit/topology metadata."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import math
import re
import tempfile

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


def natural_key(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"(\d+)", value))


def _metadata(scenario_id, data, profile):
    parsed = sections(data.decode())
    options = {r[0].upper(): r[1] for r in parsed["[OPTIONS]"]}
    length_factor = 0.3048 if options["FLOW_UNITS"].upper() in {"CFS", "GPM", "MGD"} else 1.0
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
                if xs[1].upper() != "RECT_CLOSED":
                    raise ValueError("Only curated rectangular bottom orifices are supported by these controllers.")
                assets.append({"id": row[0], "node_id": row[1], "area_m2": float(xs[2]) * float(xs[3]) * length_factor**2,
                               "discharge_coefficient": float(row[5])})
    # Stable natural order matches the published baseline parameter ordering.
    assets.sort(key=lambda a: natural_key(a["id"]))
    start = datetime.strptime(options["START_DATE"] + " " + options["START_TIME"], "%m/%d/%Y %H:%M:%S")
    end = datetime.strptime(options["END_DATE"] + " " + options["END_TIME"], "%m/%d/%Y %H:%M:%S")
    meta = {"id": scenario_id, **profile, "nodes": nodes, "links": links, "assets": assets,
            "horizon_s": (end-start).total_seconds(), "start_datetime": start.isoformat(),
            "input_units": options["FLOW_UNITS"], "base_model_sha256": digest(data),
            "coordinates_kind": "model schematic; not a geographic flood map"}
    return meta


def metadata(scenario_id, custom_model=None):
    if custom_model is not None:
        custom = normalize_custom_model(custom_model)
        expected = custom_model_id(custom)
        if scenario_id != expected:
            raise ValueError("Imported model ID differs from its input and declared mapping.")
        model_path = f"engine/data/imports/{expected}.inp"
        path = ROOT.parent / model_path
        data = custom["inp_text"].encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            # Content-addressed names cannot select or overwrite arbitrary files.
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                handle.write(data)
                temporary = Path(handle.name)
            temporary.replace(path)
        return _metadata(expected, data, {
            "label": custom["name"], "description": "User-supplied model. Calibration and ownership are not independently verified.",
            "downstream_link": custom["downstream_link"], "threshold_m3s": custom["downstream_threshold_m3s"],
            "targets_m3s": custom["targets_m3s"], "model_kind": "user-supplied simulation model", "origin": "imported",
            "model_path": model_path, "source_url": "", "license": "User-supplied; original rights apply",
            "mapping_sha256": digest({k: v for k, v in custom.items() if k != "inp_text"}),
        })
    if scenario_id not in SCENARIOS:
        raise ValueError("Choose a published scenario or supply its registered custom_model.")
    return _metadata(scenario_id, (ROOT / "data" / f"{scenario_id}.inp").read_bytes(), {
        **SCENARIOS[scenario_id], "origin": "published", "model_path": f"engine/data/{scenario_id}.inp",
        "source_url": f"https://github.com/kLabUM/pystorms/blob/{PYSTORMS_COMMIT}/pystorms/networks/{scenario_id}.inp",
        "license": "GPL-3.0-only (pystorms repository)",
    })


IMPORT_MAX_BYTES = 262144
IMPORT_SECTIONS = {"TITLE", "OPTIONS", "RAINGAGES", "EVAPORATION", "SUBCATCHMENTS", "SUBAREAS", "INFILTRATION",
                   "JUNCTIONS", "OUTFALLS", "DIVIDERS", "STORAGE", "CONDUITS", "ORIFICES", "XSECTIONS", "LOSSES",
                   "CURVES", "TIMESERIES", "REPORT", "TAGS", "MAP", "COORDINATES", "VERTICES", "POLYGONS", "SYMBOLS"}
IMPORT_OPTIONS = set("FLOW_UNITS INFILTRATION FLOW_ROUTING LINK_OFFSETS MIN_SLOPE ALLOW_PONDING SKIP_STEADY_STATE START_DATE START_TIME REPORT_START_DATE REPORT_START_TIME END_DATE END_TIME SWEEP_START SWEEP_END DRY_DAYS REPORT_STEP WET_STEP DRY_STEP ROUTING_STEP INERTIAL_DAMPING NORMAL_FLOW_LIMITED FORCE_MAIN_EQUATION VARIABLE_STEP LENGTHENING_STEP MIN_SURFAREA MAX_TRIALS HEAD_TOLERANCE SYS_FLOW_TOL LAT_FLOW_TOL MINIMUM_STEP THREADS SURCHARGE_METHOD IGNORE_QUALITY IGNORE_SNOWMELT IGNORE_GROUNDWATER IGNORE_RDII".split())


def inspect_input(name, inp_text):
    """Inspect a deliberately bounded self-contained SWMM subset before native execution.

    External file directives, arbitrary control rules and unsupported sections are
    rejected; the original input bytes are preserved, never silently repaired.
    Native SWMM validation still runs when the user starts the experiment.
    """
    if not isinstance(inp_text, str) or not inp_text or len(inp_text.encode()) > IMPORT_MAX_BYTES:
        raise ValueError("Upload a UTF-8 .inp file of at most 256 KiB.")
    if any(ord(c) < 32 and c not in "\r\n\t" for c in inp_text):
        raise ValueError("The model contains unsupported control characters.")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("Model name must contain 1–80 characters.")
    seen = set()
    for line in inp_text.splitlines():
        clean = line.split(";", 1)[0].strip()
        if len(line) > 1024:
            raise ValueError("Model lines must be at most 1024 characters.")
        if clean.startswith("["):
            section = clean.upper()
            if section not in {f"[{s}]" for s in IMPORT_SECTIONS}:
                raise ValueError(f"Unsupported import section {section}. Use inline rainfall and supported hydraulic elements.")
            if section in seen:
                raise ValueError(f"Duplicate section {section} is unsupported.")
            seen.add(section)
    parsed = sections(inp_text)
    for section, rows in parsed.items():
        if section != "[TITLE]" and any(token.upper().strip('"\'') == "FILE" for row in rows for token in row):
            raise ValueError("External FILE references are unsupported. Embed all time-series values in the .inp file.")
    options = {}
    for row in parsed.get("[OPTIONS]", []):
        if len(row) != 2 or row[0].upper() not in IMPORT_OPTIONS:
            raise ValueError("Unsupported OPTIONS entry. External paths and ambiguous option abbreviations are rejected.")
        key = row[0].upper()
        if key in options:
            raise ValueError(f"Duplicate option {key} is unsupported.")
        options[key] = row[1].upper()
    if options.get("FLOW_UNITS") not in {"CFS", "GPM", "MGD", "CMS", "LPS", "MLD"}:
        raise ValueError("Declare FLOW_UNITS explicitly (CFS, GPM, MGD, CMS, LPS or MLD).")
    if options.get("LINK_OFFSETS", "DEPTH") != "DEPTH" or options.get("FLOW_ROUTING") != "DYNWAVE":
        raise ValueError("Imported models require DYNWAVE routing and DEPTH link offsets.")
    if options.get("THREADS", "1") != "1":
        raise ValueError("Set THREADS to 1 for reproducible bounded execution.")
    try:
        provisional = _metadata("inspection", inp_text.encode(), {})
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"Cannot read supported model metadata: {exc}") from exc
    if not 0 < provisional["horizon_s"] <= 168 * 3600:
        raise ValueError("Use a simulation horizon greater than zero and at most 168 hours.")
    if not 1 <= len(provisional["nodes"]) <= 200 or len(provisional["links"]) > 500 or len(parsed.get("[SUBCATCHMENTS]", [])) > 200:
        raise ValueError("Import limit: 200 nodes, 500 links and 200 subcatchments.")
    if not 1 <= len(provisional["assets"]) <= 40:
        raise ValueError("Include 1–40 controllable rectangular bottom orifices.")
    basins = {n["id"] for n in provisional["nodes"] if n["type"] == "basin" and n["max_depth_m"] > 0}
    for row in parsed.get("[ORIFICES]", []):
        if row[1] not in basins or row[3].upper() != "BOTTOM" or float(row[4]) != 0:
            raise ValueError("Every controlled orifice must be a zero-offset BOTTOM outlet from a positive-depth storage node.")
    for asset in provisional["assets"]:
        if not math.isfinite(asset["area_m2"]) or asset["area_m2"] <= 0 or not 0 < asset["discharge_coefficient"] <= 1:
            raise ValueError("Outlet area must be positive and discharge coefficient must be in (0, 1].")
    for node in provisional["nodes"]:
        if not all(math.isfinite(node[k]) for k in ("x", "y")):
            raise ValueError("Model coordinates must be finite.")
        if node["type"] == "basin" and (not math.isfinite(node["max_depth_m"]) or node["max_depth_m"] <= 0):
            raise ValueError("Storage-node maximum depths must be finite and positive.")
    if not parsed.get("[RAINGAGES]"):
        raise ValueError("Include at least one rain gauge with inline TIMESERIES rainfall.")
    series = {r[0] for r in parsed.get("[TIMESERIES]", [])}
    for row in parsed["[RAINGAGES]"]:
        if len(row) < 6 or row[4].upper() != "TIMESERIES" or row[5] not in series:
            raise ValueError("Every rain gauge must reference an included TIMESERIES.")
    return {"name": name.strip(), "sha256": provisional["base_model_sha256"], "flow_units": provisional["input_units"],
            "duration_hours": provisional["horizon_s"] / 3600, "assets": provisional["assets"],
            "nodes": provisional["nodes"], "downstream_links": provisional["links"],
            "warnings": ["Input structure inspected; SWMM hydraulic validation runs when you start an experiment.",
                         "No calibration or field validity is inferred. Choose your downstream measurement and targets in SI units."]}


def normalize_custom_model(payload):
    if not isinstance(payload, dict):
        raise ValueError("custom_model must be an object.")
    info = inspect_input(payload.get("name"), payload.get("inp_text"))
    downstream = str(payload.get("downstream_link", ""))
    if downstream not in {l["id"] for l in info["downstream_links"]}:
        raise ValueError("Select a downstream link present in the imported model.")
    threshold = payload.get("downstream_threshold_m3s")
    if isinstance(threshold, bool) or not isinstance(threshold, (float, int)) or not math.isfinite(threshold) or not 0 < threshold <= 1e5:
        raise ValueError("Downstream flow threshold must be in (0, 100000] m³/s.")
    targets = payload.get("targets_m3s")
    if targets is None:
        targets = [threshold / len(info["assets"])] * len(info["assets"])
    if not isinstance(targets, list) or len(targets) != len(info["assets"]):
        raise ValueError("Provide one discharge target for each outlet in the displayed asset order.")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not 0 < v <= 1e5 for v in targets):
        raise ValueError("Every outlet target must be in (0, 100000] m³/s.")
    return {"name": info["name"], "inp_text": payload["inp_text"], "downstream_link": downstream,
            "downstream_threshold_m3s": float(threshold), "targets_m3s": [float(v) for v in targets]}


def custom_model_id(payload):
    return "custom_" + digest(payload)[:24]


def rainfall_model(scenario_id, multiplier, custom_model=None):
    """Scale only time series referenced by the input's rain gauges."""
    text = custom_model["inp_text"] if custom_model is not None else (ROOT / "data" / f"{scenario_id}.inp").read_text()
    parsed = sections(text)
    names = {r[5] for r in parsed["[RAINGAGES]"] if len(r) > 5 and r[4].upper() == "TIMESERIES"}
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
