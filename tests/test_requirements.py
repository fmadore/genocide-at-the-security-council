"""The lock still satisfies the ranges it was generated from.

`requirements.lock` is what CI installs and `requirements.txt` is what a
maintainer edits; nothing tied the two together, so a range could be moved
without the lock following, and the review of 1 September 2026 (§6.4) asked
for the check. Every range in the two range files must be met by exactly one
pin in the lock.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def ranges(path: Path) -> list[Requirement]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-r"):
            continue
        out.append(Requirement(line))
    return out


def pins(path: Path) -> dict[str, Version]:
    """`name==version` per package; the hash continuation lines are skipped."""
    out: dict[str, Version] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        match = re.match(r"^([A-Za-z0-9_.\-\[\]]+)==([^\s\;]+)", line)
        if match:
            out[canonicalize_name(match.group(1).split("[")[0])] = Version(match.group(2))
    return out


@pytest.mark.parametrize("path", ["requirements.txt", "requirements-dev.txt"])
def test_every_range_is_met_by_the_lock(path: str) -> None:
    locked = pins(ROOT / "requirements.lock")
    missing = []
    outside = []
    for requirement in ranges(ROOT / path):
        name = canonicalize_name(requirement.name)
        if name not in locked:
            missing.append(requirement.name)
        elif not requirement.specifier.contains(locked[name], prereleases=True):
            outside.append(f"{requirement} (locked {locked[name]})")
    assert not missing, f"not in requirements.lock: {missing}"
    assert not outside, f"lock outside the declared range: {outside}"
