"""Nothing in a tracked file may identify a person, an account or a host.

This repository is meant to become public with a citable release, and the GPU
steps run on a university cluster behind a VPN. The failure mode is banal: a
command that worked gets pasted into the documentation with a real account name
still in it, and it is then in the history forever.

So the cluster is addressed only through an ssh alias the user defines in their
own `~/.ssh/config`, paths are built from `$USER` at runtime, and anything
machine-specific lives in `.env`, which is git-ignored. These tests are the
enforcement.

Third-party contact details are a different thing and are left alone: the corpus
authors' emails appear in `docs/CORPUS.md` and in the published paper under
`docs/reference/`, which is citation, not leakage.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Files whose whole purpose is to quote a third party.
EXEMPT = {
    "docs/CORPUS.md",
    "tests/test_privacy.py",
}
EXEMPT_PREFIXES = ("docs/reference/",)

SUSPECT = [
    (
        "university account id",
        # Bayreuth accounts are `bt` and six digits. Bounded on the left so that
        # ordinary words ending in "bt" cannot match.
        re.compile(r"\bbt\d{6}\b"),
    ),
    (
        "cluster hostname",
        re.compile(r"\b[\w.-]*\.(?:hpc\.)?uni-bayreuth\.de\b", re.IGNORECASE),
    ),
    (
        "ssh user@host",
        re.compile(r"\bssh\s+[\w.-]+@[\w.-]+", re.IGNORECASE),
    ),
    (
        "absolute Windows home directory",
        re.compile(r"[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_.-]+", re.IGNORECASE),
    ),
    (
        "absolute POSIX home directory",
        # /home/<user> and /Users/<user>, but not the $HOME and /home/<n>/<account>
        # placeholders the documentation uses.
        re.compile(r"(?<!\w)/(?:home|Users)/(?!<)[a-z][a-z0-9_.-]{2,}", re.IGNORECASE),
    ),
]


def tracked_text_files() -> list[str]:
    """Committed files, plus new ones that are not git-ignored.

    `--others --exclude-standard` is what makes this useful before a commit
    rather than after: a leak should fail the check while it is still a working
    copy, not once it is in the history. Ignored files — `.env`, `data/` — are
    excluded, which is exactly the point of ignoring them.
    """
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    keep = []
    for name in out:
        if name in EXEMPT or name.startswith(EXEMPT_PREFIXES):
            continue
        path = ROOT / name
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        keep.append(name)
    return keep


@pytest.fixture(scope="module")
def tracked() -> list[tuple[str, str]]:
    files = []
    for name in tracked_text_files():
        try:
            files.append((name, (ROOT / name).read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue  # binary
    return files


@pytest.mark.parametrize(("label", "pattern"), SUSPECT, ids=[s[0] for s in SUSPECT])
def test_no_identifying_strings(tracked, label: str, pattern: re.Pattern[str]) -> None:
    hits = []
    for name, text in tracked:
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = pattern.search(line)
            if match:
                hits.append(f"{name}:{line_number}: {match.group(0)}")
    assert not hits, f"{label} in tracked files:\n  " + "\n  ".join(hits)


def test_env_is_ignored_but_the_example_is_tracked() -> None:
    """The template is committed; the file it is copied to must never be."""
    tracked_names = set(tracked_text_files())
    assert ".env.example" in tracked_names, ".env.example should be committed"
    assert ".env" not in tracked_names, ".env must stay out of git — it holds cluster paths"
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()


def test_env_example_holds_no_values() -> None:
    """Every setting in the template is commented out.

    An uncommented value would be loaded by `scripts/cluster/env.sh` on every
    run, which is how a placeholder quietly becomes a default nobody chose.
    """
    live = [
        line
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert not live, f".env.example must be entirely commented out; found: {live}"
