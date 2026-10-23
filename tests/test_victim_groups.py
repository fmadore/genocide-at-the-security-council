"""`victim_groups.csv`: the model's free-text victim groups, grouped by a checked table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from lib import referents, victim_groups
from lib.paths import REFERENTS

COMMITTED = REFERENTS.parent / "victim_groups.csv"
HEADER = "label,referent,group,checked\n"


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "victim_groups.csv"
    path.write_text("# a comment line\n" + HEADER + body, encoding="utf-8")
    return path


def test_the_lookup_form_sets_aside_case_a_leading_article_and_spacing() -> None:
    assert victim_groups.key("The  Jewish people ") == "jewish people"
    assert victim_groups.key("the Tutsi in Rwanda") == "tutsi in rwanda"
    # Only a leading article, and only "the": "our people" is a different label.
    assert victim_groups.key("our people") == "our people"
    assert victim_groups.key("people of the Sudan") == "people of the sudan"


def test_two_spellings_of_one_people_share_a_group(tmp_path: Path) -> None:
    table = victim_groups.read(write(tmp_path, "jewish people,,Jews,no\njews,,Jews,yes\n"))
    assert table.group("the Jewish people") == table.group("Jews") == "Jews"


def test_a_referent_row_wins_and_the_plain_row_is_the_fallback(tmp_path: Path) -> None:
    table = victim_groups.read(
        write(
            tmp_path,
            "muslims,,Muslims (unspecified),no\nmuslims,india_muslims,Muslims in India,no\n",
        )
    )
    assert table.group("Muslims", "india_muslims") == "Muslims in India"
    assert table.group("the Muslims", "other") == "Muslims (unspecified)"


def test_a_label_the_table_does_not_list_is_left_ungrouped(tmp_path: Path) -> None:
    table = victim_groups.read(write(tmp_path, "jews,,Jews,no\n"))
    assert table.group("an authentic civilization") == ""
    assert table.group("") == ""


@pytest.mark.parametrize(
    ("body", "rule"),
    [
        ("Jews,,Jews,no\n", "lookup form"),
        ("jews,,,no\n", "both a label and a group"),
        ("jews,,Jews,maybe\n", "not yes or no"),
        ("jews,,Jews,no\njews,,Jewish people,no\n", "listed twice"),
    ],
)
def test_a_row_that_would_make_a_label_mean_two_things_is_refused(
    tmp_path: Path, body: str, rule: str
) -> None:
    with pytest.raises(victim_groups.VictimGroupError, match=rule):
        victim_groups.read(write(tmp_path, body))


def test_the_review_list_counts_every_label_under_its_lookup_form(tmp_path: Path) -> None:
    table = victim_groups.read(write(tmp_path, "jews,,Jews,no\n"))
    rows = victim_groups.review_rows(
        table, [("Jews", "holocaust"), ("the Jews", "holocaust"), ("Hazaras", ""), ("", "")]
    )
    assert rows == [
        {
            "label": "jews",
            "occurrences": 2,
            "grouped": 2,
            "group": "Jews",
            "spellings": "Jews | the Jews",
        },
        {"label": "hazaras", "occurrences": 1, "grouped": 0, "group": "", "spellings": "Hazaras"},
    ]


def test_the_committed_table_reads_and_names_only_referents_the_list_holds() -> None:
    table = victim_groups.read(COMMITTED)
    known = {row.id for row in referents.read(REFERENTS).rows}
    named = {referent for _, referent in table.rows if referent}
    assert named <= known
    # The pair FM raised on 23 October 2026.
    assert table.group("the Jewish people") == table.group("Jews")


def occurrences(*rows: tuple[str, str, str, str, bool]) -> pd.DataFrame:
    """(victim_group, referent, speaker, date, eligible) per occurrence."""
    columns = ["victim_group", "referent", "country_org", "date", "verdict", "evidence_valid"]
    return pd.DataFrame(
        [
            {
                "victim_group": label,
                "referent": referent,
                "country_org": speaker,
                "date": date,
                "verdict": "true_positive" if eligible else "false_positive",
                "evidence_valid": True,
            }
            for label, referent, speaker, date, eligible in rows
        ],
        columns=columns,
    )


def test_the_victims_block_puts_every_eligible_row_in_one_of_four_classes(
    tmp_path: Path,
) -> None:
    table = victim_groups.read(
        write(
            tmp_path,
            "jews,,Jews,yes\njewish people,,Jews,no\ncivilians,,Civilians (unspecified),no\n",
        )
    )
    block = victim_groups.victims_block(
        occurrences(
            ("Jews", "holocaust", "Israel", "1948-05-01", True),
            ("the Jewish people", "holocaust", "Israel", "1951-02-01", True),
            ("civilians", "gaza", "Algeria", "2023-11-01", True),
            ("an authentic civilization", "other", "Jordan", "1957-01-01", True),
            ("", "genocide_convention_law", "France", "2023-01-01", True),
            # A false positive names no victim and is not counted at all.
            ("Jews", "holocaust", "Israel", "1948-05-01", False),
        ),
        table,
    )
    assert block["table"] == {"rows": 3, "checked": 1}
    assert block["groups"] == [
        {"group": "Jews", "unspecified": False, "count": 2, "actors": 1},
        {"group": "Civilians (unspecified)", "unspecified": True, "count": 1, "actors": 1},
    ]
    decades = {row["decade"]: row for row in block["decades"]}  # type: ignore[index]
    assert decades[1940] == {
        "decade": 1940,
        "eligible": 1,
        "people": 1,
        "unspecified": 0,
        "ungrouped": 0,
        "none": 0,
    }
    assert decades[1950]["ungrouped"] == 1 and decades[1950]["people"] == 1
    # Every decade from the first to the last, zero-filled.
    assert sorted(decades) == [1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]
    assert decades[1980]["eligible"] == 0
    assert decades[2020] == {
        "decade": 2020,
        "eligible": 2,
        "people": 0,
        "unspecified": 1,
        "ungrouped": 0,
        "none": 1,
    }
    assert block["cells"] == [
        {"group": "Jews", "decade": 1940, "count": 1},
        {"group": "Jews", "decade": 1950, "count": 1},
        {"group": "Civilians (unspecified)", "decade": 2020, "count": 1},
    ]
    assert block["by_actor"] == [
        {"group": "Civilians (unspecified)", "actor": "Algeria", "count": 1},
        {"group": "Jews", "actor": "Israel", "count": 2},
    ]


def test_an_empty_run_writes_an_empty_victims_block(tmp_path: Path) -> None:
    table = victim_groups.read(write(tmp_path, "jews,,Jews,no\n"))
    block = victim_groups.victims_block(occurrences(), table)
    assert block["groups"] == block["decades"] == block["cells"] == block["by_actor"] == []
