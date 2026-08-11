import json
import tempfile
import unittest
from pathlib import Path

from sweeper.config import load_config
from sweeper.cli import initialize
from sweeper.engine import policy_reason
from sweeper.engine import run
from sweeper.model import Candidate, Policy
from sweeper.state import State


class SweeperV2Test(unittest.TestCase):
    def test_exact_two_plus_six_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = Path(__file__).parents[1] / "examples/sweeper.example.json"
            data = json.loads(example.read_text())
            data["workspace"] = "data"
            path = root / "sweeper.json"
            path.write_text(json.dumps(data))
            config = load_config(path)
            self.assertEqual(2, config.major_slots)
            self.assertEqual(6, config.minor_slots)
            self.assertEqual(8, len(config.sources))

    def test_policy_fails_closed_on_missing_rights(self):
        item = Candidate("s", "i", "https://example.test/i", language="en", license="")
        reason = policy_reason(item, Policy(languages=["en"], licenses=["CC0-1.0"]))
        self.assertEqual("missing-license", reason)

    def test_content_hash_dedup_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            state = State(Path(directory) / "state.sqlite3")
            state.record(source_id="a", item_id="1", url="u", title="t", status="accepted",
                         updated_at="now", digest="abc", size=3, local_path="p")
            self.assertEqual("a:1", state.hash_owner("abc"))
            state.close()

    def test_reviewer_is_disabled_by_default(self):
        self.assertEqual([], Policy().reviewer_command)

    def test_init_creates_editable_config_and_manifest_example(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sweeper.json"
            initialize(path)
            self.assertTrue(path.exists())
            self.assertTrue((path.parent / "manifests/source.example.jsonl").exists())
            self.assertEqual([], json.loads(path.read_text())["sources"])

    def test_end_to_end_local_manifest_is_resumable_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload.txt"
            payload.write_text("solid institutional record", encoding="utf-8")
            manifest = root / "items.jsonl"
            records = [
                {"id": "one", "url": payload.as_uri(), "title": "One", "language": "en",
                 "license": "CC0-1.0", "media_type": "text/plain"},
                {"id": "two", "url": payload.as_uri(), "title": "Two", "language": "en",
                 "license": "CC0-1.0", "media_type": "text/plain"},
            ]
            manifest.write_text("\n".join(json.dumps(value) for value in records) + "\n")
            config_path = root / "sweeper.json"
            config_path.write_text(json.dumps({
                "workspace": "data", "user_agent": "Test Institute (test@example.org)",
                "layout": {"major_slots": 2, "minor_slots": 6},
                "policy": {"languages": ["en"], "licenses": ["CC0-1.0"],
                           "media_types": ["text/plain"], "minimum_bytes": 1},
                "sources": [{"id": "local", "slot": 1, "lane": "minor",
                             "manifest": "items.jsonl", "requests_per_second": 10.0}],
            }))
            config = load_config(config_path)
            first = run(config)
            second = run(config)
            self.assertEqual({"accepted": 1, "duplicate": 1}, first["counts"])
            self.assertEqual(first["counts"], second["counts"])


if __name__ == "__main__":
    unittest.main()
