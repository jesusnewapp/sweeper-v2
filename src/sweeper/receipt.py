"""Restartable, atomic staging verification receipts for public adapters."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class RestartableStagingReceipt:
    """Checkpoint exact readback without exposing a premature receipt.

    Adapters call :meth:`record` after each remote artifact is read back and
    hash-matched. A crash leaves only neutral progress. :meth:`finish` creates
    the admission receipt atomically and only after every member is verified.
    """

    def __init__(self, workspace: Path, unit: str, membership: dict[str, str]):
        if not unit.strip() or not membership:
            raise ValueError("unit and non-empty exact membership are required")
        self.workspace = workspace
        self.unit = unit
        self.membership = dict(sorted((str(key), str(value))
                                      for key, value in membership.items()))
        self.progress_path = workspace / "staging-verification-progress.json"
        self.verified: dict[str, str] = {}
        if self.progress_path.exists():
            progress = json.loads(self.progress_path.read_text(encoding="utf-8"))
            if progress.get("unit") == unit and progress.get("membership") == self.membership:
                candidate = progress.get("verified") or {}
                self.verified = {key: digest for key, digest in candidate.items()
                                 if self.membership.get(key) == digest}

    def remaining(self) -> list[str]:
        return [key for key in self.membership if key not in self.verified]

    def record(self, key: str, observed_sha256: str) -> None:
        if self.membership.get(key) != observed_sha256:
            raise ValueError(f"{key}: remote staging hash differs from exact membership")
        self.verified[key] = observed_sha256
        _atomic_json(self.progress_path, {
            "schemaVersion": 1, "unit": self.unit, "membership": self.membership,
            "verified": dict(sorted(self.verified.items())),
            "verifiedCount": len(self.verified), "total": len(self.membership),
            "updatedAt": _now(),
        })

    def finish(self, receipt_name: str = "dock-staging.json") -> dict:
        if self.remaining():
            raise ValueError(f"staging verification incomplete: {len(self.verified)}/{len(self.membership)}")
        receipt = {
            "schemaVersion": 1, "verifiedAt": _now(), "unit": self.unit,
            "items": self.membership, "staged": len(self.membership),
            "passed": True, "production_mutated": False,
            "verification": "exact-remote-readback",
        }
        _atomic_json(self.workspace / receipt_name, receipt)
        if self.progress_path.exists():
            self.progress_path.unlink()
        return receipt
