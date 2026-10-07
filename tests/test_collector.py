"""Tests for the catalog-pulse collector script."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.collector.collect import entity_counts, summarize


def sample_file(root: Path, name: str, data: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class CollectorTests(unittest.TestCase):
    def test_counts_categories_subjects_and_nested_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample_file(root, "catalog.json", {
                "categories": [
                    {"name_en": "General Knowledge", "sub_categories": [{"name_en": "Nepal Geography"}]},
                ],
                "subjects": [
                    {
                        "name_en": "General Knowledge",
                        "chapters": [{"name_en": "Nepal", "topics": [{"name_en": "Geography"}]}],
                    }
                ],
                "questions": [],
                "question_sets": [],
            })
            counts = entity_counts(load_one(root))
            self.assertEqual(counts["categories"], 1)
            self.assertEqual(counts["sub_categories"], 1)
            self.assertEqual(counts["subjects"], 1)
            self.assertEqual(counts["chapters"], 1)
            self.assertEqual(counts["topics"], 1)

    def test_questions_split_by_difficulty_and_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample_file(root, "catalog.json", {
                "questions": [
                    {"difficulty": "easy", "language": "both"},
                    {"difficulty": "hard", "language": "np"},
                ]
            })
            counts = entity_counts(load_one(root))
            self.assertEqual(counts["questions"], 2)
            self.assertEqual(counts["q:easy"], 1)
            self.assertEqual(counts["q:hard"], 1)
            self.assertEqual(counts["qLang:both"], 1)
            self.assertEqual(counts["qLang:np"], 1)

    def test_summarize_aggregates_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample_file(root, "a.json", {"questions": [{"difficulty": "easy", "language": "both"}]})
            sample_file(root, "b.json", {"question_sets": [{"written_questions": [{}]}]})
            text = summarize(root, mode="live")
            self.assertIn("questions (MCQ)   : 1", text)
            self.assertIn("question sets     : 1", text)
            self.assertIn("written questions : 1", text)

    def test_invalid_json_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.json").write_text("not json", encoding="utf-8")
            text = summarize(root, mode="live")
            self.assertIn("Files with problems", text)
            self.assertIn("bad.json", text)

    def test_empty_folder_returns_helpful_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = summarize(Path(tmp), mode="live")
            self.assertIn("No structured data yet", text)


def load_all(root: Path):
    from src.collector.collect import load_json_files
    return [(p, d) for p, d in load_json_files(root)]


def load_one(root: Path):
    return next(iter(load_all(root)))[1]


if __name__ == "__main__":
    unittest.main()