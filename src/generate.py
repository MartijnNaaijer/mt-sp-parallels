"""
Generate side-by-side MT/SP HTML pages for every chapter in the Pentateuch.
Run from the tf_claude/ parent directory:
    python parallel_mt_sp/src/generate.py
Outputs one HTML file per chapter plus index.html into docs/.
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from corpus import load_bhsa, load_sp, get_chapters, get_verse_texts, clean_bhsa_trailer
from html_render import write_chapter_html, write_index_html, chapter_filename

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
)

PENTATEUCH = [
    ("Genesis",     "בראשית"),
    ("Exodus",      "שמות"),
    ("Leviticus",   "ויקרא"),
    ("Numbers",     "במדבר"),
    ("Deuteronomy", "דברים"),
]


def main():
    print("Loading BHSA...")
    bhsa_api = load_bhsa("bhsa/tf/2021")
    print("Loading SP...")
    sp_api = load_sp("sp/tf/6.0.3")

    toc = [
        (book_en, book_he, get_chapters(bhsa_api, book_en))
        for book_en, book_he in PENTATEUCH
    ]

    flat = [(book_en, book_he, c) for book_en, book_he, chapters in toc for c in chapters]
    print(f"\n{len(flat)} chapters total. Generating...\n")

    for idx, (book_en, book_he, chap_num) in enumerate(flat):
        print(f"  {book_en} {chap_num}...", end=" ", flush=True)

        bhsa_verses = get_verse_texts(
            bhsa_api, book_en, chap_num, "word", "g_cons_utf8", "trailer_utf8",
            extra_feats=("ps", "gn", "vt", "vs"), trailer_clean_fn=clean_bhsa_trailer)
        sp_verses = get_verse_texts(
            sp_api, book_en, chap_num, "word", "g_cons_utf8", "trailer",
            extra_feats=("ps", "gn", "vt"))

        write_chapter_html(
            bhsa_verses, sp_verses,
            os.path.join(OUT_DIR, chapter_filename(book_en, chap_num)),
            book_en, book_he, chap_num,
            prev_info=flat[idx - 1] if idx > 0 else None,
            next_info=flat[idx + 1] if idx < len(flat) - 1 else None,
        )
        print("done")

    write_index_html(toc, OUT_DIR)
    print("\nAll done.")


if __name__ == "__main__":
    main()
