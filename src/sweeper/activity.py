from __future__ import annotations

import json, os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def now() -> str: return datetime.now(timezone.utc).isoformat()


def record(workspace: Path, event: str, *, lane: str = "system", status: str = "info",
           detail: dict | None = None) -> dict:
    row={"at":now(),"event":event,"lane":lane,"status":status,"detail":detail or {}}
    path=workspace/"activity-log.jsonl"; path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as handle:
        handle.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")
        handle.flush(); os.fsync(handle.fileno())
    return row


def report(workspace: Path, limit: int = 100) -> dict:
    path=workspace/"activity-log.jsonl"; rows=[]
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except (ValueError,TypeError): continue
    counts=Counter(str(row.get("event","unknown")) for row in rows)
    lanes=Counter(str(row.get("lane","system")) for row in rows)
    return {"schemaVersion":1,"workspace":str(workspace),"log":str(path),
            "totalEvents":len(rows),"eventCounts":dict(sorted(counts.items())),
            "laneCounts":dict(sorted(lanes.items())),"firstEvent":rows[0]["at"] if rows else None,
            "lastEvent":rows[-1]["at"] if rows else None,"recent":rows[-max(1,limit):]}
