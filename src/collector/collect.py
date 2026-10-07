"""collect.py - pulse of the Loksewa question-paper catalog.

Reads the structured JSON files under data/structured/ and prints a quick
summary of what has been contributed so far: categories, sub-categories,
subjects, chapters, topics, multiple-choice questions, written questions,
and question sets - plus a breakdown of questions by difficulty and language.

Usage (run from the repository root):

    python src/collector/collect.py                       # live data pulse
    python src/collector/collect.py --folder examples     # the EXAMPLE records

Python built-ins only - nothing to install.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STRUCTURED_DIR = REPO_ROOT / "data" / "structured"

# Top-level keys we know how to count in a structured catalog file.
ENTITY_KEYS = (
    "categories",
    "subjects",
    "questions",
    "question_sets",
)


def as_list(value):
    """Return value as a list (or [] when it is missing or not a list)."""
    return value if isinstance(value, list) else []


def load_json_files(folder: Path):
    """Yield (path, data_or_error) for every .json file in folder."""
    if not folder.is_dir():
        return
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            yield path, {"_error": str(exc)}
            continue
        if isinstance(data, dict):
            yield path, data
        else:
            yield path, {"_error": "top-level JSON must be an object"}


def entity_counts(data: dict) -> Counter:
    """Return a tally of every entity type found in one catalog file."""
    counts = Counter()
    if "_error" in data:
        return counts

    categories = as_list(data.get("categories"))
    subjects = as_list(data.get("subjects"))
    questions = as_list(data.get("questions"))
    question_sets = as_list(data.get("question_sets"))

    counts["categories"] += len(categories)
    counts["sub_categories"] += sum(len(as_list(c.get("sub_categories"))) for c in categories)
    counts["subjects"] += len(subjects)
    counts["chapters"] += sum(len(as_list(s.get("chapters"))) for s in subjects)
    counts["topics"] += sum(
        len(as_list(ch.get("topics")))
        for s in subjects
        for ch in as_list(s.get("chapters"))
    )
    counts["questions"] += len(questions)
    counts["question_sets"] += len(question_sets)
    counts["written_questions"] += sum(
        len(as_list(qs.get("written_questions"))) for qs in question_sets
    )

    for q in questions:
        if isinstance(q, dict):
            counts[f"q:{str(q.get('difficulty', 'unknown')).lower()}"] += 1
            counts[f"qLang:{str(q.get('language', 'unknown')).lower()}"] += 1
    return counts


def summarize(folder: Path, mode: str = "live") -> str:
    lines = ["Loksewa question-paper catalog pulse", "=" * 46]
    lines.append(f"source  : {mode}  ({folder})")

    total = Counter()
    errors = []
    for path, data in load_json_files(folder):
        if "_error" in data:
            errors.append(f"{path.name}: {data['_error']}")
        else:
            total += entity_counts(data)

    if not total and not errors:
        lines.append("-" * 46)
        lines.append("No structured data yet.")
        lines.append("Add JSON files to data/structured/ - see the format in examples/example-catalog.json.")
        return "\n".join(lines)

    lines.append("-" * 46)
    lines.append(f"categories        : {total['categories']}")
    lines.append(f"sub_categories    : {total['sub_categories']}")
    lines.append(f"subjects          : {total['subjects']}")
    lines.append(f"chapters          : {total['chapters']}")
    lines.append(f"topics            : {total['topics']}")
    lines.append(f"questions (MCQ)   : {total['questions']}")
    lines.append(f"written questions : {total['written_questions']}")
    lines.append(f"question sets     : {total['question_sets']}")

    if total["questions"]:
        lines.append("-" * 46)
        lines.append("MCQs by:  difficulty  /  language")
        for key in sorted(total):
            if key.startswith("q:") or key.startswith("qLang:"):
                lines.append(f"  {key.replace('q:difficulty:', 'difficulty ').replace('qLang:', 'language   '):20s}: {total[key]}")

    if errors:
        lines.append("-" * 46)
        lines.append("Files with problems:")
        lines.extend(f"  - {e}" for e in errors)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Show how much Loksewa question-paper content has been contributed."
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=str(STRUCTURED_DIR),
        help="folder with structured JSON files (default: data/structured)",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="live",
        help="how the source is labelled in the output (default: live)",
    )
    args = parser.parse_args(argv)

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"error: folder not found: {folder}", file=sys.stderr)
        return 1

    print(summarize(folder, mode=args.label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())