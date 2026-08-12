# Overnight Sweeper Mini-Model

Overnight Sweeper is an optional operating model for unattended, continuous,
staging-only acquisition. It extends Web Sweeper without changing its rights,
quality, provenance, hashing, deduplication, or continuation rules.

## Boundary

- Run source workers with staging authority only.
- Keep publication, live promotion, and live verification in a separate writer.
- Keep one canonical coordinator per source unit. Never run overlapping workers
  against the same unit or checkpoint.
- Continue without a numeric batch limit when configured. Stop only for source
  exhaustion, operator shutdown, a capacity gate, or a fail-closed integrity or
  source error.
- Allow the operator to raise a source unit ceiling when measured acceptance
  throughput and free-space headroom support it; the ceiling changes packaging
  size only and never weakens item gates or the capacity stop.
- Let the operator select the next unit size explicitly. Start at 50 or 100
  while proving the lane, and never exceed 1,000 accepted items in one staging
  unit. This applies across configured artifact classes; the public runtime
  enforces the ceiling.
- After a successful staging upload, record a receipt and immediately begin the
  next source unit.
- A unit may close because it reached its accepted-item target or because its
  current source frontier was genuinely exhausted. In either case, stage every
  eligible survivor already prepared, record the exact survivor count, and
  advance. Never hold a valid remainder merely because it is smaller than the
  configured target.
- Treat exhaustion of one discovery page, cursor window, or partition as an
  internal continuation event, not a successful coordinator exit. Persist the
  next frontier, retain the same incomplete unit and checkpoint, and continue
  immediately. Exit only when the source frontier itself is proven exhausted.
- Use this direct continuation state machine for simple source models. A
  separate pivot advisor is optional and is not required for deterministic
  `checkpoint -> exhaust set -> advance set -> stage survivors -> next unit`
  operation. Design pivot pools at the beginning of future complex systems
  whose workers have several materially different safe recovery routes.
- Bind a proven-exhausted frozen manifest to its exact fingerprint, retire it
  from active rotation, and skip it on restart. If a local manifest's bytes
  change, reactivate it automatically. Source adapters may discard generated
  frozen candidate files after recording retirement, but must never delete
  accepted artifacts, receipts, journals, checkpoints, or deduplication memory.
- Do not perform staging verification inside the staging loop. The separate
  stage-to-live workflow owns independent validation, staging verification,
  and promotion policy.

## Unit loop

1. Confirm source ownership and the authoritative workspace.
2. Refresh the operator-configured identity/deduplication evidence.
3. Resume the exact checkpoint, candidate frontier, and screening memory.
   When only the current discovery window is exhausted, atomically advance the
   frontier and repeat this step inside the same coordinator and source unit.
4. Apply metadata, rights, language, format, completeness, and policy gates.
5. Acquire, hash, deduplicate, and preserve accepted artifacts.
6. Upload only to the configured isolated staging destination. Mark the unit as
   awaiting stage-to-live validation; do not claim it is independently validated.
7. Write a staging receipt containing source, unit, count, timestamp, artifact
   binding, and an explicit declaration that live production was not mutated.
8. Commit the completed-unit checkpoint and next frontier before launching the
   successor. Treat receipt, completion accounting, and successor selection as
   one recoverable transition so a crash can replay safely without double
   staging or skipping a frontier.
9. Immediately begin the next unit. Independent validation is not part of this
   transition and cannot block acquisition continuation.

The source adapter's acquisition gates remain mandatory. Moving the independent
audit out of the staging loop does not permit missing rights evidence, unsafe
formats, incomplete acquisition, absent hashes, or known duplicates to stage.
The public V2 guarded dock remains unchanged: before live promotion, an operator
or review system must independently attest and validate the exact staged hashes.

An individual fresh-delta duplicate never aborts a staging unit or prevents its
coordinator from advancing. Quarantine that member with its matched identity
keys and remote record IDs, rewrite the exact local membership atomically, stage
all remaining survivors, record the survivor count in the receipt, and continue.
If every member is already represented, record a zero-survivor completion and
advance without uploading or retrying the duplicates.

Apply the same isolation rule to malformed generated candidate files and other
item-scoped preparation failures: record and discard the failed generated input,
preserve accepted artifacts and checkpoint evidence, and keep the source lane
moving. A source-wide integrity failure remains fail-closed.

## Autonomous scaling

Do not raise a source toward the 1,000-item ceiling merely because one large unit
fills successfully. Observe at least 5–10 consecutive autonomous unit
continuations before considering a controlled increase, and require a longer
record such as 50 consecutive autonomous continuations before calling a size
established or making it the default. Each qualifying continuation must
stage the exact eligible survivors, quarantine individual duplicates, persist the
checkpoint and accounting, and begin the next unit without an operator, monitor,
or replacement process restarting it.

Track automatic continuations, crash recoveries, monitor-triggered restarts, and
manual restarts separately. A manual or monitor-triggered restart resets the
consecutive-autonomy streak. Reaching an observation threshold is evidence for
evaluation, not an automatic upgrade: disk headroom, source yield, staging
latency, dedup behavior, stage-to-live throughput, and absence of overlapping
workers must also support the larger tier. Discovery frontiers may contain
millions of records, but the 1,000 ceiling applies to items packaged in one
staging unit.

## Stage-to-live drainage

Keep acquisition continuous while one separately authorized writer drains ready
staged units in deterministic order. For each exact unit, validate its bound
artifacts, perform the fresh live-delta check, publish once under a serialized
writer lease, verify the deployment, clean only live-verified staging and local
payloads, and immediately take the next ready unit. Report queue depth and age so
staging throughput cannot silently outrun verified publication capacity.

## Inactivity monitor

- Check coordinator and child-process health every five minutes for the
  operator-requested monitoring window.
- Compare process liveness, stage, checkpoint timestamp, counters, activity log,
  and free space with the prior check.
- Allow long indexing, deduplication, retrieval, and upload phases while the
  process is live and its resource behavior is plausible.
- Treat a lane as inactive after two consecutive checks without meaningful
  progress, or immediately when its process exits unexpectedly or records a
  failure state.
- Before recovery, prove the former coordinator and child are dead and no
  overlapping unit is active.
- Restart the same canonical coordinator from its existing checkpoint, cache,
  candidate frontier, and deduplication state.
- Never reset a source, delete evidence, broaden scope, or create a second
  claimant during automatic recovery.
- Alert the operator when inactivity occurs. Include source, unit, stage,
  counters, timestamps, process state, free space, recovery action, and result.
- Stay quiet while lanes are healthy or legitimately busy.

## Capacity and network recovery

- Configure an explicit free-space stop appropriate to the deployment. Never
  lower it automatically.
- Stop before scheduling new retrieval or atomic output work when the capacity
  gate fails.
- Retry only transient transport failures such as broken pipes, connection
  resets, timeouts, rate limits, and server errors.
- Use low upload concurrency, bounded attempts, and exponential backoff.
- Never reinterpret rights, identity, membership, or deduplication
  failures as network failures.
- Preserve local artifacts until the operator's separate promotion
  workflow establishes its required remote evidence or explicitly authorizes a
  different cleanup boundary.
- If independent promotion validation requires raw source evidence that was
  evicted after staging, deterministically rehydrate only the exact unit from
  its recorded source URLs, verify every recorded source hash, validate and
  live-verify under the serialized writer, then remove only those restored
  source files. Missing or mismatched evidence fails closed.
- After an exact staging receipt and remote object-count/binding check succeed,
  a deployment may evict only re-downloadable source caches belonging to that
  completed unit. Preserve manuscripts, catalogs, hashes, receipts, checkpoints,
  rejection memory, and active-unit caches unless the configured recovery path
  proves those bytes are available elsewhere.
- Never delete from an active unit. Resolve cleanup targets from completed
  receipt membership, validate every path beneath the configured cache root,
  log the reclaimed count and bytes, then recheck free space and worker health.
- Evaluate projected headroom before beginning the successor unit. The gate must
  include the configured reserve plus the largest measured temporary/atomic
  working set; accepted-item count alone is not a disk estimate.

## Replacement workers

A stopped source worker may be replaced only after confirming that its former
process is dead. The replacement inherits the same source scope, unit,
checkpoint, journal, candidate frontier, and deduplication database. Parallel
workers for one source require explicitly non-overlapping deterministic shards
and shared global deduplication evidence.

## Accounting

Report these states separately:

- candidates screened;
- accepted, rejected, deferred, and duplicate;
- staging uploads completed;
- units advanced, with automatic advances, crash recoveries, monitor recoveries,
  and manual restarts counted separately;
- recovery events and capacity stops;
- independently validated, staging-verified, published, and live-verified
  counts, which remain deferred in a staging-only run.

Never describe a staging upload as verified or published without evidence from
the separate workflow responsible for those states.
