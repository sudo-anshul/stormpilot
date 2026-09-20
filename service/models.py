"""Contained, content-addressed registration of user-owned model inputs."""
import re
import uuid

from engine.models import custom_model_id, inspect_input, metadata, normalize_custom_model
from service.common import RUNTIME, read_json, write_json

REGISTRY = RUNTIME / "models"
TOKEN = re.compile(r"^[a-f0-9]{32}$")
MODEL_ID = re.compile(r"^custom_[a-f0-9]{24}$")


def inspect_model(payload):
    name, text = payload.get("name"), payload.get("inp_text")
    inspection = inspect_input(name, text)
    drafts = REGISTRY / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    # Inspections are disposable; registered models remain independently saved.
    for path in sorted(drafts.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-19]:
        path.unlink(missing_ok=True)
    token = uuid.uuid4().hex
    write_json(drafts / f"{token}.json", {"name": inspection["name"], "inp_text": text})
    return {"token": token, "inspection": inspection}


def register_model(payload):
    token = payload.get("token", "")
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise ValueError("Inspect a model before confirming its mapping.")
    draft = REGISTRY / "drafts" / f"{token}.json"
    if not draft.is_file():
        raise ValueError("That model inspection expired. Inspect the file again.")
    custom = normalize_custom_model({**read_json(draft), **{k: payload[k] for k in (
        "downstream_link", "downstream_threshold_m3s", "targets_m3s") if k in payload}})
    model_id = custom_model_id(custom)
    path = REGISTRY / f"{model_id}.json"
    if not path.exists() and len(list(REGISTRY.glob("custom_*.json"))) >= 20:
        raise ValueError("This server has reached its 20-model import limit.")
    model = metadata(model_id, custom)
    write_json(path, custom)
    return model


def resolve_model(model_id):
    if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id):
        raise ValueError("Choose a published or registered imported model.")
    path = REGISTRY / f"{model_id}.json"
    if not path.is_file():
        raise ValueError("This imported model is unavailable on this server. Import it again.")
    custom = normalize_custom_model(read_json(path))
    if custom_model_id(custom) != model_id:
        raise ValueError("Registered model content does not match its identity.")
    return custom


def imported_models():
    models = []
    for path in sorted(REGISTRY.glob("custom_*.json")):
        try:
            models.append(metadata(path.stem, resolve_model(path.stem)))
        except (ValueError, OSError, KeyError):
            continue
    return models
