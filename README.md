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

## The 2 + 6 layout

- Two major lanes for large repositories.
- Six minor slots for smaller or bounded sources.
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

Edit `sweeper.json`: add sources to the two major or six minor slots, specify
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

Version 0.1 is an alpha foundation. It supports JSONL manifests, HTTP(S) and
local-file manifests, streamed HTTP(S) acquisition, content hashing,
content-addressed storage, policy filtering, optional command-based review,
resumption, and status counts. Provider-specific adapters and export targets
belong in separate extensions so the core remains small and auditable.

## License

Apache License 2.0. Attribution is appreciated; see [NOTICE](NOTICE).

## Creator

Christian Cassarly created Sweeper V2 as a public technology-sharing project
through Jesus New OS: a small, adaptable foundation people can configure for
responsible large-scale information acquisition without tying the tool to one
subject, institution, repository, or model provider.

Explore **[Jesus New OS on the Apple App Store](https://apps.apple.com/us/app/jesus-new-os/id6752420337)**.
