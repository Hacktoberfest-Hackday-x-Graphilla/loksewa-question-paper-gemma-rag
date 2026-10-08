# Loksewa Question Paper Collector & Gemma RAG Assistant

Collect real **Loksewa (Public Service Commission) exam content** — categories, subjects, topics, and past-paper questions — as an open dataset. Later, this feeds a **Gemma-powered AI assistant**.

**Status: just started.** The starter collector and the English-paper scanner work; the dataset is what contributors build.

## What we collect

- **Categories** (e.g. General Knowledge → Nepal Geography)
- **Subjects → chapters → topics** (e.g. General Knowledge → Nepal → Geography)
- **MCQs** — question, 4 options, correct answer, difficulty (English and/or Nepali)
- **Past-paper sets** — objective + written (marks/answers)

The exact JSON format: [`examples/example-catalog.json`](examples/example-catalog.json). Copy it, replace the content, that's your contribution.

## See it working

```bash
python src/collector/collect.py
```

_Prints how many categories, sub-categories, subjects, topics, and questions exist._ Python 3 only, nothing to install.

There are already two real categories — **General Knowledge** and **Computer Science** — in [`data/structured/categories.json`](data/structured/categories.json). Try adding another one.

To also see the clearly-marked example file:

```bash
python src/collector/collect.py --folder examples --label example
```

## Scan a paper into the database

The scanner reads English question-paper files, asks a Google AI Studio model (Gemma) to extract the MCQs, and stores them in `data/db/questions.db`.

Setup (once):

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and put your Google AI Studio API key in `GEMINI_API_KEY`. `.env` is gitignored, so the key never leaves your machine.
3. Drop English question papers in the scan folder (default `data/inbox/`) and run:

```bash
python -m src.scan.scan
```

`data/inbox/` already ships with one small sample file (`sample-english-questions.txt`) so the very first run works immediately — it is read as plain text, exactly like any `.txt` / `.md` paper. Delete it whenever you start adding your own papers.

Every run only scans new files (already-scanned ones are skipped), so re-running after adding papers is safe.

Papers are read two ways, depending on the file:

- Plain text (`.txt`, `.md`) and PDFs that have a text layer → the text is sent to the model.
- Image-only PDFs (a phone scan / photo of a paper — no text layer) → the page images are sent to the model and read by vision. No local OCR / Tesseract needed.

After extraction, the model's short category / sub-category labels are matched against the catalog in `data/structured/` and the canonical names are stored (unknown labels become `uncategorized`). Labels are matched locally, so a large catalog never slows a scan down.

## Contribute — 3 steps, no coding

1. Open the **Issues** tab.
2. Pick any issue labelled `beginner` or `good first issue`.
3. Comment **"I'll take this"** and follow the lines in the issue — a comment is enough.

Easiest right now: `#5` add 5 categories, `#6` submit 3 MCQs, `#7` list topics for one subject.

Stuck? Post in the **Discussions** tab — no question is dumb.

## Data rules (keep it honest)

- **Real only** — you can stand behind every fact you contribute.
- **Say how you know** — add a `source` note (own study, sat the exam, a paper you hold…).
- **No fabrication** — never invent, guess, or AI-fill content. Unknown translation? Write `null`.
- **No personal data** — no candidate names, roll numbers, addresses, or signatures.
- **Rights** — only share material you have the right to redistribute.

## Layout

```text
data/structured/   the catalog JSON files (contribute here)
data/inbox/        drop question-paper files here for the scanner (gitignored)
data/db/           SQLite database written by the scanner (gitignored)
examples/          example catalog (clearly marked EXAMPLE)
src/collector/     the starter collector script
src/scan/          the question-paper scanner (needs a Gemini API key)
tests/             tests for the collector and the scanner
.env.example       template for your local, gitignored .env
```

## License

Code: [MIT](LICENSE). Contributed data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).