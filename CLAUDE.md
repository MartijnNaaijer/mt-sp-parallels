# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This project extracts Exodus 20 from two Hebrew Bible corpora and generates a side-by-side HTML comparison:
- **BHSA 2021** (Biblia Hebraica Stuttgartensia Amstelodamensis) — Masoretic Text
- **SP 6.0.3** (Samaritan Pentateuch)

## Running

```bash
python extract.py
```

Expects corpus data at `../bhsa/tf/2021` and `../sp/tf/6.0.3` relative to the project root (`tf_claude/`). Outputs `exodus20.html`.

## Dependencies

- `text-fabric` (the `tf` package) — used to load and query both corpora via `tf.fabric.Fabric`

## Architecture

`extract.py` is a single-file pipeline:

1. **`load_bhsa` / `load_sp`** — load Text-Fabric corpora with their relevant features (`otype`, `book`, `chapter`, `verse`, `g_cons_utf8`, `trailer_utf8`/`trailer`, `lex_utf8`, `nu`)
2. **`get_verse_texts`** — walks the TF node hierarchy (chapter → verse → word) and builds per-verse HTML strings with `<span class="w" data-tip="...">` tooltips showing lexeme (`lex_utf8`) and number (`nu`)
3. **`clean_lex`** — normalizes lexeme strings: strips disambiguation markers, converts word-final regular forms to Hebrew final forms (ם ן ף ך ץ)
4. **`generate_html`** — produces a self-contained HTML page with inline CSS; pairs MT and SP rows for each verse; tooltips are CSS-only (no JS)

## Feature differences between corpora

| Feature | BHSA | SP |
|---|---|---|
| Surface text | `g_cons_utf8` | `g_cons_utf8` |
| Trailer (inter-word spacing/punctuation) | `trailer_utf8` | `trailer` |
