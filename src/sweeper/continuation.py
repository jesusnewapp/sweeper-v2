from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .model import Config, Source
from .state import State


DEFAULT_POOL = (
    "continue-current-manifest",
    "advance-continuation-manifest",
    "retry-transient-failures",
    "switch-to-next-ready-source",
    "reduce-request-pressure",
    "restore-normal-request-pressure",
    "narrow-next-cycle-scope",
    "broaden-next-cycle-scope",
    "checkpoint-and-yield-slot",
    "resume-from-checkpoint",
)


def _score(action: str, source: Source, counts: dict, peer_stages: dict) -> tuple[int, list[str]]:
    accepted = int(counts.get("accepted", 0)); failed = int(counts.get("failed", 0))
    deficit = max(0, source.target_items - accepted) if source.target_items else 0
    score = 30; reasons: list[str] = []
    if action == "continue-current-manifest":
        score += 20; reasons.append("preserves the active source checkpoint")
    if action == "advance-continuation-manifest" and deficit:
        score += 28; reasons.append(f"target deficit is {deficit}")
    if action == "retry-transient-failures" and failed:
        score += min(30, failed * 3); reasons.append(f"{failed} retryable failures")
    if action == "switch-to-next-ready-source" and failed > accepted:
        score += 24; reasons.append("another source can progress while this source recovers")
    if action == "reduce-request-pressure" and failed:
        score += 18; reasons.append("failure pressure detected")
    if action == "restore-normal-request-pressure" and accepted and not failed:
        score += 18; reasons.append("healthy yield supports normal pressure")
    if action == "checkpoint-and-yield-slot" and peer_stages.get(source.lane, 0) > 1:
        score += 12; reasons.append("reduces same-lane contention")
    if action == "broaden-next-cycle-scope" and deficit and not failed:
        score += 14; reasons.append("healthy source still has useful target headroom")
    if action == "narrow-next-cycle-scope" and failed:
        score += 12; reasons.append("smaller scope limits repeated failure cost")
    if action == "resume-from-checkpoint":
        score += 15; reasons.append("restart-safe default")
    return score, reasons


def build_plan(config: Config, state: State) -> dict:
    enabled = sorted((source for source in config.sources if source.enabled),
                     key=lambda source: (source.lane != "major", source.slot, source.id))
    lane_load = {lane: sum(1 for source in enabled if source.lane == lane)
                 for lane in {source.lane for source in enabled}}
    decisions = []
    for source in enabled:
        counts = state.source_counts(source.id)
        candidates = []
        for action in DEFAULT_POOL:
            score, reasons = _score(action, source, counts, lane_load)
            candidates.append({"action": action, "score": score, "reasons": reasons})
        candidates.sort(key=lambda row: (-row["score"], row["action"]))
        pressure = min(100, int(counts.get("failed", 0)) * 12)
        mode = "exhale" if pressure >= 48 else "inhale" if pressure == 0 else "steady"
        decisions.append({
            "source": source.id,
            "lane": source.lane,
            "slot": source.slot,
            "counts": counts,
            "recommendedAction": candidates[0]["action"],
            "recommendationScore": candidates[0]["score"],
            "alternatives": candidates[1:5],
            "breathing": {"mode": mode, "pressureScore": pressure},
            "autonomy": {
                "advisoryOnly": True,
                "mayChooseAlternative": True,
                "mayCreateLocalCandidate": True,
                "mustRecordReason": True,
            },
        })
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "model": "fleet-aware-continuation-advisor",
        "pool": list(DEFAULT_POOL),
        "decisions": decisions,
        "invariants": ["authorization", "rights", "policy", "identity", "hashing",
                       "deduplication", "review", "single-live-writer"],
    }


def prioritized_sources(config: Config, state: State) -> Iterable[Source]:
    plan = build_plan(config, state)
    scores = {row["source"]: row["recommendationScore"] for row in plan["decisions"]}
    return sorted((source for source in config.sources if source.enabled),
                  key=lambda source: (-scores.get(source.id, 0), source.lane != "major",
                                      source.slot, source.id))
