"""Tests for the scanner (JSON parsing + row validation - no API calls)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scan.scan import clean_row, parse_model_json


class ParseModelJsonTests(unittest.TestCase):
    def test_plain_array(self):
        data = parse_model_json('[{"question": "A?"}]')
        self.assertEqual(data, [{"question": "A?"}])

    def test_markdown_fences_are_stripped(self):
        data = parse_model_json('```json\n[{"question": "A?"}]\n```')
        self.assertEqual(data, [{"question": "A?"}])

    def test_trailing_text_after_json_is_tolerated(self):
        data = parse_model_json('[{"question": "A?"}]\nHere are my results')
        self.assertEqual(data, [{"question": "A?"}])

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            parse_model_json("I could not find any questions.")

    def test_non_array_json_raises(self):
        with self.assertRaises(ValueError):
            parse_model_json('{"question": "A?"}')


class CleanRowTests(unittest.TestCase):
    def test_valid_row_matches_catalog(self):
        row = clean_row({
            "category": "General Knowledge",
            "sub_category": "Geography of Nepal",
            "topic": "Himalayas",
            "question": "Which is the highest mountain in the world?",
            "options": ["A", "B", "C", "D"],
            "correct_option": 2,
            "difficulty": "easy",
        })
        self.assertEqual(row[0], "General Knowledge")
        self.assertEqual(row[1], "Geography of Nepal")
        self.assertEqual(row[2], "Himalayas")
        self.assertEqual(row[3], "Which is the highest mountain in the world?")
        self.assertEqual(row[5], 2)
        self.assertEqual(row[6], "easy")

    def test_matching_is_case_and_space_insensitive(self):
        row = clean_row({
            "category": "general   knowledge",
            "sub_category": "GEOGRAPHY OF NEPAL",
            "question": "Q?",
            "options": ["1", "2", "3", "4"],
            "correct_option": 1,
        })
        self.assertEqual(row[0], "General Knowledge")
        self.assertEqual(row[1], "Geography of Nepal")

    def test_unknown_labels_become_uncategorized(self):
        row = clean_row({
            "question": "Q?",
            "options": ["1", "2", "3", "4"],
            "correct_option": 1,
        })
        self.assertEqual(row[0], "uncategorized")
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])

    def test_bad_options_count_raises(self):
        with self.assertRaises(ValueError):
            clean_row({"question": "Q?", "options": ["1", "2"], "correct_option": 1})

    def test_bad_correct_option_raises(self):
        with self.assertRaises(ValueError):
            clean_row({
                "question": "Q?",
                "options": ["1", "2", "3", "4"],
                "correct_option": 7,
            })

    def test_unknown_difficulty_falls_back_to_medium(self):
        row = clean_row({
            "question": "Q?",
            "options": ["1", "2", "3", "4"],
            "correct_option": 2,
            "difficulty": "impossible",
        })
        self.assertEqual(row[6], "medium")


if __name__ == "__main__":
    unittest.main()