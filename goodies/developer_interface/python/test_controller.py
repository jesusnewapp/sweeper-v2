import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from controller import SweeperController


class ControllerTests(unittest.TestCase):
    def test_status_reads_lane_without_inventing_live_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {
                "status": "running",
                "stage": "acquiring",
                "currentBatchSize": 2000,
                "acceptedInCurrentBatch": 321,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
            config = {
                "projectRoot": str(root),
                "codexLive": 42,
                "lanes": [
                    {
                        "id": "source",
                        "name": "Source",
                        "statePath": "state.json",
                        "target": 2000,
                    }
                ],
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            status = SweeperController(config_path).status()
            self.assertEqual(status["codexLive"], 42)
            self.assertEqual(status["lanes"][0]["accepted"], 321)
            self.assertEqual(status["lanes"][0]["health"], "healthy")
            self.assertIn("progressSince", status["lanes"][0])
            self.assertEqual(status["productionWriterLimit"], 1)

    def test_unconfigured_actions_are_disabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({"projectRoot": str(root), "actions": {}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "action is disabled"):
                SweeperController(config_path).action("reset", "source")

    def test_model_slot_preferences_are_bounded_and_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({"projectRoot": str(root)}), encoding="utf-8")
            controller = SweeperController(config_path)
            controller.save_preferences({
                "sourceSlots": 4,
                "models": [
                    {"name": "Open Library", "connector": "https://openlibrary.org",
                     "batchTarget": 2000, "uploadTarget": 100},
                    {"name": "", "connector": "", "batchTarget": 2000, "uploadTarget": 100},
                ],
            })
            saved = json.loads((root / "controller.preferences.json").read_text())
            self.assertEqual(saved["sourceSlots"], 4)
            self.assertEqual(saved["models"][0]["name"], "Open Library")
            self.assertEqual(saved["models"][1]["slot"], 2)


if __name__ == "__main__":
    unittest.main()
