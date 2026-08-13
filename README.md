# Web Sweeper

<p align="center">
  <img src="assets/sweeper-logo.png" alt="Web Sweeper logo: a cybernetic sweeper organizing a stream of data" width="520">
</p>

Web Sweeper is a lightweight, source-neutral framework for continuously acquiring and
preserving large information collections with reproducible provenance. It can
be configured for institutional archives, law, science, research datasets,
books, public records, media, structured directories, or other authorized
collections. The engine treats every acquisition unit as bytes plus provenance;
it does not assume the unit is a book.

Media is first-class: projects may acquire complete audio or music files,
video, images, comics, maps, software, datasets, archives, models, or mixed
collections. MIME-family rules such as `audio/*`, `video/*`, `image/*`, and
`text/*` avoid hard-coding every container while keeping policy explicit.

### Rights-free Game ROM and open-software presets

[`examples/rights-free-game-roms.example.json`](examples/rights-free-game-roms.example.json)
preserves only public-domain, open-license, or explicitly redistribution-authorized
game ROMs. It requires item-level rights evidence, platform metadata,
redistribution scope, an expected SHA-256 checksum, approved extensions, and ZIP
integrity/path validation. It does not attempt to classify games by age or content.

This preset does **not** authorize downloading commercial copyrighted games,
circumventing DRM, defeating access controls, scraping sign-in-only collections,
or treating abandonware labels as permission.

[`examples/open-software.example.json`](examples/open-software.example.json) is a
separate preset for openly licensed software/source archives. It requires a
recognized license, rights evidence, version/type metadata, redistribution scope,
and an expected checksum. Operators can select either preset, replace its manifest
and source slots, and retain the same continuation, hashing, deduplication, staging,
and optional reviewer workflow.

**Web Sweeper was created by Christian Cassarly through Jesus New OS and shared
openly for the public—for institutions, researchers, archivists, schools,
governments, developers, and responsible independent users.**

Christian “Chris” Cassarly originally developed Sweeper for Jesus New OS and is
now offering the framework publicly. He is using its architecture in pursuit of
a one-million-book Codex goal within a year. At institutional scale, an authorized
deployment by a major library, investment firm, law firm, research organization,
or government agency can acquire, organize, deduplicate, and provenance-bind
collections whose research, replacement, and operational data value reaches tens
of millions of dollars per year. That value is the resulting governed data asset
and preservation work product—not a promise of investment performance.

Sweeper remains available to individual users and developers as well as large
institutions. Public availability does not grant rights to anyone else's data.
Christian asks every operator to use Sweeper responsibly: obtain lawful authority,
honor licenses and access controls, retrieve respectfully, preserve provenance,
protect sensitive information, and keep human accountability over consequential
uses. Scale should strengthen those responsibilities, never weaken them.

Christian's operating pattern pairs Sweeper with Codex: Sweeper performs the
continuous source work, while Codex observes checkpoints, diagnoses failures,
coordinates recovery, and oversees the separately authorized validation and
publication boundary. Sweeper remains vendor-neutral and does not require Codex,
but the two can provide a particularly smooth complementary experience for an
operator supervising large, long-running acquisition programs.

Web Sweeper is not tied to Codex, a particular library, Firebase, a subject, or
an AI vendor. It downloads only sources that the operator configures and is
intentionally fail-closed when required identity, rights, or policy metadata is
missing.

## What the program does

Web Sweeper moves authorized information from source manifests into a local,
content-addressed archive:

1. Read stable item identities and download URLs.
2. Apply the configured language, license, rights evidence, format, data-class, artifact-class,
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

For unattended staging-only operation, see the optional
[`Overnight Sweeper mini-model`](overnight-sweeper/OVERNIGHT_SWEEPER_MODEL.md).
It keeps continuous source work separate from live publication authority.

An optional, standalone staged/live search utility is available in
[`goodies/`](goodies/README.md). Operators supply their own records and categories.
It is deliberately separate from sweeping and contains no Codex catalog data.
The Goodies collection also includes a cross-platform
[`Developer Interface`](goodies/developer_interface/) for monitoring and
explicitly configured control of authorized deployments.

## Reusable projects and collection goals

Each configuration is a named project that can be saved and loaded later. A
project preserves its workspace, fleet layout, source definitions, policies,
and goals. For example:

```json
"project": {
  "name": "Codex Project",
  "overall_target_items": 1000000,
  "daily_target_items": 3000
}
```

Set either target to `0` for no numeric target. The maximum permitted overall or
daily target is 100,000,000,000 items. Targets guide planning and progress
reporting; they do not relax quality gates or guarantee that a source contains
enough eligible material.

Each source may report `estimated_eligible_items` and
`estimated_daily_items`. The background Forecast Operator combines those
high-quality estimates on every daemon cycle. `sweeper plan` reports estimated
complete capacity, estimated daily capacity, progress achieved, and the
percentage of the desired daily and overall goals the fleet can currently
cover. Sources without enough evidence remain explicitly unknown; the operator
never manufactures a favorable estimate and never forces a sweeper decision.

The background Source Intelligence Operator reports active, queued, and
potential sites with their categories, confidence, estimated capacity, and next
evaluation. It also reasons about aggregate depletion using remaining eligible
capacity, acceptance-yield trends, duplicate/rejection pressure, bounded-source
completion, and newly discovered candidates. Its scope is always the configured
and discovered aggregate landscape—it never falsely declares that the entire
internet has been exhausted. Use `sweeper sources` for this operator view.

Forecasting is deliberately gradual. The operator publishes a loose percentage
early, reports its observation window, and labels it `preliminary-loose-estimate`.
After at least 14 days of measured operation it may label the estimate mature;
even then, percentages remain approximate because source inventories, overlap,
rights, quality yield, and the wider web can change.
Before sufficient evidence exists, it reports `still-calculating` plus an
approximate number of days until the first loose estimate and the more mature
estimate. The countdown is guidance, not a promise; sparse or changing sources
can extend it.
The number is intentionally dynamic. Every daemon cycle timestamps and
recalculates the forecast, so estimates and percentages can rise or fall as the
fleet learns more.

The Operator may also watch and assist during pivots and aggregate exhaustion.
It can rank potential next aggregates and explain the next evaluation required,
but it is advisory only. The Sweeper owns the decision to request, accept,
decline, defer, or replace the guidance. The Operator cannot activate a source,
change a mode, or force a pivot. Set a source's `assistance_mode` to
`sweeper-choice` (default) or `disabled`.

```bash
sweeper project-save --config sweeper.json --name "Codex Project"
sweeper project-list
sweeper project-load --name "Codex Project" --config codex-sweeper.json
sweeper plan --config codex-sweeper.json
sweeper pivot-enforcer --config codex-sweeper.json --watch --poll-seconds 10
```

The optional Pivot Enforcer is an accountability observer, not an elapsed-time
kill switch. Source adapters define a durable progress vector appropriate to the
source: accepted items, discovery pages or cursors, candidate inventory, stage
transitions, uploads, verifications, checkpoints, and exact receipts may all
prove movement. A quiet accepted counter alone is never exhaustion and never
authorizes terminating active discovery. Only the absence of every configured
signal outside a known long operation can create an overdue pivot obligation.
The enforcer never chooses the pivot; the adapter remains free to select its
best safe continuation. Rights, quality, staging, validation, and live-writer
rules remain unchanged.

Loading refuses to overwrite an existing configuration. This keeps saved
projects reusable without silently destroying current work.

## Current adoption model

Web Sweeper uses a **two-major plus two-light default fleet**. Every source keeps
an independent checkpoint. A lightweight continuation advisor observes durable
yield, retryable failures, target deficit, lane occupancy, and the positions of
other sources. It scores a reusable continuation pool and recommends the best
next move without making that recommendation an unbreakable rule.

An operator or adapter may accept the recommendation, choose a scored
alternative, or supply a better local continuation with a recorded reason.
Start with one proven source, adopt the default fleet when healthy, inspect it
with `sweeper plan`, and expand gradually to at most six light slots when source
and host capacity permit.

The advisor changes operating pressure and whole-source order only.
Authorization, rights, policy filters, hashes, deduplication, review, and guarded
live promotion remain invariant.

Sweeper itself remains free: no particular pivot, repivot, source, mode, batch
shape, or ranked recommendation is forced. Its two mandatory operating
invariants are **quality** and **continuation**. Quality determines what may
advance. Continuation means it keeps seeking another safe, useful action until
the operator explicitly deactivates it or no safe action is currently possible.
Through those invariants, the fleet continually strives toward the largest,
best-organized collection it can responsibly build.

### Autonomous unit progression

The simplest reliable source loop is prepare → stage exact survivors → persist
the outcome → immediately begin the next unit. Individual duplicates and failed
members are bookkept and quarantined without stopping valid survivors. A depleted
page or cursor window advances inside the same coordinator; it is not treated as
a completed source or a reason to wait for an external restart. Do not infer
source or collection exhaustion from a timer. Exhaustion requires the configured
deterministic frontier to finish with no unvisited query pages, cursors, or
records. Rate-limited discovery may hold its accepted count steady while its
page checkpoint and candidate inventory continue to grow. Keep discovery and
acquisition as distinct one-way gates: finish the configured discovery window,
then process and stage its survivors. Do not alternate gates merely to create
visible counter movement; expose unique page and candidate progress instead.

Track successful automatic advances separately from manual restarts,
monitor-triggered recoveries, and crash recoveries. Operators select each
source's `batch_size` explicitly; 50 and 100 are recommended starting choices.
The public runtime enforces a hard maximum of 1,000 accepted items per source
batch, regardless of whether those items are books, documents, media, datasets,
software, or another configured artifact class. Repeated autonomous progression and end-to-end queue
capacity justify moving toward that ceiling; a single successful fill does not.
Discovery inventories may be much larger than acquisition or staging batches.

```json
{"id":"major-one","lane":"major","slot":1,"manifest":"items.jsonl","batch_size":100}
```

Change `batch_size` between completed batches, then restart or reload the
coordinator from its durable checkpoint. Never change the membership target of
an already-open batch. Main V2 records `source-batch-start` and
`source-batch-complete` activity events so operators can distinguish automatic
advances from manual or monitor-triggered recovery.

Staging and live publication remain separate. A high-throughput acquisition fleet
needs a continuously draining, serialized stage-to-live writer that verifies the
unchanged acquisition attestation, removes fresh live overlaps, publishes once,
verifies the live deployment, cleans only verified payloads, and advances directly
to the next ready unit. It does not repeat rights, relevance, source, or full-text
validation already completed during acquisition, and it does not require a
second legacy validation-report file when the exact acquisition attestation is
present. Acquisition speed is not useful
if the verified publication queue is left to grow without bound.

### Receipt-bound source transitions

Source slots can transition cleanly after their current unit finishes. Set
`source_slot_count` to 1–64 and provide the same number of ordered slot entries.
The supplied practice model has ten editable direct-download sources and nine
automatic transitions. It requires exact staging, cleanup, and checkpoint
evidence before the old coordinator yields its slot; the successor cannot
overlap it. A full unit restarts the same source, while proven exhaustion stages
any positive remainder and advances. A 1,000-item lane may stage a positive
partial unit only when its receipt proves that the bounded source is exhausted. See
[`docs/SOURCE_TRANSITION_MODEL.md`](docs/SOURCE_TRANSITION_MODEL.md) and
[`examples/source-transition.practice.json`](examples/source-transition.practice.json).
The large Internet Archive-hosted slots reuse one proven public API and direct-
download adapter with different collection queries; prior identifiers and
content hashes are excluded across slots.

The same practice configuration exposes an independent desired publication
batch-size placeholder globally and per source. Acquisition may stage a larger
unit while the one live writer publishes configured units from 1 through 1,000,
including the positive final remainder, and live-verifies each before advancing.

For a deliberately simpler deployment with no cross-source transition, use
[`examples/source-pool.two-slot.json`](examples/source-pool.two-slot.json). It
keeps exactly two continuous lanes—Open Library and Library of Congress—and
restarts each same-source lane only after its exact staging receipt. The larger
ten-slot model remains an optional reference for later source-pool testing.

## Optional Tertiary Mode

Tertiary Mode is a detachable, default-off observation field. It measures
Nurture, Pivot, and Continuation context without issuing advice, selecting a
route, opening or closing a gate, or starting or stopping a process. With the
mode off, Sweeper follows the established execution path unchanged.

The Inquisitive reader and Tertiary Adapter have independent toggles. The reader
may inspect the field or ignore it. The adapter exposes the same neutral field
to an existing host coordinator; it does not execute actions itself, and the
host retains all decision authority. This separation lets deployments add
context incrementally and detach it instantly without rewriting their working
source, rollover, staging, or publication logic.

The initial Nurture field uses deliberately simple measurement anchors: 50
accepted members emits 10%, 100 emits 20%, 1,000 emits 50%, 2,000 emits 75%,
and 10,000 emits 100%, with linear interpolation between anchors. This number
is context, not authority. A host may use stronger Nurture context to preserve
passing survivors, quarantine individual failures, stage a positive remainder,
and resume from a checkpoint. It must never use the number to force corrupt,
rights-uncertain, incomplete, duplicate, or unverified material through an
integrity boundary.

At staging-to-live, the adapter distinguishes an unchanged, hash-bound
acquisition attestation from the two checks that must be fresh. Repeating
rights, relevance, completeness, or full-text validation on unchanged membership
is continuity friction; the live duplicate delta and deployment/live
verification are fresh integrity boundaries. Nurture may help the host recognize
the former, but never overrides the latter.

Keep staging adapters stickman-simple: use one deterministic, idempotent write
per artifact with bounded retry, then create and read back one exact membership
receipt. Avoid separate existence and metadata round trips before every write;
the final hash-bound readback is the authoritative proof.

For large units, `RestartableStagingReceipt` checkpoints each successful exact
readback atomically. A timeout or process exit resumes from the last verified
member rather than replaying the unit. The progress file has no admission power;
the small `dock-staging.json` receipt appears atomically only after the entire
membership is verified.

The optional bridge switch is default-off and activates only when its nurture
score reaches the configured threshold (50% by default). It may skip repeated
acquisition review for an unchanged exact staging membership; it never skips
the live duplicate delta, serialized writer, or live verification.

```bash
sweeper bridge-switch --config sweeper.json --set on --threshold 50 \
  --accepted 500 --target 1000
sweeper bridge-switch --config sweeper.json --set off
```

```bash
# Inspect the default-off state.
sweeper tertiary-mode --config sweeper.json

# Enable observations and optional reading; execution remains unchanged.
sweeper tertiary-mode --config sweeper.json --set on --inquisitive on
sweeper tertiary-observe --config sweeper.json
sweeper inquisitive-read --config sweeper.json

# Attach/detach the neutral adapter view independently.
sweeper tertiary-mode --config sweeper.json --adapter on
sweeper tertiary-adapter --config sweeper.json
sweeper tertiary-mode --config sweeper.json --adapter off

# Restore the established model completely.
sweeper tertiary-mode --config sweeper.json --set off
```

## Nurture collections and survivor continuation

Set `nurture.threshold` (30 by default) to preserve passing membership as a
hash-bound collection. Priority rises with both collection size and lifecycle
position. A failed acquisition, review, translation, staging, or verification
member is individually recorded and excluded; it does not silently erase or
freeze valid survivors. Valid survivors continue toward the next configured
review, validation, staging, or live-dock gate.

Nurture authority bypasses ordinary queue order, batch-size waiting, idle
scheduling, restart loops, and discovery priority. It never bypasses rights,
quality, hash membership, independent validation, serialized writer ownership,
or deployment verification. Translation uses the same rule: validated
translations that the stager confirms advance, while unconfirmed members are
bookkept as individual failures.

### Sweepers never remain blocked

A failed item is bookkept and quarantined, deferred, or rejected. A failed or
exhausted source is bookkept and removed from active rotation or scheduled for
a later retry. Valid survivors remain nurtured and continue. The daemon then
resumes, retries, changes method, rotates source, or selects another safe pivot.
Accordingly, `sweeperBlocked` is always false in cycle results: a failure is a
recorded disposition plus a continuation decision, never a terminal sweeper
state. External publication may wait for credentials or a serialized writer,
but acquisition, preparation, translation, and other lanes continue.

## Activity data log

Every project keeps an append-only `activity-log.jsonl` in its workspace. It
records cycle starts/completions, item dispositions, source failures and
continuations, Nurture summaries, translation handoffs, dock validation, live
verification, and verified staging cleanup. It contains both what is happening
and what has happened, with UTC timestamps, lanes, outcomes, hashes, counts, and
reasons. Inspect a compact history with:

```bash
sweeper activity-log --config sweeper.json --limit 100
```

The JSONL history is never rewritten by this command and is suitable for later
indexing, dashboards, audits, or operator reporting.

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

Breathing adjusts operating pressure, not integrity. Failed retrievals increase
that source's delay up to eight times its configured baseline; healthy progress
gradually returns to the configured rate. Health evidence records every change
and confirms that integrity gates were not changed.

Continuation is target-driven, fleet-aware, and project-neutral. A source may define
`target_items` plus an ordered `continuation_manifests` pool. Sweeper retains
every valid partial catch, consumes the next manifest when useful, isolates a
failed manifest, and reports the remaining deficit with the next action
`add-or-discover-continuation-manifest`. The advisor also ranks resume, retry,
source-switch, scope, pacing, and checkpoint options against the configured
fleet. It never calls a partially productive
source a total failure, and it never converts an unreviewed staging item into a
live item merely to satisfy a target.

For simple source workers, continuation is deterministic and does not require
the optional pivot advisor. Exhausting one configured manifest records its exact
fingerprint and immediately advances to the next manifest. The cycle reports
`frontierAdvances` and `batchTransitions`, including survivor count, close
reason, next frontier, and whether the source itself is truly exhausted. Valid
partial batches are handed to staging; an empty or duplicate-only set is
bookkept and advanced instead of stopping the worker.

For more complex software, define a bounded pool of safe pivots during initial
design. Pivot choices must preserve checkpoints and accepted artifacts and may
never relax rights, integrity, review, deduplication, or writer controls.

The built-in pool currently contains 24 operations spanning checkpoint resume,
manifest/cursor advancement, source discovery and rotation, cache reuse,
pressure changes, review retry, per-item quarantine, survivor rebinding,
revalidation, live-delta refresh, writer recovery, queue advancement, and
verified staging cleanup. Extensions can propose local candidates; the advisor
still records the chosen action and keeps invariant gates unchanged.

## Progressive 2 + 1 → 2 → 6 layout

- Two major lanes for large repositories.
- Two light crawlers by default after the single-crawler proof.
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

Edit `sweeper.json`: add sources to the two major slots and two initial light
crawlers, specify
languages, licenses, formats, and size limits, and replace the placeholder user
agent with a truthful institutional name and contact address. Put stable item
IDs and download URLs in the generated JSONL manifests. No Python changes are
required for manifest-backed sources.

```bash
sweeper validate --config sweeper.json
sweeper run --config sweeper.json
sweeper status --config sweeper.json
sweeper plan --config sweeper.json
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

Each completed cycle writes `continuation-plan.json` with source positions, a
recommended continuation, four alternatives, breathing pressure, and invariant
safeguards. The readable JSON lets an operator, orchestrator, or AI assistant
choose a better safe alternative without modifying the acquisition core.

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

Runtime choices, official download links, installation examples, licensing
cautions, capacity planning, and the Translator Sweeper staging contract are in
[docs/TRANSLATOR_RUNTIME_OPTIONS.md](docs/TRANSLATOR_RUNTIME_OPTIONS.md).

The dedicated translation lane is operated with:

```bash
sweeper translation-status --config sweeper.json
sweeper translation-queue --config sweeper.json --target-language es
sweeper translation-run --config sweeper.json --target-language es
```

After exact language validation and translation-staging confirmation,
`translation-run` writes a shared-uploader handoff and immediately queues the
next available translation batch. It never acquires or duplicates the live
writer itself.

All public staging and live destinations are operator-supplied adapters. The
generated translation collection name is deliberately a `REPLACE_WITH_...`
placeholder, and enabling translation fails closed until it is changed. No
Codex Firebase destination or credential is included in the public package.

Web Sweeper recognizes English, Spanish, French, German, Italian, Portuguese,
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
{"id":"record-001","url":"https://example.edu/files/record-001.flac","title":"Record 001","language":"en","license":"CC0-1.0","rights_evidence_url":"https://example.edu/rights/record-001","media_type":"audio/flac","artifact_class":"music","metadata":{"collection":"example"}}
```

Manifest records require stable `id` and `url` fields. Optional
`artifact_class` values can describe documents, datasets, archives, audio,
music, video, images, comics, software, maps, models, public records, or other
units. `data_class` lets an institution
separate open-public and institution-authorized material. Policy can allowlist
language, license, media type, artifact class, data class, and byte bounds. The
downloaded bytes are hashed during streaming and stored once by SHA-256. Set
`require_rights_evidence` to `true` to reject an item before download unless it
has an item-specific license, permission, or public-domain evidence URL.

## Minimal configuration

```json
{
  "workspace": "./sweeper-data",
  "user_agent": "Example University Sweeper/2.0 (archives@example.edu)",
  "layout": {"major_slots": 2, "minor_slots": 2},
  "policy": {
    "languages": ["en"],
    "licenses": ["PUBLIC-DOMAIN", "CC0-1.0", "CC-BY-4.0"],
    "media_types": ["text/*", "audio/*", "video/*", "image/*", "application/json", "application/zip", "application/vnd.comicbook+zip"],
    "artifact_classes": ["document", "dataset", "archive", "audio", "music", "video", "image", "comic", "software", "map", "model", "other"],
    "data_classes": ["open-public"],
    "minimum_bytes": 1,
    "maximum_bytes": 1073741824,
    "require_language": true,
    "require_license": true,
    "require_rights_evidence": true
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
sweeper plan --config sweeper.json
sweeper discover --config sweeper.json --category "open scientific archives"
sweeper translator-status
sweeper dock-status --config sweeper.json
```

The workspace contains `state.sqlite3` for resumable decisions, `objects/` for
content-addressed bytes, `daemon-state.json` for health and retry timing,
`discovered-sources.json` for candidate websites awaiting operator review, and
`continuation-plan.json` for fleet-aware continuation recommendations.

## Guarded staging dock and optional live station

Acquisition always lands in the staging dock first. A live destination is not
configured or contacted by default. Before promotion, acquisition or an
authorized review system must create an attestation binding completed approval
to every staged object's exact source ID, item ID, and SHA-256 digest:

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
  --verifier-command ./verify-live-data \
  --cleanup-command ./delete-verified-staging
```

Promotion reuses that attestation while its membership, hashes, policy version,
and validator version remain unchanged. It must not repeat source retrieval,
rights research, or full-text validation. The live connector must still run a
fresh duplicate delta immediately before writing and omit each newly live
identity individually. Promotion fails closed if an object changes, membership
differs, either command fails, or either response omits an eligible survivor.
Evidence is written to
`dock-validation.json` and `dock-promotion.json`. Acquisition can continue in
staging even when no live connector exists or a live destination is offline.

Staging deletion is optional and can occur only after exact live verification.
The cleanup command receives the hash-bound promoted membership and must return
`{"deleted":["source:item", "..."]}` for that exact set. A partial response or
cleanup failure preserves staging and fails closed. If live promotion succeeded
but cleanup later failed, retry cleanup without republishing:

```bash
sweeper dock-cleanup --config sweeper.json \
  --cleanup-command ./delete-verified-staging
```

Successful deletion is recorded in `dock-cleanup.json` and bound to the exact
`dock-promotion.json` hash.

Deployments with reproducible source downloads may reclaim raw source cache
earlier, after an exact non-production staging receipt. Write `dock-staging.json`
with `passed: true`, `production_mutated: false`, and the exact hash-bound item
membership, then run:

```bash
python -m sweeper.source_cleanup --workspace ./data \
  --cleanup-command ./delete-exact-rehydratable-source-cache
```

The cleaner must confirm every exact key and report reclaimed bytes. This never
deletes staged artifacts, catalogs, hashes, journals, checkpoints, receipts, or
active-unit data. If later validation needs original source evidence, restore it
from recorded URLs and require the recorded hashes before promotion. Local
manuscripts may be discarded only after exact live verification; retain their
hash manifest and cleanup receipt.

Phone numbers and email addresses may be processed only when the operator is
authorized to acquire and use those records—for example, a consented internal
directory or a lawfully published government contact dataset. Web Sweeper is not
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
validator. Web Sweeper does not send information to an AI service by default.
Never send confidential, personal, regulated, or contract-restricted content
to a model without the required authorization and data controls.

## Safety and responsible use

The operator is responsible for permission, copyright, privacy, records rules,
robots guidance, provider terms, rate limits, retention, and security. Use a
truthful contact-bearing user agent. Prefer official APIs and bulk exports.
Never use Web Sweeper to bypass authentication, paywalls, technical controls, or
access restrictions.

See [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Status

Version 0.8.0 is an alpha foundation. It supports JSONL manifests, HTTP(S) and
local-file manifests, streamed HTTP(S) acquisition, content hashing,
content-addressed storage, policy filtering, optional command-based review,
resumption, status counts, and guarded hash-bound staging-to-live promotion.
This release adds MIME-family media acquisition, item-level rights-evidence
gates, access-required skipping, media-aware pivots, saved projects and goals, background forecasting and source
intelligence, advisory operator assistance, translation staging with a shared
uploader handoff, and the standalone Goodies staged/live index and UI starter.
It retains fleet-aware continuation scoring, source reordering between whole
source turns, explicit breathing state, and `sweeper plan`.
Provider-specific adapters and export targets
belong in separate extensions so the core remains small and auditable.

## License

Apache License 2.0. Attribution is appreciated; see [NOTICE](NOTICE).

## Creator

Christian Cassarly is a Codex-assisted software developer and operating-system
architect for Jesus New OS. He created Web Sweeper as a public
technology-sharing project: a small, adaptable foundation people can configure
for responsible large-scale information acquisition without tying the tool to
one subject, institution, repository, or model provider.

Explore **[Jesus New OS on the Apple App Store](https://apps.apple.com/us/app/jesus-new-os/id6752420337)**.
