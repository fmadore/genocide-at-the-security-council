"""The documentation states the numbers the pipeline commits, not older ones.

The corpus migration of September 2026 left the retired corpus's figures in the
README, in `docs/CORPUS.md` and in code comments that presented them as current
(docs/ROADMAP.md, RV27). These tests tie the few figures a reader quotes to the
files that define them, and keep the retired corpus's speech identifiers out of
the code, where they resolve to nothing.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from lib import lexicon
from lib.paths import EXPECTED_SPEECHES, EXPECTED_WORDS

ROOT = Path(__file__).resolve().parents[1]


def committed_genocide() -> tuple[int, int, int]:
    record = lexicon.load_counts()
    entry = record["terms"]["genocide"]
    return int(record["lexicon_version"]), int(entry["speeches"]), int(entry["occurrences"])


def test_the_readme_quotes_the_committed_counts() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    version, speeches, occurrences = committed_genocide()
    row = re.search(
        r"\(lexicon v(\d+)\) \| ([\d,]+) speeches · ([\d,]+) occurrences", readme
    )
    assert row, "the README's corpus table lost its genocide row"
    quoted = tuple(int(group.replace(",", "")) for group in row.groups())
    assert quoted == (version, speeches, occurrences)
    words = re.search(r"\| Analytical words \| ([\d,]+) \|", readme)
    assert words and int(words.group(1).replace(",", "")) == EXPECTED_WORDS
    assert f"{EXPECTED_SPEECHES:,}" in readme


def test_the_corpus_guide_quotes_the_committed_counts() -> None:
    corpus = (ROOT / "docs" / "CORPUS.md").read_text(encoding="utf-8")
    version, speeches, occurrences = committed_genocide()
    assert f"Lexicon v{version} finds" in corpus
    assert f"**{speeches:,} speeches**, with **{occurrences:,} occurrences**" in corpus
    assert f"| Project analytical words | {EXPECTED_WORDS:,} |" in corpus


def test_no_code_names_a_speech_of_the_retired_corpus() -> None:
    """`UNSC_1994_SPV.3377_spch0004` was the Schoenfeld corpus's file name; the
    Sakamoto-Matsuoka corpus names the same speech `SC03377-01-004`. A comment or
    example carrying the old form points a reader at nothing."""
    listed = subprocess.run(
        ["git", "ls-files", "scripts", "tools", "web/src"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    retired = re.compile(r"UNSC_\d{4}_(?:SPV|S_)")
    offenders = [
        name
        for name in listed
        if name.endswith((".py", ".ts", ".svelte", ".mjs"))
        and not name.endswith(".test.ts")
        and (ROOT / name).is_file()
        and retired.search((ROOT / name).read_text(encoding="utf-8"))
    ]
    assert offenders == []
