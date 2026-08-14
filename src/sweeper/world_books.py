from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .translation import LANGUAGES, translate_file


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:120] or "untitled"


def _words(value: str) -> int:
    return len(re.findall(r"\b[\w'’.-]+\b", value, flags=re.UNICODE))


def _pages(value: str, target_chars: int = 5000) -> list[dict[str, Any]]:
    """Preserve paragraph order while producing bounded reader pages."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", value) if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
        if current and size + len(paragraph) + 2 > target_chars:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    if not chunks:
        chunks = [value]
    return [
        {"id": f"page-{index}", "pageNumber": index, "text": text}
        for index, text in enumerate(chunks, 1)
    ]


def quick_english_check(text: str) -> dict[str, Any]:
    """Cheap fail-closed screen before independent/model review."""
    words = re.findall(r"\b[\w'’.-]+\b", text.lower(), flags=re.UNICODE)
    common = {"the", "and", "of", "to", "in", "that", "is", "for", "with", "was",
              "as", "on", "by", "from", "this", "be", "are", "which", "or", "not"}
    common_hits = sum(word in common for word in words)
    replacement_rate = text.count("�") / max(1, len(text))
    alpha = sum(char.isalpha() for char in text)
    printable_ratio = sum(char.isprintable() or char in "\n\t" for char in text) / max(1, len(text))
    english_signal = common_hits / max(1, len(words))
    passed = (len(words) >= 1000 and english_signal >= 0.025 and replacement_rate <= 0.0005
              and printable_ratio >= 0.98 and alpha >= len(text) * 0.55)
    return {"passed": passed, "wordCount": len(words), "englishSignal": english_signal,
            "replacementRate": replacement_rate, "printableRatio": printable_ratio,
            "independentCoherenceReviewRequired": True}


def build_translated_manuscript(
    *,
    source_text: Path,
    output_root: Path,
    source_id: str,
    title: str,
    authors: list[str],
    source_language: str,
    target_language: str = "en",
    source_url: str,
    rights: dict[str, Any],
    translator_command: str | None = None,
) -> dict[str, Any]:
    """Translate a complete source directly into a review-gated Codex manuscript.

    The translated bytes are never considered live merely because conversion
    succeeds. A hash-bound translation receipt and a separate review record are
    written atomically beside the manuscript.
    """
    if source_language not in LANGUAGES or target_language not in LANGUAGES:
        raise ValueError("unsupported source or target language")
    if source_language == target_language:
        raise ValueError("World Books requires a real translation pair")
    if not source_id.strip() or not title.strip() or not source_url.strip():
        raise ValueError("source id, title, and source URL are required")
    if rights.get("eligible") is not True or not str(rights.get("evidenceUrl", "")).strip():
        raise ValueError("item-level reusable-rights evidence is required")
    if not source_text.is_file():
        raise ValueError("complete source text is missing")

    item_id = f"world-books-{_slug(source_id)}-{_slug(title)}"
    object_root = output_root / "objects" / item_id
    translated_path = object_root / "translated.txt"
    evidence = translate_file(
        source_text, translated_path, source_language, target_language,
        command=translator_command,
    )
    translated = translated_path.read_text(encoding="utf-8")
    source = source_text.read_text(encoding="utf-8")
    if _words(source) < 1000 or _words(translated) < 1000:
        raise ValueError("complete-book minimum of 1,000 words was not met")
    quick_check = quick_english_check(translated)
    if not quick_check["passed"]:
        raise ValueError("translated manuscript failed quick English readability checks")

    created = _now()
    pages = _pages(translated)
    manuscript = {
        "schemaVersion": 2,
        "id": item_id,
        "title": title,
        "authors": authors,
        "description": f"An English World Books translation of {title}.",
        "category": "Christian Literature",
        "subjects": [],
        "language": target_language,
        "originalLanguage": source_language,
        "edition": "World Books translated public-domain reader edition",
        "contentFormat": "book",
        "chapters": [{"id": "complete-volume", "title": title, "startPage": 1, "endPage": len(pages)}],
        "pages": pages,
        "provenance": {
            "source": "World Books",
            "sourceId": source_id,
            "sourceUrl": source_url,
            "sourceLanguage": source_language,
            "sourceSha256": evidence["source_sha256"],
            "translationSha256": evidence["translation_sha256"],
            "translationReceipt": str(translated_path.with_suffix(".txt.translation.json")),
            "createdAt": created,
            "converterVersion": "world-books-translation-manuscript-1",
        },
        "rights": {
            "status": rights.get("status", "public-domain"),
            "jurisdiction": rights.get("jurisdiction", "source-record"),
            "evidence": rights.get("evidence", "item-level rights record"),
            "evidenceUrl": rights["evidenceUrl"],
            "assessedAt": created,
        },
        "statistics": {"wordCount": _words(translated), "pageCount": len(pages), "chapterCount": 1},
        "translation": {
            "sourceLanguage": source_language,
            "targetLanguage": target_language,
            "lengthRatio": evidence["length_ratio"],
            "humanOrDomainValidationRequired": True,
            "originalOverwritten": False,
            "quickEnglishCheck": quick_check,
        },
    }
    encoded = json.dumps(manuscript, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    manuscript["provenance"]["manuscriptSha256"] = hashlib.sha256(encoded).hexdigest()

    manuscript_dir = output_root / "manuscripts"
    review_dir = output_root / "review"
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    manuscript_path = manuscript_dir / f"{item_id}.json"
    temporary = manuscript_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manuscript, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manuscript_path)

    review = {
        "schemaVersion": 1,
        "id": item_id,
        "status": "awaiting-approval",
        "manuscriptPath": str(manuscript_path),
        "sourceSha256": evidence["source_sha256"],
        "translationSha256": evidence["translation_sha256"],
        "rightsPassed": True,
        "translationValidated": False,
        "completenessValidated": False,
        "deduplicationValidated": False,
        "publicationApproved": False,
        "createdAt": created,
    }
    review_path = review_dir / f"{item_id}.json"
    temporary = review_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    temporary.replace(review_path)
    return {"manuscript": str(manuscript_path), "review": str(review_path), "status": review["status"]}
