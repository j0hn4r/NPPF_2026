# -*- coding: utf-8 -*-
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import PDF, WORK, OUT, w
import json, re, html

doc = json.load(open(w('doc.json')))
adoc = json.load(open(w('annexes.json')))
chapters = doc['chapters']
annexes = adoc['annexes']
footnotes = {f['num']: f for f in doc['footnotes']}
footnotes.update({f['num']: f for f in adoc['footnotes']})
FN_NUMS = set(footnotes)

# National decision-making policies that state development proposals "should
# be refused" (or equivalently "should not be approved") in specific
# circumstances -- the class of policy that policies S4 and S5 refer to when
# describing when the presumption in favour of development is displaced.
# Curated by reading every dm policy for that mandatory-refusal language;
# there is no structural marker in the PDF for this, so this list must be
# re-checked by hand against the new text whenever the source PDF changes.
REFUSAL_POLICIES = {
    'TC3',   # sequential test failure / significant adverse impact under TC4
    'DP3',   # conflict with the design principles in paragraphs 1-2
    'TR6',   # severe impact on the transport network or highway safety
    'HC5',   # hot food takeaways near schools / adding to a harmful concentration
    'M5',    # peat extraction; coal or onshore oil and gas without necessity
    'L3',    # development that fails to make efficient use of land
    'GB6',   # inappropriate development in the Green Belt
    'F6',    # use incompatible with flood risk / failing the exception test
    'F7',    # development that is not safe from flooding
    'N2',    # unavoidable, unmitigated, uncompensated harm to biodiversity
    'N4',    # major development in Protected Landscapes without exceptional circumstances
    'N6',    # harm to a habitats site, or loss of irreplaceable habitats
    'HE6',   # substantial harm to, or total loss of, a designated heritage asset
}

fn_owner = {}          # footnote num -> chapter marker (where referenced)
fn_modes = {}          # footnote num -> set of modes referencing it
current_chapter = [None]
current_mode = ['both']


def mode_of(chapter_marker, section_title):
    if chapter_marker == '2':
        return 'pm'
    if chapter_marker == '3':
        return 'dm'
    t = (section_title or '').strip().lower()
    if t.startswith('plan-making policies'):
        return 'pm'
    if t.startswith('national decision-making policies'):
        return 'dm'
    return 'both'


def norm(t):
    t = t.replace(' ', ' ')
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t


def runs_html(runs, allow_fn=True):
    out = []
    prev_char = ''
    for r in runs:
        t = norm(r['text'])
        if t == '':
            continue
        esc = html.escape(t)
        stripped = t.strip()
        if r['sup'] and stripped.isdigit() and stripped in FN_NUMS and \
                prev_char.lower() != 'm' and allow_fn:
            n = stripped
            fn_owner.setdefault(n, current_chapter[0])
            fn_modes.setdefault(n, set()).add(current_mode[0])
            out.append(
                f'<sup class="fnref"><a href="#fn{n}" id="fnref{n}" '
                f'data-fn="{n}">{n}</a></sup>')
            trail = t[len(t.rstrip()):]
            if trail:
                out.append(' ')
            prev_char = ''
            continue
        if r['sup'] and stripped.isdigit():
            esc = f'<sup>{esc.strip()}</sup>'
        if r['b']:
            esc = f'<strong>{esc}</strong>'
        if r['i']:
            esc = f'<em>{esc}</em>'
        if r['href']:
            esc = (f'<a class="ext" href="{html.escape(r["href"], quote=True)}" '
                   f'target="_blank" rel="noopener">{esc}</a>')
        out.append(esc)
        if stripped:
            prev_char = stripped[-1]
    s = ''.join(out)
    s = re.sub(r'^\s+|\s+$', '', s)
    return s


def plain(runs):
    return norm(''.join(r['text'] for r in runs)).strip()


MK = {'para': lambda m: f'{m}.', 'item': lambda m: f'{m}.',
      'subitem': lambda m: f'{m}.'}


def render_block(node, ids, out):
    kind = node['type']
    if kind == 'para':
        nid = ids + '-' + node['marker'] if ids else 'p' + node['marker']
    elif kind == 'item':
        nid = ids + '-' + node['marker']
    elif kind == 'subitem':
        nid = ids + '-' + node['marker']
    else:
        nid = ids
    cls = {'para': 'para', 'item': 'item', 'subitem': 'subitem'}[kind]
    out.append(f'<div class="node {cls}" id="{nid}" data-page="{node["page"]}">')
    out.append('<div class="row">')
    out.append(f'<span class="mk">{MK[kind](node["marker"])}</span>')
    out.append(f'<div class="tx srch">{runs_html(node["runs"])}</div>')
    out.append('</div>')
    if node['children']:
        out.append('<div class="kids">')
        for ch in node['children']:
            render_block(ch, nid, out)
        out.append('</div>')
    out.append('</div>')


def fnmode(n):
    m = fn_modes.get(n, set())
    return m.pop() if len(m) == 1 else 'both'


nav = []
body = []

POL_MODE = {}

for ch in chapters:
    current_chapter[0] = ch['marker']
    current_mode[0] = mode_of(ch['marker'], None)
    cid = 'ch' + ch['marker']
    kindattr = ' data-kind="intro"' if ch['marker'] == '1' else ''
    body.append(f'<section class="chapter" id="{cid}" data-ch="{ch["marker"]}"'
                f'{kindattr} data-chmode="{mode_of(ch["marker"], None)}">')
    body.append(f'<h1 class="chapter-h"><span class="cn">{ch["marker"]}.</span> '
                f'<span class="srch">{html.escape(norm(ch["title"]))}</span></h1>')
    navpolicies = []
    navsections = []

    st = {'section': False, 'policy': False}

    def close_policy():
        if st['policy']:
            body.append('</div>')
            st['policy'] = False

    def close_section():
        close_policy()
        if st['section']:
            body.append('</div>')
            st['section'] = False

    def walk(nodes):
      for node in nodes:
          k = node['type']
          if k == 'objective':
              close_policy()
              body.append('<div class="objective srch">' +
                          runs_html(node['runs']) + '</div>')
          elif k == 'section':
              close_section()
              title = plain(node['runs'])
              sid = cid + '-s' + str(len(navsections) + 1)
              navsections.append((sid, title))
              current_mode[0] = mode_of(ch['marker'], title)
              body.append(f'<div class="secgrp" id="{sid}" '
                          f'data-mode="{current_mode[0]}">')
              body.append(f'<h2 class="section-h srch">{html.escape(title)}</h2>')
              st['section'] = True
              walk(node['children'])
          elif k == 'policy':
              close_policy()
              pid = node['marker']
              title = plain(node['runs'])
              navpolicies.append((pid, title, current_mode[0]))
              POL_MODE[pid] = current_mode[0]
              refusal_attr = ' data-refusal="1"' if pid in REFUSAL_POLICIES else ''
              body.append(f'<div class="policy" id="{pid}" data-policy="{pid}" '
                          f'data-mode="{current_mode[0]}"{refusal_attr} '
                          f'data-page="{node["page"]}">')
              body.append(f'<h3 class="policy-h"><span class="policy-title">'
                          f'<span class="pid">{pid}:</span> '
                          f'<span class="srch">{html.escape(title)}</span></span>'
                          f'<button type="button" class="bookmark-btn" data-bookmark="{pid}" '
                          f'aria-pressed="false" aria-label="Bookmark {pid}">&#9734;</button></h3>')
              st['policy'] = True
              for sub in node['children']:
                  render_block(sub, pid, body)
          elif k == 'para':
              render_block(node, cid, body)
          else:
              raise SystemExit('unexpected ' + k)

    walk(ch['children'])
    close_section()

    # ---- chapter footnotes
    fns = [n for n, o in fn_owner.items() if o == ch['marker']]
    fns.sort(key=int)
    if fns:
        body.append('<div class="fnlist"><h4>Footnotes</h4>')
        for n in fns:
            body.append(
                f'<div class="fn" id="fn{n}" data-mode="{fnmode(n)}">'
                f'<span class="fnn">{n}</span>'
                f'<div class="tx srch">{runs_html(footnotes[n]["runs"], allow_fn=False)}'
                f' <a class="fnback" href="#fnref{n}" title="back to text">&#8617;</a>'
                f'</div></div>')
        body.append('</div>')
    body.append('</section>')

    # ---- nav entry
    nav.append(f'<li class="nav-ch" data-chmode="{mode_of(ch["marker"], None)}"'
               f'{kindattr}>'
               f'<a href="#{cid}" class="navlink chlink" '
               f'data-target="{cid}"><span class="cn">{ch["marker"]}</span>'
               f'{html.escape(norm(ch["title"]))}</a>')
    if navpolicies:
        nav.append('<ul class="nav-pol">')
        for pid, title, pmode in navpolicies:
            refusal_attr = ' data-refusal="1"' if pid in REFUSAL_POLICIES else ''
            nav.append(f'<li data-mode="{pmode}" data-policy="{pid}"{refusal_attr}>'
                       f'<a href="#{pid}" class="navlink" data-target="{pid}">'
                       f'<span class="pid">{pid}</span>'
                       f'{html.escape(title)}</a></li>')
        nav.append('</ul>')
    elif navsections:
        nav.append('<ul class="nav-pol">')
        for sid, title in navsections:
            nav.append(f'<li data-mode="both"><a href="#{sid}" class="navlink" '
                       f'data-target="{sid}">{html.escape(title)}</a></li>')
        nav.append('</ul>')
    nav.append('</li>')


# =====================================================================
#                            annexes
# =====================================================================
AMK = {'para': lambda m: f'{m}.', 'item': lambda m: f'{m}.',
       'subitem': lambda m: f'{m}.', 'bullet': lambda m: '&bull;'}


def slug(t):
    t = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')
    return t[:60] or 'x'


def cell_html(cell):
    out = []
    run = []
    for para in cell['paras']:
        if para['bullet']:
            run.append(f'<li>{runs_html(para["runs"])}</li>')
        else:
            if run:
                out.append('<ul>' + ''.join(run) + '</ul>')
                run = []
            out.append(f'<p>{runs_html(para["runs"])}</p>')
    if run:
        out.append('<ul>' + ''.join(run) + '</ul>')
    return ''.join(out) or '&nbsp;'


def table_html(node, out):
    out.append('<div class="tblwrap"><table class="tbl">')
    if node['header']:
        out.append('<thead>')
        for row in node['header']:
            out.append('<tr>')
            for c in row:
                sp = f' colspan="{c["span"]}"' if c['span'] > 1 else ''
                out.append(f'<th{sp} class="srch">{cell_html(c)}</th>')
            out.append('</tr>')
        out.append('</thead>')
    out.append('<tbody>')
    for row in node['rows']:
        out.append('<tr>')
        for c in row:
            sp = f' colspan="{c["span"]}"' if c['span'] > 1 else ''
            out.append(f'<td{sp} class="srch">{cell_html(c)}</td>')
        out.append('</tr>')
    out.append('</tbody></table></div>')


def render_annex_node(n, path, out, navsub, idx=0):
    k = n['type']
    if k == 'section':
        title = plain(n['runs'])
        sid = path + '-' + slug(title)
        navsub.append((sid, title))
        out.append(f'<div class="secgrp" data-mode="both" id="{sid}">')
        out.append(f'<h2 class="section-h srch">{html.escape(title)}</h2>')
        for i, c in enumerate(n['children']):
            render_annex_node(c, sid, out, navsub, i)
        out.append('</div>')
        return
    if k == 'subhead':
        title = plain(n['runs'])
        sid = path + '-' + slug(title)
        if title.lower().startswith('table '):
            navsub.append((sid, title.split(':')[0]))
        out.append(f'<div class="subgrp" id="{sid}">')
        out.append(f'<h3 class="subhead srch">{runs_html(n["runs"])}</h3>')
        for i, c in enumerate(n['children']):
            render_annex_node(c, sid, out, navsub, i)
        out.append('</div>')
        return
    if k == 'table':
        table_html(n, out)
        return
    if k == 'glossentry':
        term = plain(n['termruns'])
        gid = 'g-' + slug(term)
        out.append(f'<div class="node gloss" id="{gid}" data-term="{html.escape(term, quote=True)}" '
                   f'data-page="{n["page"]}"><div class="row"><div class="tx srch">'
                   f'<span class="term">{runs_html(n["termruns"])}</span>: '
                   f'{runs_html(n["runs"])}</div></div>')
        if n['children']:
            out.append('<div class="kids">')
            for i, c in enumerate(n['children']):
                render_annex_node(c, gid, out, navsub, i)
            out.append('</div>')
        out.append('</div>')
        return
    # para / item / subitem / bullet / note
    mk = AMK[k](n['marker']) if k in AMK else None
    # NB: must be deterministic - CI compares the committed page with a rebuild
    nid = path + '-' + (n['marker'] if n['marker'] and k != 'bullet'
                        else 'b' + str(idx))
    cls = {'para': 'para', 'item': 'item', 'subitem': 'subitem',
           'bullet': 'bullet', 'note': 'note'}[k]
    out.append(f'<div class="node {cls}" id="{nid}" data-page="{n["page"]}">')
    out.append('<div class="row">')
    if mk:
        out.append(f'<span class="mk">{mk}</span>')
    out.append(f'<div class="tx srch">{runs_html(n["runs"])}</div>')
    out.append('</div>')
    if n['children']:
        out.append('<div class="kids">')
        for i, c in enumerate(n['children']):
            render_annex_node(c, nid, out, navsub, i)
        out.append('</div>')
    out.append('</div>')


annex_nav = []
for an in annexes:
    current_chapter[0] = an['marker']
    current_mode[0] = 'both'
    aid = 'annex' + an['marker']
    body.append(f'<section class="chapter annex" id="{aid}" data-kind="annex" '
                f'data-chmode="both">')
    body.append(f'<h1 class="chapter-h"><span class="cn">Annex {an["marker"]}</span> '
                f'<span class="srch">{html.escape(norm(an["title"]))}</span></h1>')
    navsub = []
    inner = []
    for i, c in enumerate(an['children']):
        render_annex_node(c, aid, inner, navsub, i)
    if an['marker'] == 'B':
        letters = []
        seen = set()
        for c in an['children']:
            if c['type'] != 'glossentry':
                continue
            ltr = plain(c['termruns'])[:1].upper()
            if ltr and ltr not in seen:
                seen.add(ltr)
                letters.append((ltr, 'g-' + slug(plain(c['termruns']))))
        body.append('<div class="azbar">' + ''.join(
            f'<a href="#{i}">{l}</a>' for l, i in letters) + '</div>')
    body.extend(inner)

    fns = [n for n, o in fn_owner.items() if o == an['marker']]
    fns.sort(key=int)
    if fns:
        body.append('<div class="fnlist" data-mode="both"><h4>Footnotes</h4>')
        for n in fns:
            body.append(
                f'<div class="fn" id="fn{n}" data-mode="both">'
                f'<span class="fnn">{n}</span>'
                f'<div class="tx srch">{runs_html(footnotes[n]["runs"], allow_fn=False)}'
                f' <a class="fnback" href="#fnref{n}" title="back to text">&#8617;</a>'
                f'</div></div>')
        body.append('</div>')
    body.append('</section>')

    annex_nav.append(f'<li class="nav-ch" data-chmode="both" data-kind="annex">'
                     f'<a href="#{aid}" class="navlink chlink" data-target="{aid}">'
                     f'<span class="cn">{an["marker"]}</span>'
                     f'{html.escape(norm(an["title"]))}</a>')
    if navsub:
        annex_nav.append('<ul class="nav-pol">')
        for sid, title in navsub:
            annex_nav.append(f'<li data-mode="both"><a href="#{sid}" class="navlink" '
                             f'data-target="{sid}">{html.escape(title)}</a></li>')
        annex_nav.append('</ul>')
    annex_nav.append('</li>')

nav.append('<li class="navgroup">Annexes</li>')
nav.extend(annex_nav)

# footnote tooltip data
fndata = {n: runs_html(footnotes[n]['runs'], allow_fn=False) for n in footnotes}

CSS = r"""
/* ============================================================
   National Planning Policy Framework — reading edition
   Warm paper ground, white page column, serif text, one accent.
   ============================================================ */
:root{
  color-scheme: light dark;
  --paper:#f6f4ef;  --card:#fffdfa;
  --ink:#171614;    --ink2:#544f49;  --ink3:#8a847a;
  --rule:#e6e1d6;   --rule2:#d3ccbd;
  --accent:#2d5044; --accent2:#44705e; --tint:#eaefec;
  --mark:#f6e7a6;   --marktx:#3b3005;
  --sel:#bfd9cb;    --seltx:#0f221a;  --flash:#e6ede9;
  --refusal:#a5502e; --refusaltint:#f4e8e0;
  --star:#b8860b;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,ui-serif,serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --fs:16.5px; --lh:1.66; --line:calc(var(--fs) * var(--lh));
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#141618; --card:#1a1d1f;
    --ink:#e8e5df;   --ink2:#a59f97;  --ink3:#7a746b;
    --rule:#292c2f;  --rule2:#3a3e42;
    --accent:#8dc4ad;--accent2:#a4d4bf;--tint:#1e2523;
    --mark:#4b3f13;  --marktx:#f4ecd3;
    --sel:#3a5b4d;   --seltx:#f0f6f2;  --flash:#232d29;
    --refusal:#d98a6e; --refusaltint:#2b211d;
    --star:#e3b54c;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);
  font:var(--fs)/var(--lh) var(--serif);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
::selection{background:var(--sel);color:var(--seltx)}
:focus-visible{outline:2px solid var(--accent2);outline-offset:2px;border-radius:2px}
.wrap{display:flex;min-height:100vh;align-items:flex-start}

/* ---------- reading-progress hairline ---------- */
#prog{position:fixed;top:0;left:0;height:2px;width:0;background:var(--accent);
  z-index:80;transition:width .08s linear;opacity:.85}

/* ---------- sidebar ---------- */
aside{width:306px;flex:0 0 306px;position:sticky;top:0;height:100vh;
  background:var(--paper);border-right:1px solid var(--rule);
  display:flex;flex-direction:column;font-family:var(--sans)}
.brand{padding:24px 24px 17px;margin:0 0 16px;border-bottom:1px solid var(--rule)}
.eyebrow{font:600 9.5px/1.5 var(--sans);letter-spacing:.16em;text-transform:uppercase;
  color:var(--ink3)}
.brand h1{margin:7px 0 0;font:400 17px/1.28 var(--serif);letter-spacing:-.005em;color:var(--ink)}
.brand p{margin:6px 0 0;font-size:11.5px;line-height:1.45;color:var(--ink2)}

.modebar{display:flex;margin:0 24px;border:1px solid var(--rule2);border-radius:3px;
  overflow:hidden;background:var(--card)}
.modebar button{flex:1;padding:7px 2px 6px;font:600 10.5px/1.3 var(--sans);
  letter-spacing:.055em;color:var(--ink2);background:none;border:0;
  border-right:1px solid var(--rule);cursor:pointer;white-space:nowrap;
  transition:color .13s,background .13s}
.modebar button:last-child{border-right:0}
.modebar button:hover{color:var(--accent);background:var(--tint)}
.modebar button.on{color:var(--accent);background:var(--tint);
  box-shadow:inset 0 -2px 0 var(--accent)}

.refusalbar{display:flex;align-items:center;gap:8px;margin:12px 24px 0;
  font:500 11px/1.35 var(--sans);color:var(--ink2);cursor:pointer}
.refusalbar input{accent-color:var(--refusal);width:13px;height:13px;flex:0 0 auto;
  cursor:pointer}
.refusalbar:hover{color:var(--ink)}

.bookmarkbar{display:flex;align-items:center;gap:8px;margin:8px 24px 0;
  font:500 11px/1.35 var(--sans);color:var(--ink2);cursor:pointer}
.bookmarkbar input{accent-color:var(--star);width:13px;height:13px;flex:0 0 auto;
  cursor:pointer}
.bookmarkbar:hover{color:var(--ink)}
.bookmarkbar .bmcount{margin-left:auto;font:600 10px/1 var(--sans);color:var(--ink3);
  background:var(--tint);border-radius:8px;padding:2px 7px}

.searchbox{position:relative;margin:16px 24px 0;border-bottom:1px solid var(--rule2)}
.searchbox input{width:100%;padding:7px 22px 7px 19px;font:400 13.5px/1.4 var(--sans);
  color:var(--ink);background:none;border:0;outline:none}
.searchbox input::placeholder{color:var(--ink3)}
.searchbox:focus-within{border-bottom-color:var(--accent)}
.searchbox .ico{position:absolute;left:0;top:50%;transform:translateY(-50%);
  color:var(--ink3);font-size:12px;pointer-events:none}
.searchbox .clr{position:absolute;right:0;top:50%;transform:translateY(-50%);
  border:0;background:none;color:var(--ink3);font-size:15px;cursor:pointer;
  display:none;padding:0 2px;line-height:1}
.searchbox .clr:hover{color:var(--accent)}
#count{display:none;padding:8px 24px 0;font:500 10.5px/1.4 var(--sans);
  letter-spacing:.09em;text-transform:uppercase;color:var(--accent2)}

nav{overflow-y:auto;overscroll-behavior:contain;padding:16px 14px 48px;flex:1;
  scrollbar-width:thin}
.navtoggle{display:none}
nav ul{list-style:none;margin:0;padding:0}
nav .navlink{position:relative;display:block;text-decoration:none;color:var(--ink2);
  padding:4px 10px 4px 12px;font-size:12.5px;line-height:1.38;
  border-left:2px solid transparent;transition:color .12s,border-color .12s}
nav .chlink{color:var(--ink);font-weight:600;font-size:12.5px;margin-top:12px;
  letter-spacing:.005em}
nav .navlink:hover{color:var(--accent)}
nav .navlink.active{color:var(--accent);border-left-color:var(--accent);font-weight:600}
nav .cn{display:inline-block;min-width:22px;color:var(--ink3);
  font-variant-numeric:tabular-nums;font-weight:500}
nav .chlink.active .cn,nav .navlink.active .pid{color:var(--accent)}
nav .pid{display:inline-block;min-width:42px;color:var(--accent2);font-weight:600;
  font-size:11px;letter-spacing:.04em}
nav .nav-pol{margin:1px 0 2px 12px;padding-left:0}
nav .navgroup{margin:22px 12px 6px;font:600 9.5px/1.5 var(--sans);letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink3);border-top:1px solid var(--rule);padding-top:12px}
nav li.hide,section.hide,.policy.hide,.node.hide,.secgrp.hide,.fnlist.hide,
.tblwrap.hide,.subgrp.hide,.azbar.hide{display:none}
.mhide{display:none !important}
.bhide{display:none !important}

/* ---------- the page ---------- */
main{flex:1;min-width:0;background:var(--paper);padding:0 0 90px}
.doc{max-width:872px;margin:0 auto;background:var(--card);
  border-inline:1px solid var(--rule);padding:52px 62px 0}

.docmeta{padding-bottom:26px;border-bottom:1px solid var(--rule2)}
.docmeta .doctitle{margin:8px 0 0;font:400 31px/1.16 var(--serif);letter-spacing:-.014em;
  text-wrap:balance}
.docmeta .docsub{margin:9px 0 0;font:400 14.5px/1.5 var(--serif);color:var(--ink2);
  font-style:italic}
.docmeta .sub{margin:20px 0 0;font:500 10.5px/1.5 var(--sans);letter-spacing:.1em;
  text-transform:uppercase;color:var(--ink3)}
.docmeta .sub.filtered{color:var(--accent)}
.docmeta .scope{margin:18px 0 0;padding-left:16px;border-left:2px solid var(--rule2);
  font-size:14px;line-height:1.62;color:var(--ink2)}

/* ---------- chapters ---------- */
section.chapter{padding-top:56px;scroll-margin-top:0}
.chapter-h{margin:0 0 4px;padding-bottom:14px;border-bottom:1px solid var(--ink);
  font:400 26px/1.22 var(--serif);letter-spacing:-.012em;text-wrap:balance}
.chapter-h .cn{color:var(--accent);font-weight:400}
section.annex .chapter-h .cn{font:600 11px/1 var(--sans);letter-spacing:.16em;
  text-transform:uppercase;display:block;margin-bottom:9px;color:var(--ink3)}

.objective{margin:26px 0 6px;padding:2px 0 2px 20px;border-left:2px solid var(--accent2);
  font-style:italic;font-size:15.5px;line-height:1.6;color:var(--ink2)}

.section-h{margin:44px 0 2px;font:600 10.5px/1.5 var(--sans);letter-spacing:.15em;
  text-transform:uppercase;color:var(--accent);padding-bottom:8px;
  border-bottom:1px solid var(--rule)}
.secgrp{margin:0}

/* ---------- policies ---------- */
.policy{margin:30px 0 0;padding-top:22px;border-top:1px solid var(--rule)}
.secgrp>.policy:first-of-type{border-top:0;padding-top:6px}
.policy-h{margin:0 0 14px;font:600 18px/1.34 var(--serif);letter-spacing:-.006em;
  display:flex;align-items:flex-start;gap:12px}
.policy-h .policy-title{flex:1 1 auto;min-width:0;text-wrap:pretty}
.policy-h .pid{display:inline-block;margin-right:.45em;font:700 11.5px/1 var(--sans);
  letter-spacing:.1em;color:var(--accent);vertical-align:2.5px}
.bookmark-btn{flex:0 0 auto;margin-top:.15em;padding:2px 4px;border:0;border-radius:3px;
  background:none;color:var(--rule2);font-size:16px;line-height:1;cursor:pointer;
  transition:color .13s,background .13s}
.bookmark-btn:hover{color:var(--accent2);background:var(--tint)}
.bookmark-btn.on{color:var(--star)}
.bookmark-btn.on:hover{color:var(--star)}
nav li.bookmarked .pid{color:var(--star)}
[id]{scroll-margin-top:26px}

/* landing marker: a persistent accent bar in the margin plus a background that
   fades away, so it never competes with the text-selection colour */
@keyframes landing{from{background:var(--flash)}to{background:transparent}}
.policy,.node>.row,.fn{position:relative}
.policy:target,.node:target>.row,.fn:target{animation:landing 2.8s ease-out 1}
.policy:target::before,.node:target>.row::before,.fn:target::before{
  content:'';position:absolute;left:-17px;top:1px;bottom:1px;width:2px;
  background:var(--accent);border-radius:1px}
@media (prefers-reduced-motion:reduce){
  .policy:target,.node:target>.row,.fn:target{animation:none;background:var(--flash)}
}

/* S4/S5 refusal-policy highlight, toggled by the sidebar checkbox */
body.show-refusal .policy[data-refusal]{background:var(--refusaltint)}
body.show-refusal .policy[data-refusal]::after{
  content:'';position:absolute;left:-17px;top:1px;bottom:1px;width:2px;
  background:var(--refusal);border-radius:1px}
body.show-refusal .policy[data-refusal] .policy-h,
body.show-refusal .policy[data-refusal] .policy-h .pid{color:var(--refusal)}
body.show-refusal nav li[data-refusal] .pid{color:var(--refusal)}

/* ---------- numbered / lettered structure ---------- */
.node{margin:0}
.node>.row{display:flex;gap:13px;margin:11px 0}
.node>.row>.mk{flex:0 0 26px;text-align:right;color:var(--ink3);
  font:500 12.5px/var(--line) var(--sans);font-variant-numeric:tabular-nums}
.item>.row>.mk{flex-basis:20px}
.subitem>.row>.mk{flex-basis:26px}
.bullet>.row>.mk{flex-basis:13px;color:var(--accent2);text-align:left;
  font-size:15px;font-family:var(--serif)}
.node>.row>.tx{flex:1;min-width:0;text-wrap:pretty}
.kids{margin-left:39px}
.subitem .kids{margin-left:26px}
.subhead{margin:30px 0 4px;font:600 15px/1.4 var(--serif);color:var(--ink)}
.subgrp{margin:0}

/* ---------- footnotes ---------- */
sup.fnref{font-size:.68em;line-height:0}
sup.fnref a{text-decoration:none;font-weight:600;padding:0 .5px;color:var(--accent);
  font-family:var(--sans)}
sup.fnref a:hover{background:var(--mark);color:var(--marktx);border-radius:2px}
.fnlist{margin:38px 0 0;padding-top:14px;border-top:1px solid var(--rule2)}
.fnlist h4{margin:0 0 10px;font:600 9.5px/1.5 var(--sans);letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink3)}
.fn{display:flex;gap:11px;margin:7px 0;font-size:13px;line-height:1.55;color:var(--ink2)}
.fn .fnn{flex:0 0 22px;text-align:right;color:var(--accent2);font:600 11px/1.72 var(--sans);
  font-variant-numeric:tabular-nums}
.fnback{text-decoration:none;opacity:.45;font-size:.9em}
.fnback:hover{opacity:1}
a.ext{word-break:break-word;color:var(--accent);text-decoration:underline;
  text-decoration-color:var(--rule2)}
a.ext:hover{text-decoration-color:var(--accent)}
mark{background:var(--mark);color:var(--marktx);padding:0 .08em;border-radius:1px}

/* ---------- glossary ---------- */
.azbar{display:flex;flex-wrap:wrap;gap:1px;margin:24px 0 4px;padding:9px 0;
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  background:var(--card);position:sticky;top:0;z-index:6}
.azbar a{display:inline-block;min-width:23px;text-align:center;padding:2px 3px;
  font:600 11.5px/1.4 var(--sans);letter-spacing:.05em;color:var(--ink2);
  text-decoration:none;border-radius:2px}
.azbar a:hover{background:var(--accent);color:var(--card)}
.gloss{padding:13px 0;border-bottom:1px solid var(--rule)}
.gloss:last-child{border-bottom:0}
.gloss .term{font-weight:600;color:var(--accent)}
#annexB .gloss[id]{scroll-margin-top:56px}

/* ---------- tables ---------- */
.tblwrap{overflow-x:auto;margin:18px 0 22px;border:1px solid var(--rule2)}
table.tbl{width:100%;border-collapse:collapse;font:14px/1.52 var(--serif)}
table.tbl th,table.tbl td{border:1px solid var(--rule);padding:9px 12px;
  vertical-align:top;text-align:left}
table.tbl thead th{background:var(--tint);color:var(--accent);
  font:600 10.5px/1.45 var(--sans);letter-spacing:.1em;text-transform:uppercase;
  border-bottom:1px solid var(--rule2)}
table.tbl thead th p{margin:0}
table.tbl tbody td:first-child{font-weight:600;color:var(--ink)}
table.tbl p{margin:0 0 8px}
table.tbl p:last-child{margin-bottom:0}
table.tbl ul{margin:6px 0 8px;padding-left:16px}
table.tbl ul:last-child{margin-bottom:0}
table.tbl li{margin:3px 0}
table.tbl li::marker{color:var(--ink3)}

/* ---------- footnote popover ---------- */
#pop{position:absolute;z-index:60;max-width:420px;background:var(--ink);
  color:var(--card);font:13px/1.55 var(--serif);padding:11px 14px;border-radius:4px;
  box-shadow:0 10px 30px rgba(0,0,0,.22);display:none}
#pop .pn{float:left;margin:1px 8px 0 0;font:600 10.5px/1.6 var(--sans);letter-spacing:.08em}
#pop .pn a{color:var(--accent2);text-decoration:none}
#pop a{color:#cfe6da}
@media (prefers-color-scheme: dark){
  #pop{background:#0e1011;color:var(--ink);box-shadow:0 10px 30px rgba(0,0,0,.6);
    border:1px solid var(--rule2)}
}

.noresults{display:none;padding:52px 0;text-align:center;color:var(--ink3);font-style:italic}
.footer{margin:64px 0 0;padding:20px 0 46px;border-top:1px solid var(--rule);
  font-size:12px;line-height:1.6;color:var(--ink3)}
.footer em{font-style:italic}

@media (max-width:1000px){
  .wrap{display:block}
  aside{position:static;width:auto;height:auto;flex:none;border-right:0;
    border-bottom:1px solid var(--rule2);padding-bottom:14px}
  .brand{padding:18px 20px 14px}
  .brand h1{font-size:16px}
  .modebar,.searchbox{margin-inline:20px}
  .navtoggle{display:flex;align-items:center;justify-content:space-between;gap:10px;
    width:calc(100% - 40px);margin:14px 20px 0;padding:9px 12px;
    font:600 10.5px/1.3 var(--sans);letter-spacing:.13em;text-transform:uppercase;
    color:var(--accent);background:var(--card);border:1px solid var(--rule2);
    border-radius:3px;cursor:pointer}
  .navtoggle::after{content:'\25be';font-size:11px;letter-spacing:0;line-height:1}
  body.nav-open .navtoggle::after{content:'\25b4'}
  nav{display:none;max-height:60vh;padding:12px 6px 20px}
  body.nav-open nav{display:block}
  .doc{padding:26px 20px 0;border-inline:0}
  .kids{margin-left:22px}
  .docmeta .doctitle{font-size:25px}
  .chapter-h{font-size:22px}
}
@media print{
  aside,#prog,.azbar{display:none}
  body{background:#fff;font-size:10.5pt}
  .doc{max-width:none;border:0;padding:0}
  .policy,.node,table.tbl,.fnlist{break-inside:avoid}
  sup.fnref a{color:#000}
}
"""

JS = r"""
const FN = __FNDATA__;

/* ---------- footnote popover ---------- */
const pop = document.getElementById('pop');
let popTimer = null;
function showPop(a){
  const n = a.dataset.fn;
  if(!FN[n]) return;
  pop.innerHTML = '<span class="pn"><a href="#fn'+n+'" title="go to footnote list">'+n+'</a></span>'+FN[n];
  pop.style.display='block';
  const r = a.getBoundingClientRect();
  const pw = pop.offsetWidth, ph = pop.offsetHeight;
  let left = window.scrollX + r.left - pw/2 + r.width/2;
  left = Math.max(window.scrollX+8, Math.min(left, window.scrollX+document.documentElement.clientWidth-pw-8));
  let top = window.scrollY + r.top - ph - 10;
  if(top < window.scrollY+6) top = window.scrollY + r.bottom + 10;
  pop.style.left = left+'px'; pop.style.top = top+'px';
}
function hidePop(){ pop.style.display='none'; }
document.addEventListener('mouseover', e=>{
  const a = e.target.closest('sup.fnref a');
  if(a){ clearTimeout(popTimer); showPop(a); }
});
document.addEventListener('mouseout', e=>{
  if(e.target.closest('sup.fnref a')){ popTimer = setTimeout(hidePop, 180); }
});
pop.addEventListener('mouseenter', ()=>clearTimeout(popTimer));
pop.addEventListener('mouseleave', hidePop);
document.addEventListener('click', e=>{
  const a = e.target.closest('sup.fnref a');
  if(a){ e.preventDefault(); clearTimeout(popTimer);
         if(pop.style.display==='block' && pop.dataset.for===a.dataset.fn){ hidePop(); }
         else { showPop(a); pop.dataset.for = a.dataset.fn; } }
  else if(!e.target.closest('#pop')) hidePop();
});

/* ---------- plan-making / decision-making filter ---------- */
let MODE = 'all';
const modeBtns = Array.from(document.querySelectorAll('.modebar button'));
const sub = document.getElementById('sub');

function deriveVisibility(){
  document.querySelectorAll('section.chapter').forEach(c=>{
    const vis = (MODE === 'all' && !BOOKMARKS_ONLY) || !!c.dataset.kind
                || !!c.querySelector('.policy:not(.mhide):not(.bhide)');
    c.classList.toggle('mhide', !vis);
    const li = document.querySelector('nav li.nav-ch[data-chmode] a[data-target="'+c.id+'"]');
    if(li) li.parentElement.classList.toggle('mhide', !vis);
  });
  document.querySelectorAll('.fnlist').forEach(f=>{
    f.classList.toggle('mhide', !f.querySelector('.fn:not(.mhide)'));
  });
}

function applyMode(m){
  MODE = m;
  modeBtns.forEach(b=>b.classList.toggle('on', b.dataset.setmode === m));
  document.querySelectorAll('[data-mode]').forEach(el=>{
    const dm = el.dataset.mode;
    el.classList.toggle('mhide', m !== 'all' && dm !== 'both' && dm !== m);
  });
  deriveVisibility();
  if(sub){ sub.innerHTML = sub.dataset[m]; sub.classList.toggle('filtered', m !== 'all'); }
  hidePop();
  const q = input.value.trim();
  if(q.length >= 2) run(input.value); else clearAll();
}
modeBtns.forEach(b=>b.addEventListener('click', ()=>applyMode(b.dataset.setmode)));

/* ---------- S4/S5 refusal-policy highlight ---------- */
const refusalToggle = document.getElementById('refusalToggle');
refusalToggle.addEventListener('change', ()=>{
  document.body.classList.toggle('show-refusal', refusalToggle.checked);
});

/* ---------- bookmarks (saved to this browser only, via localStorage) ---------- */
let BOOKMARKS;
try { BOOKMARKS = new Set(JSON.parse(localStorage.getItem('nppf-bookmarks')) || []); }
catch(e){ BOOKMARKS = new Set(); }
let BOOKMARKS_ONLY = false;
const bookmarkToggle = document.getElementById('bookmarkToggle');
const bmCount = document.getElementById('bmCount');

function saveBookmarks(){
  try { localStorage.setItem('nppf-bookmarks', JSON.stringify(Array.from(BOOKMARKS))); }
  catch(e){ /* storage unavailable (private mode, quota) - bookmarks just won't persist */ }
}

function syncBookmarkUI(pid){
  const on = BOOKMARKS.has(pid);
  const btn = document.querySelector('.bookmark-btn[data-bookmark="'+pid+'"]');
  if(btn){ btn.classList.toggle('on', on); btn.setAttribute('aria-pressed', on ? 'true' : 'false');
           btn.textContent = on ? '★' : '☆'; }
  const navLi = document.querySelector('nav li[data-policy="'+pid+'"]');
  if(navLi) navLi.classList.toggle('bookmarked', on);
}

function applyBookmarkFilter(){
  document.querySelectorAll('.policy[data-policy]').forEach(p=>{
    p.classList.toggle('bhide', BOOKMARKS_ONLY && !BOOKMARKS.has(p.dataset.policy));
  });
  document.querySelectorAll('nav li[data-policy]').forEach(li=>{
    li.classList.toggle('bhide', BOOKMARKS_ONLY && !BOOKMARKS.has(li.dataset.policy));
  });
  deriveVisibility();
  hidePop();
  const q = input.value.trim();
  if(q.length >= 2) run(input.value); else clearAll();
}

document.querySelectorAll('.bookmark-btn').forEach(btn=>{
  const pid = btn.dataset.bookmark;
  syncBookmarkUI(pid);
  btn.addEventListener('click', ()=>{
    if(BOOKMARKS.has(pid)) BOOKMARKS.delete(pid); else BOOKMARKS.add(pid);
    saveBookmarks();
    syncBookmarkUI(pid);
    bmCount.textContent = BOOKMARKS.size;
    if(BOOKMARKS_ONLY) applyBookmarkFilter();
  });
});
bmCount.textContent = BOOKMARKS.size;
bookmarkToggle.addEventListener('change', ()=>{
  BOOKMARKS_ONLY = bookmarkToggle.checked;
  applyBookmarkFilter();
});

/* ---------- search ---------- */
const searchable = Array.from(document.querySelectorAll('.srch'));
searchable.forEach(el => el.dataset.orig = el.innerHTML);
const input = document.getElementById('q');
const clr = document.getElementById('clr');
const count = document.getElementById('count');
const nores = document.getElementById('noresults');

function esc(s){ return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }

function clearAll(){
  searchable.forEach(el => { if(el.dataset.hit) { el.innerHTML = el.dataset.orig; delete el.dataset.hit; } });
  document.querySelectorAll('.hide').forEach(el=>el.classList.remove('hide'));
  count.style.display='none'; nores.style.display='none'; clr.style.display='none';
  deriveVisibility();
}

function highlight(el, re){
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const nodes = []; let n;
  while(n = walker.nextNode()) nodes.push(n);
  let hits = 0;
  nodes.forEach(node=>{
    const t = node.nodeValue;
    if(!re.test(t)) return;
    re.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0, m;
    while((m = re.exec(t))){
      frag.appendChild(document.createTextNode(t.slice(last, m.index)));
      const mk = document.createElement('mark'); mk.textContent = m[0];
      frag.appendChild(mk); hits++; last = m.index + m[0].length;
      if(m[0].length === 0) re.lastIndex++;
    }
    frag.appendChild(document.createTextNode(t.slice(last)));
    node.parentNode.replaceChild(frag, node);
  });
  return hits;
}

function run(q){
  clearAll();
  q = q.trim();
  if(q.length < 2){ return; }
  clr.style.display='block';
  const re = new RegExp(esc(q), 'gi');
  let total = 0;
  searchable.forEach(el=>{
    if(el.closest('.mhide') || el.closest('.bhide')) return;
    if(new RegExp(esc(q),'i').test(el.textContent)){
      el.dataset.hit = '1';
      total += highlight(el, new RegExp(esc(q),'gi'));
    }
  });
  /* hide blocks with no hits */
  document.querySelectorAll('.node').forEach(b=>{
    if(!b.querySelector('mark')) b.classList.add('hide');
  });
  document.querySelectorAll('.policy').forEach(p=>{
    if(!p.querySelector('mark')) p.classList.add('hide');
  });
  document.querySelectorAll('.objective,.fnlist,.tblwrap,.subgrp,.azbar').forEach(o=>{
    if(!o.querySelector('mark')) o.classList.add('hide');
  });
  document.querySelectorAll('.secgrp').forEach(s=>{
    if(!s.querySelector('mark')) s.classList.add('hide');
  });
  document.querySelectorAll('section.chapter').forEach(c=>{
    const on = !!c.querySelector('mark');
    if(!on) c.classList.add('hide');
    if(c.classList.contains('mhide')) return;
    const link = document.querySelector('nav .chlink[data-target="'+c.id+'"]');
    if(link) link.parentElement.classList.toggle('hide', !on);
  });
  document.querySelectorAll('nav .nav-pol a').forEach(a=>{
    const p = document.getElementById(a.dataset.target);
    a.parentElement.classList.toggle('hide', !p || p.classList.contains('hide'));
  });
  document.querySelectorAll('.fnlist').forEach(f=>{
    if(!f.querySelector('mark')) f.classList.add('hide');
  });
  count.style.display='block';
  count.textContent = total ? total + ' match' + (total===1?'':'es') : 'No matches';
  nores.style.display = total ? 'none' : 'block';
}

let t=null;
input.addEventListener('input', ()=>{ clearTimeout(t); t=setTimeout(()=>run(input.value), 140); });
clr.addEventListener('click', ()=>{ input.value=''; clearAll(); input.focus(); });
document.addEventListener('keydown', e=>{
  if((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==='f'){ e.preventDefault(); input.focus(); input.select(); }
  if(e.key==='Escape'){ if(document.activeElement===input){ input.value=''; clearAll(); } hidePop(); }
});

/* ---------- contents panel on narrow screens ---------- */
const navEl = document.querySelector('nav');
const navBtn = document.getElementById('navtoggle');
const narrow = () => !window.matchMedia('(min-width:1001px)').matches;
function setNav(open){
  document.body.classList.toggle('nav-open', open);
  if(navBtn) navBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
}
if(navBtn) navBtn.addEventListener('click', ()=>setNav(!document.body.classList.contains('nav-open')));
navEl.addEventListener('click', e=>{
  const a = e.target.closest('a.navlink');
  if(!a || !narrow()) return;
  e.preventDefault();
  setNav(false);
  requestAnimationFrame(()=>{ location.hash = a.dataset.target; });
});

/* ---------- active nav on scroll ---------- */
const targets = Array.from(document.querySelectorAll('section.chapter, .policy'));
const links = new Map();
document.querySelectorAll('nav .navlink').forEach(a=>links.set(a.dataset.target, a));
/* Keep the active link visible by scrolling the nav's own box only.
   scrollIntoView() would scroll the document too, which on narrow screens
   (nav in the page flow) yanks the reader back up to the index. */
function revealInNav(a){
  if(navEl.scrollHeight <= navEl.clientHeight + 2) return;   // nav isn't scrolling
  const nb = a.getBoundingClientRect(), nr = navEl.getBoundingClientRect(), pad = 10;
  if(nb.top < nr.top + pad) navEl.scrollTop -= (nr.top + pad - nb.top);
  else if(nb.bottom > nr.bottom - pad) navEl.scrollTop += (nb.bottom - (nr.bottom - pad));
}
const io = new IntersectionObserver(entries=>{
  entries.forEach(en=>{
    if(!en.isIntersecting) return;
    const a = links.get(en.target.id);
    if(!a) return;
    document.querySelectorAll('nav .navlink.active').forEach(x=>x.classList.remove('active'));
    a.classList.add('active');
    revealInNav(a);
  });
}, {rootMargin:'-10% 0px -80% 0px', threshold:0});
targets.forEach(t=>io.observe(t));

/* ---------- reading progress ---------- */
const prog = document.getElementById('prog');
let raf = null;
function updateProg(){
  const h = document.documentElement;
  const max = h.scrollHeight - h.clientHeight;
  prog.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
  raf = null;
}
window.addEventListener('scroll', ()=>{ if(!raf) raf = requestAnimationFrame(updateProg); },
                        {passive:true});
window.addEventListener('resize', updateProg);
updateProg();

applyMode('all');
"""

HTML = """<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>National Planning Policy Framework &mdash; August 2026</title>
<style>__CSS__</style>
</head>
<body>
<div id="prog"></div>
<div class="wrap">
<aside>
  <div class="brand">
    <h1>National Planning Policy Framework</h1>
    <p>Plan-making and national decision-making policies<br>August&nbsp;2026</p>
  </div>
  <div class="modebar" role="group" aria-label="Filter by policy type">
    <button type="button" data-setmode="all" class="on">All</button>
    <button type="button" data-setmode="pm" title="Plan-making policies only">Plan-making</button>
    <button type="button" data-setmode="dm" title="National decision-making policies only">Decision-making</button>
  </div>
  <label class="refusalbar" for="refusalToggle"
         title="Policies S4 and S5: national decision-making policies which state that development proposals should be refused in specific circumstances">
    <input type="checkbox" id="refusalToggle">
    <span>Highlight S4/S5 refusal policies</span>
  </label>
  <label class="bookmarkbar" for="bookmarkToggle"
         title="Show only the policies you've bookmarked (saved in this browser)">
    <input type="checkbox" id="bookmarkToggle">
    <span>Bookmarks only</span>
    <span class="bmcount" id="bmCount">0</span>
  </label>
  <div class="searchbox">
    <span class="ico">&#9906;</span>
    <input id="q" type="search" placeholder="Search the Framework&hellip;" autocomplete="off" spellcheck="false">
    <button class="clr" id="clr" title="Clear">&times;</button>
  </div>
  <div id="count"></div>
  <button type="button" class="navtoggle" id="navtoggle" aria-expanded="false"
          aria-controls="nav">Contents</button>
  <nav id="nav"><ul class="nav-root">__NAV__</ul></nav>
</aside>
<main>
  <div class="doc">
    <div class="docmeta">
      <div class="eyebrow">Ministry of Housing, Communities &amp; Local Government</div>
      <div class="doctitle">National Planning Policy Framework</div>
      <div class="docsub">Plan-making and national decision-making policies &middot; August 2026</div>
    </div>
    <div id="noresults" class="noresults">Nothing matches that search.</div>
__BODY__
    <div class="footer">Source: <em>National Planning Policy Framework &mdash; Plan-making and
    national decision-making policies</em>, Ministry of Housing, Communities and Local Government,
    August 2026. &copy; Crown copyright. Text reproduced under the Open Government Licence v3.0.</div>
  </div>
</main>
</div>
<div id="pop"></div>
<script>__JS__</script>
</body>
</html>
"""

NPOL = len(re.findall(r'class="policy" id=', '\n'.join(body)))
N_PM = sum(1 for v in POL_MODE.values() if v == 'pm')
N_DM = sum(1 for v in POL_MODE.values() if v == 'dm')
out = (HTML.replace('__CSS__', CSS).replace('__NPOL__', str(NPOL))
           .replace('__NPM__', str(N_PM)).replace('__NDM__', str(N_DM))
           .replace('__NAV__', '\n'.join(nav))
           .replace('__BODY__', '\n'.join(body))
           .replace('__JS__', JS.replace('__FNDATA__', json.dumps(fndata, ensure_ascii=False))))

open(str(OUT), 'w').write(out)
print('written', len(out), 'bytes')
print('footnote owners:', {k: v for k, v in sorted(fn_owner.items(), key=lambda x: int(x[0]))})
missing = FN_NUMS - set(fn_owner)
print('footnotes never referenced in body:', sorted(missing, key=int))

json.dump(fn_owner, open(w('fn_owner.json'),'w'))
