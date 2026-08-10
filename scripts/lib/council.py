"""Council membership: who held a seat, in which year.

The Council's composition changes every 1 January, so "P5 / E10 / non-member"
is a property of a *speech*, not of a country. Rwanda spoke as an elected
member in 1994 and 2013-2014 and as a non-member in every other year of the
corpus; collapsing that would erase the thing most worth looking at.

`config/council_membership.csv` holds one row per term. This module expands
those into a year-by-year table and derives the speaker group used throughout
the dashboard.
"""

from __future__ import annotations

import pandas as pd

from .paths import COUNCIL_MEMBERSHIP, rel

#: Speaker groups. Membership decides the first three; everything else is
#: settled by entity_type, so the UN administration — the corpus's sixth-
#: largest speaker — does not get filed under "non-member state".
PERMANENT = "P5"
ELECTED = "E10"
NON_MEMBER = "Non-member state"
UN_GROUP = "UN"
NON_STATE = "Non-state"

SPEAKER_GROUPS: tuple[str, ...] = (PERMANENT, ELECTED, NON_MEMBER, UN_GROUP, NON_STATE)

#: Seats on the Council, fixed by the Charter since 1965.
N_PERMANENT = 5
N_ELECTED = 10


def load_terms() -> pd.DataFrame:
    """One row per term served, as recorded in config/."""
    if not COUNCIL_MEMBERSHIP.exists():
        raise FileNotFoundError(f"{rel(COUNCIL_MEMBERSHIP)} is missing")
    terms = pd.read_csv(COUNCIL_MEMBERSHIP, encoding="utf-8", comment="#")
    for column in ("start_year", "end_year"):
        terms[column] = terms[column].astype(int)
    return terms


def membership_by_year(terms: pd.DataFrame | None = None) -> pd.DataFrame:
    """Expand terms into ``(year, country_org, seat)``, one row per seat-year."""
    terms = load_terms() if terms is None else terms
    rows = [
        {"year": year, "country_org": row.country_org, "seat": row.seat}
        for row in terms.itertuples()
        for year in range(row.start_year, row.end_year + 1)
    ]
    return pd.DataFrame(rows).drop_duplicates()


def validate(membership: pd.DataFrame, first_year: int, last_year: int) -> list[str]:
    """Check the roster is internally consistent over the corpus period.

    The Charter fixes the Council at five permanent and ten elected members, so
    any year that does not add up is a mistake in the config file rather than a
    fact about the world. This catches a mistyped year immediately.
    """
    problems: list[str] = []
    window = membership[membership["year"].between(first_year, last_year)]
    counts = window.pivot_table(
        index="year", columns="seat", values="country_org", aggfunc="count"
    ).reindex(range(first_year, last_year + 1), fill_value=0).fillna(0).astype(int)

    for seat, expected in (("permanent", N_PERMANENT), ("elected", N_ELECTED)):
        if seat not in counts.columns:
            problems.append(f"no {seat} members recorded at all")
            continue
        wrong = counts.index[counts[seat] != expected].tolist()
        for year in wrong:
            problems.append(
                f"{year}: {counts.loc[year, seat]} {seat} members, expected {expected}"
            )
    return problems


def validate_against_corpus(
    membership: pd.DataFrame, speeches: pd.DataFrame
) -> list[str]:
    """Check every recorded member actually speaks in the year it served.

    A country holding a seat attends the Council all year, so a member that
    never speaks is nearly always a wrong year or a misspelled name in
    config/council_membership.csv rather than a silent delegation.
    """
    spoke = set(zip(speeches["year"], speeches["country_org"], strict=True))
    silent = [
        f"{row.country_org} ({row.year})"
        for row in membership.itertuples()
        if (row.year, row.country_org) not in spoke
    ]
    if not silent:
        return []
    shown = ", ".join(silent[:10])
    more = f" (+{len(silent) - 10} more)" if len(silent) > 10 else ""
    return [f"{len(silent)} recorded members never speak in their term: {shown}{more}"]


def drift(speeches: pd.DataFrame, membership: pd.DataFrame | None = None) -> list[str]:
    """Where the `speaker_group` 02 froze into the corpus no longer matches config/.

    `02_normalise.py` derives the group once and writes it into the parquet, and
    every step after it reads that column rather than recomputing — which is the
    right dependency, and also the one that hides an edit. A term corrected in
    `config/council_membership.csv` after 02 last ran would change nothing in the
    corpus and nothing in any artefact built from it, while the config file and
    the published figures quietly disagreed about who sat on the Council.

    The same stance `lib.actors.crosswalk_drift` takes on `entities.csv`: stop,
    and re-run 02, rather than build one artefact from the new file while the
    rest of the payload carries the old one.
    """
    if "speaker_group" not in speeches.columns:
        return []
    recomputed = speaker_group(speeches, membership)
    disagreeing = speeches.loc[recomputed != speeches["speaker_group"]]
    if disagreeing.empty:
        return []
    pairs = (
        disagreeing.assign(config=recomputed)
        .groupby(["country_org", "year", "speaker_group", "config"], sort=True)
        .size()
        .reset_index(name="speeches")
    )
    shown = [
        f"{row.country_org} ({row.year}): {row.speaker_group} in the corpus, "
        f"{row.config} in config/council_membership.csv ({row.speeches:,} speeches)"
        for row in pairs.head(8).itertuples()
    ]
    if len(pairs) > 8:
        shown.append(f"(+{len(pairs) - 8} more speaker-years)")
    return shown


def speaker_group(
    speeches: pd.DataFrame, membership: pd.DataFrame | None = None
) -> pd.Series:
    """Classify each speech as P5 / E10 / non-member state / UN / non-state.

    Expects ``year``, ``country_org`` and ``entity_type`` columns.
    """
    membership = membership_by_year() if membership is None else membership
    seat_of = dict(
        zip(
            zip(membership["year"], membership["country_org"], strict=True),
            membership["seat"],
            strict=True,
        )
    )
    seats = pd.Series(
        list(zip(speeches["year"], speeches["country_org"], strict=True)),
        index=speeches.index,
    ).map(seat_of)

    group = pd.Series(NON_STATE, index=speeches.index, dtype="object")
    group[speeches["entity_type"] == "un"] = UN_GROUP
    is_state = speeches["entity_type"] == "state"
    group[is_state] = NON_MEMBER
    group[is_state & (seats == "permanent")] = PERMANENT
    group[is_state & (seats == "elected")] = ELECTED
    return group
