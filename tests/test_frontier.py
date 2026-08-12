import json
import tempfile
import unittest
from pathlib import Path

from sweeper.frontier import FrontierRetirement


class FrontierRetirementTest(unittest.TestCase):
    def test_exact_exhausted_file_is_skipped_until_its_bytes_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "items.jsonl"
            manifest.write_text(json.dumps({"id": "one"}) + "\n", encoding="utf-8")
            memory = FrontierRetirement(root / "workspace")
            self.assertFalse(memory.is_retired("source", str(manifest)))
            receipt = memory.retire("source", str(manifest))
            self.assertFalse(receipt["acceptedArtifactsChanged"])
            self.assertTrue(memory.is_retired("source", str(manifest)))
            manifest.write_text(json.dumps({"id": "two"}) + "\n", encoding="utf-8")
            self.assertFalse(memory.is_retired("source", str(manifest)))


if __name__ == "__main__":
    unittest.main()
