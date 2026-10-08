"""scan.py - Scan English question papers into a local SQLite database.

Run it with no arguments (from the repo root):

    python -m src.scan.scan

It picks up every question-paper file in the scan folder (default data/inbox/,
override with SCAN_FOLDER in .env), asks a Google AI Studio model (Gemma
served by the Gemini Developer API) to read each document and extract the
questions as JSON, then stores them in data/db/questions.db.

Categories are NOT sent to the model. The model only proposes short
category / sub-category labels; the scanner then matches those labels
against the existing catalog (data/structured/*.json) and stores the
canonical catalog names - so a large category file never affects the
prompt, tokens, or speed.

Files that were already scanned are skipped on later runs, so it is safe to
re-run whenever you drop new papers in.

Setup (once):
    1. pip install -r requirements.txt
    2. Copy .env.example to .env and put your API key in GEMINI_API_KEY.
       .env is gitignored - the key never leaves your machine.

Reading a document:
    - .txt / .md  -> read directly.
    - PDF with a text layer -> text layer is used.
    - PDF without a text layer (a phone scan) -> the page images are sent to
      the model and read by vision. No local OCR / Tesseract needed.
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # the key can also be exported in the shell instead
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
INBOX = Path(os.environ.get("SCAN_FOLDER", str(REPO_ROOT / "data" / "inbox")))
DB_PATH = Path(os.environ.get("QUESTIONS_DB", str(REPO_ROOT / "data" / "db" / "questions.db")))
MODEL = os.environ.get("GEMINI_MODEL", "gemma-4-26b-a4b-it")
CATALOG_DIR = REPO_ROOT / "data" / "structured"

TEXT_SUFFIXES = {".txt", ".md"}
PDF_SUFFIX = ".pdf"
MAX_TEXT_CHARS = 60000
TEXT_MIN_NONSPACE = 30        # below this the PDF text layer counts as empty
VISION_DPI = 200
VISION_MAX_PAGES = 3
MAX_RENDER_PIXELS = 30_000_000
UNCATEGORIZED = "uncategorized"

MODEL_PROMPT = """You read English question papers from the Loksewa (Public Service Commission) exams in Nepal.

Return ONLY valid JSON - an array of question objects, with no text before or after the JSON.
Each object uses exactly these keys:
  "category": a short category label for the question (e.g. General Knowledge, English, Computer Science, Nepal History)
  "sub_category": a short narrower label, or null (e.g. Computer Network, Geography of Nepal)
  "topic": a one-line topic, or null
  "question": the full question text
  "options": exactly 4 answer strings
  "correct_option": the index (1, 2, 3 or 4) of the correct option
  "difficulty": "easy", "medium" or "hard"

Only include multiple-choice questions that really have four options.
Skip written/long-answer questions and anything that is not a question."""


# ---------------------------------------------------------------------------
# Catalog loading (only for local label matching - never sent to the model)
# ---------------------------------------------------------------------------
def normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (label or "").lower())


def load_catalog(folder: Path) -> tuple[dict, dict]:
    """Return (category_map, sub_category_map) keyed by normalized name_en."""
    cats, subs = {}, {}
    if not folder.is_dir():
        return cats, subs
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for cat in data.get("categories", []):
            key = normalize_label(cat.get("name_en", ""))
            if key:
                cats[key] = cat
            for sub in cat.get("sub_categories", []):
                sub_key = normalize_label(sub.get("name_en", ""))
                if sub_key:
                    subs[sub_key] = sub
    return cats, subs


CATEGORIES, SUB_CATEGORIES = load_catalog(CATALOG_DIR)


def match_category(label: str) -> str:
    info = CATEGORIES.get(normalize_label(label))
    return (info or {}).get("name_en") or UNCATEGORIZED


def match_sub_category(label: str) -> str | None:
    info = SUB_CATEGORIES.get(normalize_label(label))
    return (info or {}).get("name_en") if info else None


# ---------------------------------------------------------------------------
# Read the document
# ---------------------------------------------------------------------------
def extract_text(path: Path) -> str:
    """Return the plain text of a .txt/.md file, or a PDF's text layer
    ('' when a PDF has no usable text layer)."""
    if path.suffix.lower() == PDF_SUFFIX:
        return pdf_text_or_none(path)
    return path.read_text(encoding="utf-8", errors="replace")


def pdf_text_or_none(path: Path) -> str:
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - import error path
            raise SystemExit(
                "pymupdf is not installed - run: pip install -r requirements.txt"
            ) from exc

    doc = fitz.open(path)
    try:
        text = "\n".join(page.get_text("text") for page in doc)
        if len(re.sub(r"\s", "", text)) >= TEXT_MIN_NONSPACE:
            return text
        return ""
    finally:
        doc.close()


def render_pdf_pages(path: Path) -> list:
    """Render the first pages of a scanned PDF as PNG bytes for the model."""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - import error path
            raise SystemExit(
                "pymupdf is not installed - run: pip install -r requirements.txt"
            ) from exc

    doc = fitz.open(path)
    try:
        pages = []
        for page in list(doc)[:VISION_MAX_PAGES]:
            w = max(page.rect.width, 1) * (VISION_DPI / 72)
            h = max(page.rect.height, 1) * (VISION_DPI / 72)
            scale = 1.0
            if w * h > MAX_RENDER_PIXELS:  # keep huge pages within limits
                scale = (MAX_RENDER_PIXELS / (w * h)) ** 0.5
            pix = page.get_pixmap(
                matrix=fitz.Matrix(VISION_DPI / 72 * scale, VISION_DPI / 72 * scale)
            )
            pages.append(pix.tobytes("png"))
        return pages
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Ask the model (Google AI Studio / Gemini Developer API)
# ---------------------------------------------------------------------------
def _client():
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit(
            "GEMINI_API_KEY not found - copy .env.example to .env, add your key, and re-run."
        )
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - import error path
        raise SystemExit(
            "google-genai is not installed - run: pip install -r requirements.txt"
        ) from exc
    return genai.Client()  # reads GEMINI_API_KEY from the environment


def ask_model_text(text: str) -> list:
    client = _client()
    response = client.models.generate_content(
        model=MODEL,
        contents=[MODEL_PROMPT, "Document text:\n" + text[:MAX_TEXT_CHARS]],
    )
    return parse_model_json(response.text)


def ask_model_vision(pages: list) -> list:
    try:
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - import error path
        raise SystemExit(
            "google-genai is not installed - run: pip install -r requirements.txt"
        ) from exc
    client = _client()
    parts = [types.Part.from_bytes(data=png, mime_type="image/png") for png in pages]
    response = client.models.generate_content(
        model=MODEL,
        contents=[*parts, MODEL_PROMPT],
    )
    return parse_model_json(response.text)


def parse_model_json(raw: str) -> list:
    """Turn the model reply into a list of question dicts."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            raise ValueError("model reply contained no JSON array")
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise ValueError("model reply is not a JSON array")
    return data


# ---------------------------------------------------------------------------
# Validate + store
# ---------------------------------------------------------------------------
def clean_row(raw: dict) -> tuple:
    """Turn one model object into a row tuple, or raise ValueError.

    Category / sub-category labels are matched against the catalog and the
    canonical catalog names are stored (unknown labels become 'uncategorized').
    """
    question = str(raw.get("question") or "").strip()
    if not question:
        raise ValueError("empty question")

    category = match_category(str(raw.get("category") or ""))
    sub_category = match_sub_category(str(raw.get("sub_category") or ""))

    topic = raw.get("topic")
    topic = str(topic).strip() if topic else None
    if not topic:
        topic = None

    options = raw.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("question does not have exactly 4 options")
    options = [str(o) for o in options]

    try:
        correct = int(raw.get("correct_option") or 0)
    except (TypeError, ValueError):
        correct = 0
    if correct not in (1, 2, 3, 4):
        raise ValueError("correct_option must be 1-4")

    difficulty = str(raw.get("difficulty") or "medium")
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    return (
        category,
        sub_category,
        topic,
        question,
        json.dumps(options, ensure_ascii=False),
        correct,
        difficulty,
    )


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            sub_category TEXT,
            topic TEXT,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            correct_option INTEGER NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'medium',
            language TEXT NOT NULL DEFAULT 'en',
            source_file TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS scanned_files (
            path TEXT PRIMARY KEY,
            questions INTEGER NOT NULL DEFAULT 0,
            source TEXT,
            scanned_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_questions_category ON questions(category)")
    return con


def is_scanned(con: sqlite3.Connection, file_path: str) -> bool:
    return con.execute(
        "SELECT 1 FROM scanned_files WHERE path = ?", (file_path,)
    ).fetchone() is not None


def insert_rows(con: sqlite3.Connection, rows: list, file_path: str, source: str) -> int:
    """Insert question rows; return how many were stored."""
    stored = 0
    for row in rows:
        con.execute(
            """
            INSERT INTO questions
                (category, sub_category, topic, question, options, correct_option,
                 difficulty, language, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'en', ?)
            """,
            row + (file_path,),
        )
        stored += 1
    con.execute(
        "INSERT OR REPLACE INTO scanned_files (path, questions, source) VALUES (?, ?, ?)",
        (file_path, stored, source),
    )
    con.commit()
    return stored


def scan_one(con: sqlite3.Connection, path: Path) -> int:
    """Scan a single file; return the number of questions stored."""
    file_key = str(path.resolve())
    if is_scanned(con, file_key):
        print(f"  skip  {path.name} (already scanned)")
        return 0

    print(f"  scan  {path.name} ...")

    source = ""
    questions = None
    if path.suffix.lower() == PDF_SUFFIX:
        text = pdf_text_or_none(path)
        if text:
            source, questions = "text", ask_model_text(text)
        else:
            pages = render_pdf_pages(path)
            if pages:
                source, questions = "vision", ask_model_vision(pages)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.sub(r"\s", "", text):
            source, questions = "text", ask_model_text(text)

    if questions is None:
        print(f"  note  {path.name}: nothing to read (no text or images)")
        return 0

    rows, skipped = [], 0
    for q in questions:
        try:
            rows.append(clean_row(q))
        except ValueError as err:
            skipped += 1
            print(f"  warn  {path.name}: skipped a question ({err})")

    stored = insert_rows(con, rows, file_key, source) if rows else 0
    print(f"  done  {path.name}: {stored} question(s) stored (source: {source})"
          + (f", {skipped} skipped" if skipped else ""))
    return stored


def count_questions(db_path: Path) -> int:
    if not db_path.is_file():
        return 0
    con = sqlite3.connect(db_path)
    try:
        return con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    finally:
        con.close()


def main() -> int:
    if not INBOX.is_dir():
        print(f"Scan folder not found: {INBOX}")
        print(f"Create it ({INBOX}) and drop English question-paper files inside.")
        return 1
    files = sorted(
        p for p in INBOX.iterdir()
        if p.is_file()
        and (p.suffix.lower() in TEXT_SUFFIXES or p.suffix.lower() == PDF_SUFFIX)
    )
    if not files:
        print(f"No papers in {INBOX} yet - add a PDF, .txt or .md and re-run.")
        return 0

    print(f"Scan folder : {INBOX}")
    print(f"DB          : {DB_PATH}")
    print(f"Model       : {MODEL}")
    print(f"Catalog cats: {len(CATEGORIES)}, sub-cats: {len(SUB_CATEGORIES)}")
    print(f"Papers      : {len(files)}")
    print("----------------------------------------------")

    con = init_db(DB_PATH)
    total = 0
    try:
        for path in files:
            try:
                total += scan_one(con, path)
            except SystemExit:
                raise
            except Exception as err:  # keep going to the next file
                print(f"  fail  {path.name}: {err}")
    finally:
        con.close()

    print("----------------------------------------------")
    print(f"Total questions in the database: {count_questions(DB_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())