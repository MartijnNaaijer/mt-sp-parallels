"""
Generate side-by-side MT/SP HTML pages for every chapter in the Pentateuch.
Run from the tf_claude/ parent directory:
    python parallel_texts_sp_mt_pentateuch/generate.py
Outputs one HTML file per chapter plus index.html into parallel_texts_sp_mt_pentateuch/.
"""

import sys, io, html, re, difflib, unicodedata, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

PENTATEUCH = [
    ("Genesis",     "בראשית"),
    ("Exodus",      "שמות"),
    ("Leviticus",   "ויקרא"),
    ("Numbers",     "במדבר"),
    ("Deuteronomy", "דברים"),
]


def clean_lex(lex):
    cleaned = re.sub(r'[^\u05c1\u05c2\u05d0-\u05ea\u05f0-\u05f4\ufb1d-\ufb4f ]', '', lex).strip()
    final_forms = {'מ': 'ם', 'נ': 'ן', 'פ': 'ף', 'כ': 'ך', 'צ': 'ץ'}
    words = cleaned.split(' ')
    result = []
    for w in words:
        if w and w[-1] in final_forms:
            w = w[:-1] + final_forms[w[-1]]
        result.append(w)
    return ' '.join(result)


def clean_bhsa_trailer(tr):
    tr = tr.replace('\u05be', ' ')
    tr = re.sub(r'[\u05c0\u05c3\u05e1\u05e4]', '', tr)
    return re.sub(r' +', ' ', tr)


from tf.fabric import Fabric


def load_bhsa(path):
    F = Fabric(locations=path, silent=True)
    api = F.load("otype book chapter verse g_cons_utf8 trailer_utf8 lex_utf8 nu vt ps gn vs", silent=True)
    return api


def load_sp(path):
    F = Fabric(locations=path, silent=True)
    api = F.load("otype book chapter verse g_cons_utf8 trailer lex_utf8 nu vt ps gn", silent=True)
    return api


def get_chapters(api, book_name):
    Tt = api.T; Lt = api.L; Ft = api.F
    book_node = Tt.nodeFromSection((book_name,))
    if book_node is None:
        return []
    return sorted(Ft.chapter.v(c) for c in Lt.d(book_node, otype='chapter'))


def get_verse_texts(api, book, chapter, word_otype, text_feat, trailer_feat,
                    extra_feats=(), trailer_clean_fn=None):
    Ft = api.F; Lt = api.L; Tt = api.T
    chap_node = Tt.nodeFromSection((book, chapter))
    if chap_node is None:
        return {}
    result = {}
    for vnode in Lt.d(chap_node, otype="verse"):
        vnum = Ft.verse.v(vnode)
        word_data = []
        for w in Lt.d(vnode, otype=word_otype):
            t  = getattr(Ft, text_feat).v(w) or ""
            tr = getattr(Ft, trailer_feat).v(w) or ""
            if trailer_clean_fn:
                tr = trailer_clean_fn(tr)
            lex = clean_lex(Ft.lex_utf8.v(w) or "")
            nu  = Ft.nu.v(w) or ""
            extras = {f: (getattr(Ft, f).v(w) or "") for f in extra_feats}
            word_data.append((t, tr, lex, nu, extras))
        result[vnum] = word_data
    return result


def diff_verses(mt_words, sp_words):
    HCONS = re.compile(r'[\u05d0-\u05ea\ufb1d-\ufb4f]')
    mt_index, sp_index = [], []
    for wi, (text, *_) in enumerate(mt_words):
        for ci, ch in enumerate(text):
            if HCONS.match(ch):
                mt_index.append((wi, ci))
    for wi, (text, *_) in enumerate(sp_words):
        for ci, ch in enumerate(text):
            if HCONS.match(ch):
                sp_index.append((wi, ci))

    def base_cons(ch):
        return unicodedata.normalize('NFKD', ch)[0]

    mt_str = ''.join(base_cons(mt_words[wi][0][ci]) for wi, ci in mt_index)
    sp_str = ''.join(base_cons(sp_words[wi][0][ci]) for wi, ci in sp_index)
    mt_marks = [[False]*len(t) for t, *_ in mt_words]
    sp_marks = [[False]*len(t) for t, *_ in sp_words]
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, mt_str, sp_str, autojunk=False).get_opcodes():
        if tag in ('delete', 'replace'):
            for k in range(i1, i2):
                wi, ci = mt_index[k]
                mt_marks[wi][ci] = True
        if tag in ('insert', 'replace'):
            for k in range(j1, j2):
                wi, ci = sp_index[k]
                sp_marks[wi][ci] = True
    return mt_marks, sp_marks


def render_verse(word_data, char_marks, extra_class):
    spans = []
    for (text, trailer, lex, nu, extras), marks in zip(word_data, char_marks):
        inner = ""
        i = 0
        while i < len(text):
            cluster = text[i]
            j = i + 1
            while j < len(text) and unicodedata.category(text[j]).startswith('M'):
                cluster += text[j]
                j += 1
            esc = html.escape(cluster)
            inner += f'<span class="{extra_class}">{esc}</span>' if marks[i] else esc
            i = j

        def fmt(v):
            return "-" if v == "NA" else v

        tip_lines = [f"lex: {fmt(lex)}", f"ps: {fmt(extras.get('ps', ''))}",
                     f"nu: {fmt(nu)}", f"gn: {fmt(extras.get('gn', ''))}",
                     f"vt: {fmt(extras.get('vt', ''))}"]
        if 'vs' in extras:
            tip_lines.append(f"vs: {fmt(extras['vs'])}")
        tooltip = html.escape("\n".join(tip_lines))
        spans.append(f'<span class="w" data-tip="{tooltip}">{inner}</span>{html.escape(trailer)}')
    return "".join(spans).strip()


def chapter_filename(book_en, chap_num):
    return f"{book_en.lower()}_{chap_num:02d}.html"


def generate_html(bhsa_verses, sp_verses, out_path,
                  book_en, book_he, chap_num, prev_info, next_info):
    """prev_info / next_info: (book_en, book_he, chap_num) or None."""

    all_verse_nums = sorted(set(bhsa_verses) | set(sp_verses))
    rows = []
    for vnum in all_verse_nums:
        mt_words = bhsa_verses.get(vnum)
        sp_words = sp_verses.get(vnum)
        if mt_words and sp_words:
            mt_marks, sp_marks = diff_verses(mt_words, sp_words)
            bhsa_text = render_verse(mt_words, mt_marks, "plus-mt")
            sp_text   = render_verse(sp_words, sp_marks, "plus-sp")
        else:
            bhsa_text = render_verse(mt_words, [[False]*len(t) for t,*_ in mt_words], "plus-mt") if mt_words else "—"
            sp_text   = render_verse(sp_words, [[False]*len(t) for t,*_ in sp_words], "plus-sp") if sp_words else "—"
        rows.append(f"""
        <tr class="verse-group">
            <td class="vnum" rowspan="2">{vnum}</td>
            <td class="heb bhsa-row" dir="rtl" lang="he"><span class="src-label">MT</span>{bhsa_text}</td>
        </tr>
        <tr class="verse-group">
            <td class="heb sp-row" dir="rtl" lang="he"><span class="src-label">SP</span>{sp_text}</td>
        </tr>""")

    rows_html = "".join(rows)

    def nav_link(info, label):
        if info is None:
            return f'<span class="nav-disabled">{label}</span>'
        b_en, b_he, c = info
        return f'<a href="{chapter_filename(b_en, c)}">{label} {b_he} {c}</a>'

    prev_link = nav_link(prev_info, "◀")
    next_link = nav_link(next_info, "▶")
    nav_html = f'<nav class="chapter-nav">{prev_link} <a href="index.html">index</a> {next_link}</nav>'

    page = f"""<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book_en} {chap_num} — MT &amp; SP</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: sans-serif;
    background: #f7f4ef;
    color: #222;
    padding: 2rem 1rem;
  }}

  header {{
    max-width: 960px;
    margin: 0 auto 1.5rem;
    text-align: center;
  }}

  header h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.6rem;
  }}

  .legend {{
    display: flex;
    justify-content: center;
    gap: 2rem;
    font-size: 0.9rem;
  }}

  .legend span {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }}

  .dot {{
    width: 12px; height: 12px;
    border-radius: 50%;
    display: inline-block;
  }}

  .dot-bhsa {{ background: #3a6ea5; }}
  .dot-sp   {{ background: #8b4513; }}

  .chapter-nav {{
    max-width: 960px;
    margin: 0 auto 1.2rem;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1.5rem;
    font-size: 0.95rem;
  }}

  .chapter-nav a {{ color: #3a6ea5; text-decoration: none; }}
  .chapter-nav a:hover {{ text-decoration: underline; }}
  .chapter-nav .nav-disabled {{ color: #bbb; }}

  .table-wrap {{
    max-width: 960px;
    margin: 0 auto;
    overflow-x: auto;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}

  tbody tr.verse-group:nth-child(4n+1),
  tbody tr.verse-group:nth-child(4n+2) {{ background: #faf8f5; }}

  td {{
    padding: 0.55rem 1rem;
    vertical-align: middle;
    border-bottom: 1px solid #e8e4dc;
  }}

  tr.verse-group td.bhsa-row {{ border-bottom: 1px dashed #d0ccc4; }}
  tr.verse-group td.sp-row   {{ border-bottom: 2px solid #ccc7be; }}

  td.vnum {{
    text-align: center;
    font-size: 0.85rem;
    color: #777;
    font-weight: 600;
    white-space: nowrap;
    width: 3rem;
    border-bottom: 2px solid #ccc7be;
  }}

  td.heb {{
    font-family: 'Frank Ruhl Libre', serif;
    font-size: 1.25rem;
    line-height: 1.8;
    unicode-bidi: embed;
  }}

  td.bhsa-row {{ border-left: 3px solid #3a6ea5; }}
  td.sp-row   {{ border-left: 3px solid #8b4513; }}

  .src-label {{
    float: left;
    font-family: sans-serif;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 1px 5px;
    border-radius: 3px;
    margin-top: 0.45rem;
  }}

  td.bhsa-row .src-label {{ background: #ddeaf7; color: #3a6ea5; }}
  td.sp-row   .src-label {{ background: #f5e8de; color: #8b4513; }}

  .w {{
    cursor: default;
    border-radius: 2px;
    transition: background 0.1s;
  }}

  .w:hover {{ background: #ffe9a0; }}

  #tip {{
    display: none;
    position: absolute;
    background: #222;
    color: #fff;
    font-family: 'Frank Ruhl Libre', serif;
    font-size: 1rem;
    padding: 5px 10px;
    border-radius: 4px;
    white-space: pre;
    direction: ltr;
    text-align: left;
    pointer-events: none;
    z-index: 100;
  }}

  .plus-mt {{ color: #1a5bbf; font-weight: bold; }}
  .plus-sp {{ color: #c0392b; font-weight: bold; }}

  footer {{
    max-width: 960px;
    margin: 2rem auto 0;
    text-align: center;
    font-size: 0.8rem;
    color: #888;
  }}
</style>
</head>
<body>

<header>
  <h1>{book_en} / {book_he} — Chapter {chap_num}</h1>
  <div class="legend">
    <span><span class="dot dot-bhsa"></span> BHSA 2021 (MT, consonantal)</span>
    <span><span class="dot dot-sp"></span> SP 6.0.3 — Samaritan Pentateuch (consonantal)</span>
  </div>
</header>

{nav_html}

<div class="table-wrap">
  <table>
    <tbody>{rows_html}
    </tbody>
  </table>
</div>

{nav_html}

<footer>
  <p>BHSA data: ETCBC, Amsterdam. SP data: Stefan Schorch et al. Rendered via Text-Fabric.</p>
</footer>

<script>
  const tip = document.createElement('div');
  tip.id = 'tip';
  document.body.appendChild(tip);

  document.querySelectorAll('.w[data-tip]').forEach(el => {{
    el.addEventListener('mouseenter', () => {{
      tip.textContent = el.dataset.tip;
      tip.style.visibility = 'hidden';
      tip.style.display = 'block';
      const r = el.getBoundingClientRect();
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      const top = r.top >= th + 12
        ? r.top + window.scrollY - th - 8
        : r.bottom + window.scrollY + 8;
      const left = Math.max(8, Math.min(
        r.left + window.scrollX + r.width / 2 - tw / 2,
        window.innerWidth - tw - 8
      ));
      tip.style.top = top + 'px';
      tip.style.left = left + 'px';
      tip.style.visibility = 'visible';
    }});
    el.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; }});
  }});
</script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)


def generate_index(toc, out_dir):
    """toc: list of (book_en, book_he, [chap_nums])"""
    rows = []
    for book_en, book_he, chapters in toc:
        links = " ".join(
            f'<a href="{chapter_filename(book_en, c)}">{c}</a>'
            for c in chapters
        )
        rows.append(f"""
      <tr>
        <td class="book-name">{book_en}<br><span class="book-he">{book_he}</span></td>
        <td class="chapter-links">{links}</td>
      </tr>""")

    rows_html = "".join(rows)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pentateuch — MT &amp; SP parallel texts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: sans-serif;
    background: #f7f4ef;
    color: #222;
    padding: 2rem 1rem;
  }}
  header {{
    max-width: 820px;
    margin: 0 auto 2rem;
    text-align: center;
  }}
  header h1 {{ font-size: 1.8rem; margin-bottom: 0.4rem; }}
  header p  {{ color: #555; font-size: 0.95rem; }}
  .table-wrap {{ max-width: 820px; margin: 0 auto; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}
  td {{
    padding: 0.7rem 1rem;
    vertical-align: top;
    border-bottom: 1px solid #e8e4dc;
  }}
  td.book-name {{
    white-space: nowrap;
    font-weight: 600;
    width: 130px;
    border-right: 3px solid #3a6ea5;
  }}
  .book-he {{
    font-family: 'Frank Ruhl Libre', serif;
    font-size: 1.1rem;
    font-weight: 400;
  }}
  td.chapter-links {{ line-height: 2; }}
  td.chapter-links a {{
    display: inline-block;
    margin: 2px 3px;
    padding: 2px 7px;
    border-radius: 4px;
    background: #eef3fa;
    color: #3a6ea5;
    text-decoration: none;
    font-size: 0.9rem;
  }}
  td.chapter-links a:hover {{ background: #3a6ea5; color: #fff; }}
  footer {{
    max-width: 820px;
    margin: 2rem auto 0;
    text-align: center;
    font-size: 0.8rem;
    color: #888;
  }}
</style>
</head>
<body>
<header>
  <h1>Pentateuch — MT &amp; SP parallel texts</h1>
  <p>BHSA 2021 (Masoretic Text, consonantal) aligned with SP 6.0.3 (Samaritan Pentateuch)</p>
</header>
<div class="table-wrap">
  <table>{rows_html}
  </table>
</div>
<footer>
  <p>BHSA data: ETCBC, Amsterdam. SP data: Stefan Schorch et al. Rendered via Text-Fabric.</p>
</footer>
</body>
</html>
"""
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("Written: index.html")


def main():
    print("Loading BHSA...")
    bhsa_api = load_bhsa("bhsa/tf/2021")
    print("Loading SP...")
    sp_api = load_sp("sp/tf/6.0.3")

    # Build full TOC
    toc = []
    for book_en, book_he in PENTATEUCH:
        chapters = get_chapters(bhsa_api, book_en)
        toc.append((book_en, book_he, chapters))

    # Flat list for prev/next navigation
    flat = [(book_en, book_he, c)
            for book_en, book_he, chapters in toc
            for c in chapters]

    total = len(flat)
    print(f"\n{total} chapters total. Generating...\n")

    for idx, (book_en, book_he, chap_num) in enumerate(flat):
        prev_info = flat[idx - 1] if idx > 0 else None
        next_info = flat[idx + 1] if idx < total - 1 else None

        print(f"  {book_en} {chap_num}...", end=" ", flush=True)

        bhsa_verses = get_verse_texts(
            bhsa_api, book_en, chap_num, "word", "g_cons_utf8", "trailer_utf8",
            extra_feats=("ps", "gn", "vt", "vs"), trailer_clean_fn=clean_bhsa_trailer)
        sp_verses = get_verse_texts(
            sp_api, book_en, chap_num, "word", "g_cons_utf8", "trailer",
            extra_feats=("ps", "gn", "vt"))

        out_path = os.path.join(OUT_DIR, chapter_filename(book_en, chap_num))
        generate_html(bhsa_verses, sp_verses, out_path,
                      book_en, book_he, chap_num, prev_info, next_info)
        print("done")

    generate_index(toc, OUT_DIR)
    print("\nAll done.")


if __name__ == "__main__":
    main()
