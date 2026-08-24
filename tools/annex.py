# -*- coding: utf-8 -*-
"""Extract and structure Annexes A-F (pdf pages 101-130), including ruled tables.

Cell text in this PDF is often merged into a single text span spanning several
table columns, so extraction is done at character level and split on the column
boundaries taken from the drawn rules.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import PDF, WORK, OUT, w
import pymupdf, re, json, collections

DOC = pymupdf.open(str(PDF))
START, END = 100, 129            # 0-based page indices (pdf pages 101-130)

ROMAN = r'(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)'
RE_NUM = re.compile(r'^(\d+)\.\s')
RE_LET = re.compile(r'^([a-z])\.\s')
RE_ROM = re.compile(r'^(' + ROMAN + r')\.\s')
RE_ANNEX = re.compile(r'^Annex\s+([A-F]):\s*(.*)$')


# ----------------------------------------------------------------- helpers
def links(page):
    return [(l['from'], l['uri']) for l in page.get_links() if l.get('uri')]


def char_link(x0, y0, x1, y1, lnks):
    b = pymupdf.Rect(x0, y0, x1, y1)
    for r, uri in lnks:
        inter = b & r
        if inter.is_valid and inter.get_area() > 0.35 * max(b.get_area(), 0.01):
            return uri
    return None


def style_key(c):
    return (c['b'], c['i'], c['sup'], c['href'], c['size'])


def runs_from_chars(chars):
    """Merge consecutive same-style chars into runs."""
    out = []
    for c in chars:
        if out and style_key(c) == out[-1]['_k']:
            out[-1]['text'] += c['c']
        else:
            out.append({'text': c['c'], 'b': c['b'], 'i': c['i'],
                        'sup': c['sup'], 'href': c['href'], 'size': c['size'],
                        '_k': style_key(c)})
    for r in out:
        del r['_k']
    return out


def txt(runs):
    return ''.join(r['text'] for r in runs)


def footnote_rule(page):
    y = None
    for dr in page.get_drawings():
        r = dr['rect']
        if abs(r.x0 - 48) < 1.5 and 189 < r.x1 < 196 and (r.y1 - r.y0) < 2.5:
            y = r.y0 if y is None else min(y, r.y0)
    return y


def hrule_groups(page, fny):
    raw = []
    for dr in page.get_drawings():
        r = dr['rect']
        if (r.x1 - r.x0) > 20 and (r.y1 - r.y0) < 3:
            if abs(r.x0 - 48) < 1.5 and 189 < r.x1 < 196:
                continue
            if fny is not None and r.y0 >= fny - 1:
                continue
            raw.append((round(r.y0, 1), r.x0, r.x1))
    byy = collections.defaultdict(list)
    for y, x0, x1 in raw:
        key = next((k for k in byy if abs(k - y) < 2.5), y)
        byy[key].append((x0, x1))
    rules = []
    for y in sorted(byy):
        segs = sorted({(round(a, 1), round(b, 1)) for a, b in byy[y]})
        keep = [s1 for s1 in segs
                if not any(s2 != s1 and s2[0] <= s1[0] and s1[1] <= s2[1]
                           for s2 in segs)]
        if len(keep) >= 2:
            rules.append((y, keep))
    groups, cur = [], []
    for y, segs in rules:
        if cur and len(segs) == len(cur[-1][1]) and all(
                abs(a1 - a2) < 4 for (a1, _), (a2, _) in zip(segs, cur[-1][1])):
            cur.append((y, segs))
        else:
            if len(cur) >= 2:
                groups.append(cur)
            cur = [(y, segs)]
    if len(cur) >= 2:
        groups.append(cur)
    return groups


# ----------------------------------------------------------------- page pass
PAGES = []
for pi in range(START, END + 1):
    page = DOC[pi]
    fny = footnote_rule(page)
    lnks = links(page)
    body, foot = [], []
    for blk in page.get_text('rawdict')['blocks']:
        if blk['type'] != 0:
            continue
        for line in blk['lines']:
            live = [s for s in line['spans']
                    if ''.join(c['c'] for c in s['chars']).strip()]
            if not live:
                continue
            mx = max(round(s['size'], 1) for s in live)
            chars = []
            for s in line['spans']:
                sz = round(s['size'], 1)
                sup = sz <= mx - 1.0
                bold = 'Bold' in s['font']
                ital = 'Italic' in s['font']
                for c in s['chars']:
                    bb = c['bbox']
                    chars.append({'c': c['c'], 'x0': bb[0], 'x1': bb[2],
                                  'b': bold, 'i': ital, 'sup': sup,
                                  'href': char_link(bb[0], bb[1], bb[2], bb[3], lnks),
                                  'size': sz})
            raw = ''.join(c['c'] for c in chars)
            y0, y1, x0 = line['bbox'][1], line['bbox'][3], line['bbox'][0]
            if y0 > 775 and re.fullmatch(r'\s*\d+\s*', raw):
                continue
            rec = {'x0': round(x0, 1), 'x1': round(line['bbox'][2], 1),
                   'y0': round(y0, 1), 'y1': round(y1, 1), 'size': mx,
                   'bold': any('Bold' in s['font'] for s in live),
                   'chars': chars, 'page': pi + 1}
            (foot if (fny is not None and y0 >= fny - 1) else body).append(rec)
    body.sort(key=lambda r: (r['y0'], r['x0']))
    foot.sort(key=lambda r: (r['y0'], r['x0']))
    PAGES.append({'page': pi + 1, 'body': body, 'foot': foot,
                  'groups': hrule_groups(page, fny)})


def col_of(cols, x):
    for i, (a, b) in enumerate(cols):
        if x + 2 >= a and x + 2 < b:
            return i
    return 0 if x < cols[0][1] else len(cols) - 1


def split_line(cols, chars):
    """Split a line's chars into (startcol, colspan, chars) groups.

    A column boundary only breaks a cell when the characters either side are
    separated by whitespace or a positional gap; otherwise the line is one wide
    (centred) cell spanning several columns.
    """
    if not chars:
        return []
    groups, cur = [], [chars[0]]
    for prev, nxt in zip(chars, chars[1:]):
        newcol = col_of(cols, prev['x0']) != col_of(cols, nxt['x0'])
        gap = (prev['c'].isspace() or nxt['c'].isspace()
               or (nxt['x0'] - prev['x1']) > 1.5)
        if newcol and gap:
            groups.append(cur)
            cur = [nxt]
        else:
            cur.append(nxt)
    groups.append(cur)
    out = []
    for g in groups:
        live = [c for c in g if not c['c'].isspace()]
        if not live:
            continue
        a = col_of(cols, live[0]['x0'])
        b = col_of(cols, live[-1]['x0'])
        out.append([a, b - a + 1, g])
    return [(a, sp, g) for a, sp, g in out]


def resolve_spans(spans, ncols, header):
    """Make column spans non-overlapping; widen header cells over empty gaps."""
    occ = sorted(spans)
    for i, c in enumerate(occ):
        limit = (occ[i + 1] - c) if i + 1 < len(occ) else (ncols - c)
        spans[c] = min(spans[c], limit)
    if header and occ:
        for i in range(1, len(occ)):
            prev = occ[i - 1]
            pend = prev + spans[prev]
            if occ[i] > pend:                    # absorb empty gap columns
                spans[occ[i]] += occ[i] - pend
                spans[pend] = spans.pop(occ[i])
                occ[i] = pend
        last = occ[-1]
        if last + spans[last] < ncols:
            spans[last] = ncols - last
    return spans


def is_content_marker(l):
    """A line that clearly is NOT part of a table row."""
    t = ''.join(c['c'] for c in l['chars']).strip()
    if RE_NUM.match(t) or RE_ANNEX.match(t):
        return True
    if l['bold'] and l['x0'] < 60 and (
            t.startswith('Table ') or t.startswith('Purpose ') or
            t.startswith('Step ') or t.startswith('Key:') or
            t.startswith('Notes to')):
        return True
    return False


# ---------------------------------------------- split each page into segments
SEGMENTS = []
for pg in PAGES:
    lines = pg['body']
    used, tables = set(), []
    for grp in pg['groups']:
        cols = list(grp[0][1])
        ys = [y for y, _ in grp]
        prev_bot = max([t['ybot'] for t in tables] or [0.0])
        bands = [(None, ys[0], [l for l in lines
                                if l['y0'] > prev_bot and l['y1'] <= ys[0] + 1
                                and id(l) not in used and l['size'] == 12])]
        for i in range(len(ys) - 1):
            bands.append((ys[i], ys[i + 1],
                          [l for l in lines
                           if l['y0'] >= ys[i] - 1 and l['y1'] <= ys[i + 1] + 2
                           and id(l) not in used and l['size'] == 12]))
        cur = None
        for (top, bot, bl) in bands:
            if not bl:
                continue
            split = (top is None) or any(is_content_marker(l) for l in bl)
            if split:
                nc = [l for l in bl if col_of(cols, l['x0']) > 0]
                hy = min((l['y0'] for l in nc), default=None)
                pre = [l for l in bl if hy is None or l['y0'] < hy - 3]
                rowl = [l for l in bl if hy is not None and l['y0'] >= hy - 3]
                if pre and cur:
                    tables.append(cur)
                    cur = None
            else:
                pre, rowl = [], bl
            if not rowl:
                continue
            for l in rowl:
                used.add(id(l))
            hdr_guess = sum(1 for l in rowl if l['bold']) * 2 >= len(rowl)
            cells = [[] for _ in cols]
            spans = {}
            for l in rowl:
                for ci, sp, cs in split_line(cols, l['chars']):
                    cells[ci].append({'chars': cs, 'x0': cs[0]['x0'],
                                      'y0': l['y0'], 'bold': l['bold'],
                                      'page': l['page']})
                    spans[ci] = max(spans.get(ci, 1), sp)
            spans = resolve_spans(dict(spans), len(cols), hdr_guess)
            # a widened header cell may have moved left: shift its content
            newcells = [[] for _ in cols]
            occ_old = sorted(c for c in range(len(cols)) if cells[c])
            occ_new = sorted(spans)
            for a, b in zip(occ_old, occ_new):
                newcells[b] = cells[a]
            cells = newcells
            nlines = sum(len(c) for c in cells)
            nbold = sum(1 for c in cells for s in c if s['bold'])
            row = {'cells': cells, 'spans': spans,
                   'bold': nbold * 2 >= max(nlines, 1)}
            if cur is None:
                cur = {'cols': cols, 'rows': [row], 'page': pg['page'],
                       'ytop': rowl[0]['y0'], 'ybot': bot or ys[-1],
                       'lastrule': ys[-1]}
            else:
                cur['rows'].append(row)
                cur['ybot'] = bot or cur['ybot']
        if cur:
            tables.append(cur)
    items = [(l['y0'], 0, ('text', l)) for l in lines if id(l) not in used]
    items += [(t['ytop'], 1, ('table', t)) for t in tables]
    items.sort(key=lambda z: (z[0], z[1]))
    SEGMENTS.extend(x[2] for x in items)

# ------------------------------------------------- merge tables across pages
def celltxt(cell):
    return ' '.join(''.join(c['c'] for c in s['chars']).strip() for s in cell)


def hdr_sig(t):
    return ' || '.join(celltxt(c) for c in t['rows'][0]['cells'])


merged = []
for kind, v in SEGMENTS:
    if kind == 'table' and merged and merged[-1][0] == 'table':
        prev = merged[-1][1]
        if (prev['page'] != v['page'] and prev['cols'] == v['cols']
                and prev['lastrule'] > 740 and hdr_sig(prev) == hdr_sig(v)):
            prev['rows'].extend(v['rows'][1:])
            prev['lastrule'] = v['lastrule']
            continue
    merged.append((kind, v))
SEGMENTS = merged

# a table's leading header rows: bold rows, plus following rows with empty col 1
for kind, v in SEGMENTS:
    if kind != 'table':
        continue
    nh = 0
    for r in v['rows']:
        if r['bold'] or (nh and not r['cells'][0]):
            nh += 1
        else:
            break
    v['nheader'] = max(nh, 1)


# =====================================================================
#                        structure the annexes
# =====================================================================
GAP = 17.5


def join_runs(dst, new):
    if dst:
        prev = ''.join(r['text'] for r in dst)
        if prev.endswith(' ') or prev == '':
            pass
        elif prev.endswith('-') and len(prev) >= 2 and not prev[-2].isspace():
            pass
        else:
            dst.append({'text': ' ', 'b': False, 'i': False, 'sup': False,
                        'href': None, 'size': 12})
        new = [dict(r) for r in new]
        for r in new:
            if r['text'].strip() == '':
                r['text'] = ''
            else:
                r['text'] = r['text'].lstrip()
                break
    dst.extend(dict(r) for r in new if r['text'] != '')


def strip_n(runs, n):
    out = []
    for r in runs:
        if n <= 0:
            out.append(dict(r))
            continue
        t = r['text']
        if len(t) <= n:
            n -= len(t)
            continue
        nr = dict(r)
        nr['text'] = t[n:]
        n = 0
        out.append(nr)
    return out


def cell_paras(cell):
    """Turn a table cell's line segments into paragraphs / bullet items."""
    paras, prev_y, bullet_x = [], None, None
    for seg in cell:
        runs = runs_from_chars(seg['chars'])
        t = ''.join(r['text'] for r in runs).strip()
        if not t:
            continue
        gap = None if prev_y is None else seg['y0'] - prev_y
        if t.startswith(('•', '')):
            raw = ''.join(r['text'] for r in runs)
            k = raw.index(t[0]) + 1
            while k < len(raw) and raw[k] in ' \t\xa0':
                k += 1
            paras.append({'bullet': True, 'runs': []})
            join_runs(paras[-1]['runs'], strip_n(runs, k))
            bullet_x = seg['x0']
        elif paras and paras[-1]['bullet'] and bullet_x is not None \
                and seg['x0'] > bullet_x + 8:
            join_runs(paras[-1]['runs'], runs)
        elif paras and gap is not None and gap <= GAP:
            join_runs(paras[-1]['runs'], runs)
        else:
            paras.append({'bullet': False, 'runs': []})
            join_runs(paras[-1]['runs'], runs)
            bullet_x = None
        prev_y = seg['y0']
    for p in paras:
        if p['runs']:
            p['runs'][0]['text'] = p['runs'][0]['text'].lstrip()
            p['runs'][-1]['text'] = p['runs'][-1]['text'].rstrip()
    return [p for p in paras if ''.join(r['text'] for r in p['runs']).strip()]


RANK = {'annex': 0, 'section': 1, 'subhead': 2, 'glossentry': 2, 'table': 2,
        'para': 3, 'note': 3, 'item': 4, 'subitem': 5}

annexes, stack = [], []
cur = None          # node accumulating text
prev_y = None
prev_page = None
cur_annex = [None]


def new_node(kind, marker, page, rank=None):
    return {'type': kind, 'marker': marker, 'runs': [], 'children': [],
            'page': page, 'rank': rank if rank is not None else RANK[kind]}


def push(node):
    r = node['rank']
    while stack and (stack[-1]['rank'] >= r or
                     stack[-1]['type'] in ('table',)):
        stack.pop()
    (annexes if not stack else stack[-1]['children']).append(node)
    stack.append(node)


for kind, v in SEGMENTS:
    if kind == 'table':
        nheader = v['nheader']
        tbl = new_node('table', None, v['page'])
        tbl['ncols'] = len(v['cols'])
        tbl['header'] = []
        tbl['rows'] = []
        for ri, row in enumerate(v['rows']):
            out = []
            for ci in range(len(v['cols'])):
                out.append({'span': row['spans'].get(ci, 1),
                            'paras': cell_paras(row['cells'][ci])})
            # drop cells covered by a previous colspan
            keep, skip = [], 0
            for ci, c in enumerate(out):
                if skip > 0:
                    skip -= 1
                    continue
                keep.append(c)
                skip = c['span'] - 1
            (tbl['header'] if ri < nheader else tbl['rows']).append(keep)
        push(tbl)
        cur = None
        prev_y = None
        continue

    l = v
    runs = runs_from_chars(l['chars'])
    raw = ''.join(r['text'] for r in runs)
    t = raw.strip()
    x0, size, bold = l['x0'], l['size'], l['bold']
    gap = None if (prev_y is None or prev_page != l['page']) else l['y0'] - prev_y
    prev_y, prev_page = l['y0'], l['page']

    # ---- annex heading (24pt, may wrap)
    if size >= 22:
        m = RE_ANNEX.match(t)
        if m:
            node = new_node('annex', m.group(1), l['page'])
            node['title'] = m.group(2).strip()
            stack.clear()
            push(node)
            cur = node
            cur_annex[0] = m.group(1)
        elif cur is not None and cur['type'] == 'annex':
            cur['title'] = (cur['title'] + ' ' + t).strip()
        continue

    # ---- section heading (18pt, may wrap)
    if size >= 16:
        if cur is not None and cur['type'] == 'section' and gap is not None \
                and gap <= 22:
            join_runs(cur['runs'], runs)
        else:
            node = new_node('section', None, l['page'])
            push(node)
            join_runs(node['runs'], runs)
            cur = node
        continue

    # ---- bullets
    if t.startswith(('•', '')):
        rank = 3 if x0 < 60 else (4 if x0 < 80 else 5)
        k = raw.index(t[0]) + 1
        while k < len(raw) and raw[k] in ' \t\xa0':
            k += 1
        node = new_node('bullet', '•', l['page'], rank)
        node['bx'] = x0
        push(node)
        join_runs(node['runs'], strip_n(runs, k))
        if node['runs']:
            node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
        cur = node
        continue

    # ---- numbered / lettered / roman
    if x0 < 60 and RE_NUM.match(t):
        node = new_node('para', RE_NUM.match(t).group(1), l['page'])
        push(node)
        join_runs(node['runs'], strip_n(runs, raw.index('.') + 1))
        node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
        cur = node
        continue
    if x0 < 80 and RE_LET.match(t):
        node = new_node('item', RE_LET.match(t).group(1), l['page'])
        push(node)
        join_runs(node['runs'], strip_n(runs, raw.index('.') + 1))
        node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
        cur = node
        continue
    if 80 <= x0 < 100 and RE_ROM.match(t):
        node = new_node('subitem', RE_ROM.match(t).group(1), l['page'])
        push(node)
        join_runs(node['runs'], strip_n(runs, raw.index('.') + 1))
        node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
        cur = node
        continue

    # ---- glossary entry (Annex B only): bold term ending in ':'
    first_live = next((r for r in runs if r['text'].strip()), None)
    if cur_annex[0] == 'B' and x0 < 60 and bold and first_live \
            and first_live['b'] and (gap is None or gap > GAP):
        k = raw.find(':')
        if 0 < k < 120:
            nb = tot = 0
            pos = 0
            for r in runs:
                for chx in r['text']:
                    if pos < k and not chx.isspace():
                        tot += 1
                        if r['b']:
                            nb += 1
                    pos += 1
            if tot and nb / tot >= 0.6:
                node = new_node('glossentry', None, l['page'])
                node['term'] = raw[:k].strip()
                keep, acc = [], 0
                for r in runs:
                    if acc + len(r['text']) <= k:
                        keep.append(dict(r)); acc += len(r['text'])
                    else:
                        nr = dict(r); nr['text'] = r['text'][:k - acc]
                        if nr['text']:
                            keep.append(nr)
                        break
                node['termruns'] = keep
                push(node)
                join_runs(node['runs'], strip_n(runs, k + 1))
                if node['runs']:
                    node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
                cur = node
                continue

    # ---- bold subheading
    if x0 < 60 and bold and (gap is None or gap > GAP) and len(t) < 160:
        node = new_node('subhead', None, l['page'])
        push(node)
        join_runs(node['runs'], runs)
        cur = node
        continue

    # ---- continuation or new unnumbered paragraph
    if cur is not None and (gap is None or gap <= GAP):
        join_runs(cur['runs'], runs)
        continue
    rank = 3 if x0 < 60 else 4
    node = new_node('note', None, l['page'], rank)
    push(node)
    join_runs(node['runs'], runs)
    cur = node

# ------------------------------------------------------------- footnotes
footnotes = []
for pg in PAGES:
    curfn = None
    for l in pg['foot']:
        runs = runs_from_chars(l['chars'])
        raw = ''.join(r['text'] for r in runs)
        if not raw.strip():
            continue
        first = next((r for r in runs if r['text'].strip()), None)
        if first is not None and first['sup'] and first['text'].strip().isdigit():
            num = first['text'].strip()
            k = raw.index(num) + len(num)
            curfn = {'num': num, 'runs': [], 'page': pg['page']}
            footnotes.append(curfn)
            join_runs(curfn['runs'], strip_n(runs, k))
            if curfn['runs']:
                curfn['runs'][0]['text'] = curfn['runs'][0]['text'].lstrip()
        elif curfn is not None:
            join_runs(curfn['runs'], runs)

raw_nontable = [''.join(c['c'] for c in l['chars'])
                for k, l in SEGMENTS if k == 'text']
raw_tables = []
for k, v in SEGMENTS:
    if k != 'table':
        continue
    raw_tables.append([''.join(c['c'] for c in seg['chars'])
                       for row in v['rows'] for cell in row['cells']
                       for seg in cell])
raw_foot = [''.join(c['c'] for c in l['chars'])
            for pg in PAGES for l in pg['foot']]

json.dump({'annexes': annexes, 'footnotes': footnotes,
           'raw_nontable': raw_nontable, 'raw_tables': raw_tables,
           'raw_foot': raw_foot},
          open(w('annexes.json'), 'w'), ensure_ascii=False, indent=1)

print('annexes:', len(annexes))
for a in annexes:
    print('  ', a['marker'], repr(a['title'])[:60], 'children', len(a['children']))
print('footnotes:', [f['num'] for f in footnotes])
ntab = sum(1 for k, _ in SEGMENTS if k == 'table')
print('tables:', ntab)

# diagnostics
def walk(n, depth=0, out=None):
    out = out if out is not None else []
    out.append(n)
    for c in n['children']:
        walk(c, depth + 1, out)
    return out
allnodes = [n for a in annexes for n in walk(a)]
print('nodes:', len(allnodes), collections.Counter(n['type'] for n in allnodes))
sus = [(n['type'], n['page'], ''.join(r['text'] for r in n['runs'])[:70])
       for n in allnodes
       if n['type'] in ('note', 'para', 'subhead', 'glossentry', 'bullet')
       and ''.join(r['text'] for r in n['runs'])[:1].islower()]
print('\nblocks starting lowercase (possible bad split):', len(sus))
for x in sus: print('   ', x)
long = [(n['type'], n['page'], len(''.join(r['text'] for r in n['runs'])))
        for n in allnodes if len(''.join(r['text'] for r in n['runs'])) > 1400]
print('very long blocks (possible bad merge):', long)
