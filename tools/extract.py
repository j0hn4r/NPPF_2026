import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import PDF, WORK, OUT, w
import pymupdf, re, json, unicodedata

DOC = pymupdf.open(str(PDF))
START, END = 4, 99          # 0-based page indices, chapters 1..20 (pdf pages 5..100)

def page_footnote_rule(page):
    y = None
    for dr in page.get_drawings():
        r = dr['rect']
        if abs(r.x0 - 48) < 1.5 and 189 < r.x1 < 196 and (r.y1 - r.y0) < 2.5:
            y = r.y0 if y is None else min(y, r.y0)
    return y

def links(page):
    out = []
    for l in page.get_links():
        if l.get('uri'):
            out.append((l['from'], l['uri']))
    return out

def span_link(sp, lnks):
    b = pymupdf.Rect(sp['bbox'])
    for r, uri in lnks:
        inter = b & r
        if inter.is_valid and inter.get_area() > 0.35 * b.get_area():
            return uri
    return None

def line_runs(line, lnks):
    """Return list of runs: dict(text, b, i, sup, href)."""
    spans = [s for s in line['spans']]
    live = [s for s in spans if s['text'].strip()]
    if not live:
        return []
    mx = max(round(s['size'], 1) for s in live)
    runs = []
    for s in spans:
        t = s['text']
        if not t:
            continue
        sz = round(s['size'], 1)
        sup = sz <= mx - 1.0
        font = s['font']
        run = {
            'text': t,
            'b': 'Bold' in font,
            'i': 'Italic' in font,
            'sup': sup,
            'href': span_link(s, lnks),
            'size': sz,
        }
        runs.append(run)
    return runs

pages = []
for pi in range(START, END + 1):
    page = DOC[pi]
    fny = page_footnote_rule(page)
    lnks = links(page)
    body, foot = [], []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for line in b['lines']:
            raw = ''.join(s['text'] for s in line['spans'])
            if not raw.strip():
                continue
            y0, y1 = line['bbox'][1], line['bbox'][3]
            x0 = line['bbox'][0]
            live = [s for s in line['spans'] if s['text'].strip()]
            mx = max(round(s['size'], 1) for s in live)
            # page number
            if y0 > 775 and re.fullmatch(r'\s*\d+\s*', raw):
                continue
            rec = {'x0': round(x0, 1), 'y0': round(y0, 1), 'y1': round(y1, 1),
                   'size': mx, 'runs': line_runs(line, lnks), 'page': pi + 1}
            if fny is not None and y0 >= fny - 1:
                foot.append(rec)
            else:
                body.append(rec)
    body.sort(key=lambda r: (r['y0'], r['x0']))
    foot.sort(key=lambda r: (r['y0'], r['x0']))
    pages.append({'page': pi + 1, 'body': body, 'foot': foot})

json.dump(pages, open(w('lines.json'), 'w'), ensure_ascii=False)
print('pages', len(pages),
      'body lines', sum(len(p['body']) for p in pages),
      'foot lines', sum(len(p['foot']) for p in pages))

# report line-ending hyphens and superscripts for sanity
hy = []
sups = []
for p in pages:
    for r in p['body'] + p['foot']:
        txt = ''.join(x['text'] for x in r['runs']).rstrip()
        if txt.endswith('-'):
            hy.append((p['page'], txt[-40:]))
        for x in r['runs']:
            if x['sup']:
                sups.append((p['page'], x['text'].strip(), txt[:60]))
print('\n--- line-ending hyphens:', len(hy))
for h in hy[:80]:
    print('   ', h)
print('\n--- superscripts:', len(sups))
for s in sups:
    print('   ', s)
