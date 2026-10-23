"""`victim_groups.csv`: the model's free-text victim groups, grouped by a checked table."""

from __future__ import annotations

from pathlib import Path

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
