from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .model import Config, Policy, Source


def load_config(path: Path) -> Config:
    raw = json.loads(path.read_text(encoding="utf-8"))
    layout = raw.get("layout", {})
    sources = []
    for item in raw.get("sources", []):
        value = dict(item)
        manifest = str(value.get("manifest", ""))
        if urlparse(manifest).scheme not in {"http", "https", "file"}:
            value["manifest"] = str((path.parent / manifest).resolve())
        continuations = []
        for location in value.get("continuation_manifests", []):
            location = str(location)
            if urlparse(location).scheme not in {"http", "https", "file"}:
                location = str((path.parent / location).resolve())
            continuations.append(location)
        value["continuation_manifests"] = continuations
        sources.append(Source(**value))
    config = Config(
        workspace=(path.parent / raw.get("workspace", "./sweeper-data")).resolve(),
        user_agent=str(raw.get("user_agent", "Institutional-Sweeper/0.1 (+contact-required)")),
        major_slots=int(layout.get("major_slots", 2)),
        minor_slots=int(layout.get("minor_slots", 1)),
        sources=sources,
        policy=Policy(**raw.get("policy", {})),
    )
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    if config.major_slots != 2 or not 1 <= config.minor_slots <= 6:
        raise ValueError("Sweeper requires two major slots and between one and six light slots")
    if not config.user_agent or "contact-required" in config.user_agent:
        raise ValueError("set a truthful user_agent containing institutional contact information")
    ids = [source.id for source in config.sources]
    if len(ids) != len(set(ids)):
        raise ValueError("source IDs must be unique")
    occupied = [(source.lane, source.slot) for source in config.sources if source.enabled]
    if len(occupied) != len(set(occupied)):
        raise ValueError("each enabled major/minor slot may contain only one source")
    for source in config.sources:
        maximum = config.major_slots if source.lane == "major" else config.minor_slots
        if source.lane not in {"major", "minor"} or not 1 <= source.slot <= maximum:
            raise ValueError(f"invalid lane/slot for {source.id}")
        if source.workers < 1 or source.workers > (4 if source.lane == "major" else 2):
            raise ValueError(f"unsafe worker count for {source.id}")
        if source.requests_per_second <= 0 or source.requests_per_second > 10:
            raise ValueError(f"invalid request rate for {source.id}")
        if source.target_items < 0:
            raise ValueError(f"target items cannot be negative for {source.id}")
        if len(source.continuation_manifests) > 1000:
            raise ValueError(f"continuation manifest pool is too large for {source.id}")
