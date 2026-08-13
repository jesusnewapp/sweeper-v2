#!/usr/bin/env python3
"""Source-neutral, read-mostly controller used by the developer interfaces."""

from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_CONFIG = Path(__file__).with_name("controller.example.json")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _first(mapping: Dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        value = mapping.get(name)
        if value is not None:
            return value
    return default


def _timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _progress_key(value: Dict[str, Any]) -> str:
    """Bind the inactivity clock to every durable progress signal.

    Accepted count is only one signal. A rate-limited discovery adapter may be
    healthy while it advances query pages or candidate inventory without yet
    accepting another item. Hashing the complete evidence vector prevents that
    legitimate work from being mislabeled as a stalled lane.
    """
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _publication_progress(root: Path) -> Dict[str, Any]:
    """Read exact progress, falling back to exact counters emitted by older writers."""
    progress = _read_json(root / "publication_progress.json")
    try:
        log = (root / "promotion.log").read_text(encoding="utf-8")
    except OSError:
        return progress
    value: Dict[str, Any] = {"phase": "fresh-live-delta"}
    delta = list(re.finditer(
        r"Fresh live delta checked (\d+) published books; removed (\d+), retained (\d+)\.",
        log,
    ))
    if delta:
        match = delta[-1]
        value.update({"phase": "room-allocation", "duplicateRemoved": int(match.group(2)),
                      "publishable": int(match.group(3))})
    uploads = list(re.finditer(r"Uploaded (\d+)/(\d+)", log))
    if uploads:
        # Legacy concurrent writers emitted completed item indexes out of
        # order. The maximum is a monotonic observed marker, not a fabricated
        # completion count. New writers persist an exact atomic counter above.
        maximum = max(int(match.group(1)) for match in uploads)
        target = int(uploads[-1].group(2))
        value.update({"phase": "storage-upload", "uploaded": maximum,
                      "uploadTarget": target, "legacyObservedMarker": True})
    published = list(re.finditer(r"Published (\d+) new or changed Codex records\.", log))
    if published:
        value.update({"phase": "publication-complete",
                      "published": int(published[-1].group(1))})
        if uploads:
            value["uploaded"] = int(uploads[-1].group(2))
    verified = list(re.finditer(r"Verified (\d+)/(\d+) live Codex books\.", log))
    if verified:
        match = verified[-1]
        value.update({"phase": "live-verification", "liveVerified": int(match.group(1)),
                      "verificationTarget": int(match.group(2))})
    return {**value, **progress}


class SweeperController:
    """Loads trusted local state and exposes allow-listed control actions."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        requested = config_path or Path(os.environ.get("WEB_SWEEPER_CONFIG", DEFAULT_CONFIG))
        self.config_path = requested.expanduser().resolve()
        self.config = _read_json(self.config_path)
        root = self.config.get("projectRoot") or Path(__file__).resolve().parents[3]
        self.project_root = Path(root).expanduser().resolve()
        self._progress_observations: Dict[str, Dict[str, Any]] = {}
        self._stage_observations: Dict[str, Dict[str, Any]] = {}

    def _path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.project_root / path

    def _lane(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        if definition.get("kind") == "publisher":
            return self._publisher_lane(definition)
        state_path = self._path(str(definition.get("statePath", "missing.json")))
        state = _read_json(state_path)
        current_root = _first(state, ("currentRoot", "root"), "")
        checkpoint = _read_json(Path(current_root) / "checkpoint.json") if current_root else {}
        progress = _read_json(Path(current_root) / "staging_upload_progress.json") if current_root else {}
        accepted = _count(
            _first(
                checkpoint,
                ("acceptedCount", "catalogCount", "accepted"),
                _first(
                    state,
                    ("acceptedInCurrentBatch", "accepted", "membershipReconciliation"),
                    0,
                ),
            )
        )
        if isinstance(state.get("membershipReconciliation"), dict) and not accepted:
            accepted = _count(state["membershipReconciliation"].get("catalogMembers"))
        target = int(_first(state, ("currentBatchSize", "batchSize", "target"), definition.get("target", 0)) or 0)
        uploaded = int(_first(progress, ("uploaded", "uploadedCount", "verified"), 0) or 0)
        progress_phase = str(progress.get("phase", ""))
        stage = progress_phase if progress_phase and progress_phase != "complete" else str(
            _first(state, ("stage", "status"), "inactive")
        )
        state_updated = _first(
            checkpoint,
            ("updatedAt", "checkpointTimestamp", "lastUpdated"),
            _first(state, ("updatedAt", "checkpointTimestamp"), ""),
        )
        progress_updated = _first(progress, ("updatedAt", "checkpointTimestamp"), "")
        state_observed = _timestamp(state_updated)
        progress_observed = _timestamp(progress_updated)
        updated = (
            progress_updated
            if progress_observed and (not state_observed or progress_observed > state_observed)
            else state_updated
        )
        observed = _timestamp(updated)
        age = (datetime.now(timezone.utc) - observed).total_seconds() if observed else None
        progress_active = bool(
            progress_phase
            and progress_phase != "complete"
            and age is not None
            and age <= 300
        )
        running = str(state.get("status", "")).lower() == "running" or progress_active
        if not running:
            health = "failed"
        elif age is None or age > int(definition.get("redAfterSeconds", 3600)):
            health = "stuck"
        elif age > int(definition.get("watchAfterSeconds", 900)):
            health = "watch"
        else:
            health = "healthy"
        display_accepted = accepted
        display_target = target
        detail = definition.get("detail", f"State: {state_path.name}")
        if progress_active:
            display_accepted = uploaded
            display_target = int(progress.get("total") or accepted or target)
            detail = (
                f"{accepted}/{target} accepted · exact staging upload"
            )
        return {
            "id": definition.get("id", definition.get("name", "lane")),
            "name": definition.get("name", "Unnamed lane"),
            "stage": stage,
            "accepted": display_accepted,
            "target": display_target,
            "uploaded": uploaded,
            "health": health,
            "detail": detail,
            "updatedAt": updated,
            "currentRoot": current_root,
            "progressEvidence": {
                "stage": stage,
                "accepted": accepted,
                "uploaded": uploaded,
                "discovered": _count(_first(checkpoint, ("discovered", "discoveredCount"),
                                           _first(state, ("discovered", "discoveredCount"), 0))),
                "prefiltered": _count(_first(checkpoint, ("prefiltered", "prefilteredCount"),
                                            _first(state, ("prefiltered", "prefilteredCount"), 0))),
                "candidateInventory": _count(_first(
                    state, ("sourceCandidateInventory", "candidateInventory", "candidateCount"), 0)),
                "candidateOffset": _count(_first(state, ("candidateOffset", "cursor", "page"), 0)),
                "discoveryFrontier": _count(_first(state, ("discoveryFrontier", "frontier"), 0)),
                "stateUpdatedAt": state.get("updatedAt", ""),
                "checkpointUpdatedAt": state_updated,
                "uploadUpdatedAt": progress_updated,
            },
        }

    def _publisher_lane(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        state_path = self._path(str(definition.get("statePath", "missing.json")))
        state = _read_json(state_path)
        advances = state.get("automaticAdvanceLog")
        latest = advances[-1] if isinstance(advances, list) and advances else {}
        current_root = str(state.get("currentUnit") or latest.get("root") or "")
        current = bool(state.get("currentUnit"))
        if current:
            root = Path(current_root)
            catalog = _read_json(root / "catalog.json").get("books", [])
            publication = _read_json(root / "publication_verification.json")
            promotion = _read_json(root / "promotion_validation.json")
            progress = _publication_progress(root)
            accepted = _count(catalog)
            published = _count(progress.get("published", publication.get("published")))
            verified = _count(
                progress.get("liveVerified", promotion.get("liveVerified", publication.get("verified")))
            )
            duplicate_removed = _count(progress.get("duplicateRemoved"))
            uploaded = _count(progress.get("uploaded"))
            target = accepted
            updated = _first(
                promotion,
                ("checkedAt", "completedAt"),
                _first(publication, ("checkedAt", "completedAt"), state.get("checkedAt", "")),
            )
            stage = str(progress.get("phase") or state.get("currentAction", "publishing"))
            phase_count = {
                "storage-upload": uploaded,
                "publication-complete": published,
                "live-verification": verified,
                "complete": verified,
            }.get(stage, 0)
            target = {
                "storage-upload": _count(progress.get("uploadTarget")) or accepted,
                "publication-complete": _count(progress.get("publishable")) or accepted,
                "live-verification": _count(progress.get("verificationTarget")) or accepted,
                "complete": _count(progress.get("verificationTarget")) or accepted,
            }.get(stage, accepted)
        else:
            last_published = _count(latest.get("published"))
            last_verified = _count(latest.get("liveVerified"))
            published = 0
            verified = 0
            accepted = 0
            target = 0
            updated = latest.get("completedAt") or state.get("checkedAt", "")
            duplicate_removed = 0
            uploaded = 0
            phase_count = 0
        observed = _timestamp(state.get("checkedAt"))
        age = (datetime.now(timezone.utc) - observed).total_seconds() if observed else None
        running = bool(state.get("listenerActive"))
        if not running:
            health = "failed"
        elif age is None or age > int(definition.get("redAfterSeconds", 3600)):
            health = "stuck"
        elif age > int(definition.get("watchAfterSeconds", 900)):
            health = "watch"
        else:
            health = "healthy"
        queue = state.get("queue") if isinstance(state.get("queue"), dict) else {}
        pending_units = _count(queue.get("pendingUnits"))
        parked_units = _count(queue.get("parkedUnchanged"))
        preflight_units = _count(queue.get("bookkeptPreflight"))
        ready_units = max(0, pending_units - parked_units - preflight_units)
        queued_behind_current = ready_units if current else 0
        if current:
            ready_units = 0
        if not current:
            stage = (
                "Ready for next exact staged unit"
                if ready_units > 0
                else "Listening for next exact staged unit"
            )
        continuation = (
            state.get("automaticContinuation")
            if isinstance(state.get("automaticContinuation"), dict)
            else {}
        )
        return {
            "id": definition.get("id", "publisher"),
            "name": definition.get("name", "Stage-to-live publisher"),
            "stage": stage,
            "accepted": phase_count,
            "target": target,
            "uploaded": uploaded,
            "published": published,
            "liveVerified": verified,
            "health": health,
            "detail": (
                f"{accepted} prepared · {duplicate_removed} duplicates removed · "
                f"{uploaded} uploaded · {published} published · {verified} live-verified · "
                f"{queued_behind_current} queued behind current · "
                f"{parked_units} parked · {preflight_units} preflight"
                if current else
                f"Last completed: {last_published} published · {last_verified} live-verified · "
                f"{ready_units} ready · {parked_units} parked · {preflight_units} preflight"
            ),
            "queueReady": ready_units,
            "queueParked": parked_units,
            "queuePreflight": preflight_units,
            "updatedAt": updated,
            "currentRoot": current_root,
            "progressSince": latest.get("completedAt") if not current else None,
            "codexLive": _count(
                _read_json(Path(current_root) / "promotion_validation.json").get(
                    "publishedLiveTotal"
                )
            )
            if current_root
            else 0,
            "progressEvidence": {
                "stage": stage,
                "currentRoot": current_root,
                "prepared": accepted,
                "duplicatesRemoved": duplicate_removed,
                "uploaded": uploaded,
                "published": published,
                "liveVerified": verified,
                "pendingUnits": pending_units,
                "parkedUnits": parked_units,
                "preflightUnits": preflight_units,
                "watcherCheckedAt": state.get("checkedAt", ""),
                "unitUpdatedAt": updated,
            },
        }

    def _metrics(self) -> Dict[str, Any]:
        value = self.config.get("metricsPath")
        if not value:
            return {}
        return _read_json(self._path(str(value)))

    def status(self) -> Dict[str, Any]:
        lanes = [self._lane(item) for item in self.config.get("lanes", []) if isinstance(item, dict)]
        checked_at = datetime.now(timezone.utc)
        metrics = self._metrics()
        active_ids = {str(lane["id"]) for lane in lanes}
        self._progress_observations = {
            lane_id: observation
            for lane_id, observation in self._progress_observations.items()
            if lane_id in active_ids
        }
        for lane in lanes:
            evidence = lane.pop("progressEvidence", {})
            key = _progress_key(evidence)
            lane_id = str(lane["id"])
            observation = self._progress_observations.get(lane_id)
            if observation is None or observation["key"] != key:
                observation = {"key": key, "since": checked_at}
                self._progress_observations[lane_id] = observation
            lane["progressSince"] = observation["since"].isoformat().replace("+00:00", "Z")
            stage = str(lane.get("stage", "unknown"))
            stage_observation = self._stage_observations.get(lane_id)
            if stage_observation is None or stage_observation["stage"] != stage:
                supplied = _timestamp(lane.get("updatedAt"))
                stage_observation = {"stage": stage, "since": supplied or checked_at}
                self._stage_observations[lane_id] = stage_observation
            lane["stageSince"] = stage_observation["since"].isoformat().replace("+00:00", "Z")
        codex_live = _count(metrics.get("codexLive", self.config.get("codexLive", 0)))
        publisher_live = max((_count(lane.get("codexLive")) for lane in lanes), default=0)
        codex_live = max(codex_live, publisher_live)
        return {
            "schemaVersion": 1,
            "checkedAt": checked_at.isoformat().replace("+00:00", "Z"),
            "codexLive": codex_live,
            "confirmedStaged": _count(metrics.get("confirmedStaged")),
            "metricsCheckedAt": metrics.get("checkedAt", ""),
            "lanes": lanes,
            "allHealthy": bool(lanes) and all(item["health"] == "healthy" for item in lanes),
            "productionWriterLimit": 1,
        }

    def action(self, action: str, lane_id: str) -> Dict[str, Any]:
        """Run only a command explicitly provided by the trusted host config."""
        actions = self.config.get("actions", {})
        definition = actions.get(action) if isinstance(actions, dict) else None
        if not isinstance(definition, dict):
            raise ValueError(f"action is disabled: {action}")
        allowed_lanes = definition.get("lanes", [])
        if allowed_lanes and lane_id not in allowed_lanes:
            raise ValueError(f"action {action} is not allowed for lane {lane_id}")
        command = definition.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            raise ValueError(f"action has no trusted command: {action}")
        rendered = [part.replace("{lane}", lane_id) for part in command]
        process = subprocess.Popen(
            rendered,
            cwd=self.project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"accepted": True, "action": action, "lane": lane_id, "pid": process.pid}

    def save_preferences(self, preferences: Dict[str, Any]) -> None:
        """Atomically save harmless UI settings separately from host commands."""
        slot_count = max(1, min(10, int(preferences.get("sourceSlots", 2))))
        raw_models = preferences.get("models", [])
        models: List[Dict[str, Any]] = []
        if isinstance(raw_models, list):
            for index, raw in enumerate(raw_models[:slot_count], start=1):
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("name", "")).strip()[:120]
                connector = str(raw.get("connector", "")).strip()[:1000]
                models.append({
                    "slot": index,
                    "name": name,
                    "connector": connector,
                    "batchTarget": max(1, min(100000, int(raw.get("batchTarget", 2000)))),
                    "uploadTarget": max(1, min(100000, int(raw.get("uploadTarget", 100)))),
                })
        allowed = {
            "sourceSlots": slot_count,
            "batchTarget": max(1, min(100000, int(preferences.get("batchTarget", 2000)))),
            "uploadTarget": max(1, min(100000, int(preferences.get("uploadTarget", 100)))),
            "tertiaryEnabled": bool(preferences.get("tertiaryEnabled", False)),
            "models": models,
        }
        destination = self.config_path.with_name("controller.preferences.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=destination.name, dir=destination.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(allowed, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
