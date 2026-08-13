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

    def test_active_staging_uses_upload_progress_and_fresh_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit"
            unit.mkdir()
            (unit / "checkpoint.json").write_text(
                json.dumps({"acceptedCount": 870}), encoding="utf-8"
            )
            (unit / "staging_upload_progress.json").write_text(
                json.dumps({
                    "phase": "storage-upload",
                    "uploaded": 400,
                    "total": 870,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }),
                encoding="utf-8",
            )
            (root / "state.json").write_text(
                json.dumps({
                    "status": "continuation-needed",
                    "stage": "prepare",
                    "currentRoot": str(unit),
                    "currentBatchSize": 2000,
                }),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({
                    "projectRoot": str(root),
                    "lanes": [{
                        "id": "source",
                        "name": "Source",
                        "statePath": "state.json",
                        "target": 2000,
                    }],
                }),
                encoding="utf-8",
            )
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual(lane["stage"], "storage-upload")
            self.assertEqual((lane["accepted"], lane["target"]), (400, 870))
            self.assertEqual(lane["uploaded"], 400)
            self.assertEqual(lane["health"], "healthy")
            self.assertIn("870/2000 accepted", lane["detail"])

    def test_publisher_uses_exact_phase_counter_not_prepared_total(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit"
            unit.mkdir()
            (unit / "catalog.json").write_text(
                json.dumps({"books": [{"id": str(index)} for index in range(870)]}),
                encoding="utf-8",
            )
            (unit / "publication_progress.json").write_text(
                json.dumps({"phase": "storage-upload", "prepared": 870,
                            "duplicateRemoved": 17, "uploadTarget": 853,
                            "uploaded": 675, "published": 0, "liveVerified": 0}),
                encoding="utf-8",
            )
            (root / "publisher.json").write_text(
                json.dumps({"listenerActive": True, "currentUnit": str(unit),
                            "currentAction": "publish-and-five-gate-verify",
                            "checkedAt": datetime.now(timezone.utc).isoformat(),
                            "queue": {"pendingUnits": 1}}),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({"projectRoot": str(root), "lanes": [{"id": "publisher",
                    "kind": "publisher", "statePath": "publisher.json"}]}),
                encoding="utf-8",
            )
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual((lane["accepted"], lane["target"]), (675, 853))
            self.assertEqual(lane["published"], 0)
            self.assertEqual(lane["liveVerified"], 0)
            self.assertIn("870 prepared", lane["detail"])
            self.assertIn("17 duplicates removed", lane["detail"])

    def test_publisher_distinguishes_ready_from_parked_queue_units(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = root / "completed"
            completed.mkdir()
            (completed / "promotion_validation.json").write_text(
                json.dumps({"publishedLiveTotal": 99}), encoding="utf-8"
            )
            (root / "publisher.json").write_text(
                json.dumps({
                    "listenerActive": True,
                    "checkedAt": datetime.now(timezone.utc).isoformat(),
                    "automaticAdvanceLog": [{
                        "root": str(completed),
                        "published": 853,
                        "liveVerified": 853,
                        "completedAt": datetime.now(timezone.utc).isoformat(),
                    }],
                    "queue": {
                        "pendingUnits": 5,
                        "parkedUnchanged": 2,
                        "bookkeptPreflight": 3,
                    },
                }),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({"projectRoot": str(root), "lanes": [{
                    "id": "publisher",
                    "kind": "publisher",
                    "statePath": "publisher.json",
                }]}),
                encoding="utf-8",
            )
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual(lane["stage"], "Listening for next exact staged unit")
            self.assertEqual(lane["queueReady"], 0)
            self.assertEqual((lane["accepted"], lane["target"]), (0, 0))
            self.assertEqual(lane["uploaded"], 0)
            self.assertIn("Last completed: 853 published", lane["detail"])
            self.assertIn("0 ready · 2 parked · 3 preflight", lane["detail"])

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
