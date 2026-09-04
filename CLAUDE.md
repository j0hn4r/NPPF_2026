# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A single self-contained `index.html` holding the complete verbatim text of the
**National Planning Policy Framework (MHCLG, August 2026)**, generated from the
official PDF in `source/`. Published from the repo root via GitHub Pages.

## Commands

Setup (Python 3.10+; PyMuPDF is required, `poppler-utils` is optional and enables
an extra cross-check against a second PDF engine):

```bash
pip install -r requirements.txt
```

Build + verify — the only command needed for almost every change:

```bash
python tools/build.py
```

Variants, useful while iterating:

```bash
python tools/build.py --no-verify     # rebuild index.html only, skip fidelity checks
python tools/build.py --verify-only   # re-run checks against the already-committed index.html
```

There is no separate test framework — `verify.py` and `verify_annex.py` *are* the
tests, and `build.py` is the only entry point that runs the full pipeline plus
both in the right order. You can run one stage directly (e.g. `python
tools/annex.py`) to regenerate just its `.build/*.json` for quick inspection,
but always finish with a full `python tools/build.py` before committing — later
stages consume earlier stages' `.build/*.json` output, so a partial run leaves
them stale.

## The one rule that matters

**`index.html` is a build artefact. Never edit it by hand.**

It is ~640 KB of generated markup. Any manual change is silently destroyed by the
next build, and CI will fail the push because the committed file no longer matches
a clean rebuild. Every change goes into the pipeline and then:

```bash
python tools/build.py          # rebuild + verify (the only command you need)
```

If you are tempted to hand-edit because "it's just one word of text" — stop. The
text is not editorial content; it is the statutory wording of the Framework,
verified character-for-character against the PDF. If the page shows something
wrong, either the extraction is wrong (fix the pipeline) or the PDF says that.

## Layout

```
source/nppf-august-2026.pdf   the only input; do not replace without reading below
tools/extract.py              pages 5-100  -> .build/lines.json     span-level text
tools/parse.py                             -> .build/doc.json       chapter hierarchy
tools/annex.py                pages 101-130-> .build/annexes.json   annexes + tables
tools/render.py                            -> index.html            ALL design lives here
tools/verify.py               fidelity checks for chapters + rendered HTML
tools/verify_annex.py         fidelity checks for the annexes and their tables
tools/build.py                runs the lot, exits non-zero on any failure
```

`.build/` is git-ignored scratch. Delete it freely.

## Where to make a change

| You want to change… | Edit | Notes |
|---|---|---|
| Colours, type, spacing, layout, dark mode | `render.py` → the `CSS` string | One long stylesheet; tokens at the top |
| Page furniture (header, sidebar, buttons) | `render.py` → the `HTML` template | Keep the `__CSS__` / `__NAV__` / `__BODY__` / `__JS__` placeholders |
| Search, filter, footnote popovers, scroll-spy, bookmarks | `render.py` → the `JS` string | See the traps below |
| How a block type is marked up | `render.py` → `render_block`, `walk`, `render_annex_node` | Changing text content here will fail verification |
| Which pages are read | `extract.py` `START/END`, `annex.py` `START/END` | 0-based page indices |
| How hierarchy is detected | `parse.py` | Indent thresholds and marker regexes |
| Annex tables, glossary entries | `annex.py` | The trickiest code in the repo — read below |
| Which dm policies are tagged as "S4/S5 refusal policies" | `render.py` → `REFUSAL_POLICIES` | Hand-curated — see below |

## The S4/S5 refusal-policy highlight

Policies S4 and S5 displace the presumption in favour of development where a
proposal "would fail to comply with one of the national decision-making
policies which state that development proposals should be refused in specific
circumstances." The sidebar checkbox (`#refusalToggle`, toggling `body.
show-refusal`) highlights exactly those policies, tagged with
`data-refusal="1"` in both the document and the nav.

`REFUSAL_POLICIES` in `render.py` is a hand-curated set of policy codes — there
is no structural marker for this in the PDF, so it was built by reading every
national decision-making policy for mandatory refusal/non-approval language
("should be refused", "should not be approved ... except/unless"), and
deliberately excludes self-referential wording inside S4/S5 itself and
procedural "should not be approved without [steps]" clauses that aren't a
refusal test. **Re-derive this list by hand** against the new text whenever
the source PDF changes; nothing will fail verification if it drifts, since it
only adds an HTML attribute and doesn't touch any verified text.

## Bookmarks

Every policy, plus the "sections" of the introduction and of Annexes A and D
(the `secgrp`/`section-h` groupings — e.g. "Using the Framework", "The standard
method" — *not* the annex subheads/tables), has a star button that saves its
id to `localStorage` under the key `nppf-bookmarks` — per-browser, no backend.
A sidebar checkbox (`#bookmarkToggle`, toggling the module-level
`BOOKMARKS_ONLY` flag) filters the document down to just the bookmarked
policies/sections, composing with the existing plan-making / decision-making
filter (`MODE`) via the `.bhide` class, exactly parallel to how `.mhide`
implements that filter. See `deriveVisibility()`, `applyBookmarkFilter()` and
`syncBookmarkUI()` in the `JS` string.

Two independent identity attributes feed this: `.policy` divs and their nav
`<li>` keep the pre-existing `data-policy="{pid}"`; bookmarkable sections (and
*their* nav `<li>`) get a new `data-bm="{sid}"`, added in `render.py`'s
`walk()` (gated to chapter `'1'`, the introduction) and in `render_annex_node()`
(every annex `section`-type node — Annex A and D are the only annexes that
have any). `applyBookmarkFilter()` toggles `.bhide` by querying `[data-policy]`
and `[data-bm]` generically, so it doesn't care which kind of id it's hiding.
Every bookmarkable unit gets **two** star buttons sharing one
`data-bookmark="{id}"` — one on its own heading, one as a sibling of its `<a>`
in the nav (never nested inside it — buttons can't nest inside links). Both
are wired by one delegated `.bookmark-btn` click handler and kept in sync by
`syncBookmarkUI()`, which now does `querySelectorAll` (not `querySelector`)
precisely because there are two buttons per id.

Because sections can now be bookmarked, the introduction and the annexes are
**no longer unconditionally visible** the way they are under the plan-making /
decision-making filter — `deriveVisibility()`'s chapter-visibility check only
takes that `data-kind` shortcut when `BOOKMARKS_ONLY` is off; when it's on, an
intro/annex chapter shows only if it has a visible bookmarked policy or
section, same as any other chapter. Annexes B, C, E and F have no `section`-type
nodes at all (Annex B is glossentries, C is basically one table, E and F use
`subhead`, not `section`, for their sub-groupings) — under "bookmarks only"
they disappear entirely unless something in this list is re-scoped to make
them bookmarkable too.

**The bookmark button's markup must stay excluded from `verify.py`'s HTML
extraction.** It's interactive chrome (a star glyph + label), not document
text, so it's stripped by name (`<button ... class="bookmark-btn">...</button>`)
in the same place the `fnback` back-arrows are — before the generic
tag-stripping regex runs. This only matters for the *content-area* buttons:
the nav lives in `<aside>`, entirely outside the `<div id="noresults">…<div
class="footer">` region verify.py extracts, so nav bookmark buttons need no
exclusion of their own. Forgetting the content-area exclusion, or renaming the
class without updating the regex, makes every rendered-HTML fidelity check
fail with a `★`/`☆` glyph showing up in the diff.

## Traps that have already bitten us

Fixed bugs. Please do not reintroduce them.

- **Never call `scrollIntoView` on a nav link.** On narrow screens the nav sits in
  the page flow, so scrolling it into view scrolls the *document* and yanks the
  reader back to the index mid-paragraph. Use `revealInNav()`, which only touches
  `nav.scrollTop`.
- **`::selection` must not share a colour with the `:target` highlight.** When both
  were `--mark` yellow, selecting text over a highlighted policy showed no visible
  change and read as "copy/paste is broken". Selection is `--sel`; the landing
  marker is a fading `--flash` tint plus an accent margin bar.
- **Hyphens at line ends.** A line ending `-` is joined to the next with *no*
  space (`plan-` + `making` → `plan-making`) — but only when the character before
  the hyphen is not a space, or link text like `new system - GOV.UK` gets mangled.
- **Superscript `2` is not a footnote.** `m2` (square metres) appears in TC and
  flood-risk policies. A superscript digit is a footnote reference only if it is a
  known footnote number (1–78); everything else renders as a plain `<sup>`.
- **Table cells are merged into single text spans.** In the annex tables the PDF
  draws adjacent cells as one text object (`"Development Viability DM5: Development"`),
  so `annex.py` works at *character* level and splits on column boundaries taken
  from the drawn rules — and only where the characters either side are separated by
  whitespace or a positional gap. Splitting naively by span breaks Annex C; splitting
  at every boundary chops the centred header of Annex F Table 3 into fragments.
- **Tables continue across page breaks.** Annex C and Annex E's Purpose A table
  repeat their header row on the next page. `annex.py` merges them and drops the
  repeat. Two header rows are intentionally not in the output — this is why the
  pdftotext token cross-check reports a small, expected surplus on the PDF side.
- **The introduction and the annexes are always visible** under the plan-making /
  decision-making filter, because the document does not designate them as either.
  They carry `data-kind` and are skipped in `deriveVisibility()`.

## What the checks actually prove

`verify.py` and `verify_annex.py` are not smoke tests. Ignoring whitespace, they
assert exact character equality between:

1. the raw PDF line stream and the parsed tree (chapters: 191,241 chars; footnotes: 11,012)
2. the parsed tree and the text rendered into `index.html` (263,609 chars)
3. the annexes: non-table stream in order (51,773), all six tables cell-by-cell,
   annex footnotes (1,694), and a global character multiset (61,388)

Plus a cross-check against a second extraction engine (`pdftotext`), which is
skipped if poppler is not installed.

**A failure means real text drift.** Read the diff it prints — it shows the first
divergence with context on both sides. Do not "fix" a failure by loosening the
comparison.

Structural counts to sanity-check: 20 chapters, 6 annexes, **131 policies**,
129 glossary terms, 6 tables, **78 footnotes**, 0 duplicate element ids.

## Replacing the PDF with a newer Framework

The pipeline is tuned to this document's typography: 24pt chapter headings, 18pt
sections, 12pt body, 10pt footnotes, footnote rules at x≈48–192, and the indent
ladder 48 / 66 / 84 / 102. A new edition will almost certainly shift these. Expect
to re-derive them (dump font sizes and x-positions per line first) rather than
hoping the current constants hold. Do not trust a build that verifies but reports
different structural counts.

## Publishing

GitHub Pages serves `index.html` from the repo root. Commit the rebuilt page along
with whatever pipeline change produced it, in the same commit, so the repo is always
internally consistent.

```bash
python tools/build.py && git add -A && git commit -m "…"
```

`.github/workflows/build.yml` reruns the full build on every push and fails if the
committed `index.html` differs from a clean rebuild — the CI-side enforcement of
the one rule above.

## Line endings

The build writes LF. `.gitattributes` forces `eol=lf` on checkout so a rebuild on
Windows does not show up as a whole-file diff (and does not fail the CI check that
compares the committed page with a clean rebuild). Do not remove it.
