# -*- coding: utf-8 -*-
"""Fidelity checks: parsed structure vs raw PDF text, and HTML vs PDF."""
import json, re, html, collections, sys
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import PDF, WORK, OUT, w

lines = json.load(open(w('lines.json')))
doc = json.load(open(w('doc.json')))

def squash(s):
    s = s.replace(' ', ' ')
    return re.sub(r'\s+', '', s)

# ---------- A. raw line stream from the PDF ----------
raw_body = ''.join(''.join(r['text'] for r in ln['runs'])
                   for pg in lines for ln in pg['body'])
raw_foot = ''.join(''.join(r['text'] for r in ln['runs'])
                   for pg in lines for ln in pg['foot'])

# ---------- B. reconstruct from the parsed tree ----------
parts = []
def emit(n):
    if n['type'] == 'chapter':
        parts.append(n['marker'] + '.' + n['title'])
    elif n['type'] in ('para', 'item', 'subitem'):
        parts.append(n['marker'] + '.')
    elif n['type'] == 'policy':
        parts.append(n['marker'] + ':')
    if n['type'] != 'chapter':
        parts.append(''.join(r['text'] for r in n['runs']))
    for c in n['children']:
        emit(c)
for ch in doc['chapters']:
    emit(ch)
tree_body = ''.join(parts)
tree_foot = ''.join(f['num'] + ''.join(r['text'] for r in f['runs'])
                    for f in doc['footnotes'])

def cmp(name, a, b):
    A, B = squash(a), squash(b)
    if A == B:
        print(f'PASS  {name}: {len(A):,} chars identical')
        return True
    print(f'FAIL  {name}: {len(A):,} vs {len(B):,}')
    for i in range(min(len(A), len(B))):
        if A[i] != B[i]:
            print('   first divergence at', i)
            print('   pdf :', repr(A[i-90:i+90]))
            print('   tree:', repr(B[i-90:i+90]))
            break
    else:
        print('   tail pdf :', repr(A[min(len(A),len(B)):][:200]))
        print('   tail tree:', repr(B[min(len(A),len(B)):][:200]))
    return False

ok = True
ok &= cmp('body text (PDF lines vs parsed tree)', raw_body, tree_body)
ok &= cmp('footnotes (PDF lines vs parsed tree)', raw_foot, tree_foot)

# ---------- C. HTML vs parsed tree ----------
h = open(str(OUT)).read()
m = re.search(r'<div id="noresults".*?</div>(.*)<div class="footer">', h, re.S)
bodyhtml = m.group(1)
txt = re.sub(r'<script.*?</script>', '', bodyhtml, flags=re.S)
txt = re.sub(r'<a class="fnback".*?</a>', '', txt, flags=re.S)
txt = re.sub(r'<button[^>]*class="bookmark-btn".*?</button>', '', txt, flags=re.S)
txt = re.sub(r'<h4>Footnotes</h4>', '', txt)
txt = re.sub(r'<div class="azbar">.*?</div>', '', txt, flags=re.S)
txt = re.sub(r'<[^>]+>', '', txt)
txt = html.unescape(txt)
# HTML order: chapter body then that chapter's footnotes -> compare per chapter
fn_by_ch = collections.defaultdict(list)
for n, c in json.load(open(w('fn_owner.json'))).items():
    fn_by_ch[c].append(n)
expect = []
for ch in doc['chapters']:
    parts = []
    def emit2(n):
        if n['type'] == 'chapter':
            parts.append(n['marker'] + '.' + n['title'])
        elif n['type'] in ('para', 'item', 'subitem'):
            parts.append(n['marker'] + '.')
        elif n['type'] == 'policy':
            parts.append(n['marker'] + ':')
        if n['type'] != 'chapter':
            parts.append(''.join(r['text'] for r in n['runs']))
        for c in n['children']:
            emit2(c)
    emit2(ch)
    fns = {f['num']: f for f in doc['footnotes']}
    for n in sorted(fn_by_ch[ch['marker']], key=int):
        parts.append(n + ''.join(r['text'] for r in fns[n]['runs']))
    expect.append(''.join(parts))
# ---- annexes appended in render order
adoc = json.load(open(w('annexes.json')))
fnall = {f['num']: f for f in doc['footnotes']}
fnall.update({f['num']: f for f in adoc['footnotes']})
fn_owner = json.load(open(w('fn_owner.json')))


def anode(n, out):
    k = n['type']
    if k == 'table':
        for row in n['header'] + n['rows']:
            for c in row:
                for pp in c['paras']:
                    out.append(''.join(r['text'] for r in pp['runs']))
        return
    if k == 'glossentry':
        out.append(''.join(r['text'] for r in n['termruns']) + ':' +
                   ''.join(r['text'] for r in n['runs']))
    elif k in ('para', 'item', 'subitem'):
        out.append(n['marker'] + '.' + ''.join(r['text'] for r in n['runs']))
    elif k == 'bullet':
        out.append('\u2022' + ''.join(r['text'] for r in n['runs']))
    else:
        out.append(''.join(r['text'] for r in n['runs']))
    for c in n['children']:
        anode(c, out)


for an in adoc['annexes']:
    parts = ['Annex ' + an['marker'] + an['title']]
    for c in an['children']:
        anode(c, parts)
    for nn in sorted([k for k, v in fn_owner.items() if v == an['marker']], key=int):
        parts.append(nn + ''.join(r['text'] for r in fnall[nn]['runs']))
    expect.append(''.join(parts))

ok &= cmp('rendered HTML vs parsed tree', ''.join(expect), txt)

# ---------- D. independent engine: pdftotext word multiset (optional) ----------
import os
if not os.path.exists(w('nppf_raw.txt')):
    print('\n(skipping the pdftotext cross-check: no .build/nppf_raw.txt '
          '- install poppler-utils to enable it)')
    print('\nOVERALL', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
pt = open(w('nppf_raw.txt'), encoding='utf-8').read()
pages = pt.split('\f')
sel = pages[4:130]
words = []
for pg in sel:
    for ln in pg.split('\n'):
        if re.fullmatch(r'\s*\d+\s*', ln):
            continue
        words += re.findall(r"[\w’'%£&/\-\.]+", ln)
hw = re.findall(r"[\w’'%£&/\-\.]+", txt)
ca, cb = collections.Counter(words), collections.Counter(hw)
only_pdf = ca - cb
only_html = cb - ca
print(f'\npdftotext tokens: {sum(ca.values()):,}   html tokens: {sum(cb.values()):,}')
print('tokens only in pdftotext:', sum(only_pdf.values()),
      dict(list(only_pdf.items())[:25]))
print('tokens only in html     :', sum(only_html.values()),
      dict(list(only_html.items())[:25]))

# ---------- E. structural counts ----------
pol = re.findall(r'class="policy" id="([^"]+)"', h)
print('\npolicies rendered:', len(pol))
print('footnote refs:', len(re.findall(r'class="fnref"', h)),
      ' footnote entries:', len(re.findall(r'class="fn" id="fn', h)))
dupes = [k for k, v in collections.Counter(re.findall(r'\sid="([^"]+)"', h)).items() if v > 1]
print('duplicate element ids:', dupes[:20], f'({len(dupes)})')
print('\nOVERALL', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)

