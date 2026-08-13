import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from controller import SweeperController


class ControllerTests(unittest.TestCase):
    def test_discovery_checkpoint_growth_resets_progress_clock_without_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "state.json"
            state = {
                "status": "running",
                "stage": "discovery",
                "currentBatchSize": 2000,
                "acceptedInCurrentBatch": 44,
                "candidateOffset": 500,
                "discoveryFrontier": 2,
                "updatedAt": "2026-01-01T00:00:00Z",
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "name": "Source",
                           "statePath": "state.json", "target": 2000}],
            }), encoding="utf-8")
            controller = SweeperController(config_path)
            first = controller.status()["lanes"][0]["progressSince"]
            state["candidateOffset"] = 1000
            state["updatedAt"] = "2026-01-01T00:01:00Z"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            second_lane = controller.status()["lanes"][0]
            self.assertEqual(44, second_lane["accepted"])
            self.assertNotEqual(first, second_lane["progressSince"])

    def test_supplemental_discovery_file_resets_progress_clock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "discovery",
                "acceptedInCurrentBatch": 6, "currentBatchSize": 2000,
                "discoveryPagesBaseline": 100,
                "discoveryPagesTarget": 200,
            }), encoding="utf-8")
            progress = root / "discovery.partial.json"
            progress.write_text(json.dumps({
                "completed": ["page-149", "page-150"],
                "records": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            }), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json",
                           "progressPaths": ["discovery.partial.json"]}],
            }), encoding="utf-8")
            controller = SweeperController(config_path)
            first_lane = controller.status()["lanes"][0]
            first = first_lane["progressSince"]
            self.assertEqual("discovery", first_lane["stage"])
            self.assertIn("moving smoothly", first_lane["detail"])
            self.assertEqual("discovery", first_lane["mode"])
            self.assertEqual(2, first_lane["modeDetail"]["pagesCompleted"])
            self.assertEqual(3, first_lane["modeDetail"]["candidateRecords"])
            self.assertEqual(2, first_lane["modeDetail"]["newlyCompletedPages"])
            self.assertEqual("Discovery pages", first_lane["modeDetail"]["gateProgressLabel"])
            self.assertEqual(0, first_lane["modeDetail"]["gateProgressCurrent"])
            self.assertEqual(200, first_lane["modeDetail"]["gateProgressTarget"])
            progress.write_text(json.dumps({
                "completed": ["page-149", "page-150", "page-151"],
                "records": [{"id": str(index)} for index in range(5)],
            }), encoding="utf-8")
            second = controller.status()["lanes"][0]["progressSince"]
            self.assertNotEqual(first, second)

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
            self.assertEqual(status["lanes"][0]["mode"], "acquisition")
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
            self.assertEqual(lane["mode"], "uploading")
            self.assertEqual(lane["modeDetail"]["uploaded"], 400)

    def test_completed_staging_unit_exposes_persistent_staged_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit"
            unit.mkdir()
            (unit / "checkpoint.json").write_text(
                json.dumps({"acceptedCount": 44}), encoding="utf-8"
            )
            (unit / "staging_upload_progress.json").write_text(
                json.dumps({"phase": "complete", "uploaded": 44, "total": 44,
                            "updatedAt": datetime.now(timezone.utc).isoformat()}),
                encoding="utf-8",
            )
            (root / "state.json").write_text(
                json.dumps({"status": "running", "stage": "staged",
                            "currentRoot": str(unit), "currentBatchSize": 2000}),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json"}],
            }), encoding="utf-8")
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual("staged", lane["modeDetail"]["completionState"])

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
            self.assertEqual(0, lane["queueReady"])
            self.assertIn("1 queued behind current", lane["detail"])
            self.assertEqual(lane["mode"], "uploading")
            self.assertEqual(lane["modeDetail"]["prepared"], 870)
            self.assertEqual("Storage upload", lane["modeDetail"]["gateProgressLabel"])
            self.assertEqual(675, lane["modeDetail"]["gateProgressCurrent"])
            self.assertEqual(853, lane["modeDetail"]["gateProgressTarget"])

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
            self.assertEqual("published", lane["modeDetail"]["completionState"])

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
