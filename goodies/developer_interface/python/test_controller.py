import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from controller import SweeperController


class JsonReadCacheTest(unittest.TestCase):
    def test_json_cache_reuses_unchanged_file_and_invalidates_atomic_replace(self):
        from controller import _read_json
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text(json.dumps({"accepted": 1}))
            first = _read_json(path)
            self.assertIs(first, _read_json(path))
            replacement = path.with_suffix(".tmp")
            replacement.write_text(json.dumps({"accepted": 2}))
            replacement.replace(path)
            self.assertEqual(2, _read_json(path)["accepted"])

    def test_public_optimization_standard_has_exactly_200_points(self):
        from controller import (OPTIMIZATION_CONTROLS, OPTIMIZATION_POINT_COUNT,
                                OPTIMIZATION_STAGES)
        self.assertEqual(10, len(OPTIMIZATION_STAGES))
        self.assertEqual(20, len(OPTIMIZATION_CONTROLS))
        self.assertEqual(200, OPTIMIZATION_POINT_COUNT)

    def test_workspace_identity_is_derived_from_controller_lanes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            regular = root / "regular.json"
            regular.write_text(json.dumps({"projectRoot": str(root), "lanes": []}))
            self.assertEqual("web_sweeper", SweeperController(regular).status()["workspace"])


class ControllerTests(unittest.TestCase):
    def test_retired_open_library_receipts_remain_in_archived_source_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt_root = root / "work/judah_library/imports/open_library_batch_0001"
            receipt_root.mkdir(parents=True)
            (receipt_root / "staging_verification.json").write_text(json.dumps({
                "verified": 1643, "productionMutated": False,
            }))
            (receipt_root / "promotion_validation.json").write_text(json.dumps({
                "status": "published-and-five-gate-verified",
                "published": 1643, "liveVerified": 1643,
                "completedAt": "2026-08-13T18:11:42Z",
            }))
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root), "lanes": [],
            }))
            archived = SweeperController(config_path).status()["archivedSources"]
            self.assertEqual(1, len(archived))
            self.assertEqual("Open Library", archived[0]["name"])
            self.assertEqual(1643, archived[0]["liveVerified"])
            self.assertEqual(1, archived[0]["receiptCount"])

    def test_acquisition_red_flag_starts_only_after_five_minutes_without_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json", "target": 1000}],
            }), encoding="utf-8")
            four_minutes_ago = datetime.now(timezone.utc).timestamp() - 240
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "initialize",
                "updatedAt": datetime.fromtimestamp(
                    four_minutes_ago, timezone.utc
                ).isoformat(),
            }), encoding="utf-8")
            self.assertEqual(
                "watch", SweeperController(config_path).status()["lanes"][0]["health"]
            )
            six_minutes_ago = datetime.now(timezone.utc).timestamp() - 360
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "initialize",
                "updatedAt": datetime.fromtimestamp(
                    six_minutes_ago, timezone.utc
                ).isoformat(),
            }), encoding="utf-8")
            self.assertEqual(
                "stuck", SweeperController(config_path).status()["lanes"][0]["health"]
            )

    def test_push_freezes_exact_survivors_and_queues_immediate_publisher_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "work/judah_library/imports/library_of_congress_batch_0027"
            unit.mkdir(parents=True)
            (unit / "catalog.json").write_text(json.dumps({
                "books": [{"id": str(index)} for index in range(65)],
            }), encoding="utf-8")
            (root / "loc.json").write_text(json.dumps({
                "currentRoot": str(unit), "acceptedInCurrentBatch": 65,
            }), encoding="utf-8")
            (root / "publisher.json").write_text(json.dumps({
                "listenerActive": True,
                "checkedAt": datetime.now(timezone.utc).isoformat(),
                "queue": {"pendingUnits": 0},
            }), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "pushHandoffsPath": "handoffs.json",
                "lanes": [
                    {"id": "library-of-congress", "statePath": "loc.json", "target": 2000},
                    {"id": "publisher", "kind": "publisher", "statePath": "publisher.json"},
                ],
            }), encoding="utf-8")
            controller = SweeperController(config_path)
            result = controller.action("push", "library-of-congress")
            self.assertEqual(65, result["books"])
            self.assertTrue((unit / "operator_switch_request.json").exists())
            lanes = controller.status()["lanes"]
            source = lanes[0]
            publisher = lanes[1]
            self.assertEqual((65, 65), (source["accepted"], source["target"]))
            self.assertEqual("staging", source["modeDetail"]["custodyStage"])
            self.assertEqual(65, source["acceptedCumulative"])
            self.assertEqual((65, 65), (publisher["accepted"], publisher["target"]))
            self.assertEqual(65, publisher["batchQueue"][0]["books"])
            self.assertEqual(
                "Approved handoff · preparing for staging",
                publisher["batchQueue"][0]["status"],
            )
            (unit / "staging_upload_progress.json").write_text(json.dumps({
                "phase": "storage-upload", "uploaded": 25, "total": 65,
            }), encoding="utf-8")
            publisher = controller.status()["lanes"][1]
            self.assertEqual("staging-upload", publisher["stage"])
            self.assertEqual((25, 65), (publisher["accepted"], publisher["target"]))
            self.assertEqual("Staging upload", publisher["modeDetail"]["gateProgressLabel"])

    def test_completed_handoffs_are_history_only_and_next_push_is_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            imports = root / "work/judah_library/imports"
            completed = imports / "internet_archive_unit_009"
            completed.mkdir(parents=True)
            alberta = imports / "alberta_unit_001"
            alberta.mkdir()
            (alberta / "catalog.json").write_text(json.dumps({
                "books": [{"id": str(index)} for index in range(68)],
            }), encoding="utf-8")
            (root / "alberta.json").write_text(json.dumps({
                "currentRoot": str(alberta), "acceptedInCurrentBatch": 68,
            }), encoding="utf-8")
            completed_at = datetime.now(timezone.utc).isoformat()
            (root / "publisher.json").write_text(json.dumps({
                "listenerActive": True,
                "checkedAt": completed_at,
                "automaticAdvanceLog": [{
                    "root": str(completed), "published": 690,
                    "liveVerified": 690, "completedAt": completed_at,
                }],
                "queue": {"pendingUnits": 0},
            }), encoding="utf-8")
            (root / "handoffs.json").write_text(json.dumps({"handoffs": [{
                "lane": "internet-archive", "root": str(completed), "books": 690,
            }]}), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root), "pushHandoffsPath": "handoffs.json",
                "lanes": [
                    {"id": "university-of-alberta", "statePath": "alberta.json",
                     "target": 2000},
                    {"id": "publisher", "kind": "publisher",
                     "statePath": "publisher.json"},
                ],
            }), encoding="utf-8")
            controller = SweeperController(config_path)

            publisher = controller.status()["lanes"][1]
            self.assertEqual((0, 0), (publisher["accepted"], publisher["target"]))
            self.assertEqual([], publisher["batchQueue"])
            self.assertEqual(690, publisher["successHistory"][0]["liveVerified"])

            controller.action("push", "university-of-alberta")
            publisher = controller.status()["lanes"][1]
            self.assertEqual((68, 68), (publisher["accepted"], publisher["target"]))
            self.assertEqual(1, len(publisher["batchQueue"]))
            self.assertEqual(68, publisher["batchQueue"][0]["books"])
            self.assertEqual(str(alberta.resolve()), publisher["batchQueue"][0]["root"])

    def test_completed_sub_one_percent_window_is_exhausted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state.json").write_text(json.dumps({
                "status": "complete", "stage": "complete",
            }), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{
                    "id": "princeton", "statePath": "state.json",
                    "screeningCompleted": True,
                    "screeningAccepted": 18, "screeningTotal": 2209,
                }],
            }), encoding="utf-8")
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertTrue(lane["exhaustedSource"])
            self.assertAlmostEqual(0.8148483476686283, lane["acceptanceRate"])

    def test_navigation_pool_is_bounded_and_source_specific(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "loc", "statePath": "state.json",
                           "navigationPath": "navigation.json"}],
            }), encoding="utf-8")
            controller = SweeperController(config_path)
            result = controller.navigate("loc", [
                "Sermons, English", "Christian stories", "Christian stories",
            ])
            self.assertEqual(
                ["Sermons, English", "Christian stories"], result["queries"]
            )
            saved = json.loads((root / "navigation.json").read_text(encoding="utf-8"))
            self.assertEqual("pending-safe-discovery-window", saved["status"])
            with self.assertRaisesRegex(ValueError, "disabled"):
                controller.navigate("other", ["Christian books"])
            with self.assertRaisesRegex(ValueError, "plain-text"):
                controller.navigate("loc", ["$(unsafe)"])

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
            self.assertEqual(status["lanes"][0]["health"], "watch")
            self.assertEqual(status["lanes"][0]["mode"], "acquisition")
            self.assertIn("progressSince", status["lanes"][0])
            self.assertEqual(status["productionWriterLimit"], 1)

    def test_acquisition_health_requires_observed_accepted_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "state.json"
            state_path.write_text(json.dumps({
                "status": "running", "stage": "prepare", "accepted": 4, "target": 2000,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json"}],
            }), encoding="utf-8")
            controller = SweeperController(config_path)
            self.assertEqual("watch", controller.status()["lanes"][0]["health"])
            state = json.loads(state_path.read_text())
            state["accepted"] = 5
            state_path.write_text(json.dumps(state), encoding="utf-8")
            lane = controller.status()["lanes"][0]
            self.assertEqual("healthy", lane["health"])
            self.assertIsNotNone(lane["acceptedGrowthSince"])

    def test_acquisition_health_uses_cumulative_acceptance_across_rollover(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            imports = root / "work/judah_library/imports"
            imports.mkdir(parents=True)
            first = imports / "lane_batch_0001"
            first.mkdir()
            (first / "catalog.json").write_text(json.dumps({"books": [{"id": "one"}]}))
            (first / "staging_upload_receipt.json").write_text(json.dumps({
                "staged": 1, "productionMutated": False,
            }))
            second = imports / "lane_batch_0002"
            second.mkdir()
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "prepare", "currentRoot": str(second),
                "currentBatchSize": 2000,
            }))
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json",
                           "historyPrefix": "lane_batch_"}],
            }))
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual(0, lane["accepted"])
            self.assertEqual(1, lane["acceptedCumulative"])

    def test_recent_acceptance_journal_survives_controller_restart_as_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit_001"
            unit.mkdir()
            (unit / "progress.jsonl").write_text(
                json.dumps({"kind": "accepted", "id": "one"}) + "\n")
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "prepare", "currentRoot": str(unit),
            }))
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json"}],
            }))
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual("healthy", lane["health"])
            self.assertIsNotNone(lane["acceptedGrowthSince"])

    def test_in_progress_writer_cannot_regress_permanent_live_total(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            imports = root / "work/judah_library/imports/unit_001"
            imports.mkdir(parents=True)
            (imports / "promotion_validation.json").write_text(json.dumps({
                "status": "published-and-five-gate-verified",
                "publishedLiveTotal": 39673,
                "liveVerified": 81,
            }))
            metrics = root / "metrics.json"
            metrics.write_text(json.dumps({"codexLive": 39320}))
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root), "metricsPath": "metrics.json", "lanes": [],
            }))
            self.assertEqual(39673, SweeperController(config_path).status()["codexLive"])

    def test_uploading_source_lane_is_not_healthy_without_accepted_growth(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = root / "state.json"
            progress = root / "staging_progress.json"
            state.write_text(json.dumps({
                "status": "running", "stage": "staging-upload",
                "accepted": 4, "target": 2000,
            }))
            progress.write_text(json.dumps({
                "phase": "fresh-staging-delta", "total": 4,
            }))
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{
                    "id": "open-library", "statePath": "state.json",
                    "progressPath": "staging_progress.json",
                }]
            }))
            controller = SweeperController(config_path)
            lane = controller.status()["lanes"][0]
            self.assertEqual(lane["mode"], "uploading")
            self.assertEqual(lane["health"], "watch")
            self.assertIsNone(lane["acceptedGrowthSince"])

    def test_status_uses_newer_authoritative_accepted_journal_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit_001"
            unit.mkdir()
            (unit / "checkpoint.json").write_text(
                json.dumps({"acceptedCount": 1}), encoding="utf-8"
            )
            with (unit / "progress.jsonl").open("w", encoding="utf-8") as journal:
                journal.write(json.dumps({"kind": "accepted", "id": "one"}) + "\n")
                journal.write(json.dumps({"kind": "rejected", "id": "two"}) + "\n")
                journal.write(json.dumps({"kind": "accepted", "id": "three"}) + "\n")
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "prepare", "currentRoot": str(unit),
                "currentBatchSize": 2000,
            }), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json"}],
            }), encoding="utf-8")
            controller = SweeperController(config_path)
            lane = controller.status()["lanes"][0]
            self.assertEqual(2, lane["accepted"])
            self.assertEqual(2, lane["modeDetail"]["acceptedJournalCount"])
            with (unit / "progress.jsonl").open("a", encoding="utf-8") as journal:
                journal.write(json.dumps({"kind": "accepted", "id": "four"}) + "\n")
            self.assertEqual(3, controller.status()["lanes"][0]["accepted"])
            with (unit / "progress.jsonl").open("a", encoding="utf-8") as journal:
                journal.write(json.dumps({"kind": "rejected", "id": "three"}) + "\n")
            self.assertEqual(2, controller.status()["lanes"][0]["accepted"])

    def test_rejection_does_not_reset_last_accepted_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit_001"
            unit.mkdir()
            progress = unit / "progress.jsonl"
            progress.write_text(json.dumps({"kind": "accepted", "id": "one"}) + "\n")
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "prepare", "currentRoot": str(unit),
            }))
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json"}],
            }))
            controller = SweeperController(config_path)
            before = controller.status()["lanes"][0]["acceptedGrowthSince"]
            with progress.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps({"kind": "rejected", "id": "one"}) + "\n")
            lane = controller.status()["lanes"][0]
            self.assertEqual(0, lane["accepted"])
            self.assertEqual(before, lane["acceptedGrowthSince"])

    def test_archive_identity_rejection_revokes_generated_codex_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit_001"
            unit.mkdir()
            progress = unit / "progress.jsonl"
            progress.write_text(
                json.dumps({"kind": "accepted", "id": "generated-id",
                            "identifiers": {"archive": "source-id"}}) + "\n" +
                json.dumps({"kind": "rejected", "archiveId": "source-id"}) + "\n"
            )
            (root / "state.json").write_text(json.dumps({
                "status": "running", "stage": "prepare", "currentRoot": str(unit),
            }))
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json"}],
            }))
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual(0, lane["accepted"])
            self.assertEqual(0, lane["modeDetail"]["acceptedJournalCount"])

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
            self.assertEqual((lane["accepted"], lane["target"]), (870, 2000))
            self.assertEqual(lane["uploaded"], 400)
            self.assertEqual(lane["health"], "watch")
            self.assertIn("870/2000 accepted", lane["detail"])
            self.assertEqual(lane["mode"], "uploading")
            self.assertEqual(lane["modeDetail"]["uploaded"], 400)
            self.assertEqual(lane["modeDetail"]["uploadTarget"], 870)

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

    def test_new_batch_does_not_inherit_prior_membership_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "batch_0014"
            unit.mkdir()
            (root / "state.json").write_text(json.dumps({
                "status": "running",
                "stage": "fresh-live-export",
                "currentBatch": 14,
                "currentRoot": str(unit),
                "currentBatchSize": 2000,
                "membershipReconciliation": {"catalogMembers": 894},
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }), encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "source", "statePath": "state.json", "target": 2000}],
            }), encoding="utf-8")
            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual((lane["accepted"], lane["target"]), (0, 2000))

    def test_exact_upload_receipt_appears_in_source_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "work/judah_library/imports/open_library_christian_2000_staging_batch_0013"
            unit.mkdir(parents=True)
            (unit / "staging_upload_receipt.json").write_text(json.dumps({
                "staged": 894,
                "stagedAt": "2026-08-13T10:26:10Z",
                "productionMutated": False,
            }), encoding="utf-8")
            state = root / "state.json"
            state.write_text(json.dumps({"status": "running"}), encoding="utf-8")
            config = root / "config.json"
            config.write_text(json.dumps({
                "projectRoot": str(root),
                "lanes": [{"id": "open-library", "statePath": "state.json"}],
            }), encoding="utf-8")
            history = SweeperController(config).status()["lanes"][0]["successHistory"]
            self.assertEqual(history[0]["batchNumber"], 13)
            self.assertEqual(history[0]["staged"], 894)

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

    def test_publisher_does_not_regress_when_log_is_newer_than_progress_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit = root / "unit"
            unit.mkdir()
            (unit / "catalog.json").write_text(
                json.dumps({"books": [{"id": "one"}]}), encoding="utf-8"
            )
            (unit / "publication_progress.json").write_text(
                json.dumps({
                    "phase": "live-verification",
                    "prepared": 1,
                    "uploaded": 1,
                    "published": 1,
                    "liveVerified": 0,
                    "verificationTarget": 1,
                }),
                encoding="utf-8",
            )
            (unit / "promotion.log").write_text(
                "Uploaded 1/1\n"
                "Published 1 new or changed Codex records.\n"
                "Verified 1/1 live Codex books.\n",
                encoding="utf-8",
            )
            (root / "publisher.json").write_text(
                json.dumps({
                    "listenerActive": True,
                    "currentUnit": str(unit),
                    "currentAction": "publish-and-five-gate-verify",
                    "checkedAt": datetime.now(timezone.utc).isoformat(),
                    "queue": {"pendingUnits": 1},
                    "units": [{
                        "root": str(unit),
                        "status": "eligible",
                        "bridge": {"accepted": 1},
                    }],
                }),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps({
                    "projectRoot": str(root),
                    "lanes": [{
                        "id": "publisher",
                        "kind": "publisher",
                        "statePath": "publisher.json",
                    }],
                }),
                encoding="utf-8",
            )

            lane = SweeperController(config_path).status()["lanes"][0]
            self.assertEqual((1, 1), (lane["accepted"], lane["target"]))
            self.assertEqual(1, lane["published"])
            self.assertEqual(1, lane["liveVerified"])
            self.assertEqual("live-verification", lane["stage"])
            self.assertEqual(1, lane["modeDetail"]["gateProgressCurrent"])
            self.assertEqual(1, lane["batchQueue"][0]["books"])
            self.assertEqual("live-verification", lane["batchQueue"][0]["status"])
            self.assertTrue(lane["batchQueue"][0]["current"])

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
