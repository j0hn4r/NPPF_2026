# National Planning Policy Framework — reading edition

The complete text of the **National Planning Policy Framework** (Ministry of
Housing, Communities and Local Government, August 2026) as a single self-contained
web page: the introduction, all nineteen policy chapters and Annexes A–F,
including the glossary and every annex table.

Generated from the official PDF and checked character-for-character against it.

## What the page does

- **Sidebar navigator** — chapters and all 131 policies (PM1–17, DM1–10, S1–6,
  CC1–3, HO1–13, E1–4, TC1–4, CO1–2, W1–4, M1–6, L1–3, GB1–8, DP1–4, TR1–8,
  HC1–8, P1–6, F1–9, N1–6, HE1–10), plus the annexes.
- **Plan-making / decision-making filter** — 52 plan-making policies, 79 national
  decision-making policies. The introduction and annexes stay visible, since the
  Framework designates them as neither.
- **S4/S5 refusal-policy highlight** — a sidebar checkbox marks the national
  decision-making policies which state that development proposals should be
  refused in specific circumstances, the class of policy that policies S4 and
  S5 refer to when describing when the presumption in favour of development is
  displaced.
- **Full-text search** with match highlighting, reaching into table cells and
  glossary definitions.
- **Footnotes 1–78** with markers exactly where they appear in the source; hover or
  tap for a popover, or read the list at the end of each chapter or annex.
- **A–Z jump bar** for the 129-term glossary in Annex B.
- Stable anchors for citation — `#PM1`, `#GB8-1-a-ii`, `#fn43`, `#g-grey-belt`.
- Light and dark themes, and a print stylesheet.

## Building

Requires Python 3.10+ and PyMuPDF. `poppler-utils` is optional and enables an
extra cross-check with a second PDF engine.

```bash
pip install -r requirements.txt
python tools/build.py
```

That rebuilds `index.html` from `source/nppf-august-2026.pdf` and then runs the
fidelity checks. It exits non-zero if anything fails.

```bash
python tools/build.py --no-verify     # build only
python tools/build.py --verify-only   # check the committed page
```

`index.html` is generated — do not edit it by hand. See [CLAUDE.md](CLAUDE.md) for
where each kind of change belongs, and for the bugs already fixed that are worth
not reintroducing.

## Continuous integration

`.github/workflows/build.yml` rebuilds from the PDF on every push and fails if the
committed `index.html` differs from a clean rebuild — which catches both a stale
page and a hand-edited one.

## Licence and attribution

The Framework text is © Crown copyright, reproduced under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
This repository is an unofficial reading edition and is not published by MHCLG;
for the authoritative document see
[GOV.UK](https://www.gov.uk/government/collections/revised-national-planning-policy-framework).
