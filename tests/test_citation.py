"""`CITATION.cff` holds the fields the Citation File Format requires.

A light check rather than `cffconvert`, which would be one more package in the
hash-pinned lock for a file that changes at each release (audit of 19 November
2026, item 61): the keys CFF 1.2 makes required, at the top and in every
reference, and none of the stale claims the audit found.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CITATION = Path(__file__).resolve().parents[1] / "CITATION.cff"


def load() -> dict:
    return yaml.safe_load(CITATION.read_text(encoding="utf-8"))


def test_the_required_keys_are_there() -> None:
    record = load()
    assert str(record["cff-version"]).startswith("1.2")
    for key in ("message", "title", "authors"):
        assert record.get(key), key
    assert all(author.get("family-names") or author.get("name") for author in record["authors"])


def test_every_reference_names_its_type_title_and_authors() -> None:
    for reference in load().get("references", []):
        for key in ("type", "title", "authors"):
            assert reference.get(key), f"{reference.get('title', '?')}: no {key}"


def test_no_published_run_is_called_unpublished() -> None:
    assert "not yet published" not in CITATION.read_text(encoding="utf-8")
