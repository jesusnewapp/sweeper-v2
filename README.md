# Sweeper V2

Sweeper V2 is a lightweight, source-neutral framework for downloading and
preserving large information collections with reproducible provenance. It can
be configured for institutional archives, law, science, research datasets,
books, public records, media, structured directories, or other authorized
collections. The engine treats every acquisition unit as bytes plus provenance;
it does not assume the unit is a book.

**Sweeper V2 was created by Christian Cassarly through Jesus New OS and shared
openly for the public—for institutions, researchers, archivists, schools,
governments, developers, and responsible independent users.**

Sweeper V2 is not tied to Codex, a particular library, Firebase, a subject, or
an AI vendor. It downloads only sources that the operator configures and is
intentionally fail-closed when required identity, rights, or policy metadata is
missing.

## What the program does

Sweeper V2 moves authorized information from source manifests into a local,
content-addressed archive:

1. Read stable item identities and download URLs.
2. Apply the configured language, license, format, data-class, artifact-class,
   and size policy before acquisition.
3. Download candidates at the source's configured request rate.
4. Stream every object through SHA-256 hashing without loading the entire object
   into memory.
5. Store identical bytes once and record duplicates explicitly.
6. Optionally invoke an operator-configured reviewer.
7. Save decisions in SQLite so an interrupted run continues instead of starting
   over.

Sweeper is an acquisition and preservation foundation. It does not grant
rights, bypass access controls, infer permission, or publish into an external
system automatically.

## The boat model

Think of Sweeper as a small, durable research boat. The two major sweepers handle
large repositories, while one lightweight crawler handles a smaller or bounded
source. After that light lane is proven stable, configuration can expand it to
as many as six isolated light slots.
A valid partial catch is retained. Temporary failures use bounded backoff.
Completed decisions remain checkpointed, and later cycles continue from
unresolved items. One unavailable source does not erase another source's
progress.

The daemon writes live `working` heartbeats with the current source and item.
Each network and reviewer operation has a timeout, failed items remain
retryable, and a broken source is isolated so later slots continue fishing.
Successful, rejected, and duplicate decisions are durable across restarts.

Continuation is target-driven and project-neutral. A source may define
`target_items` plus an ordered `continuation_manifests` pool. Sweeper retains
every valid partial catch, consumes the next manifest when useful, isolates a
failed manifest, and reports the remaining deficit with the next action
`add-or-discover-continuation-manifest`. It never calls a partially productive
source a total failure, and it never converts an unreviewed staging item into a
live item merely to satisfy a target.

## Progressive 2 + 1 → 6 layout

- Two major lanes for large repositories.
- One light crawler by default for a smaller or bounded source.
- Operator-controlled expansion up to six isolated light slots.
- Per-source request rates and worker ceilings.
- A shared content-addressed object store and SHA-256 duplicate index.
- Resumable SQLite state, explicit decisions, and deterministic source order.
- An optional external reviewer command for ChatGPT, another model, or local
  institutional review software.

Slots organize acquisition. They do not bypass a provider's terms, create
permission, or authorize concurrent publishing into another system.

## Install

Requires Python 3.9 or newer and has no runtime dependencies outside the Python
standard library.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
sweeper init
```

Edit `sweeper.json`: add sources to the two major slots and the initial light
crawler, specify
languages, licenses, formats, and size limits, and replace the placeholder user
agent with a truthful institutional name and contact address. Put stable item
IDs and download URLs in the generated JSONL manifests. No Python changes are
required for manifest-backed sources.

```bash
sweeper validate --config sweeper.json
sweeper run --config sweeper.json
sweeper status --config sweeper.json
```

For unattended operation, run:

```bash
sweeper daemon --config sweeper.json --interval 60
```

Daemon mode continuously resumes known items, records health in
`sweeper-data/daemon-state.json`, retries source/manifest failures after the
configured interval, and keeps independent sources available on later cycles.
It never converts a policy rejection into an acceptance merely to remain busy.
Temporary failures use bounded exponential backoff, so an unavailable source
does not create a busy retry loop. Accepted, rejected, and duplicate decisions
remain checkpointed; each later cycle continues from unresolved items.

## Website discovery

Search for candidate source websites by category without acquiring their
content:

```bash
sweeper discover --config sweeper.json --category "open scientific archives"
```

Results are a review queue, not permission to crawl. Operators must establish
the source contract, robots guidance, terms, rights, privacy boundary, stable
identifiers, and respectful rate limits before adding a discovered site.

## Optional ten-language translation bridge

Sweeper V2 recognizes English, Spanish, French, German, Italian, Portuguese,
Dutch, Russian, Greek, and Latin. Translation engines are deliberately external
and local/configurable so the core stays lightweight and does not send data to
an AI service by default.

```bash
sweeper translator-status
export SWEEPER_TRANSLATOR_IT_EN=/path/to/your/local-json-translation-command
sweeper translate --input source.txt --output derived-en.txt \
  --source-language it --target-language en
```

The command receives JSON on standard input and returns
`{"translation":"..."}`. Sweeper preserves the original, validates basic
output safety, and writes SHA-256 evidence beside the derived translation.
Translated output always requires human or domain-specific validation.

## Source contract

Each source points to a JSON Lines manifest. Every line represents one
acquisition unit:

```json
{"id":"record-001","url":"https://example.edu/files/record-001.xml","title":"Record 001","language":"en","license":"CC0-1.0","media_type":"application/xml","metadata":{"collection":"example"}}
```

Manifest records require stable `id` and `url` fields. Optional
`artifact_class` values can describe documents, datasets, archives, media,
public records, or structured directories. `data_class` lets an institution
separate open-public and institution-authorized material. Policy can allowlist
language, license, media type, artifact class, data class, and byte bounds. The
downloaded bytes are hashed during streaming and stored once by SHA-256.

## Minimal configuration

```json
{
  "workspace": "./sweeper-data",
  "user_agent": "Example University Sweeper/2.0 (archives@example.edu)",
  "layout": {"major_slots": 2, "minor_slots": 1},
  "policy": {
    "languages": ["en"],
    "licenses": ["PUBLIC-DOMAIN", "CC0-1.0", "CC-BY-4.0"],
    "media_types": ["text/plain", "text/html", "application/json"],
    "data_classes": ["open-public"],
    "minimum_bytes": 1,
    "maximum_bytes": 1073741824,
    "require_language": true,
    "require_license": true
  },
  "sources": [{
    "id": "example-archive",
    "lane": "major",
    "slot": 1,
    "manifest": "./manifests/example.jsonl",
    "requests_per_second": 1.0,
    "workers": 1
  }]
}
```

Start with one source, inspect its decisions and stored objects, then expand.
Every enabled source must occupy a unique lane and slot.

## Commands and workspace outputs

```bash
sweeper init
sweeper validate --config sweeper.json
sweeper run --config sweeper.json
sweeper daemon --config sweeper.json --interval 60
sweeper status --config sweeper.json
sweeper discover --config sweeper.json --category "open scientific archives"
sweeper translator-status
sweeper dock-status --config sweeper.json
```

The workspace contains `state.sqlite3` for resumable decisions, `objects/` for
content-addressed bytes, `daemon-state.json` for health and retry timing, and
`discovered-sources.json` for candidate websites awaiting operator review.

## Guarded staging dock and optional live station

Acquisition always lands in the staging dock first. A live destination is not
configured or contacted by default. Before promotion, an operator or review
system must create an attestation binding approval to every staged object's
exact source ID, item ID, and SHA-256 digest:

```json
{
  "approved": true,
  "reviewed_by": "Institutional review team",
  "reviewed_at": "2026-08-11T12:00:00Z",
  "items": {"example-archive:record-001": "EXPECTED_SHA256"}
}
```

Validate and freeze that exact membership:

```bash
sweeper dock-validate --config sweeper.json --attestation approval.json
```

Live promotion is an explicit, separate operation. The operator supplies both
a publisher and an independent verifier; Sweeper sends JSON on standard input
and requires JSON responses containing the exact item keys in `published` and
`verified`, respectively:

```bash
sweeper dock-promote --config sweeper.json \
  --publisher-command ./publish-approved-data \
  --verifier-command ./verify-live-data
```

Promotion fails closed if an object changes, membership differs, either
command fails, or either response omits an item. Evidence is written to
`dock-validation.json` and `dock-promotion.json`. Acquisition can continue in
staging even when no live connector exists or a live destination is offline.

Phone numbers and email addresses may be processed only when the operator is
authorized to acquire and use those records—for example, a consented internal
directory or a lawfully published government contact dataset. Sweeper V2 is not
designed for personal-contact harvesting, unsolicited marketing, doxxing, or
circumventing privacy and access controls.

## AI-assisted review

AI review is optional and vendor-neutral. Configure `policy.reviewer_command`
as an executable and arguments. Sweeper sends one JSON object to its standard
input containing candidate metadata and the local object path. The command must
return JSON:

```json
{"accepted": true, "reason": "policy checks passed"}
```

This allows an operator to connect ChatGPT through their own approved API
client, another hosted model, a local model, or a deterministic institutional
validator. Sweeper V2 does not send information to an AI service by default.
Never send confidential, personal, regulated, or contract-restricted content
to a model without the required authorization and data controls.

## Safety and responsible use

The operator is responsible for permission, copyright, privacy, records rules,
robots guidance, provider terms, rate limits, retention, and security. Use a
truthful contact-bearing user agent. Prefer official APIs and bulk exports.
Never use Sweeper V2 to bypass authentication, paywalls, technical controls, or
access restrictions.

See [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Status

Version 0.3.1 is an alpha foundation. It supports JSONL manifests, HTTP(S) and
local-file manifests, streamed HTTP(S) acquisition, content hashing,
content-addressed storage, policy filtering, optional command-based review,
resumption, status counts, and guarded hash-bound staging-to-live promotion.
Provider-specific adapters and export targets
belong in separate extensions so the core remains small and auditable.

## License

Apache License 2.0. Attribution is appreciated; see [NOTICE](NOTICE).

## Creator

Christian Cassarly created Sweeper V2 as a public technology-sharing project
through Jesus New OS: a small, adaptable foundation people can configure for
responsible large-scale information acquisition without tying the tool to one
subject, institution, repository, or model provider.

Explore **[Jesus New OS on the Apple App Store](https://apps.apple.com/us/app/jesus-new-os/id6752420337)**.
