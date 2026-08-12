from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .dock import atomic_json, command_json
from .model import Config
from .state import State
from .translation import LANGUAGES, translate_file


SCHEMA = """
CREATE TABLE IF NOT EXISTS translation_jobs (
  job_key TEXT PRIMARY KEY, source_id TEXT NOT NULL, item_id TEXT NOT NULL,
  source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
  source_language TEXT NOT NULL, target_language TEXT NOT NULL,
  status TEXT NOT NULL, output_path TEXT, output_sha256 TEXT,
  reason TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TranslationFleet:
    def __init__(self, config: Config):
        self.config = config
        root = config.workspace / "translation"
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.db = sqlite3.connect(str(root / "state.sqlite3"))
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def status(self) -> dict:
        counts = {row[0]: int(row[1]) for row in self.db.execute(
            "SELECT status,COUNT(*) FROM translation_jobs GROUP BY status")}
        by_language = {row[0]: int(row[1]) for row in self.db.execute(
            "SELECT target_language,COUNT(*) FROM translation_jobs GROUP BY target_language")}
        handoffs = sorted(str(path) for path in self.root.glob("live-handoff-*.json"))
        return {"enabled": self.config.translation.enabled,
            "stagingCollection": self.config.translation.staging_collection,
            "batchSize": self.config.translation.batch_size,
            "targetLanguages": self.config.translation.target_languages,
            "counts": counts, "jobsByTargetLanguage": by_language,
            "liveHandoffs": handoffs, "sharedOverallUploaderRequired": True}

    def queue(self, target: str, source_language: str = "en") -> dict:
        if not self.config.translation.enabled:
            raise ValueError("translation lane is disabled")
        if target not in self.config.translation.target_languages or target not in LANGUAGES:
            raise ValueError("target language is not enabled")
        source_state = State(self.config.workspace / "state.sqlite3")
        try: originals = source_state.accepted_items()
        finally: source_state.close()
        added = []
        for item in originals:
            if len(added) >= self.config.translation.batch_size:
                break
            key = f"{item['source_id']}:{item['item_id']}:{target}"
            exists = self.db.execute("SELECT 1 FROM translation_jobs WHERE job_key=?", (key,)).fetchone()
            if exists:
                continue
            path = Path(str(item.get("local_path") or ""))
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
                continue
            with self.db:
                self.db.execute("INSERT INTO translation_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (key, item["source_id"], item["item_id"], str(path), item["sha256"],
                     source_language, target, "queued", None, None, "", now()))
            added.append(key)
        payload = {"operation": "translation-work-available", "target_language": target,
                   "jobs": added, "count": len(added), "created_at": now()}
        if added and self.config.translation.notifier_command:
            response = command_json(self.config.translation.notifier_command, payload)
            if response.get("acknowledged") is not True:
                raise ValueError("translator notifier did not acknowledge the batch")
        return payload

    def run_batch(self, target: str) -> dict:
        if not self.config.translation.validator_command or not self.config.translation.stager_command:
            raise ValueError("translation validator and stager commands are required")
        rows = self.db.execute("SELECT job_key,source_path,source_language,target_language "
            "FROM translation_jobs WHERE status='queued' AND target_language=? "
            "ORDER BY job_key LIMIT ?", (target, self.config.translation.batch_size)).fetchall()
        passing, failed = {}, []
        for key, source_path, source_language, target_language in rows:
            safe_key = hashlib.sha256(key.encode()).hexdigest()
            output = self.root / "objects" / target_language / f"{safe_key}.txt"
            try:
                evidence = translate_file(Path(source_path), output, source_language, target_language)
                decision = command_json(self.config.translation.validator_command,
                    {"operation": "validate-translation", "job_key": key,
                     "target_language": target_language, "translation": evidence})
                if (decision.get("approved") is not True or
                        decision.get("language") != target_language or
                        decision.get("sha256") != evidence["translation_sha256"]):
                    raise ValueError("language validator did not approve exact translated bytes")
                passing[key] = {"sha256": evidence["translation_sha256"],
                                "path": str(output), "target_language": target_language,
                                "validation": decision}
                with self.db:
                    self.db.execute("UPDATE translation_jobs SET status='validated',output_path=?,"
                        "output_sha256=?,updated_at=? WHERE job_key=?",
                        (str(output), evidence["translation_sha256"], now(), key))
            except Exception as error:
                failed.append({"job": key, "error": f"{type(error).__name__}: {error}"})
                with self.db:
                    self.db.execute("UPDATE translation_jobs SET status='failed',reason=?,updated_at=? "
                        "WHERE job_key=?", (failed[-1]["error"], now(), key))
        if not passing:
            return {"targetLanguage": target, "validated": 0, "staged": 0, "failed": failed,
                    "nextBatchMayQueue": True}
        request = {"operation": "stage-validated-translations",
            "collection": self.config.translation.staging_collection,
            "target_language": target, "items": passing, "requested_at": now(),
            "sharedOverallUploaderRequired": True}
        staged = command_json(self.config.translation.stager_command, request)
        keys = sorted(passing)
        if sorted(map(str, staged.get("staged", []))) != keys:
            raise ValueError("translation stager did not confirm exact validated membership")
        with self.db:
            self.db.executemany("UPDATE translation_jobs SET status='staged',updated_at=? WHERE job_key=?",
                                [(now(), key) for key in keys])
        handoff = {"schema_version": 1, "created_at": now(),
            "translationCollection": self.config.translation.staging_collection,
            "targetLanguage": target, "items": passing, "itemCount": len(keys),
            "sharedOverallUploaderRequired": True, "liveWriterAcquired": False}
        atomic_json(self.root / f"live-handoff-{target}.json", handoff)
        next_batch = self.queue(target)
        return {"targetLanguage": target, "validated": len(keys), "staged": len(keys),
                "failed": failed, "handoff": str(self.root / f"live-handoff-{target}.json"),
                "nextBatchMayQueue": True, "nextBatch": next_batch}
