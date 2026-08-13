import json
import tempfile
import unittest
from pathlib import Path

from sweeper.receipt import (
    RestartableStagingReceipt,
    canonical_acceptance_receipt,
    exact_live_overlap_completion,
    migrate_legacy_staging_verification,
)


class RestartableReceiptTests(unittest.TestCase):
    def test_exact_live_overlap_does_not_depend_on_reason_wording(self):
        verification = {
            "published": 0,
            "verified": 0,
            "preparedBookIds": ["exact", "edition"],
            "removedOverlapIds": ["edition", "exact"],
            "removedLiveOverlaps": [
                {"bookId": "exact", "reasons": ["already published"]},
                {"bookId": "edition", "reasons": ["title-author overlap"]},
            ],
            "startingLiveRevision": {"publishedBooks": 100, "identitySha256": "abc"},
            "finalLiveRevision": {"publishedBooks": 100, "identitySha256": "abc"},
        }
        self.assertTrue(exact_live_overlap_completion(verification, 2))
        verification["removedOverlapIds"] = ["exact", "different"]
        self.assertFalse(exact_live_overlap_completion(verification, 2))

    def test_exact_legacy_verification_migrates_without_reupload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "staging_verification.json").write_text(json.dumps({
                "verifiedAt": "2026-08-11T00:00:00Z",
                "prepared": 42,
                "staged": 42,
                "verified": 42,
                "productionMutated": False,
                "byteIdenticalToValidatedLocalArtifacts": True,
            }), encoding="utf-8")
            receipt = migrate_legacy_staging_verification(root, 42)
            self.assertEqual(42, receipt["staged"])
            self.assertEqual("legacy-exact-remote-readback", receipt["verification"])
            self.assertTrue((root / "dock-staging.json").exists())

    def test_inexact_legacy_verification_never_migrates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "staging_verification.json").write_text(json.dumps({
                "prepared": 42,
                "staged": 42,
                "verified": 41,
                "productionMutated": False,
                "byteIdenticalToValidatedLocalArtifacts": True,
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not an exact isolated set"):
                migrate_legacy_staging_verification(root, 42)
            self.assertFalse((root / "dock-staging.json").exists())

    def test_importer_prepared_survivor_count_is_an_exact_acceptance_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "import_report.json").write_text(json.dumps({
                "source": "Open Library", "prepared": 1442,
            }), encoding="utf-8")
            evidence = canonical_acceptance_receipt(root, "Open Library", 1442)
            self.assertEqual(1442, evidence["accepted"])
            self.assertEqual("import-report", evidence["receiptKind"])

    def test_conflicting_importer_count_aliases_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "import_report.json").write_text(json.dumps({
                "source": "Open Library", "accepted": 1442, "prepared": 1441,
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact accepted source unit"):
                canonical_acceptance_receipt(root, "Open Library", 1442)

    def test_validator_first_adapter_is_not_blocked_by_report_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = {
                "passed": True,
                "errors": [],
                "booksAudited": 1965,
                "stagingSource": "library-of-congress",
            }
            (root / "validation_report.json").write_text(
                json.dumps(report), encoding="utf-8")
            evidence = canonical_acceptance_receipt(
                root, "Library of Congress", 1965)
            self.assertEqual("validation_report.json", evidence["receipt"])
            self.assertEqual("validation-report", evidence["receiptKind"])
            self.assertEqual(1965, evidence["accepted"])

    def test_acceptance_receipt_count_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "validation_report.json").write_text(json.dumps({
                "passed": True, "errors": [], "booksAudited": 99,
                "stagingSource": "library-of-congress",
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact source unit"):
                canonical_acceptance_receipt(root, "Library of Congress", 100)

    def test_resumes_and_emits_receipt_only_after_exact_membership(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            membership = {"a": "1" * 64, "b": "2" * 64}
            first = RestartableStagingReceipt(root, "unit-1", membership)
            first.record("a", "1" * 64)
            self.assertFalse((root / "dock-staging.json").exists())

            resumed = RestartableStagingReceipt(root, "unit-1", membership)
            self.assertEqual(["b"], resumed.remaining())
            resumed.record("b", "2" * 64)
            receipt = resumed.finish()
            self.assertEqual(2, receipt["staged"])
            self.assertFalse(receipt["production_mutated"])
            self.assertFalse((root / "staging-verification-progress.json").exists())
            self.assertEqual(receipt, json.loads(
                (root / "dock-staging.json").read_text(encoding="utf-8")))

    def test_wrong_hash_and_partial_finish_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = RestartableStagingReceipt(root, "unit-1", {"a": "1" * 64})
            with self.assertRaisesRegex(ValueError, "hash differs"):
                receipt.record("a", "2" * 64)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                receipt.finish()


if __name__ == "__main__":
    unittest.main()
