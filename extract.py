"""
Extract Exodus 20 from BHSA (2021) and SP (6.0.3) and generate exodus20.html.
BHSA uses pointed Hebrew (g_word_utf8 + trailer_utf8).
SP uses consonantal Hebrew (g_cons_utf8 + trailer).
"""

import sys, io, html, re, difflib, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def clean_lex(lex):
    """Keep only Hebrew letters (including precomposed presentation forms U+FB1D-FB4F
    for shin/sin with dot), shin/sin combining dots (U+05C1-05C2), and spaces.
    Strips disambiguation markers like / and [.
    Converts word-final regular forms to final forms (מ→ם, נ→ן, פ→ף, כ→ך, צ→ץ)."""
    cleaned = re.sub(r'[^\u05c1\u05c2\u05d0-\u05ea\u05f0-\u05f4\ufb1d-\ufb4f ]', '', lex).strip()
    final_forms = {'מ': 'ם', 'נ': 'ן', 'פ': 'ף', 'כ': 'ך', 'צ': 'ץ'}
    words = cleaned.split(' ')
    result = []
    for w in words:
        if w and w[-1] in final_forms:
            w = w[:-1] + final_forms[w[-1]]
        result.append(w)
    return ' '.join(result)

from tf.fabric import Fabric


def load_bhsa(path):
    F = Fabric(locations=path, silent=True)
    api = F.load("otype book chapter verse g_cons_utf8 trailer_utf8 lex_utf8 nu", silent=True)
    return api


def load_sp(path):
    F = Fabric(locations=path, silent=True)
    api = F.load("otype book chapter verse g_cons_utf8 trailer lex_utf8 nu", silent=True)
    return api


def get_verse_texts(api, book, chapter, word_otype, text_feat, trailer_feat):
    Ft = api.F
    Lt = api.L
    Tt = api.T

    chap_node = Tt.nodeFromSection((book, chapter))
    if chap_node is None:
        raise ValueError(f"Section {book} {chapter} not found")

    result = {}
    for vnode in Lt.d(chap_node, otype="verse"):
        vnum = Ft.verse.v(vnode)
        words = Lt.d(vnode, otype=word_otype)
        word_data = []
        for w in words:
            t = getattr(Ft, text_feat).v(w) or ""
            tr = getattr(Ft, trailer_feat).v(w) or ""
            lex = clean_lex(Ft.lex_utf8.v(w) or "")
            nu = Ft.nu.v(w) or ""
            word_data.append((t, tr, lex, nu))
        result[vnum] = word_data
    return result


def diff_verses(mt_words, sp_words):
    HCONS = re.compile(r'[\u05d0-\u05ea\ufb1d-\ufb4f]')
    mt_index, sp_index = [], []
    for wi, (text, _, _, _) in enumerate(mt_words):
        for ci, ch in enumerate(text):
            if HCONS.match(ch):
                mt_index.append((wi, ci))
    for wi, (text, _, _, _) in enumerate(sp_words):
        for ci, ch in enumerate(text):
            if HCONS.match(ch):
                sp_index.append((wi, ci))
    def base_cons(ch):
        # Decompose FB-block precomposed forms (e.g. U+FB2A shin-with-dot → U+05E9)
        # so that BHSA's decomposed and SP's precomposed shinot compare as equal.
        return unicodedata.normalize('NFKD', ch)[0]

    mt_str = ''.join(base_cons(mt_words[wi][0][ci]) for wi, ci in mt_index)
    sp_str = ''.join(base_cons(sp_words[wi][0][ci]) for wi, ci in sp_index)
    mt_marks = [[False]*len(t) for t, _, _, _ in mt_words]
    sp_marks = [[False]*len(t) for t, _, _, _ in sp_words]
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
    for (text, trailer, lex, nu), marks in zip(word_data, char_marks):
        inner = ""
        i = 0
        while i < len(text):
            # Collect base character plus any following combining characters as one cluster
            cluster = text[i]
            j = i + 1
            while j < len(text) and unicodedata.category(text[j]).startswith('M'):
                cluster += text[j]
                j += 1
            esc = html.escape(cluster)
            inner += f'<span class="{extra_class}">{esc}</span>' if marks[i] else esc
            i = j
        tooltip = html.escape(f"lex: {lex}\nnu: {nu}")
        spans.append(f'<span class="w" data-tip="{tooltip}">{inner}</span>{html.escape(trailer)}')
    return "".join(spans).strip()


def generate_html(bhsa_verses, sp_verses, out_path):
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
            bhsa_text = render_verse(mt_words, [[False]*len(t) for t,_,_,_ in mt_words], "plus-mt") if mt_words else "—"
            sp_text   = render_verse(sp_words, [[False]*len(t) for t,_,_,_ in sp_words], "plus-sp") if sp_words else "—"
        rows.append(f"""
        <tr class="verse-group">
            <td class="vnum" rowspan="2">{vnum}</td>
            <td class="heb bhsa-row" dir="rtl" lang="he"><span class="src-label">MT</span>{bhsa_text}</td>
        </tr>
        <tr class="verse-group">
            <td class="heb sp-row" dir="rtl" lang="he"><span class="src-label">SP</span>{sp_text}</td>
        </tr>""")

    rows_html = "".join(rows)

    page = f"""<!DOCTYPE html>
<html lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Exodus 20 — BHSA &amp; Samaritan Pentateuch</title>
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
    margin: 0 auto 2rem;
    text-align: center;
  }}

  header h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.4rem;
  }}

  header p {{
    color: #555;
    font-size: 0.95rem;
    line-height: 1.5;
  }}

  .legend {{
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-top: 0.8rem;
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

  thead th {{
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #fff;
    background: #444;
  }}

  /* alternating verse groups (every pair of rows) */
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
    margin-left: 0;
  }}

  td.bhsa-row .src-label {{ background: #ddeaf7; color: #3a6ea5; }}
  td.sp-row   .src-label {{ background: #f5e8de; color: #8b4513; }}

  .w {{
    position: relative;
    cursor: default;
    border-radius: 2px;
    transition: background 0.1s;
  }}

  .w:hover {{ background: #ffe9a0; }}

  .w[data-tip]:hover::after {{
    content: attr(data-tip);
    position: absolute;
    bottom: calc(100% + 4px);
    left: 50%;
    transform: translateX(-50%);
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
    z-index: 10;
  }}

  .w[data-tip]:hover::before {{
    content: '';
    position: absolute;
    bottom: calc(100% + 0px);
    left: 50%;
    transform: translateX(-50%);
    border: 4px solid transparent;
    border-top-color: #222;
    pointer-events: none;
    z-index: 10;
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
  <h1>Exodus / שמות Chapter 20</h1>
<div class="legend">
    <span><span class="dot dot-bhsa"></span> BHSA 2021 — Biblia Hebraica Stuttgartensia Amstelodamensis (consonantal)</span>
    <span><span class="dot dot-sp"></span> SP 6.0.3 — Samaritan Pentateuch (consonantal)</span>
  </div>
</header>

<div class="table-wrap">
  <table>
    <tbody>{rows_html}
    </tbody>
  </table>
</div>

<footer>
  <p>BHSA data: ETCBC, Amsterdam. SP data: Stefan Schorch et al. Rendered via Text-Fabric.</p>
</footer>

</body>
</html>
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    print("Loading BHSA...")
    bhsa_api = load_bhsa("bhsa/tf/2021")
    bhsa_verses = get_verse_texts(bhsa_api, "Exodus", 20, "word", "g_cons_utf8", "trailer_utf8")
    print(f"  {len(bhsa_verses)} verses extracted")

    print("Loading SP...")
    sp_api = load_sp("sp/tf/6.0.3")
    sp_verses = get_verse_texts(sp_api, "Exodus", 20, "word", "g_cons_utf8", "trailer")
    print(f"  {len(sp_verses)} verses extracted")

    print("Generating HTML...")
    generate_html(bhsa_verses, sp_verses, "exodus20.html")
