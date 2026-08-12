# Architecture

Web Sweeper separates four responsibilities:

1. **Manifests** declare stable source identities and download locations.
2. **Policy** performs inexpensive metadata filtering before retrieval.
3. **Acquisition** streams bytes into a temporary file while computing SHA-256.
4. **State** records accepted, rejected, duplicate, and failed decisions in
   SQLite and stores accepted bytes by content hash.

The configured topology is exactly two major slots and one to six light slots.
The default is two light crawlers after operators prove the first crawler's
continuation, source isolation, rate limits, and checkpoint recovery. One through
six light slots remain valid. Sources
are ordered major-first, then by slot. Slot identity is stable across resumes.
Per-source workers and request rates are bounded by configuration validation.

Before each cycle, the continuation advisor reads per-source durable counts and
peer-lane positions. It scores a project-neutral operation pool and may reorder
whole source turns. It cannot alter item eligibility or an active manifest
checkpoint. Its JSON output is advisory, so adapters may select a safer local
alternative and record their reason.

The separate Pivot Enforcer watches durable source and translation counts. An
unchanged lane with pending work becomes overdue after exactly 60 seconds. The
enforcer records and exposes the obligation but never selects a pivot; adapters
or supervisors choose the safe continuation and preserve their checkpoints.

The core deliberately does not perform login automation, browser scraping,
robots circumvention, OCR, archive extraction, format conversion, publication,
or AI calls. These actions have different security and rights profiles and must
be implemented explicitly by an operator-approved extension.

Artifact and data classes are descriptive policy dimensions, not assertions of
permission. Operators must independently establish authorization, particularly
for structured contact records, student records, health information, or other
regulated data.

## Universal media and rights

The core stores opaque byte streams, so the acquisition path works for
documents, datasets, audio, music, video, images, comics, maps, software,
archives, models, and future media. It supports exact MIME values and safe MIME
families such as `audio/*`. Content-specific validation—duration, codec,
dimensions, comic page order, archive membership, or dataset schema—belongs in
the external reviewer and remains bound to the staged object's SHA-256.

Public manifests should provide both an exact license and
`rights_evidence_url`. When rights evidence is required, missing evidence is
rejected before retrieval. HTTP 401, 403, and 407 responses are recorded as
access-required rejections; the engine moves on and never attempts sign-in or
access-control circumvention.

An external reviewer command is the only AI integration surface. This keeps
model choice, credentials, data governance, and prompts under the institution's
control. A reviewer rejection is recorded; malformed output or a nonzero exit
fails closed.
