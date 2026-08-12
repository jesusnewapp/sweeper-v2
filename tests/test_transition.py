import json
import tempfile
import unittest
from pathlib import Path

from sweeper.transition import evaluate


class SourceTransitionTest(unittest.TestCase):
    def test_waits_then_becomes_ready_from_exact_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "transition.json"
            config.write_text(json.dumps({"practice_mode": True, "routes": [{
                "from": "open-library", "to": "plymouth-brethren",
                "target": 1000, "allow_partial_on_exhaustion": True,
                "completion_receipt": "stage.json", "cleanup_receipt": "cleanup.json",
                "checkpoint": "checkpoint.json", "commands_are_placeholders": True,
            }]}))
            self.assertEqual(1, evaluate(config)["waiting"])
            (root / "stage.json").write_text(json.dumps({
                "staged": 50, "productionMutated": False, "sourceExhausted": True,
            }))
            (root / "cleanup.json").write_text(json.dumps({"bytesReclaimed": 0}))
            (root / "checkpoint.json").write_text(json.dumps({"cursor": 10}))
            result = evaluate(config)
            self.assertEqual(1, result["ready"])
            self.assertEqual("replace-placeholder-commands", result["routes"][0]["nextAction"])
            self.assertTrue(result["routes"][0]["partialUnit"])

    def test_partial_unit_requires_exhaustion_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "transition.json"
            config.write_text(json.dumps({"routes": [{"from": "a", "to": "b",
                "target": 1000, "allow_partial_on_exhaustion": True,
                "completion_receipt": "stage.json", "cleanup_receipt": "cleanup.json",
                "checkpoint": "checkpoint.json"}]}))
            (root / "stage.json").write_text(json.dumps({"staged": 999, "productionMutated": False}))
            (root / "cleanup.json").write_text(json.dumps({"bytesReclaimed": 1}))
            (root / "checkpoint.json").write_text("{}")
            with self.assertRaises(ValueError):
                evaluate(config)

    def test_rejects_nonisolated_staging_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "transition.json"
            config.write_text(json.dumps({"routes": [{"from": "a", "to": "b",
                "completion_receipt": "stage.json", "cleanup_receipt": "cleanup.json",
                "checkpoint": "checkpoint.json"}]}))
            (root / "stage.json").write_text(json.dumps({"staged": 1, "productionMutated": True}))
            (root / "cleanup.json").write_text(json.dumps({"bytesReclaimed": 1}))
            (root / "checkpoint.json").write_text("{}")
            with self.assertRaises(ValueError):
                evaluate(config)


if __name__ == "__main__":
    unittest.main()
