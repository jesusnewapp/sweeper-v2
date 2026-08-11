# Contributing

Contributions are welcome. Keep the core source-neutral, dependency-light, and
fail-closed. New adapters must document provider terms, stable identifiers,
pagination/resume behavior, respectful rate limits, and test fixtures that do
not hit a live service.

Run the tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Do not submit scraped datasets, credentials, copyrighted payloads, or private
institutional information to this repository.
