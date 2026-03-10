"""Load Text-Fabric corpora and extract per-verse word data."""

import re
from tf.fabric import Fabric


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


def load_bhsa(path):
    F = Fabric(locations=path, silent=True)
    return F.load("otype book chapter verse g_cons_utf8 trailer_utf8 lex_utf8 nu vt ps gn vs", silent=True)


def load_sp(path):
    F = Fabric(locations=path, silent=True)
    return F.load("otype book chapter verse g_cons_utf8 trailer lex_utf8 nu vt ps gn", silent=True)


def get_chapters(api, book_name):
    book_node = api.T.nodeFromSection((book_name,))
    if book_node is None:
        return []
    return sorted(api.F.chapter.v(c) for c in api.L.d(book_node, otype='chapter'))


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
            t   = getattr(Ft, text_feat).v(w) or ""
            tr  = getattr(Ft, trailer_feat).v(w) or ""
            if trailer_clean_fn:
                tr = trailer_clean_fn(tr)
            lex    = clean_lex(Ft.lex_utf8.v(w) or "")
            nu     = Ft.nu.v(w) or ""
            extras = {f: (getattr(Ft, f).v(w) or "") for f in extra_feats}
            word_data.append((t, tr, lex, nu, extras))
        result[vnum] = word_data
    return result
