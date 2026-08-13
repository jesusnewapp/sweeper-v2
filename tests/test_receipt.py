import json
import tempfile
import unittest
from pathlib import Path

from sweeper.receipt import RestartableStagingReceipt


class RestartableReceiptTests(unittest.TestCase):
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
