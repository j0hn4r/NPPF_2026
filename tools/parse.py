import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import PDF, WORK, OUT, w
import json, re, sys

pages = json.load(open(w('lines.json')))

RANK = {'chapter': 0, 'section': 1, 'objective': 1, 'policy': 2,
        'para': 3, 'item': 4, 'subitem': 5, 'subsubitem': 6}

ROMAN = r'(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)'
RE_NUM = re.compile(r'^(\d+)\.\s')
RE_LET = re.compile(r'^([a-z])\.\s')
RE_ROM = re.compile(r'^(' + ROMAN + r')\.\s')
RE_POL = re.compile(r'^([A-Z]{1,3}\d{1,2}):\s')


def line_text(runs):
    return ''.join(r['text'] for r in runs)


def indent_level(x0):
    if x0 < 50:
        return 0
    if x0 < 60:
        return 'obj'
    if x0 < 76:
        return 1
    if x0 < 96:
        return 2
    return 3


def strip_prefix(runs, n):
    """Drop the first n characters across the run list."""
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


def append_runs(dst, new):
    """Append a new line's runs to dst, applying join rules."""
    if dst:
        prev = ''.join(r['text'] for r in dst)
        nxt = ''.join(r['text'] for r in new).lstrip()
        if prev.endswith(' '):
            pass  # already separated
        elif prev.endswith('-') and len(prev) >= 2 and not prev[-2].isspace():
            pass  # hyphenated compound split across lines -> no space
        elif prev == '':
            pass
        else:
            dst.append({'text': ' ', 'b': False, 'i': False, 'sup': False,
                        'href': None, 'size': 12})
        # left-strip the incoming first run
        new = [dict(r) for r in new]
        for r in new:
            if r['text'].strip() == '':
                r['text'] = ''
            else:
                r['text'] = r['text'].lstrip()
                break
    dst.extend(dict(r) for r in new if r['text'] != '')


chapters = []
stack = []          # list of (type, node)
unclassified = []
FOOTREF_SEEN = set()


def new_node(kind, marker, runs, page):
    return {'type': kind, 'marker': marker, 'runs': list(runs),
            'children': [], 'page': page}


def push(node):
    r = RANK[node['type']]
    while stack and (RANK[stack[-1]['type']] >= r or
                     stack[-1]['type'] == 'objective'):
        stack.pop()
    if not stack:
        chapters.append(node)
    else:
        stack[-1]['children'].append(node)
    stack.append(node)


cur = None   # node currently accumulating text

for pg in pages:
    for ln in pg['body']:
        runs = ln['runs']
        txt = line_text(runs)
        stripped = txt.strip()
        if not stripped:
            continue
        lvl = indent_level(ln['x0'])
        size = ln['size']
        bold_start = next((r['b'] for r in runs if r['text'].strip()), False)

        # ---- chapter heading (24pt)
        if size >= 22:
            if cur is not None and cur['type'] == 'chapter' and lvl != 0:
                append_runs(cur['runs'], runs)   # wrapped chapter title
                cur['title'] = ''.join(r['text'] for r in cur['runs']).strip()
                continue
            m = re.match(r'^(\d+)\.\s*(.*)$', stripped)
            num, title = (m.group(1), m.group(2)) if m else (None, stripped)
            node = new_node('chapter', num, [], ln['page'])
            node['title'] = title
            stack.clear()
            push(node)
            node['runs'] = [{'text': title, 'b': True, 'i': False,
                             'sup': False, 'href': None, 'size': 24}]
            cur = node
            continue

        # ---- section heading (18pt)
        if size >= 16:
            if cur is not None and cur['type'] == 'section' and \
               (not stack or stack[-1] is cur):
                # possible wrapped section heading
                pass
            node = new_node('section', None, runs, ln['page'])
            push(node)
            cur = node
            continue

        # ---- objective box text
        if lvl == 'obj':
            if cur is not None and cur['type'] == 'objective':
                append_runs(cur['runs'], runs)
            else:
                node = new_node('objective', None, [], ln['page'])
                push(node)
                append_runs(node['runs'], runs)
                cur = node
            continue

        # ---- policy heading
        if lvl == 0 and bold_start and RE_POL.match(stripped):
            m = RE_POL.match(stripped)
            node = new_node('policy', m.group(1), [], ln['page'])
            push(node)
            append_runs(node['runs'], strip_prefix(runs, txt.index(':') + 2))
            if node['runs']:
                node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
            cur = node
            continue

        # wrapped policy heading (bold, level 0, current node is a policy)
        if lvl == 0 and bold_start and cur is not None and cur['type'] == 'policy':
            append_runs(cur['runs'], runs)
            continue

        # ---- numbered paragraph
        if lvl == 0 and RE_NUM.match(stripped):
            m = RE_NUM.match(stripped)
            node = new_node('para', m.group(1), [], ln['page'])
            push(node)
            append_runs(node['runs'], strip_prefix(runs, txt.index('.') + 1))
            if node['runs']:
                node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
            cur = node
            continue

        # ---- lettered item
        if lvl == 1 and RE_LET.match(stripped):
            m = RE_LET.match(stripped)
            node = new_node('item', m.group(1), [], ln['page'])
            push(node)
            append_runs(node['runs'], strip_prefix(runs, txt.index('.') + 1))
            if node['runs']:
                node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
            cur = node
            continue

        # ---- roman sub-item
        if lvl == 2 and RE_ROM.match(stripped):
            m = RE_ROM.match(stripped)
            node = new_node('subitem', m.group(1), [], ln['page'])
            push(node)
            append_runs(node['runs'], strip_prefix(runs, txt.index('.') + 1))
            if node['runs']:
                node['runs'][0]['text'] = node['runs'][0]['text'].lstrip()
            cur = node
            continue

        # ---- continuation
        if cur is not None:
            append_runs(cur['runs'], runs)
        else:
            unclassified.append((ln['page'], stripped[:80]))

# ---------------- footnotes ----------------
footnotes = []
for pg in pages:
    curfn = None
    for ln in pg['foot']:
        runs = ln['runs']
        txt = line_text(runs)
        if not txt.strip():
            continue
        first = next((r for r in runs if r['text'].strip()), None)
        m = re.match(r'^(\d{1,3})\s', txt) or re.match(r'^(\d{1,3})(?=\S)', txt)
        if first is not None and first['sup'] and first['text'].strip().isdigit():
            num = first['text'].strip()
            curfn = {'num': num, 'runs': [], 'page': pg['page']}
            footnotes.append(curfn)
            rest = [r for r in runs if r is not first]
            append_runs(curfn['runs'], rest)
        elif curfn is not None:
            append_runs(curfn['runs'], runs)
        else:
            unclassified.append((pg['page'], 'FOOTNOTE?? ' + txt[:70]))

json.dump({'chapters': chapters, 'footnotes': footnotes},
          open(w('doc.json'), 'w'), ensure_ascii=False, indent=1)

print('chapters', len(chapters))
for c in chapters:
    print('  ', c['marker'], repr(c.get('title'))[:60], 'children', len(c['children']))
print('footnotes', len(footnotes), [f['num'] for f in footnotes])
print('unclassified', len(unclassified))
for u in unclassified[:40]:
    print('   ', u)
