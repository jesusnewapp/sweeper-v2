# Architecture

Sweeper V2 separates four responsibilities:

1. **Manifests** declare stable source identities and download locations.
2. **Policy** performs inexpensive metadata filtering before retrieval.
3. **Acquisition** streams bytes into a temporary file while computing SHA-256.
4. **State** records accepted, rejected, duplicate, and failed decisions in
   SQLite and stores accepted bytes by content hash.

The configured topology is exactly two major slots and six minor slots. Sources
are ordered major-first, then by slot. Slot identity is stable across resumes.
Per-source workers and request rates are bounded by configuration validation.

The core deliberately does not perform login automation, browser scraping,
robots circumvention, OCR, archive extraction, format conversion, publication,
or AI calls. These actions have different security and rights profiles and must
be implemented explicitly by an operator-approved extension.

Artifact and data classes are descriptive policy dimensions, not assertions of
permission. Operators must independently establish authorization, particularly
for structured contact records, student records, health information, or other
regulated data.

An external reviewer command is the only AI integration surface. This keeps
model choice, credentials, data governance, and prompts under the institution's
control. A reviewer rejection is recorded; malformed output or a nonzero exit
fails closed.
