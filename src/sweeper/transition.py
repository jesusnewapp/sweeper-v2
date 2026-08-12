"""Receipt-bound, restart-safe transitions between configured source slots."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def evaluate_route(route: dict, base: Path) -> dict:
    """Evaluate one transition without starting or stopping a process."""
    required = ("from", "to", "completion_receipt", "cleanup_receipt", "checkpoint")
    missing = [key for key in required if not str(route.get(key, "")).strip()]
    if missing:
        raise ValueError(f"transition route is missing {', '.join(missing)}")
    paths = {key: (base / str(route[key])).resolve()
             for key in ("completion_receipt", "cleanup_receipt", "checkpoint")}
    absent = [key for key, path in paths.items() if not path.is_file()]
    status = "waiting-for-current-unit" if absent else "ready-to-transition"
    row = {"from": route["from"], "to": route["to"], "status": status,
           "missingEvidence": absent, "evaluatedAt": now(),
           "commandsArePlaceholders": bool(route.get("commands_are_placeholders", True))}
    if absent:
        return row
    completion = json.loads(paths["completion_receipt"].read_text(encoding="utf-8"))
    cleanup = json.loads(paths["cleanup_receipt"].read_text(encoding="utf-8"))
    staged = int(completion.get("staged", 0) or 0)
    target = int(route.get("target", 1000) or 1000)
    source_exhausted = completion.get("sourceExhausted") is True
    if staged < 1 or completion.get("productionMutated") is not False:
        raise ValueError(f"{route['from']}: completion receipt is not exact isolated staging")
    if staged > target:
        raise ValueError(f"{route['from']}: staged count exceeds the configured target")
    if staged < target and not (route.get("allow_partial_on_exhaustion") is True and
                                source_exhausted):
        raise ValueError(
            f"{route['from']}: partial unit requires an exact source-exhausted receipt"
        )
    if cleanup.get("status") not in {"complete", "completed", "source-cache-cleanup-complete"}:
        # Public adapters may use different receipt schemas. Exact deleted keys
        # or a non-negative reclaimed-byte count is also acceptable evidence.
        deleted = cleanup.get("deleted") or cleanup.get("deletedFiles")
        reclaimed = cleanup.get("bytesReclaimed", cleanup.get("deletedBytes"))
        if not isinstance(deleted, list) and not isinstance(reclaimed, int):
            raise ValueError(f"{route['from']}: cleanup receipt is incomplete")
    row.update({"staged": staged, "target": target,
                "sourceExhausted": source_exhausted,
                "partialUnit": staged < target,
                "evidence": {key: {"path": str(path), "sha256": sha256(path)}
                             for key, path in paths.items()},
                "nextAction": ("replace-placeholder-commands" if row["commandsArePlaceholders"]
                               else "stop-old-confirm-dead-start-successor")})
    return row


def evaluate(config_path: Path) -> dict:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    routes = config.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("transition config requires at least one route")
    identities = [str(route.get("from", "")) for route in routes]
    successors = [str(route.get("to", "")) for route in routes]
    if len(identities) != len(set(identities)) or len(successors) != len(set(successors)):
        raise ValueError("each source and successor may appear in only one transition route")
    rows = [evaluate_route(route, config_path.parent) for route in routes]
    return {"schemaVersion": 1, "model": "receipt-bound-source-transition",
            "evaluatedAt": now(), "practiceMode": bool(config.get("practice_mode", True)),
            "routes": rows,
            "ready": sum(row["status"] == "ready-to-transition" for row in rows),
            "waiting": sum(row["status"] != "ready-to-transition" for row in rows),
            "invariants": ["finish-current-unit", "exact-staging-receipt",
                           "cleanup-receipt", "checkpoint-preserved",
                           "old-source-confirmed-inactive", "one-successor-only",
                           "durable-transition-receipt"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.config)
    if args.output:
        atomic_json(args.output.resolve(), result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
