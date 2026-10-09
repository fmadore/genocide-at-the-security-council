"""`referents.csv` read once, with one set of rules for every reader."""

from __future__ import annotations

from pathlib import Path

import pytest
from lib import audit, llm, referents
from lib.paths import REFERENTS as COMMITTED

HEADER = "id,label,description,kind,iso3,years,since,retired_in,superseded_by\n"
RESERVED = (
    "other,Other,Known,reserved,,,1,,\n"
    "unclear,Unclear,Unknown,reserved,,,1,,\n"
    "not_applicable,N/A,False positive,reserved,,,1,,\n"
)


def write(tmp_path: Path, body: str, header: str = HEADER) -> Path:
    path = tmp_path / "referents.csv"
    path.write_text(header + body, encoding="utf-8")
    return path


def test_the_three_views_of_the_committed_file_agree() -> None:
    parsed = referents.read(COMMITTED)
    listing = parsed.listing()
    prompt = {row.id for row in llm.read_referent_table(COMMITTED)}
    published = parsed.published()
    assert prompt == listing.current == audit.read_referents(COMMITTED)
    assert {row["id"] for row in published} == listing.all
    assert [row["id"] for row in published] == [row.id for row in parsed.rows]
    assert {row["id"] for row in published if row["retired"]} == set(listing.retired_in)


def test_a_retired_row_is_published_marked_and_left_out_of_the_prompt(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        RESERVED
        + "rwanda_1994,Rwanda 1994,Was,case,RWA,1994,1,2,rwanda\n"
        + "rwanda,Rwanda,Is,case,RWA,1994,2,,\n",
    )
    parsed = referents.read(path)
    published = {row["id"]: row for row in parsed.published()}
    assert published["rwanda_1994"] == {
        "id": "rwanda_1994",
        "label": "Rwanda 1994",
        "description": "Was",
        "kind": "case",
        "iso3": "RWA",
        "years": "1994",
        "since": 1,
        "retired_in": 2,
        "retired": True,
        "superseded_by": "rwanda",
    }
    assert published["rwanda"]["retired_in"] is None
    assert published["rwanda"]["retired"] is False
    assert [row.id for row in parsed.current()] == ["other", "unclear", "not_applicable", "rwanda"]
    assert parsed.listing().resolve("rwanda_1994") == "rwanda"
    assert parsed.version == 2


def test_a_file_without_the_later_columns_reads_as_it_meant_then(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "other,Other,Known\nunclear,Unclear,Unknown\nnot_applicable,N/A,False positive\n"
        "rwanda,Rwanda,Is\n",
        header="id,label,description\n",
    )
    parsed = referents.read(path)
    assert parsed.version == 1
    assert {row.id: row.kind for row in parsed.rows} == {
        "other": "reserved",
        "unclear": "reserved",
        "not_applicable": "reserved",
        "rwanda": "case",
    }
    # The prompt and the run check accept such a file; publishing needs the
    # columns the usage view shows, and says which are missing.
    with pytest.raises(referents.ReferentFileError, match="missing columns: iso3, kind"):
        parsed.published()


@pytest.mark.parametrize("column,value", [("since", "two"), ("retired_in", "0"), ("since", "-1")])
def test_a_bad_version_cell_is_a_named_error(tmp_path: Path, column: str, value: str) -> None:
    """Step 15's own reader turned `since = two` into a bare int() traceback."""
    cells = {"since": "1", "retired_in": ""} | {column: value}
    path = write(
        tmp_path, RESERVED + f"rwanda,Rwanda,Is,case,RWA,1994,{cells['since']},{cells['retired_in']},\n"
    )
    with pytest.raises(referents.ReferentFileError, match=rf"'rwanda' has a non-numeric {column}"):
        referents.read(path)


def test_every_reader_refuses_what_one_refuses(tmp_path: Path) -> None:
    """The prompt's reader used to accept a file the run check refused."""
    path = write(tmp_path, "other,Other,Known,reserved,,,1,,\n")
    for reader in (referents.read, audit.read_referent_list, llm.read_referent_table):
        with pytest.raises(ValueError, match="missing reserved IDs"):
            reader(path)


def test_a_version_cell_with_surrounding_space_is_read_by_every_view(tmp_path: Path) -> None:
    path = write(tmp_path, RESERVED + "rwanda,Rwanda,Is,case,RWA,1994, 2 , ,\n")
    parsed = referents.read(path)
    assert parsed.since["rwanda"] == 2
    assert parsed.published()[-1]["retired"] is False
