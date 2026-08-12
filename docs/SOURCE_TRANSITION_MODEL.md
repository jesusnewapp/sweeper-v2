# Source Transition Model

Web Sweeper may transition a source slot only at a completed-unit boundary.
The old source finishes its active unit, writes an exact non-production staging
receipt, cleans only receipt-bound re-downloadable cache, and preserves its
checkpoint. The controller then confirms the old coordinator is inactive before
starting exactly one configured successor and recording a durable transition
receipt. A restart replays the receipt instead of starting both sources.

The practice configuration contains four deliberately editable slots: Open
Library, Internet Archive, Plymouth Brethren, and Library of Congress. Its
example routes are Open Library to Plymouth Brethren and Internet Archive to
Library of Congress. The transition controller launches only the configured
command; it does not import or depend on a source-specific adapter module.

Each route targets 1,000 accepted works. If its bounded source exhausts first,
the source writes `sourceExhausted: true` into the exact completion receipt and
the controller stages every positive survivor count before transitioning. An
empty result is not staged, and a partial unit without exhaustion evidence is
rejected rather than mistaken for completion.

Google Books is intentionally excluded from the direct-acquisition practice
route: availability and download signals alone do not uniformly establish
reusable content rights. Completed or exhausted sources must not be recycled.

Evaluate the transition evidence without executing source commands:

```bash
PYTHONPATH=src python3 -m sweeper.transition \
  --config examples/source-transition.practice.json
```

The evaluator never starts, stops, downloads, stages, or publishes anything. It
reports `waiting-for-current-unit` until all three evidence files exist and then
reports `ready-to-transition`. Process supervision remains deployment-specific.
