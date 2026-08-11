from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .engine import run
from .discovery import DEFAULT_CATEGORIES, discover
from .state import State
from .translation import capabilities, translate_file


EXAMPLE = {
    "workspace": "./sweeper-data",
    "user_agent": "YOUR INSTITUTION Sweeper V2/0.1 (YOUR-CONTACT@example.org)",
    "layout": {"major_slots": 2, "minor_slots": 6},
    "policy": {
        "languages": ["en"], "licenses": ["PUBLIC-DOMAIN", "CC0-1.0", "CC-BY-4.0"],
        "media_types": ["application/json", "application/xml", "text/plain", "text/html"],
        "artifact_classes": [], "data_classes": ["open-public", "institution-authorized"],
        "minimum_bytes": 1, "maximum_bytes": 1073741824,
        "require_language": True, "require_license": True, "reviewer_command": [],
    },
    "sources": [],
}


def initialize(path: Path) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite existing configuration: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(EXAMPLE, indent=2) + "\n", encoding="utf-8")
    manifests = path.parent / "manifests"
    manifests.mkdir(exist_ok=True)
    template = manifests / "source.example.jsonl"
    template.write_text(
        json.dumps({"id": "stable-record-id", "url": "https://example.org/file.xml",
                    "title": "Example record", "language": "en", "license": "CC0-1.0",
                    "media_type": "application/xml", "artifact_class": "document",
                    "data_class": "open-public", "metadata": {"topic": "your topic"}}) + "\n",
        encoding="utf-8",
    )


def daemon(config_path: Path, interval: float, once: bool = False,
           max_backoff: float = 900.0) -> int:
    config = load_config(config_path)
    state_path = config.workspace / "daemon-state.json"
    consecutive_failures = 0
    while True:
        payload = {"mode": "always-running", "checkedAt": datetime.now(timezone.utc).isoformat()}
        try:
            payload.update({"status": "healthy", "result": run(config)})
        except Exception as error:
            payload.update({"status": "retrying", "error": f"{type(error).__name__}: {error}"})
            consecutive_failures += 1
        else:
            consecutive_failures = 0
        next_delay = min(max_backoff, interval * (2 ** max(0, consecutive_failures - 1)))
        payload.update({"consecutiveFailures": consecutive_failures,
                        "nextCheckSeconds": next_delay})
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(state_path)
        print(json.dumps(payload, indent=2), flush=True)
        if once:
            return 0 if payload["status"] == "healthy" else 1
        time.sleep(next_delay)


def main() -> int:
    parser = argparse.ArgumentParser(prog="sweeper")
    sub = parser.add_subparsers(dest="command", required=True)
    initialize_command = sub.add_parser("init")
    initialize_command.add_argument("--config", type=Path, default=Path("sweeper.json"))
    for name in ("validate", "run", "status"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, default=Path("sweeper.json"))
    daemon_command = sub.add_parser("daemon")
    daemon_command.add_argument("--config", type=Path, default=Path("sweeper.json"))
    daemon_command.add_argument("--interval", type=float, default=60.0)
    daemon_command.add_argument("--once", action="store_true")
    daemon_command.add_argument("--max-backoff", type=float, default=900.0)
    discover_command = sub.add_parser("discover")
    discover_command.add_argument("--config", type=Path, default=Path("sweeper.json"))
    discover_command.add_argument("--category", action="append", default=[])
    discover_command.add_argument("--output", type=Path)
    sub.add_parser("translator-status")
    translate_command = sub.add_parser("translate")
    translate_command.add_argument("--input", type=Path, required=True)
    translate_command.add_argument("--output", type=Path, required=True)
    translate_command.add_argument("--source-language", required=True)
    translate_command.add_argument("--target-language", required=True)
    translate_command.add_argument("--engine-command")
    args = parser.parse_args()
    if args.command == "init":
        initialize(args.config.resolve())
        print(json.dumps({"created": str(args.config.resolve()), "next": "edit sources and policy, then run sweeper validate"}, indent=2))
        return 0
    if args.command == "daemon":
        if args.interval < 5:
            raise SystemExit("daemon interval must be at least five seconds")
        if args.max_backoff < args.interval:
            raise SystemExit("daemon maximum backoff must be at least the base interval")
        return daemon(args.config.resolve(), args.interval, args.once, args.max_backoff)
    if args.command == "translator-status":
        print(json.dumps(capabilities(), indent=2)); return 0
    if args.command == "translate":
        print(json.dumps(translate_file(args.input.resolve(), args.output.resolve(),
            args.source_language, args.target_language, args.engine_command), indent=2)); return 0
    if args.command == "discover":
        config = load_config(args.config.resolve())
        output = args.output.resolve() if args.output else config.workspace / "discovered-sources.json"
        print(json.dumps(discover(args.category or list(DEFAULT_CATEGORIES), output,
                                  config.user_agent), indent=2)); return 0
    config = load_config(args.config.resolve())
    if args.command == "validate":
        print(json.dumps({"valid": True, "sources": len(config.sources), "workspace": str(config.workspace)}, indent=2))
        return 0
    if args.command == "run":
        print(json.dumps(run(config), indent=2))
        return 0
    state = State(config.workspace / "state.sqlite3")
    try:
        print(json.dumps({"counts": state.counts(), "workspace": str(config.workspace)}, indent=2))
    finally:
        state.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
