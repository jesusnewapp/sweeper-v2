# Web Sweeper World

Web Sweeper World is an isolated translation-to-manuscript workspace exposed
through the Web Sweeper developer interface. It is intended for complete,
authorized foreign-language works that an operator wants to preserve in their
original form and evaluate as translated reader manuscripts.

## Separation from Web Sweeper

The UI toggle is only a view switch. A World deployment has a separate:

- Python controller and port;
- configuration and workspace;
- source cache and translation objects;
- review queue;
- translated-staging collection; and
- publication handoff.

The included example uses port `8791`; the ordinary developer interface uses
`8790`. Neither controller imports the other controller's state.

## Translation pipeline

1. Discover the minimum authoritative source metadata.
2. Check live and staged identities before expensive retrieval.
3. Verify item-level reusable-rights evidence and relevance.
4. Retrieve and preserve the complete original textual artifact.
5. Translate directly into a structured manuscript without overwriting the
   original.
6. Hash the original, translation, and manuscript evidence.
7. Run the inexpensive target-language/readability screen.
8. Require independent language, completeness, rights, relevance, and global
   duplicate validation.
9. Place only validated survivors in a dedicated translated-staging collection.
10. Publish only through an explicitly configured serialized writer and verify
    the deployed result.

The built-in quick English check is a rejection screen, not linguistic
approval. Every generated review record starts with `publicationApproved` set
to `false`.

## Languages and engines

The routing layer recognizes 35 language codes. Each source-to-target pair
still needs an operator-installed translation command exposed through a
pair-specific environment variable such as `SWEEPER_TRANSLATOR_FR_EN`.
Translation fails closed when no engine is configured, output is empty, or the
length ratio is unsafe. Model licenses and redistribution terms remain the
operator's responsibility.

## Run the independent controller

From the repository root:

```bash
python3 goodies/developer_interface/python/server.py \
  --config goodies/developer_interface/world-books-controller.json \
  --host 127.0.0.1 --port 8791 --local-no-auth
```

Local no-auth mode must stay loopback-only. Configure authentication before
binding a controller to another interface.

Run the Flutter interface in World mode:

```bash
cd goodies/developer_interface/flutter
flutter run -d macos \
  --dart-define=APP_MODE=world_books \
  --dart-define=CONTROLLER_URL=http://127.0.0.1:8791
```

The regular build can also switch between local ports `8790` and `8791` using
the header toggle.

## Worldwide knowledge collections

With lawful sources and domain review, the same workflow can support translated
medical-history collections, open scientific literature, exploration archives,
public legal history, educational libraries, and cultural preservation. The
value is not indiscriminate collection: it is the ability to cross a language
boundary while retaining source bytes, provenance, explicit decisions, and a
human-controlled publication boundary.
