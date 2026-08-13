#!/usr/bin/env python3
"""Source-neutral, read-mostly controller used by the developer interfaces."""

from __future__ import annotations

import json
import os
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


class SweeperController:
    """Loads trusted local state and exposes allow-listed control actions."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        requested = config_path or Path(os.environ.get("WEB_SWEEPER_CONFIG", DEFAULT_CONFIG))
        self.config_path = requested.expanduser().resolve()
        self.config = _read_json(self.config_path)
        root = self.config.get("projectRoot") or Path(__file__).resolve().parents[3]
        self.project_root = Path(root).expanduser().resolve()

    def _path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.project_root / path

    def _lane(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        state_path = self._path(str(definition.get("statePath", "missing.json")))
        state = _read_json(state_path)
        current_root = _first(state, ("currentRoot", "root"), "")
        checkpoint = _read_json(Path(current_root) / "checkpoint.json") if current_root else {}
        progress = _read_json(Path(current_root) / "staging_upload_progress.json") if current_root else {}
        accepted = int(
            _first(
                checkpoint,
                ("accepted", "acceptedCount", "catalogCount"),
                _first(state, ("acceptedInCurrentBatch", "accepted"), 0),
            )
            or 0
        )
        target = int(_first(state, ("currentBatchSize", "batchSize", "target"), definition.get("target", 0)) or 0)
        uploaded = int(_first(progress, ("uploaded", "uploadedCount", "verified"), 0) or 0)
        stage = str(_first(state, ("stage", "status"), "inactive"))
        updated = _first(
            checkpoint,
            ("updatedAt", "checkpointTimestamp", "lastUpdated"),
            _first(state, ("updatedAt", "checkpointTimestamp"), ""),
        )
        observed = _timestamp(updated)
        age = (datetime.now(timezone.utc) - observed).total_seconds() if observed else None
        running = str(state.get("status", "")).lower() == "running"
        if not running:
            health = "failed"
        elif age is None or age > int(definition.get("redAfterSeconds", 3600)):
            health = "stuck"
        elif age > int(definition.get("watchAfterSeconds", 900)):
            health = "watch"
        else:
            health = "healthy"
        return {
            "id": definition.get("id", definition.get("name", "lane")),
            "name": definition.get("name", "Unnamed lane"),
            "stage": stage,
            "accepted": accepted,
            "target": target,
            "uploaded": uploaded,
            "health": health,
            "detail": definition.get("detail", f"State: {state_path.name}"),
            "updatedAt": updated,
            "currentRoot": current_root,
        }

    def status(self) -> Dict[str, Any]:
        lanes = [self._lane(item) for item in self.config.get("lanes", []) if isinstance(item, dict)]
        return {
            "schemaVersion": 1,
            "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "codexLive": int(self.config.get("codexLive", 0)),
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
        allowed = {
            "sourceSlots": max(1, min(10, int(preferences.get("sourceSlots", 2)))),
            "batchTarget": max(1, min(100000, int(preferences.get("batchTarget", 2000)))),
            "uploadTarget": max(1, min(100000, int(preferences.get("uploadTarget", 100)))),
            "tertiaryEnabled": bool(preferences.get("tertiaryEnabled", False)),
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
