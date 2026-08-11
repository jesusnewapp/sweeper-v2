from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .engine import run
from .state import State


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="sweeper")
    sub = parser.add_subparsers(dest="command", required=True)
    initialize_command = sub.add_parser("init")
    initialize_command.add_argument("--config", type=Path, default=Path("sweeper.json"))
    for name in ("validate", "run", "status"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, default=Path("sweeper.json"))
    args = parser.parse_args()
    if args.command == "init":
        initialize(args.config.resolve())
        print(json.dumps({"created": str(args.config.resolve()), "next": "edit sources and policy, then run sweeper validate"}, indent=2))
        return 0
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
