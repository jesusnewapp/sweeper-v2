from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .manifest import candidates
from .model import Candidate, Config, Policy, Source
from .state import State


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def policy_reason(item: Candidate, policy: Policy) -> str:
    if policy.require_language and not item.language:
        return "missing-language"
    if policy.languages and item.language.lower() not in {value.lower() for value in policy.languages}:
        return "language-not-allowed"
    if policy.require_license and not item.license:
        return "missing-license"
    if policy.licenses and item.license.lower() not in {value.lower() for value in policy.licenses}:
        return "license-not-allowed"
    if policy.media_types and item.media_type.lower() not in {value.lower() for value in policy.media_types}:
        return "media-type-not-allowed"
    if policy.artifact_classes and item.artifact_class.lower() not in {value.lower() for value in policy.artifact_classes}:
        return "artifact-class-not-allowed"
    if policy.data_classes and item.data_class.lower() not in {value.lower() for value in policy.data_classes}:
        return "data-class-not-allowed"
    return ""


def review(item: Candidate, path: Path, policy: Policy) -> tuple[bool, str]:
    if not policy.reviewer_command:
        return True, ""
    payload = {"candidate": item.__dict__, "local_path": str(path)}
    result = subprocess.run(policy.reviewer_command, input=json.dumps(payload), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        return False, f"reviewer-exit-{result.returncode}"
    try:
        decision = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, "reviewer-invalid-json"
    return decision.get("accepted") is True, str(decision.get("reason", "reviewer-rejected"))


def retrieve(item: Candidate, source: Source, config: Config, state: State) -> None:
    early = policy_reason(item, config.policy)
    stamp = now()
    common = dict(source_id=item.source_id, item_id=item.item_id, url=item.url, title=item.title, updated_at=stamp)
    if early:
        state.record(**common, status="rejected", reason=early)
        return
    request = urllib.request.Request(item.url, headers={"User-Agent": config.user_agent, **source.headers})
    store = config.workspace / "objects"
    store.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    fd, temporary_name = tempfile.mkstemp(prefix="sweeper-", dir=str(config.workspace))
    try:
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(request, timeout=90) as response:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if config.policy.maximum_bytes is not None and size > config.policy.maximum_bytes:
                    state.record(**common, status="rejected", reason="maximum-bytes-exceeded", size=size)
                    return
                digest.update(block)
                output.write(block)
        if size < config.policy.minimum_bytes:
            state.record(**common, status="rejected", reason="below-minimum-bytes", size=size)
            return
        hexdigest = digest.hexdigest()
        owner = state.hash_owner(hexdigest)
        if owner:
            state.record(**common, status="duplicate", reason=f"content-match:{owner}", digest=hexdigest, size=size)
            return
        destination = store / hexdigest[:2] / hexdigest
        destination.parent.mkdir(parents=True, exist_ok=True)
        Path(temporary_name).replace(destination)
        accepted, reason = review(item, destination, config.policy)
        if not accepted:
            state.record(**common, status="rejected", reason=reason, digest=hexdigest,
                         size=size, local_path=str(destination))
            return
        state.record(**common, status="accepted", digest=hexdigest, size=size, local_path=str(destination))
    except Exception as error:
        state.record(**common, status="failed", reason=f"{type(error).__name__}:{error}")
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def run(config: Config, progress: Optional[Callable[[dict], None]] = None) -> dict:
    config.workspace.mkdir(parents=True, exist_ok=True)
    state = State(config.workspace / "state.sqlite3")
    source_errors = []
    try:
        ordered = sorted((s for s in config.sources if s.enabled), key=lambda s: (s.lane != "major", s.slot, s.id))
        for source in ordered:
            delay = 1.0 / source.requests_per_second
            if progress:
                progress({"phase": "source", "source": source.id})
            try:
                for item in candidates(source, config.user_agent):
                    if state.status(item.source_id, item.item_id) in {"accepted", "rejected", "duplicate"}:
                        continue
                    if progress:
                        progress({"phase": "item", "source": source.id, "item": item.item_id})
                    retrieve(item, source, config, state)
                    time.sleep(delay)
            except Exception as error:
                source_errors.append({"source": source.id,
                    "error": f"{type(error).__name__}: {error}"})
                if progress:
                    progress({"phase": "source-error", "source": source.id,
                              "error": source_errors[-1]["error"]})
                continue
        return {"completedAt": now(), "counts": state.counts(), "workspace": str(config.workspace),
                "sourceErrors": source_errors}
    finally:
        state.close()
