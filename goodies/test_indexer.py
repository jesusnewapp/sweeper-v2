import json
import tempfile
import unittest
from pathlib import Path

from indexer import export_json, index_jsonl, search


class GoodiesIndexerTest(unittest.TestCase):
    def test_staged_and_live_are_separate_and_incremental(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); database = root / "index.sqlite3"
            staged = root / "staged.jsonl"; live = root / "live.jsonl"
            staged.write_text(json.dumps({"id":"one","title":"Sample Record",
                "category":"Research","text":"alpha staged material"}) + "\n")
            live.write_text(json.dumps({"id":"one","title":"Sample Record",
                "category":"Research","text":"alpha live material"}) + "\n")
            self.assertEqual(1, index_jsonl(database, staged, "staged")["indexed"])
            self.assertEqual(1, index_jsonl(database, staged, "staged")["unchanged"])
            self.assertEqual(1, index_jsonl(database, live, "live")["indexed"])
            self.assertEqual(1, search(database, "staged", "staged")["count"])
            self.assertEqual(0, search(database, "staged", "live")["count"])
            self.assertEqual(2, search(database, "alpha", "all")["count"])
            exported = export_json(database, root / "index.json")
            self.assertEqual(2, exported["recordCount"])
            self.assertEqual(2, len(json.loads((root / "index.json").read_text())["records"]))


if __name__ == "__main__": unittest.main()
