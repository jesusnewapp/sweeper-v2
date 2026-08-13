"""Restartable, atomic staging verification receipts for public adapters."""

from __future__ import annotations

import hashlib
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


def _acceptance_count(report: dict) -> int:
    """Normalize exact survivor counts while rejecting ambiguous reports."""
    values = [int(report[key]) for key in ("accepted", "prepared")
              if key in report]
    return values[0] if values and len(set(values)) == 1 else -1


def canonical_acceptance_receipt(workspace: Path, source: str,
                                 expected_count: int) -> dict:
    """Normalize a source adapter's exact acceptance evidence.

    Importers may emit ``import_report.json`` while validator-first adapters
    emit ``validation_report.json``. The boundary accepts either known shape,
    validates its exact source/count result, and binds the selected file hash.
    """
    if not source.strip() or expected_count < 1:
        raise ValueError("source and a positive expected count are required")
    import_path = workspace / "import_report.json"
    validation_path = workspace / "validation_report.json"
    if import_path.exists():
        path = import_path
        report = json.loads(path.read_text(encoding="utf-8"))
        if (str(report.get("source", "")) != source or
                _acceptance_count(report) != expected_count):
            raise ValueError("import report does not bind the exact accepted source unit")
        kind = "import-report"
    elif validation_path.exists():
        path = validation_path
        report = json.loads(path.read_text(encoding="utf-8"))
        source_slug = source.casefold().replace(" ", "-")
        if (report.get("passed") is not True or report.get("errors") or
                int(report.get("booksAudited", -1)) != expected_count or
                str(report.get("stagingSource", "")).casefold() != source_slug):
            raise ValueError("validation report does not bind a passing exact source unit")
        kind = "validation-report"
    else:
        raise ValueError("canonical source acceptance receipt is missing")
    return {
        "schemaVersion": 1,
        "source": source,
        "accepted": expected_count,
        "receipt": path.name,
        "receiptKind": kind,
        "receiptSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def migrate_legacy_staging_verification(workspace: Path,
                                        expected_count: int) -> dict:
    """Create a modern receipt only from exact isolated legacy readback."""
    if expected_count < 1:
        raise ValueError("a positive expected count is required")
    verification_path = workspace / "staging_verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if not (
        int(verification.get("prepared", -1)) == expected_count
        and int(verification.get("staged", -1)) == expected_count
        and int(verification.get("verified", -1)) == expected_count
        and verification.get("productionMutated") is False
        and verification.get("byteIdenticalToValidatedLocalArtifacts") is True
    ):
        raise ValueError("legacy staging verification is not an exact isolated set")
    receipt = {
        "schemaVersion": 1,
        "verifiedAt": verification.get("verifiedAt") or _now(),
        "staged": expected_count,
        "passed": True,
        "production_mutated": False,
        "verification": "legacy-exact-remote-readback",
        "stagingVerificationSha256": hashlib.sha256(
            verification_path.read_bytes()).hexdigest(),
    }
    _atomic_json(workspace / "dock-staging.json", receipt)
    return receipt


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
