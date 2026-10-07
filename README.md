# Loksewa Question Paper Collector & Gemma RAG Assistant

Collect real **Loksewa (Public Service Commission) exam content** — categories, subjects, topics, and past-paper questions — as an open dataset. Later, this feeds a **Gemma-powered AI assistant**.

**Status: just started.** The starter collector works; the dataset is what contributors build.

## What we collect

- **Categories** (e.g. General Knowledge → Nepal Geography)
- **Subjects → chapters → topics** (e.g. General Knowledge → Nepal → Geography)
- **MCQs** — question, 4 options, correct answer, difficulty (English and/or Nepali)
- **Past-paper sets** — objective + written (marks/answers)

The exact JSON format: [`examples/example-catalog.json`](examples/example-catalog.json). Copy it, replace the content, that's your contribution.

## See it working

```bash
python src/collector/collect.py --folder examples --label example
```

_Prints how many categories, subjects, topics, and questions exist._ Python 3 only, nothing to install.

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
examples/          example catalog (clearly marked EXAMPLE)
src/collector/     the starter collector script
tests/             tests for the collector
```

## License

Code: [MIT](LICENSE). Contributed data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).