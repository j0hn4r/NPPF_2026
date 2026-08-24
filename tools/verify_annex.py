# -*- coding: utf-8 -*-
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import PDF, WORK, OUT, w
import json, re, collections, sys

d = json.load(open(w('annexes.json')))

def sq(s):
    return re.sub(r'\s+', '', s.replace(' ', ' '))

def rt(runs):
    return ''.join(r['text'] for r in runs)

# ---- reconstruct the non-table stream in document order
parts, tables_out = [], []
def emit(n):
    t = n['type']
    if t == 'annex':
        parts.append('Annex ' + n['marker'] + ': ' + n['title'])
    elif t == 'table':
        cells = []
        for row in n['header'] + n['rows']:
            for c in row:
                for p in c['paras']:
                    cells.append(('•' if p['bullet'] else '') + rt(p['runs']))
        tables_out.append(cells)
        return
    elif t == 'glossentry':
        parts.append(rt(n['termruns']) + ':' + rt(n['runs']))
    elif t in ('para', 'item', 'subitem'):
        parts.append(n['marker'] + '.' + rt(n['runs']))
    elif t == 'bullet':
        parts.append('•' + rt(n['runs']))
    else:
        parts.append(rt(n['runs']))
    for c in n['children']:
        emit(c)
for a in d['annexes']:
    emit(a)

raw_nt = sq(''.join(d['raw_nontable']))
rec_nt = sq(''.join(parts))
print('non-table stream:', 'PASS' if raw_nt == rec_nt else 'FAIL',
      f'{len(raw_nt):,} vs {len(rec_nt):,}')
if raw_nt != rec_nt:
    for i in range(min(len(raw_nt), len(rec_nt))):
        if raw_nt[i] != rec_nt[i]:
            print('  raw:', repr(raw_nt[i-100:i+100]))
            print('  rec:', repr(rec_nt[i-100:i+100]))
            break

print('tables:', len(d['raw_tables']), 'reconstructed:', len(tables_out))
ok = True
for i, (raw, rec) in enumerate(zip(d['raw_tables'], tables_out)):
    a, b = collections.Counter(sq(x) for x in raw if sq(x)), \
           collections.Counter(sq(x) for x in rec if sq(x))
    # cell paragraphs merge multiple lines, so compare concatenations
    ca, cb = sq(''.join(raw)), sq(''.join(rec)).replace('•', '')
    ca2 = ca.replace('•', '')
    if ca2 != cb:
        ok = False
        print(f'  table {i}: FAIL {len(ca2):,} vs {len(cb):,}')
        for j in range(min(len(ca2), len(cb))):
            if ca2[j] != cb[j]:
                print('    raw:', repr(ca2[j-90:j+90]))
                print('    rec:', repr(cb[j-90:j+90]))
                break
    else:
        print(f'  table {i}: PASS {len(ca2):,} chars')

raw_f = sq(''.join(d['raw_foot']))
rec_f = sq(''.join(f['num'] + rt(f['runs']) for f in d['footnotes']))
print('footnotes:', 'PASS' if raw_f == rec_f else 'FAIL',
      f'{len(raw_f):,} vs {len(rec_f):,}')

# global character multiset
allraw = collections.Counter(sq(''.join(d['raw_nontable']) +
                               ''.join(''.join(t) for t in d['raw_tables']) +
                               ''.join(d['raw_foot'])))
allrec = collections.Counter(sq(''.join(parts) +
                                ''.join(''.join(t) for t in tables_out) +
                                ''.join(f['num'] + rt(f['runs']) for f in d['footnotes'])))
extra_bullets = allrec['•'] - allraw['•']
allrec['•'] -= max(extra_bullets, 0)
print('global char multiset:', 'PASS' if allraw == allrec else 'FAIL',
      sum(allraw.values()), 'vs', sum(allrec.values()))
if allraw != allrec:
    print('  diff:', dict((allraw - allrec)), dict((allrec - allraw)))

sys.exit(0 if (raw_nt == rec_nt and ok and raw_f == rec_f and allraw == allrec) else 1)
