from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

from .model import Candidate, Source


def _open(location: str, headers: dict):
    parsed = urllib.parse.urlparse(location)
    if parsed.scheme in {"http", "https"}:
        return urllib.request.urlopen(urllib.request.Request(location, headers=headers), timeout=45)
    path = Path(parsed.path if parsed.scheme == "file" else location)
    return path.open("rb")


def candidates(source: Source, user_agent: str) -> Iterable[Candidate]:
    headers = {"User-Agent": user_agent, **source.headers}
    with _open(source.manifest, headers) as response:
        for number, raw_line in enumerate(response, 1):
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            item = json.loads(line)
            item_id = str(item.get("id", "")).strip()
            url = str(item.get("url", "")).strip()
            if not item_id or not url:
                raise ValueError(f"{source.id} manifest line {number} requires id and url")
            yield Candidate(
                source_id=source.id,
                item_id=item_id,
                url=url,
                title=str(item.get("title", "")),
                language=str(item.get("language", "")),
                license=str(item.get("license", "")),
                media_type=str(item.get("media_type", "application/octet-stream")),
                artifact_class=str(item.get("artifact_class", "unspecified")),
                data_class=str(item.get("data_class", "unspecified")),
                metadata=dict(item.get("metadata", {})),
            )
