from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .state import State
from .activity import record as activity_record


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def staged(state: State) -> list[dict]:
    return state.accepted_items()


def membership(items: list[dict]) -> dict[str, str]:
    result = {}
    for item in items:
        key = f"{item['source_id']}:{item['item_id']}"
        if key in result:
            raise ValueError(f"{key}: duplicate staged membership key")
        path = Path(str(item.get("local_path") or ""))
        if not item.get("sha256") or not path.is_file():
            raise ValueError(f"{key}: staged object or SHA-256 is missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ValueError(f"{key}: staged object hash changed")
        result[key] = actual
    if not result:
        raise ValueError("staging dock is empty")
    return result


def validate_attestation(workspace: Path, attestation_path: Path) -> dict:
    state = State(workspace / "state.sqlite3")
    try: current = membership(staged(state))
    finally: state.close()
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    if attestation.get("approved") is not True:
        raise ValueError("attestation is not approved")
    if not str(attestation.get("reviewed_by", "")).strip() or not attestation.get("reviewed_at"):
        raise ValueError("attestation reviewer identity and timestamp are required")
    expected = attestation.get("items")
    if not isinstance(expected,dict) or not expected:
        raise ValueError("attestation has no approved survivor membership")
    if any(current.get(key)!=digest for key,digest in expected.items()):
        raise ValueError("attested survivor membership or hashes differ from staging")
    excluded=sorted(set(current)-set(expected))
    evidence = {"schema_version": 1, "validated_at": now(), "reviewed_by": attestation["reviewed_by"],
                "reviewed_at": attestation["reviewed_at"],
                "attestation_sha256": hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
                "items": expected, "item_count": len(expected), "excluded_items":excluded,
                "single_item_never_blocks_continuation":True,"passed": True}
    atomic_json(workspace / "dock-validation.json", evidence)
    activity_record(workspace,"dock-validation",lane="uploader",status="passed",detail={
        "approved":len(expected),"excluded":len(excluded)})
    return evidence


def command_json(command: list[str], payload: dict) -> dict:
    if not command:
        raise ValueError("an explicit command is required")
    try:
        result = subprocess.run(command, input=json.dumps(payload), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=300)
    except subprocess.TimeoutExpired as error:
        raise ValueError("command exceeded the 300-second safety timeout") from error
    if result.returncode:
        raise ValueError(f"command failed with exit {result.returncode}: {result.stderr[-500:]}")
    try: return json.loads(result.stdout)
    except json.JSONDecodeError as error: raise ValueError("command returned invalid JSON") from error


def promote(workspace: Path, publisher: list[str], verifier: list[str]) -> dict:
    if publisher == verifier:
        raise ValueError("publisher and verifier commands must be independent")
    validation_path = workspace / "dock-validation.json"
    if not validation_path.exists():
        raise ValueError("dock-validation.json is required before live promotion")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    state = State(workspace / "state.sqlite3")
    try: current = membership(staged(state))
    finally: state.close()
    approved=validation.get("items") or {}
    if (validation.get("passed") is not True or not approved or
            any(current.get(key)!=digest for key,digest in approved.items())):
        raise ValueError("validated survivor membership changed after validation")
    keys = sorted(approved)
    request = {"operation": "publish-validated-staging", "items": approved,
               "validation": validation, "requested_at": now()}
    published = command_json(publisher, request)
    if sorted(map(str, published.get("published", []))) != keys:
        raise ValueError("publisher did not confirm the exact validated membership")
    verified = command_json(verifier, {**request, "publication": published})
    if sorted(map(str, verified.get("verified", []))) != keys:
        raise ValueError("verifier did not confirm the exact published membership")
    evidence = {"schema_version": 1, "promoted_at": now(), "item_count": len(keys),
                "items": approved, "published": keys, "verified": keys,
                "single_item_never_blocks_continuation": True, "passed": True}
    atomic_json(workspace / "dock-promotion.json", evidence)
    activity_record(workspace,"live-promotion-verified",lane="uploader",status="passed",
                    detail={"verified":len(keys)})
    return evidence


def cleanup_verified_staging(workspace: Path, cleaner: list[str]) -> dict:
    promotion_path = workspace / "dock-promotion.json"
    if not promotion_path.exists():
        raise ValueError("dock-promotion.json is required before staging cleanup")
    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    if promotion.get("passed") is not True or promotion.get("published") != promotion.get("verified"):
        raise ValueError("exact live verification is incomplete; refusing staging cleanup")
    keys = sorted(map(str, promotion.get("verified", [])))
    if not keys or sorted(promotion.get("items", {})) != keys:
        raise ValueError("promotion evidence membership is incomplete")
    result = command_json(cleaner, {"operation": "delete-verified-staging",
        "items": promotion["items"], "promotion": promotion, "requested_at": now()})
    if sorted(map(str, result.get("deleted", []))) != keys:
        raise ValueError("cleaner did not confirm deletion of the exact verified membership")
    evidence = {"schema_version": 1, "cleaned_at": now(), "item_count": len(keys),
                "deleted": keys, "promotion_sha256": hashlib.sha256(
                    promotion_path.read_bytes()).hexdigest(), "passed": True}
    atomic_json(workspace / "dock-cleanup.json", evidence)
    activity_record(workspace,"verified-staging-cleanup",lane="uploader",status="passed",
                    detail={"deleted":len(keys)})
    return evidence
