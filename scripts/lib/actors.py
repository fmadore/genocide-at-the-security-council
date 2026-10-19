"""Per-country aggregation: the table a map would have to depict.

`docs/PLAN.md` §7 opens by refusing to let a visual precede the table behind it,
and until this module there was no per-country table to precede. The payload
splits the corpus by speaker group, entity type, participant type, agenda item
and delivery language — never by the speaker itself. A choropleth drawn from what
`series/` currently holds would have to invent its own numerator.

Three things make this more than a groupby.

**Every speaker divides by its own denominator.** A country that spoke twice and
said `genocide` once has a rate of 50%, which is arithmetically true and
evidentially nothing. Rates are therefore *withheld* below :data:`MIN_SPEECHES` —
written as null, not as a small number — while counts, which are facts rather
than estimates, are always written. That follows :func:`lib.series.measure`,
which returns an empty occurrence count for a set rather than a plausible-looking
one.

**A country code is not a country.** A speaker that no longer exists can carry
its successor's ISO 3166 code so it can still be placed: `config/entities.csv`
gives Yugoslavia `SRB`. Such a speaker stays a distinct row here — merging it
with its successor would build a denominator no state ever had — and code
collisions are reported, because a map keyed on ISO3 will otherwise paint
several speakers onto one polygon and show whichever it drew last.

**Most speakers are not countries at all.** Fewer than a third of the corpus's
`country_org` values are states by the source's own typing; the United Nations
is among the largest speakers and has no location on any globe. Only a state
receives a centroid, and every row here carries `entity_type` and a `mappable`
flag so a consumer excludes the rest deliberately rather than by discovering a
null halfway through a render.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import console, council, lexicon, series

#: Re-exported, not redefined. The zero-ceiling arithmetic below :data:`MIN_SPEECHES`
#: is a fact about denominators rather than about countries and now lives in
#: `lib.series`, where the monthly grid needs the same rule for the same reason.
#: The names stay here because this is where the argument for them is written.
zero_ceiling = series.zero_ceiling
informative_zero_minimum = series.informative_zero_minimum

#: Speeches a speaker must have delivered in a period before its rates are
#: published. Not a round number chosen for looking careful: 125 is roughly where
#: a *zero* starts to mean something. Seeing no term-bearing speech in n tries
#: puts a 95% ceiling of about 3/n on the underlying rate
#: (:func:`zero_ceiling`), and the corpus-wide prevalence of `genocide` is 2.5%,
#: so below about 121 speeches a blank country means "not looked at for long
#: enough" rather than "quieter than the Council". Readers treat white space on a
#: map as a finding; this is the denominator at which it is entitled to be one.
#: `11_countries.py` recomputes the requirement against the corpus it loads and
#: says so if 125 stops meeting it.
MIN_SPEECHES = 125

#: Multi-year slices, matching `05_lexical.py`'s so that a speaker's collocate
#: profile and its rate are cut on the same boundaries. Round decades, fixed
#: before any result was looked at: 04's change points are the empirical dating,
#: and these are deliberately not them.
DECADES: tuple[tuple[int, int], ...] = (
    (1946, 1949),
    (1950, 1959),
    (1960, 1969),
    (1970, 1979),
    (1980, 1989),
    (1990, 1999),
    (2000, 2009),
    (2010, 2019),
    (2020, 2024),
)

#: Key of the slice covering the whole corpus.
WHOLE = "all"

#: Columns a speech table must carry to be aggregated here.
REQUIRED_COLUMNS = ("row_id", "year", "country_org", "words", "meeting_symbol")


@dataclass(frozen=True)
class Period:
    """One slice of the corpus, named."""

    key: str
    label: str
    first_year: int
    last_year: int

    def mask(self, years: pd.Series) -> pd.Series:
        return years.between(self.first_year, self.last_year)

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "first_year": self.first_year,
            "last_year": self.last_year,
        }


def periods(
    first_year: int, last_year: int, decades: tuple[tuple[int, int], ...] = DECADES
) -> list[Period]:
    """The whole corpus, then each declared slice.

    The whole-corpus row is first and is not a sum of the others in any sense a
    reader should rely on: a speaker can clear the minimum over thirty years and
    clear it in none of them.
    """
    whole = Period(WHOLE, f"{first_year}-{last_year}", first_year, last_year)
    return [whole, *(Period(f"{a}-{b}", f"{a}-{b}", a, b) for a, b in decades)]


def check_coverage(
    years: pd.Series, decades: tuple[tuple[int, int], ...] = DECADES
) -> list[str]:
    """Every observed year must fall in exactly one declared slice.

    A year in none of them would vanish from the period rows while still
    counting in the whole-corpus row, and the two would stop reconciling for a
    reason nobody could see in the output.
    """
    problems: list[str] = []
    for year in sorted({int(y) for y in years.dropna()}):
        holding = [f"{a}-{b}" for a, b in decades if a <= year <= b]
        if not holding:
            problems.append(f"{year} falls in no declared period")
        elif len(holding) > 1:
            problems.append(f"{year} falls in {len(holding)} periods: {', '.join(holding)}")
    return problems


# --- The aggregation -------------------------------------------------------


def by_country(
    speeches: pd.DataFrame, has_column: str, count_column: str | None
) -> pd.DataFrame:
    """One row per speaker: denominator, numerator, occurrences and both rates.

    The arithmetic is `lib.series`'s, with the speaker standing where the period
    normally stands: :func:`lib.series.denominators` gives each speaker the
    speeches and words it is divided by, and :func:`lib.series.measure` divides
    by them. Reusing it is the whole point — a rate computed a second way here
    would eventually disagree with the one 04 publishes, and nothing in the
    output would say which was wrong.
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in speeches.columns]
    if missing:
        raise KeyError(f"by_country needs {', '.join(missing)}")

    labels = speeches["country_org"].rename("country_org")
    totals = series.denominators(speeches, labels)
    totals.index.name = "country_org"
    measured = series.measure(speeches, labels, totals, has_column, count_column)
    return totals.rename(columns={"speeches": "held"}).join(measured)


def withhold_below(frame: pd.DataFrame, minimum: int = MIN_SPEECHES) -> pd.DataFrame:
    """Blank the rates a denominator this small cannot support.

    The counts stay. A speaker that gave three speeches and used the word once
    did exactly that, and the reader is entitled to the three and the one; what
    they are not entitled to is 33%, which would sit on a map beside Rwanda's
    17% and outrank it.

    The speaker's own denominator is the `held` column this module builds;
    :func:`lib.series.withhold_below` takes it as an argument because a period's
    denominator lives beside the measure rather than inside it.
    """
    return series.withhold_below(frame, frame["held"], minimum)


def annual_table(speeches: pd.DataFrame, measure: str, minimum: int = MIN_SPEECHES) -> pd.DataFrame:
    if minimum < 1 or speeches.empty:
        raise ValueError("a positive minimum and a nonempty corpus are required")
    if speeches[["row_id", "year", "country_org", "meeting_symbol"]].isna().any().any() or speeches.row_id.duplicated().any():
        raise ValueError("annual tables require unique speech IDs and complete grouping fields")
    has, count = series.columns_for("terms", measure)
    speakers = sorted(speeches.country_org.unique())
    tables = []
    for year in range(int(speeches.year.min()), int(speeches.year.max()) + 1):
        selected = speeches[speeches.year.eq(year)]
        table = by_country(selected, has, count).reindex(speakers)
        for column in ("held", "words", "tokens", "meetings", "speeches", "occurrences"):
            table[column] = table[column].fillna(0).astype(int)
        table = withhold_below(table, minimum)
        table["withheld_reason"] = ["no speeches" if n == 0 else "below minimum" if n < minimum else "" for n in table.held]
        if int(table.held.sum()) != len(selected) or int(table.speeches.sum()) != int(selected[has].sum()) or int(table.occurrences.sum()) != int(selected[count].sum()) or int(table.words.sum()) != int(selected.words.sum()):
            raise ValueError(f"annual totals do not reconcile for {year}")
        tables.append(table.assign(year=year, measure=measure).reset_index(names="country_org"))
    return pd.concat(tables, ignore_index=True)


# --- Who held a seat when they spoke ---------------------------------------

#: The groups that hold a seat. The Charter's two kinds of membership and
#: nothing else — the UN Secretariat briefs the Council constantly and has never
#: sat on it, so "not seated" covers three quite different situations and the
#: per-group counts are published rather than only their sum.
SEATED: tuple[str, ...] = (council.PERMANENT, council.ELECTED)


def standing(
    speeches: pd.DataFrame, groups: tuple[str, ...] = council.SPEAKER_GROUPS
) -> pd.DataFrame:
    """Per speaker: how many of its own speeches it gave in each speaker group.

    `lib.council` opens by saying that P5/E10/non-member is a property of a
    *speech* and not of a country, and Rwanda is its example: elected in 1994
    and 2013-2014, a non-member in every other year of the corpus. A row here
    therefore cannot carry a membership label without erasing the thing most
    worth looking at. What it carries is the composition of the speaker's own
    speeches — five counts that sum to its denominator.

    Those counts are always written, whatever the denominator, because they are
    facts about the record rather than estimates from it: the distinction
    :func:`withhold_below` draws between a count and a rate. `seated_share` is
    written on the same grounds, and the grounds are worth stating because it
    looks like the rates that *are* withheld. It is a proportion of a finite
    known set, not a sample estimate of a latent propensity: "of the twelve
    speeches this speaker gave in this period, twelve were given from a seat" is
    exactly true at n=12, in a way that "33% of its speeches used the word" over
    three speeches is not.

    A `speaker_group` outside the declared set stops this rather than being
    dropped. Reindexing it away would leave five counts that no longer sum to
    the denominator beside them, and every check downstream compares totals.
    """
    if "speaker_group" not in speeches.columns:
        raise KeyError("standing needs a speaker_group column; 02_normalise.py writes it")
    seen = set(speeches["speaker_group"].dropna().unique())
    if unknown := sorted(seen - set(groups)):
        raise ValueError(
            f"{len(unknown)} speaker groups are not declared in lib.council: "
            f"{', '.join(unknown)}"
        )
    if speeches["speaker_group"].isna().any():
        raise ValueError("some speeches carry no speaker_group; 02_normalise.py assigns one to all")

    counts = (
        pd.crosstab(speeches["country_org"], speeches["speaker_group"])
        .reindex(columns=list(groups), fill_value=0)
        .astype(int)
    )
    counts.index.name = "country_org"
    out = counts.copy()
    out["held"] = counts.sum(axis=1)
    out["seated"] = counts[list(SEATED)].sum(axis=1)
    out["seated_share"] = out["seated"] / out["held"].where(out["held"] > 0)
    return out


def reconcile_standing(
    frame: pd.DataFrame, speeches: pd.DataFrame, where: str,
    groups: tuple[str, ...] = council.SPEAKER_GROUPS,
) -> list[str]:
    """Check the composition adds back up to the corpus it was cut from.

    Two ways to be wrong and look right: a speaker lost to a join leaves every
    published composition correct and the totals short, and a group silently
    dropped leaves counts that no longer sum to the denominator printed beside
    them. The first is caught by the total, the second by the per-group rows.
    """
    checks: list[tuple[str, int, int]] = [
        ("speeches held", int(frame["held"].sum()), len(speeches)),
        *[
            (
                f"{group} speeches",
                int(frame[group].sum()),
                int((speeches["speaker_group"] == group).sum()),
            )
            for group in groups
        ],
    ]
    problems = [
        f"{where}: {label} sum to {got:,}, the corpus holds {want:,} ({got - want:+,})"
        for label, got, want in checks
        if got != want
    ]
    short = frame.index[frame[list(groups)].sum(axis=1) != frame["held"]].tolist()
    problems += [
        f"{where}: {name}'s group counts do not sum to its denominator" for name in short[:8]
    ]
    return problems


def standing_as_rows(
    frame: pd.DataFrame,
    period_key: str,
    groups: tuple[str, ...] = council.SPEAKER_GROUPS,
) -> list[dict[str, object]]:
    """Long form — one row per (speaker, period) — matching :func:`as_rows`.

    Every group is written, including the zeros. A row that listed only the
    groups a speaker actually spoke in would be smaller and would make an absent
    key mean zero here while it means "withheld, never computed" one block away
    in `measures`; a consumer cannot tell those apart from the JSON alone.
    """
    return [
        {
            "country_org": str(name),
            "period": period_key,
            "held": int(row["held"]),
            "seated": int(row["seated"]),
            "seated_share": _rate(row["seated_share"], 6),
            "groups": {group: int(row[group]) for group in groups},
        }
        for name, row in frame.iterrows()
    ]


# --- Who stays silent when others say it -----------------------------------

#: Meetings a speaker must have attended, while another speaker used the word,
#: before its share of them is published. The argument is :data:`MIN_SPEECHES`'s,
#: on a different denominator: across the corpus a speaker in such a meeting uses
#: the word itself in about 11.5% of them, and seeing it do so in none of n
#: meetings only puts its rate below that once n reaches about 25
#: (:func:`informative_zero_minimum`). Thirty is the round number above it.
#: `11_countries.py` recomputes the requirement and says so if 30 stops meeting it.
MIN_EXPOSED_MEETINGS = 30

#: Columns :func:`exposure` reads, beyond the term's own presence column.
EXPOSURE_COLUMNS = ("meeting_symbol", "country_org", "source_procedural")


def procedural_mask(values: pd.Series) -> pd.Series:
    """The source's procedural flag as booleans, whether read as bool or as text."""
    return values.map(lambda value: str(value) == "True")


def exposure(speeches: pd.DataFrame, has_column: str) -> pd.DataFrame:
    """Per speaker: the meetings where someone else used the term, and how many it joined.

    Silence means something only where the word was available. A delegation that
    never says *genocide* in debates about fisheries has avoided nothing; one that
    takes the floor in a meeting where another delegation has just used the word,
    and does not use it, has made a choice the record can show. So the
    denominator is a speaker's **exposed meetings**: meetings in which it gave at
    least one substantive speech and at least one *other* speaker used the term.
    The numerator, `joined`, is the exposed meetings in which it used the term
    too. A meeting in which the speaker was the only one to use the word is in
    neither: nobody else made the word available, so there was nothing to join.

    Procedural speeches are left out on both sides. The presidency's procedural
    turns read agenda titles aloud, and some titles contain the word (the Rwanda
    tribunal's full name does), so counting them would make every such meeting
    an exposure and every presidency a user.

    `share` is `joined / exposed`, with its Wilson interval. It describes the
    record, not intent: for speakers of other languages the word is the UN
    translator's, and a delegation may have spoken to another point of the same
    meeting.
    """
    missing = [column for column in (*EXPOSURE_COLUMNS, has_column) if column not in speeches.columns]
    if missing:
        raise KeyError(f"exposure needs {', '.join(missing)}")

    substantive = speeches.loc[~procedural_mask(speeches["source_procedural"])]
    attended = (
        substantive.assign(used=substantive[has_column].astype(bool))
        .groupby(["meeting_symbol", "country_org"], observed=True, sort=True)["used"]
        .any()
        .to_frame()
    )
    users = attended["used"].groupby(level="meeting_symbol").sum()
    meetings = attended.index.get_level_values("meeting_symbol")
    others = users.reindex(meetings).to_numpy() - attended["used"].astype(int).to_numpy()
    exposed = attended.loc[others > 0]

    out = exposed.groupby(level="country_org").agg(
        exposed=("used", "size"), joined=("used", "sum")
    )
    out = out.astype({"exposed": "int64", "joined": "int64"})
    out["share"] = out["joined"] / out["exposed"]
    low, high = series.wilson_interval(out["joined"].to_numpy(), out["exposed"].to_numpy())
    out["share_low"] = low
    out["share_high"] = high
    return out


def reconcile_exposure(
    frame: pd.DataFrame, speeches: pd.DataFrame, has_column: str, where: str
) -> list[str]:
    """Rebuild both totals meeting by meeting and compare.

    :func:`exposure` counts per speaker; this counts per meeting, by a different
    path. In a meeting with `n` substantive speakers of whom `u` used the term,
    every speaker is exposed when `u >= 2` and all `u` joined; when `u == 1` the
    other `n - 1` are exposed and none joined; when `u == 0` nobody is exposed.
    """
    substantive = speeches.loc[~procedural_mask(speeches["source_procedural"])]
    used = substantive[has_column].astype(bool)
    per_meeting = pd.DataFrame(
        {
            "present": substantive.groupby("meeting_symbol")["country_org"].nunique(),
            "users": substantive.loc[used].groupby("meeting_symbol")["country_org"].nunique(),
        }
    ).fillna(0).astype(int)
    one = per_meeting["users"] == 1
    several = per_meeting["users"] >= 2
    want_exposed = int((per_meeting.loc[one, "present"] - 1).sum() + per_meeting.loc[several, "present"].sum())
    want_joined = int(per_meeting.loc[several, "users"].sum())
    got_exposed = int(frame["exposed"].sum()) if not frame.empty else 0
    got_joined = int(frame["joined"].sum()) if not frame.empty else 0
    return [
        f"{where}: {label} sum to {got:,} by speaker and {want:,} by meeting ({got - want:+,})"
        for label, got, want in (
            ("exposed meetings", got_exposed, want_exposed),
            ("joined meetings", got_joined, want_joined),
        )
        if got != want
    ]


def withhold_exposure(frame: pd.DataFrame, minimum: int = MIN_EXPOSED_MEETINGS) -> pd.DataFrame:
    """Blank the shares too few exposed meetings can support; keep the counts."""
    out = frame.copy()
    out["sufficient"] = out["exposed"] >= minimum
    for column in ("share", "share_low", "share_high"):
        out.loc[~out["sufficient"], column] = float("nan")
    return out


def exposure_as_rows(frame: pd.DataFrame, period_key: str) -> list[dict[str, object]]:
    """Long form, one row per (speaker, period), matching :func:`as_rows`."""
    return [
        {
            "country_org": str(name),
            "period": period_key,
            "exposed": int(row["exposed"]),
            "joined": int(row["joined"]),
            "share": _rate(row["share"], 6),
            "share_low": _rate(row["share_low"], 6),
            "share_high": _rate(row["share_high"], 6),
            "sufficient": bool(row["sufficient"]),
        }
        for name, row in frame.iterrows()
    ]


# --- What a map would get wrong -------------------------------------------


def iso3_collisions(speakers: list[dict[str, object]]) -> dict[str, list[str]]:
    """ISO 3166 codes carried by more than one speaker.

    A historical state is given its successor's code so it can be placed at all,
    which means the code is not a key: Yugoslavia, Serbia and Montenegro and
    Serbia all answer to `SRB`. The alternative — merging them into one row —
    would build a denominator no state ever had, so they stay separate and the
    ambiguity is published instead. A consumer that joins on ISO3 and does not
    read this will draw whichever row it painted last and never know.
    """
    by_code: dict[str, set[str]] = {}
    for speaker in speakers:
        code = _text(speaker.get("iso3"))
        if code is not None:
            by_code.setdefault(code, set()).add(str(speaker["country_org"]))
    return {code: sorted(names) for code, names in sorted(by_code.items()) if len(names) > 1}


def _text(value: object) -> str | None:
    """A crosswalk cell as a string, or None. Blank is missing, not a value.

    An empty ISO3 read back as `""` is the failure this exists to prevent: it is
    falsy enough to pass a truthiness check, truthy enough to survive a join, and
    it puts a country with no code onto whatever polygon the empty key matches.
    """
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def describe_speakers(
    speeches: pd.DataFrame, crosswalk: pd.DataFrame
) -> list[dict[str, object]]:
    """Each speaker's crosswalk attributes, written once.

    `mappable` is the field a map filters on. It is deliberately not "has
    coordinates": it is "is a state, has a code, and has a centroid", so a
    consumer never has to infer from a null that the UN Secretariat was not meant
    to be drawn — and so a state that acquires a centroid but no code cannot slip
    onto the map through a truthiness test.

    A speaker the crosswalk has never seen stops this, rather than being dropped
    from the returned list. Dropping it would leave a table that still looks
    complete and a total that is quietly short. The crosswalk is the one
    `lib.entities.source_affiliation_crosswalk` builds from the corpus itself,
    so a speaker missing from it means the two were built from different
    corpora.
    """
    known = set(crosswalk["country_org"])
    unseen = sorted(set(speeches["country_org"].dropna()) - known)
    if unseen:
        raise KeyError(
            f"{len(unseen)} speakers are absent from the crosswalk and would be "
            f"dropped from the table: {', '.join(unseen[:8])}"
        )

    seen = speeches.groupby("country_org", sort=True).agg(
        speeches=("row_id", "size"),
        first_year=("year", "min"),
        last_year=("year", "max"),
    )
    attributes = crosswalk.drop_duplicates("country_org").set_index("country_org")

    out: list[dict[str, object]] = []
    for name, row in seen.iterrows():
        entity = attributes.loc[name]
        iso3 = _text(entity["iso3"])
        lat, lon = entity["lat"], entity["lon"]
        placed = bool(pd.notna(lat) and pd.notna(lon))
        out.append(
            {
                "country_org": str(name),
                "entity_type": _text(entity["entity_type"]),
                "iso3": iso3,
                "un_regional_group": _text(entity["un_regional_group"]),
                "centroid": [round(float(lat), 4), round(float(lon), 4)] if placed else None,
                "mappable": bool(entity["entity_type"] == "state" and iso3 and placed),
                "speeches": int(row["speeches"]),
                "first_year": int(row["first_year"]),
                "last_year": int(row["last_year"]),
            }
        )
    return out


# --- Reconciliation and serialisation --------------------------------------


def reconcile(
    frame: pd.DataFrame,
    speeches: pd.DataFrame,
    has_column: str,
    count_column: str | None,
    where: str,
) -> list[str]:
    """Check the aggregation adds back up to the corpus it was cut from.

    A speaker dropped by a failed join is the failure this catches: the table
    still looks complete, every rate it shows is still correct, and the total is
    quietly short.
    """
    checks: list[tuple[str, int, int]] = [
        ("speeches held", int(frame["held"].sum()), len(speeches)),
        ("words", int(frame["words"].sum()), int(speeches["words"].sum())),
        (
            "term-bearing speeches",
            int(frame["speeches"].sum()),
            int(speeches[has_column].sum()),
        ),
    ]
    if count_column is not None:
        checks.append(
            ("occurrences", int(frame["occurrences"].sum()), int(speeches[count_column].sum()))
        )
    return [
        f"{where}: {label} sum to {got:,}, the corpus holds {want:,} ({got - want:+,})"
        for label, got, want in checks
        if got != want
    ]


def reconcile_periods(
    computed: dict[str, pd.DataFrame], slices: list[Period]
) -> list[str]:
    """The declared slices must add back up to the whole-corpus row.

    :func:`check_coverage` already refuses a corpus the periods do not partition,
    so this can only fail if that check and these masks disagree — which is
    exactly the kind of thing that goes wrong when someone edits
    :data:`DECADES` and reads the assertion as the guarantee.
    """
    whole = computed[WHOLE]
    parts = [computed[window.key] for window in slices if window.key != WHOLE]
    problems: list[str] = []
    for column in ("held", "words", "speeches", "occurrences"):
        if whole[column].isna().all():
            continue  # a set carries no occurrence count; see series.measure
        got = sum(int(part[column].sum()) for part in parts)
        want = int(whole[column].sum())
        if got != want:
            problems.append(
                f"{column}: the periods hold {got:,}, the whole corpus {want:,} "
                f"({got - want:+,})"
            )
    return problems


def reconcile_withholding(computed: dict[str, dict[str, pd.DataFrame]]) -> list[str]:
    """Every measure must withhold from the same speakers, in the same periods.

    The minimum sample is a rule about a *denominator*, and a speaker's
    denominator is the speeches it delivered, whatever vocabulary is being
    counted inside them. A table carrying more than one measure must therefore
    blank the same rows in all of them. The failure this refuses is quiet: a
    rate published under one measure and withheld under another, for the same
    speaker in the same period, reads as a fact about the two vocabularies
    rather than as the accident of arithmetic it would be, and a reader
    comparing the two selections has no way to see which it is.

    :func:`withhold_below` cannot know it is being applied twice, so the
    agreement is asserted here rather than assumed from the fact that both
    calls were handed the same corpus.
    """
    names = list(computed)
    if len(names) < 2:
        return []
    first, *rest = names
    problems: list[str] = []
    for name in rest:
        for key, frame in computed[name].items():
            reference = computed[first][key]
            if missing := sorted(set(reference.index) ^ set(frame.index)):
                problems.append(
                    f"{key}: {len(missing)} speakers are in {first} and not in {name}, or the "
                    f"other way round: {', '.join(str(one) for one in missing[:6])}"
                )
                continue
            aligned = frame.reindex(reference.index)
            for column in ("held", "words", "sufficient"):
                differing = reference.index[aligned[column] != reference[column]].tolist()
                if differing:
                    problems.append(
                        f"{key}: {len(differing)} speakers disagree about {column} between "
                        f"{first} and {name}: {', '.join(str(one) for one in differing[:6])}"
                    )
    return problems


def _count(value: Any) -> int | None:
    return None if pd.isna(value) else int(value)


def _rate(value: Any, digits: int) -> float | None:
    return None if pd.isna(value) else round(float(value), digits)


def as_rows(frame: pd.DataFrame, period_key: str) -> list[dict[str, object]]:
    """Long form — one row per (speaker, period) — for the artefact.

    Long rather than nested because that is what a table, a crosstab and a
    choropleth's data join all want, and because the speaker's own attributes
    live once in the `countries` block instead of being repeated and given the
    chance to disagree with themselves.
    """
    out: list[dict[str, object]] = []
    for name, row in frame.iterrows():
        entry: dict[str, object] = {
            "country_org": str(name),
            "period": period_key,
            "held": _count(row["held"]),
            "words": _count(row["words"]),
            "speeches": _count(row["speeches"]),
            "speech_rate": _rate(row["speech_rate"], 6),
            # The Wilson bounds `lib.series.measure` wrote beside the rate, so a
            # speaker's 12 of 60 is drawn with the width it has. Null exactly
            # when the rate is: the same withholding rule blanks all three.
            "speech_rate_low": _rate(row.get("speech_rate_low"), 6),
            "speech_rate_high": _rate(row.get("speech_rate_high"), 6),
            "sufficient": bool(row["sufficient"]),
        }
        if not pd.isna(row["occurrences"]):
            entry |= {
                "occurrences": _count(row["occurrences"]),
                "token_rate": _rate(row["token_rate"], 4),
            }
        out.append(entry)
    return out


# --- The table 11 writes ---------------------------------------------------


#: The measures this table carries. It held `atrocity_core` beside the derived
#: measure until lexicon v5, and that union is the reason several of 11's
#: careful absences exist: a set has no occurrence count, so the interface had
#: to detect the withholding and drop a column, an ordering and a tooltip rather
#: than read it through `?? 0`. The withholding machinery stays — R8's
#: genocide-free corpus is a population with the same property — but no measure
#: in this artefact is a roll-up over terms any more.
#:
#: One word-family count, also used by the chronology and concordance.
TRACKED: list[tuple[str, str]] = [
    ("terms", "genocide"),
]

#: The measure used for prevalence, withholding and reconciliation.
HEADLINE = TRACKED[0][1]

#: Columns read from the corpus. The whole table is 100 columns wide and 419 MB
#: of it is speech text 11 never looks at.
COLUMNS = [
    "row_id",
    "year",
    "country_org",
    "meeting_symbol",
    "words",
    # Kept for 11's codebook assertion, never divided by.
    "tokens",
    "entity_type",
    "iso3",
    "un_regional_group",
    "speaker_group",
    "lat",
    "lon",
    "source_state",
    "source_un_org",
    "source_igo",
    "source_ngo",
    "source_permanent_member",
    "source_elected_member",
    # Read by :func:`exposure` only: procedural turns are left out of who said what.
    "source_procedural",
]


def measure_attributes(lex: lexicon.Lexicon, kind: str, name: str) -> dict[str, object]:
    """Describe each measure and retain provenance for generic derived inputs."""
    if name in lex.derived:
        measure = lex.derived[name]
        return {
            "kind": kind,
            "tier": measure.tier,
            "register": measure.register,
            "derived_from": measure.minuend,
            "derived_minus": list(measure.subtrahends),
        }
    term = lex.terms[name]
    return {"kind": kind, "tier": term.tier, "register": term.register}


def build_measures(
    speeches: pd.DataFrame,
    lex: lexicon.Lexicon,
    slices: list[Period],
    minimum: int,
) -> tuple[dict[str, object], dict[str, dict[str, pd.DataFrame]]]:
    """Every measure over every period, reconciled before it is kept."""
    payload: dict[str, object] = {}
    computed: dict[str, dict[str, pd.DataFrame]] = {}

    for kind, name in TRACKED:
        has_column, count_column = series.columns_for(kind, name)
        rows: list[dict[str, object]] = []
        computed[name] = {}

        for window in slices:
            subset = speeches[window.mask(speeches["year"])]
            frame = by_country(subset, has_column, count_column)
            if problems := reconcile(
                frame, subset, has_column, count_column, f"{name} / {window.key}"
            ):
                raise console.Refusal("the per-country aggregation does not reconcile", problems)
            frame = withhold_below(frame, minimum)
            computed[name][window.key] = frame
            rows += as_rows(frame, window.key)

        # The declared periods are asserted to partition the corpus before any of
        # this runs, so the four slices must add back up to the whole-corpus row.
        # Checking it here rather than trusting the assertion is cheap, and it is
        # the one place a mis-set period boundary would show as a number.
        if problems := reconcile_periods(computed[name], slices):
            raise console.Refusal(f"{name}: the period slices do not add up to the whole", problems)

        payload[name] = {**measure_attributes(lex, kind, name), "rows": rows}
        cleared = int(computed[name][WHOLE]["sufficient"].sum())
        console.info(
            f"{name:22s} {len(rows):,} rows over {len(slices)} periods; "
            f"{cleared} speakers clear the minimum over the whole corpus"
        )

    # The minimum governs a denominator, and a speaker's denominator does not
    # depend on which vocabulary is counted in it. So every measure must blank
    # the same rows; a rate shown for one and withheld for the other would look
    # like a finding about the words.
    if problems := reconcile_withholding(computed):
        raise console.Refusal("the measures do not agree about a denominator or a withholding", problems)
    if len(computed) > 1:
        console.info(f"the {len(computed)} measures withhold from the same speakers in every period")

    return payload, computed


def build_periods(
    speeches: pd.DataFrame, slices: list[Period], computed: dict, minimum: int
) -> list[dict[str, object]]:
    """Corpus totals per slice, so no consumer has to hard-code a denominator."""
    out: list[dict[str, Any]] = []
    for window in slices:
        subset = speeches[window.mask(speeches["year"])]
        frame = computed[HEADLINE][window.key]
        out.append(
            {
                **window.as_dict(),
                "speeches": len(subset),
                "words": int(subset["words"].sum()),
                "speakers": int(subset["country_org"].nunique()),
                "speakers_at_minimum": int(frame["sufficient"].sum()),
                "speeches_at_minimum": int(frame.loc[frame["sufficient"], "held"].sum()),
            }
        )
        window_min = out[-1]
        console.info(
            f"{window.key:10s} {window_min['speeches']:>7,} speeches  "
            f"{window_min['speakers']:>3} speakers  "
            f"{window_min['speakers_at_minimum']:>3} at or above {minimum} "
            f"({window_min['speeches_at_minimum'] / max(len(subset), 1):.1%} of speeches)"
        )
    return out
