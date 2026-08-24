#!/usr/bin/env python3
"""Build index.html from the source PDF, then prove it matches the source.

    python tools/build.py            # build + verify  (the normal command)
    python tools/build.py --no-verify
    python tools/build.py --verify-only

Stages
    extract.py  pages 5-100   -> .build/lines.json      (span-level text)
    parse.py                  -> .build/doc.json        (chapter hierarchy)
    annex.py    pages 101-130 -> .build/annexes.json    (annexes + tables)
    render.py                 -> index.html
    verify.py / verify_annex.py                         (fidelity checks)

Exit status is non-zero if any stage or check fails, so CI and Claude Code
both notice.
"""
import subprocess, sys, shutil, time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
WORK = ROOT / '.build'

BUILD = ['extract.py', 'parse.py', 'annex.py', 'render.py']
CHECK = ['verify.py', 'verify_annex.py']


def run(script):
    print(f'\n\033[1m== {script}\033[0m', flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, str(TOOLS / script)], cwd=ROOT)
    if r.returncode != 0:
        print(f'\n\033[31mFAILED: {script} exited {r.returncode}\033[0m')
        sys.exit(r.returncode)
    print(f'   ({time.time() - t0:.1f}s)')


def pdftotext():
    """Optional: raw text from a second engine, for the cross-check in verify.py."""
    exe = shutil.which('pdftotext')
    if not exe:
        print('\n(pdftotext not found - the independent cross-check will be '
              'skipped; install poppler-utils to enable it)')
        return
    WORK.mkdir(exist_ok=True)
    subprocess.run([exe, str(ROOT / 'source' / 'nppf-august-2026.pdf'),
                    str(WORK / 'nppf_raw.txt')], check=True)


def main():
    args = set(sys.argv[1:])
    if not (ROOT / 'source' / 'nppf-august-2026.pdf').exists():
        sys.exit('source/nppf-august-2026.pdf is missing - the build needs it.')

    if '--verify-only' not in args:
        for s in BUILD:
            run(s)
        size = (ROOT / 'index.html').stat().st_size
        print(f'\nindex.html written: {size:,} bytes')

    if '--no-verify' not in args:
        pdftotext()
        for s in CHECK:
            run(s)
        print('\n\033[32mAll fidelity checks passed.\033[0m')


if __name__ == '__main__':
    main()
