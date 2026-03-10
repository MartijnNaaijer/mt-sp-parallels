"""Consonantal diff between MT and SP verse word lists."""

import re
import difflib
import unicodedata

_HCONS = re.compile(r'[\u05d0-\u05ea\ufb1d-\ufb4f]')


def _base_cons(ch):
    return unicodedata.normalize('NFKD', ch)[0]


def _build_cons_index(words):
    index = []
    for wi, (text, *_) in enumerate(words):
        for ci, ch in enumerate(text):
            if _HCONS.match(ch):
                index.append((wi, ci))
    return index


def diff_verses(mt_words, sp_words):
    """Return (mt_marks, sp_marks): per-character bool lists marking differences."""
    mt_index = _build_cons_index(mt_words)
    sp_index = _build_cons_index(sp_words)

    mt_str = ''.join(_base_cons(mt_words[wi][0][ci]) for wi, ci in mt_index)
    sp_str = ''.join(_base_cons(sp_words[wi][0][ci]) for wi, ci in sp_index)

    mt_marks = [[False] * len(t) for t, *_ in mt_words]
    sp_marks = [[False] * len(t) for t, *_ in sp_words]

    matcher = difflib.SequenceMatcher(None, mt_str, sp_str, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ('delete', 'replace'):
            for k in range(i1, i2):
                wi, ci = mt_index[k]
                mt_marks[wi][ci] = True
        if tag in ('insert', 'replace'):
            for k in range(j1, j2):
                wi, ci = sp_index[k]
                sp_marks[wi][ci] = True

    return mt_marks, sp_marks
