import json
import sys
import tempfile
import unittest
from pathlib import Path

from sweeper.world_books import build_translated_manuscript, quick_english_check


class WorldBooksTest(unittest.TestCase):
    def test_translation_builds_manuscript_but_never_auto_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text(("foi esperance charite " * 400) + "fin", encoding="utf-8")
            translator = root / "translator.py"
            translator.write_text(
                "import json,sys\nr=json.load(sys.stdin)\n"
                "print(json.dumps({'translation': 'the faith and hope of the church is charity ' * 250 + 'end'}))\n",
                encoding="utf-8",
            )
            result = build_translated_manuscript(
                source_text=source,
                output_root=root / "output",
                source_id="gallica-ark-1",
                title="Livre de foi",
                authors=["Example Author"],
                source_language="fr",
                source_url="https://gallica.bnf.fr/ark:/12148/example",
                rights={"eligible": True, "status": "public-domain", "evidenceUrl": "https://example.test/rights"},
                translator_command=f"{sys.executable} {translator}",
            )
            manuscript = json.loads(Path(result["manuscript"]).read_text())
            review = json.loads(Path(result["review"]).read_text())
            self.assertEqual("en", manuscript["language"])
            self.assertEqual("fr", manuscript["originalLanguage"])
            self.assertGreaterEqual(manuscript["statistics"]["wordCount"], 1000)
            self.assertEqual("awaiting-approval", review["status"])
            self.assertFalse(review["publicationApproved"])
            self.assertFalse(review["deduplicationValidated"])

    def test_rights_evidence_is_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("texte " * 1200)
            with self.assertRaisesRegex(ValueError, "rights evidence"):
                build_translated_manuscript(
                    source_text=source, output_root=root / "out", source_id="x",
                    title="Title", authors=[], source_language="fr",
                    source_url="https://example.test/book", rights={"eligible": False},
                    translator_command="false",
                )

    def test_quick_english_check_rejects_untranslated_or_broken_text(self):
        self.assertTrue(quick_english_check("the faith and the church of Christ " * 250)["passed"])
        self.assertFalse(quick_english_check("la foi et le texte de l'église " * 250)["passed"])
        self.assertFalse(quick_english_check(("the faith " * 600) + ("�" * 100))["passed"])


if __name__ == "__main__":
    unittest.main()
