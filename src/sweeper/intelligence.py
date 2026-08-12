from __future__ import annotations

import json
from urllib.parse import urlsplit

from .model import Config
from .state import State


def source_intelligence(config: Config, state: State) -> dict:
    active, queued = [], []
    estimated_remaining = 0
    known_estimates = 0
    for source in sorted(config.sources, key=lambda value: (value.lane, value.slot, value.id)):
        counts = state.source_counts(source.id)
        accepted = int(counts.get("accepted", 0))
        if source.estimated_eligible_items:
            known_estimates += 1
            estimated_remaining += max(0, source.estimated_eligible_items - accepted)
        parsed = urlsplit(source.manifest)
        row = {
            "id": source.id, "site": parsed.netloc or "local-manifest",
            "manifest": source.manifest, "lane": source.lane, "slot": source.slot,
            "status": "active" if source.enabled else "queued-disabled", "counts": counts,
            "estimatedHighQualityEligibleItems": source.estimated_eligible_items or None,
            "estimatedRemainingHighQualityItems": max(0, source.estimated_eligible_items - accepted)
                if source.estimated_eligible_items else None,
            "estimatedDailyHighQualityItems": source.estimated_daily_items or None,
            "estimateStatus": "available" if source.estimated_eligible_items else "learning",
        }
        (active if source.enabled else queued).append(row)

    discovery_path = config.workspace / "discovered-sources.json"
    potential, errors = [], []
    if discovery_path.exists():
        try:
            discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
            errors = discovery.get("errors", [])
            seen_domains = set()
            for candidate in discovery.get("candidate_sites", []):
                domain = str(candidate.get("domain") or "").casefold()
                if not domain or domain in seen_domains:
                    continue
                seen_domains.add(domain)
                potential.append({
                    "domain": candidate.get("domain"), "url": candidate.get("url"),
                    "title": candidate.get("title"),
                    "matchedCategory": candidate.get("matched_category"),
                    "status": candidate.get("status", "operator-review-required"),
                    "estimatedHighQualityEligibleItems": candidate.get("estimated_eligible_items"),
                    "estimatedDailyHighQualityItems": candidate.get("estimated_daily_items"),
                    "confidence": candidate.get("confidence", "unassessed"),
                    "nextEvaluation": candidate.get("next_evaluation",
                        "verify authorization, access terms, data boundary, quality, and stable manifest"),
                    "automaticallyActivated": False,
                })
        except (OSError, ValueError) as error:
            errors.append({"sourceIntelligence": f"{type(error).__name__}: {error}"})

    confidence_rank = {"high": 3, "medium": 2, "partial": 1, "unassessed": 0}
    potential.sort(key=lambda row: (
        -confidence_rank.get(str(row.get("confidence", "unassessed")).casefold(), 0),
        -(int(row.get("estimatedHighQualityEligibleItems") or 0)),
        str(row.get("domain") or ""),
    ))
    for rank, row in enumerate(potential, 1):
        row["advisoryRank"] = rank
    total_sources = len(active) + len(queued)
    first_observed, last_observed = state.observation_bounds()
    estimate_coverage = round(known_estimates * 100 / total_sources, 2) if total_sources else 0.0
    if potential:
        depletion = "expansion-available"
    elif total_sources and known_estimates == total_sources and estimated_remaining == 0:
        depletion = "known-aggregates-depleted"
    elif estimated_remaining:
        depletion = "known-capacity-remaining"
    else:
        depletion = "insufficient-evidence"
    return {
        "operator": "background-source-intelligence-operator",
        "role": "observe and advise; never operate a sweeper",
        "assistanceControl": {
            "decisionOwner": "sweeper", "operatorMayOffer": True,
            "operatorMayActivateAggregate": False, "operatorMayForcePivot": False,
        },
        "activeSites": active, "queuedSites": queued, "potentialSites": potential,
        "counts": {"active": len(active), "queued": len(queued), "potential": len(potential)},
        "depletion": {
            "assessment": depletion,
            "estimatedRemainingHighQualityItems": estimated_remaining,
            "estimateCoveragePercent": estimate_coverage,
            "confidence": "high" if estimate_coverage == 100 else "partial" if known_estimates else "unassessed",
            "scope": "configured and discovered internet aggregates only",
            "firstObservedAt": first_observed, "lastObservedAt": last_observed,
            "assessmentIsApproximate": True,
            "entireInternetExhausted": False,
            "reasoningSignals": ["remaining eligible capacity", "acceptance yield trend",
                "duplicate and rejection pressure", "bounded-source completion", "new potential sources"],
        },
        "discoveryErrors": errors, "potentialSitesRequireReview": True,
    }
