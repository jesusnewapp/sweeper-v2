from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CATEGORIES = (
    "open public archives", "public domain books complete text",
    "open government document repository", "open scientific datasets",
    "open legal document archive", "open educational resources",
)


def discover(categories: list[str], output: Path, user_agent: str,
             results_per_category: int = 20) -> dict:
    """Discover candidate source sites without acquiring their content."""
    rows: list[dict] = []
    seen: set[str] = set()
    errors: list[dict] = []
    for category in categories:
        url = "https://www.bing.com/search?format=rss&q=" + urllib.parse.quote(category)
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                root = ET.fromstring(response.read(2_000_000))
            for item in root.findall(".//item")[:results_per_category]:
                link = (item.findtext("link") or "").strip()
                title = (item.findtext("title") or "").strip()
                parsed = urllib.parse.urlsplit(link)
                domain = parsed.netloc.casefold().removeprefix("www.")
                if not domain or domain in seen:
                    continue
                seen.add(domain)
                rows.append({"domain": domain, "url": link, "title": title,
                    "matched_category": category,
                    "status": "operator-review-and-source-contract-required"})
        except Exception as error:
            errors.append({"category": category, "error": f"{type(error).__name__}: {error}"})
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories,
        "candidate_sites": rows,
        "errors": errors,
        "notice": "Discovery is not permission. Review terms, robots, rights, privacy, APIs, and data boundaries before configuration.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return payload
