from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Candidate:
    source_id: str
    item_id: str
    url: str
    title: str = ""
    language: str = ""
    license: str = ""
    media_type: str = "application/octet-stream"
    artifact_class: str = "unspecified"
    data_class: str = "unspecified"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Source:
    id: str
    slot: int
    lane: str
    manifest: str
    enabled: bool = True
    requests_per_second: float = 1.0
    workers: int = 1
    headers: Dict[str, str] = field(default_factory=dict)
    continuation_manifests: List[str] = field(default_factory=list)
    target_items: int = 0


@dataclass
class Policy:
    languages: List[str] = field(default_factory=list)
    licenses: List[str] = field(default_factory=list)
    media_types: List[str] = field(default_factory=list)
    artifact_classes: List[str] = field(default_factory=list)
    data_classes: List[str] = field(default_factory=list)
    minimum_bytes: int = 1
    maximum_bytes: Optional[int] = None
    require_language: bool = True
    require_license: bool = True
    reviewer_command: List[str] = field(default_factory=list)


@dataclass
class Config:
    workspace: Path
    user_agent: str
    major_slots: int
    minor_slots: int
    sources: List[Source]
    policy: Policy
