"""Private Blob persistence; local files are only a cache in cloud deployments."""
import json
import hashlib
from contextlib import contextmanager
from functools import lru_cache
import logging
from pathlib import Path
import subprocess
import shutil
import tempfile
import threading
import time
import zipfile

from service.common import ROOT, JOBS, read_json, write_json
from service.models import REGISTRY, MODEL_ID

PREFIX = "stormpilot/v1/"
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
_REQUEST = threading.local()


@contextmanager
def request_budget(seconds=270):
    previous = getattr(_REQUEST, "deadline", None)
    deadline = time.monotonic() + seconds
    _REQUEST.deadline = min(previous, deadline) if previous is not None else deadline
    try:
        yield
    finally:
        _REQUEST.deadline = previous


def remaining_seconds():
    deadline = getattr(_REQUEST, "deadline", None)
    return None if deadline is None else deadline - time.monotonic()


def bounded_timeout(maximum, reserve=0):
    remaining = remaining_seconds()
    if remaining is None:
        return maximum
    available = remaining - reserve
    if available <= 0:
        raise RuntimeError("This request reached its cloud time limit. Retry with a smaller experiment budget.")
    return min(maximum, available)


def job_lock(job_id):
    """One cache writer/hydrator per job in this container instance."""
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(job_id, threading.RLock())


@contextmanager
def locked_job(job_id):
    lock = job_lock(job_id)
    if not lock.acquire(timeout=bounded_timeout(270)):
        raise RuntimeError("This source is busy and the request reached its time limit. Retry shortly.")
    try:
        yield
    finally:
        lock.release()


@contextmanager
def source_lease(job_id, preserve=False):
    """Keep hydrated source files alive until this dependent request finishes."""
    with locked_job(job_id):
        try:
            yield
        finally:
            folder = JOBS / job_id
            if not preserve and (folder / ".hydrated").exists():
                try:
                    _prune_job(folder)
                except OSError as exc:
                    # A completed HTTP response must not become malformed if
                    # disposable-cache cleanup fails after durable publication.
                    logging.getLogger(__name__).warning("Could not evict job cache %s: %s", job_id, exc)


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            bounded_timeout(90)
            digest.update(chunk)
    return digest.hexdigest()


def call(action, **arguments):
    completed = subprocess.run(["node", str(ROOT / "scripts/blob.mjs")],
        input=json.dumps({"action": action, **arguments}, allow_nan=False), capture_output=True, text=True,
        timeout=bounded_timeout(90))
    if completed.returncode:
        raise RuntimeError("Evidence storage did not complete: " + completed.stderr[-300:])
    return json.loads(completed.stdout)


def load_job(job_id, full=False):
    with locked_job(job_id):
        return _load_job(job_id, full)


def _load_job(job_id, full):
    folder = JOBS / job_id
    if full and (folder / ".hydrated").exists():
        return True
    manifest = call("get_json", key=PREFIX + f"jobs/{job_id}/complete.json")
    if manifest is None:
        return False
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("status", "request", "view", "report"):
        if name in manifest:
            write_json(folder / f"{name}.json", manifest[name])
    if full:
        artifact = manifest.get("artifacts", {}).get("workspace", {})
        key = artifact.get("key", PREFIX + f"jobs/{job_id}/workspace.zip")
        # Failed downloads/extractions never leave a trusted partial cache.
        with tempfile.TemporaryDirectory(prefix="hydrate-", dir=JOBS) as temporary:
            staging = Path(temporary)
            archive = staging / "workspace.zip"
            if not call("get_file", key=key, path=str(archive)):
                raise RuntimeError("The recorded job manifest exists but its evidence workspace is missing.")
            if artifact.get("sha256") and file_sha256(archive) != artifact["sha256"]:
                raise RuntimeError("The downloaded evidence workspace does not match its recorded SHA-256.")
            extracted = staging / "files"
            extracted.mkdir()
            with zipfile.ZipFile(archive) as bundle:
                if sum(item.file_size for item in bundle.infolist()) > 512 * 1024 * 1024:
                    raise RuntimeError("The recorded evidence exceeds the supported cache size.")
                for name in bundle.namelist():
                    if not (extracted / name).resolve().is_relative_to(extracted.resolve()):
                        raise RuntimeError("The recorded evidence has an invalid path.")
                for item in bundle.infolist():
                    bounded_timeout(90)
                    bundle.extract(item, extracted)
            for source in extracted.iterdir():
                destination = folder / source.name
                if destination.is_dir():
                    shutil.rmtree(destination)
                source.replace(destination)
        (folder / ".hydrated").touch()
    return True


def _same_completion(existing, proposed):
    # Archive ZIP metadata may differ across cold containers; the first complete
    # publication wins only if the actual recorded result is identical.
    return all(existing.get(name) == proposed.get(name) for name in ("status", "request", "view", "report"))


def _prune_job(folder):
    for path in list(folder.iterdir()):
        if path.name in {"status.json", "request.json", "view.json", "report.json"}:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def save_job(job_id, prune=True):
    with locked_job(job_id):
        return _save_job(job_id, prune)


def _save_job(job_id, prune):
    folder = JOBS / job_id
    status = read_json(folder / "status.json")
    manifest = {"schema_version": "stormpilot.cloud-completion.v2", "status": status,
                "request": read_json(folder / "request.json")}
    for name in ("view", "report"):
        if (folder / f"{name}.json").is_file():
            manifest[name] = read_json(folder / f"{name}.json")
    completion_key = PREFIX + f"jobs/{job_id}/complete.json"
    existing = call("get_json", key=completion_key)
    if existing is not None:
        if not _same_completion(existing, manifest):
            raise RuntimeError("This immutable job id already records a different result.")
        if prune:
            _prune_job(folder)
        return existing
    evidence = folder / "evidence.zip"
    if status.get("status") == "completed" and not evidence.is_file():
        raise RuntimeError("A completed job cannot be published without its evidence archive.")
    workspace = folder / "workspace.zip"
    with zipfile.ZipFile(workspace, "w", zipfile.ZIP_DEFLATED, compresslevel=4) as bundle:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.name not in {"workspace.zip", "evidence.zip", ".hydrated"}:
                info = zipfile.ZipInfo(str(path.relative_to(folder)), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                with path.open("rb") as source, bundle.open(info, "w") as destination:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        bounded_timeout(90)
                        destination.write(chunk)
    manifest["artifacts"] = {}
    for name, path in (("workspace", workspace), ("evidence", evidence)):
        if not path.is_file():
            continue
        sha = file_sha256(path)
        key = PREFIX + f"jobs/{job_id}/artifacts/{sha}-{name}.zip"
        call("put_file", key=key, path=str(path), sha256=sha, content_type="application/zip")
        manifest["artifacts"][name] = {"key": key, "sha256": sha, "size_bytes": path.stat().st_size}
    # Publish the immutable completion record last. Readers never observe a
    # completed result whose required data uploads are still in progress.
    try:
        call("put_json", key=completion_key, value=manifest)
    except (RuntimeError, subprocess.TimeoutExpired):
        # A competing container or an acknowledged-but-disconnected write may
        # already have committed this same result. Never overwrite completion.
        existing = call("get_json", key=completion_key)
        if existing is None or not _same_completion(existing, manifest):
            raise
        manifest = existing
    workspace.unlink()
    # Shared installed demos opt out. Other cache readers/hydrators are excluded
    # by the same per-job lock until durable publication and pruning complete.
    if prune:
        _prune_job(folder)
    return manifest


def load_models():
    cursor = None
    while True:
        result = call("list", prefix=PREFIX + "models/", limit=25, cursor=cursor)
        for key in result["paths"]:
            name = Path(key).name
            if name.endswith(".json") and MODEL_ID.fullmatch(name[:-5]):
                load_model(name[:-5])
        if not result["has_more"]:
            break
        next_cursor = result.get("cursor")
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("The model listing did not return a valid continuation cursor.")
        cursor = next_cursor


def load_model(model_id):
    """Resolve a selected model directly, independent of catalogue pagination."""
    if not isinstance(model_id, str) or not MODEL_ID.fullmatch(model_id):
        raise ValueError("Invalid imported model identity.")
    model = call("get_json", key=PREFIX + f"models/{model_id}.json")
    if model is None:
        return False
    write_json(REGISTRY / f"{model_id}.json", model)
    return True


def save_model(model_id):
    path = REGISTRY / f"{model_id}.json"
    call("put_json", key=PREFIX + "models/" + path.name, value=read_json(path), overwrite=True)


def load_draft(token):
    value = call("get_json", key=PREFIX + f"drafts/{token}.json")
    if value is not None:
        write_json(REGISTRY / "drafts" / f"{token}.json", value)


def save_draft(token):
    call("put_json", key=PREFIX + f"drafts/{token}.json", value=read_json(REGISTRY / "drafts" / f"{token}.json"))


def download_url(job_id):
    manifest = call("get_json", key=PREFIX + f"jobs/{job_id}/complete.json")
    if manifest is None:
        raise RuntimeError("This job has no completed evidence publication.")
    key = manifest.get("artifacts", {}).get("evidence", {}).get("key", PREFIX + f"jobs/{job_id}/evidence.zip")
    return call("signed_download", key=key)["url"]


@lru_cache(maxsize=8)
def _frozen_sha256(path, size, modified_ns):
    # Cache only while the immutable deployed file's identity remains unchanged.
    return file_sha256(Path(path))


def publish_frozen_archive(path, phase):
    """Publish a fixed full-proof ZIP once per content hash, then sign its URL."""
    if phase not in ("phase1", "phase2"):
        raise ValueError("Unknown fixed evaluation phase.")
    path = Path(path)
    stat = path.stat()
    sha = _frozen_sha256(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    base = PREFIX + f"frozen/{phase}/{sha}/"
    key = base + "evidence.zip"
    manifest = {"schema_version": "stormpilot.frozen-archive.v1", "phase": phase,
                "key": key, "sha256": sha, "size_bytes": stat.st_size}
    with locked_job("frozen:" + phase + ":" + sha):
        existing = call("get_json", key=base + "complete.json")
        if existing is None:
            call("put_file", key=key, path=str(path), sha256=sha, content_type="application/zip")
            call("put_json", key=base + "complete.json", value=manifest)
        elif existing != manifest:
            raise RuntimeError("The fixed evidence publication does not match its recorded content hash.")
    return {**manifest, "url": call("signed_download", key=key)["url"]}
