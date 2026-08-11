import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sweeper.config import load_config
from sweeper.cli import initialize
from sweeper.cli import daemon
from sweeper.engine import policy_reason
from sweeper.engine import run
from sweeper.dock import cleanup_verified_staging, membership, validate_attestation
from sweeper.model import Candidate, Policy
from sweeper.state import State
from sweeper.translation import LANGUAGES, capabilities, engine_variable
from sweeper.continuation import build_plan


class SweeperV2Test(unittest.TestCase):
    def test_default_two_plus_two_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = Path(__file__).parents[1] / "examples/sweeper.example.json"
            data = json.loads(example.read_text())
            data["workspace"] = "data"
            path = root / "sweeper.json"
            path.write_text(json.dumps(data))
            config = load_config(path)
            self.assertEqual(2, config.major_slots)
            self.assertEqual(2, config.minor_slots)
            self.assertEqual(4, len(config.sources))

    def test_light_layout_can_expand_to_six(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); example = Path(__file__).parents[1] / "examples/sweeper.example.json"
            data = json.loads(example.read_text()); data["workspace"] = "data"
            data["layout"]["minor_slots"] = 6
            for slot in range(3, 7):
                data["sources"].append({"id": f"minor-{slot}", "slot": slot, "lane": "minor",
                    "manifest": "./manifests/minor-one.jsonl", "workers": 1,
                    "requests_per_second": 0.5})
            path = root / "sweeper.json"; path.write_text(json.dumps(data))
            config = load_config(path)
            self.assertEqual(6, config.minor_slots); self.assertEqual(8, len(config.sources))

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

    def test_daemon_once_records_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "sweeper.json"
            config_path.write_text(json.dumps({
                "workspace": "data", "user_agent": "Test Institute (test@example.org)",
                "layout": {"major_slots": 2, "minor_slots": 6},
                "policy": {}, "sources": [],
            }))
            self.assertEqual(0, daemon(config_path, 5, once=True))
            health = json.loads((root / "data/daemon-state.json").read_text())
            self.assertEqual("healthy", health["status"])
            self.assertEqual(0, health["consecutiveFailures"])
            self.assertEqual(5, health["nextCheckSeconds"])

    def test_broken_source_does_not_stop_later_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good_object = root / "good.txt"; good_object.write_text("good public record")
            good_manifest = root / "good.jsonl"
            good_manifest.write_text(json.dumps({"id": "good", "url": good_object.as_uri(),
                "language": "en", "license": "CC0-1.0", "media_type": "text/plain"}) + "\n")
            config_path = root / "sweeper.json"
            config_path.write_text(json.dumps({"workspace": "data",
                "user_agent": "Test Institute (test@example.org)",
                "layout": {"major_slots": 2, "minor_slots": 6},
                "policy": {"languages": ["en"], "licenses": ["CC0-1.0"],
                           "media_types": ["text/plain"]},
                "sources": [
                    {"id": "broken", "slot": 1, "lane": "major", "manifest": "missing.jsonl"},
                    {"id": "good", "slot": 2, "lane": "major", "manifest": "good.jsonl"}]}))
            result = run(load_config(config_path))
            self.assertEqual(1, result["counts"]["accepted"])
            self.assertEqual("broken", result["sourceErrors"][0]["source"])

    def test_continuation_pool_retains_partial_catch_and_reaches_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); manifests = []
            for number in (1, 2):
                obj = root / f"object-{number}.txt"; obj.write_text(f"public record {number}")
                manifest = root / f"manifest-{number}.jsonl"
                manifest.write_text(json.dumps({"id": str(number), "url": obj.as_uri(),
                    "language": "en", "license": "CC0-1.0", "media_type": "text/plain"}) + "\n")
                manifests.append(manifest.name)
            config_path = root / "sweeper.json"
            config_path.write_text(json.dumps({"workspace": "data",
                "user_agent": "Test Institute (test@example.org)",
                "layout": {"major_slots": 2, "minor_slots": 1},
                "policy": {"languages": ["en"], "licenses": ["CC0-1.0"],
                           "media_types": ["text/plain"]},
                "sources": [{"id": "light", "slot": 1, "lane": "minor",
                    "manifest": manifests[0], "continuation_manifests": [manifests[1]],
                    "target_items": 2, "requests_per_second": 10.0}]}))
            result = run(load_config(config_path))
            self.assertEqual(2, result["counts"]["accepted"])
            self.assertFalse(result["continuationRequired"])

    def test_translation_bridge_has_exact_ten_languages_and_fails_closed(self):
        self.assertEqual(10, len(LANGUAGES))
        self.assertEqual("SWEEPER_TRANSLATOR_IT_EN", engine_variable("it", "en"))
        status = capabilities()
        self.assertEqual(90, len(status["pairs"]))

    def test_staging_dock_requires_exact_hash_bound_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); obj = root / "object"; obj.write_bytes(b"staged")
            digest = hashlib.sha256(obj.read_bytes()).hexdigest()
            state = State(root / "state.sqlite3")
            state.record(source_id="s", item_id="1", url="u", title="t", status="accepted",
                         updated_at="now", digest=digest,
                         size=6, local_path=str(obj))
            items = state.accepted_items(); state.close()
            attestation = root / "approval.json"
            attestation.write_text(json.dumps({"approved": True, "reviewed_by": "Reviewer",
                "reviewed_at": "now", "items": membership(items)}))
            result = validate_attestation(root, attestation)
            self.assertTrue(result["passed"]); self.assertEqual(1, result["item_count"])

    def test_continuation_plan_is_fleet_aware_and_advisory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); config_path = root / "sweeper.json"
            config_path.write_text(json.dumps({"workspace": "data",
                "user_agent": "Test Institute (test@example.org)",
                "layout": {"major_slots": 2, "minor_slots": 2}, "policy": {},
                "sources": [
                    {"id": "major", "slot": 1, "lane": "major", "manifest": "a.jsonl"},
                    {"id": "light", "slot": 1, "lane": "minor", "manifest": "b.jsonl",
                     "target_items": 10}]}))
            config = load_config(config_path); state = State(config.workspace / "state.sqlite3")
            state.record(source_id="light", item_id="1", url="u", title="t", status="failed",
                         updated_at="now", reason="timeout")
            plan = build_plan(config, state); state.close()
            self.assertEqual("fleet-aware-continuation-advisor", plan["model"])
            self.assertGreaterEqual(len(plan["pool"]), 20)
            self.assertEqual(len(plan["pool"]), len(set(plan["pool"])))
            self.assertEqual(2, len(plan["decisions"]))
            light = next(row for row in plan["decisions"] if row["source"] == "light")
            self.assertTrue(light["autonomy"]["advisoryOnly"])
            self.assertEqual("steady", light["breathing"]["mode"])
            self.assertIn(light["recommendedAction"], plan["pool"])

    def test_cleanup_requires_passing_exact_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "dock-promotion.json"):
                cleanup_verified_staging(root, ["unused"])
            (root / "dock-promotion.json").write_text(json.dumps({"passed": False,
                "published": ["s:1"], "verified": [], "items": {"s:1": "abc"}}))
            with self.assertRaisesRegex(ValueError, "live verification is incomplete"):
                cleanup_verified_staging(root, ["unused"])


if __name__ == "__main__":
    unittest.main()
