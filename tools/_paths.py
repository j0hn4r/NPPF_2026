"""Shared paths for the build pipeline.

Everything is resolved relative to the repository root, so the scripts work
from any working directory and on any machine.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / 'source' / 'nppf-august-2026.pdf'
WORK = ROOT / '.build'          # intermediate JSON; git-ignored
OUT = ROOT / 'index.html'       # the published page


def w(name):
    """Path to an intermediate file inside the (auto-created) work directory."""
    WORK.mkdir(exist_ok=True)
    return str(WORK / name)
