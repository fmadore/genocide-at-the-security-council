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

**A country code is not a country.** Three speakers in the corpus no longer
exist, and `config/entities.csv` gives each its successor's ISO 3166 code so it
can still be placed: Yugoslavia and Serbia and Montenegro both carry `SRB`, Zaire
carries `COD`. They stay distinct rows here — merging them would build a
denominator no state ever had — and the collisions are reported, because a map
keyed on ISO3 will otherwise paint several speakers onto one polygon and show
whichever it drew last.

**Most speakers are not countries at all.** Of 601 canonical `country_org`
values, 200 are states; the UN Secretariat is among the largest speakers in the
corpus and has no location on any globe. `entities.csv` deliberately gives it no
centroid, and every row here carries `entity_type` and a `mappable` flag so a
consumer excludes it deliberately rather than by discovering a null halfway
through a render.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import council, entities, series

#: Re-exported, not redefined. The zero-ceiling arithmetic below :data:`MIN_SPEECHES`
#: is a fact about denominators rather than about countries and now lives in
#: `lib.series`, where the monthly grid needs the same rule for the same reason.
#: The names stay here because this is where the argument for them is written.
zero_ceiling = series.zero_ceiling
informative_zero_minimum = series.informative_zero_minimum

#: Speeches a speaker must have delivered in a period before its rates are
#: published. Not a round number chosen for looking careful: 100 is roughly where
#: a *zero* starts to mean something. Seeing no term-bearing speech in n tries
#: puts a 95% ceiling of about 3/n on the underlying rate
#: (:func:`zero_ceiling`), and the corpus-wide prevalence of `genocide` is 3.1%,
#: so below about 96 speeches a blank country means "not looked at for long
#: enough" rather than "quieter than the Council". Readers treat white space on a
#: map as a finding; this is the denominator at which it is entitled to be one.
#: `11_countries.py` recomputes the requirement against the corpus it loads and
#: says so if 100 stops meeting it.
MIN_SPEECHES = 100

#: Multi-year slices, matching `05_lexical.py`'s so that a speaker's collocate
#: profile and its rate are cut on the same boundaries. Round decades, fixed
#: before any result was looked at: 04's change points are the empirical dating,
#: and these are deliberately not them.
DECADES: tuple[tuple[int, int], ...] = (
    (1992, 1999),
    (2000, 2009),
    (2010, 2019),
    (2020, 2023),
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
    complete and a total that is quietly short, which is the stance
    `02_normalise.py` already takes on the same file.
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


def _same(left: object, right: object) -> bool:
    """Equality that treats two missing values as agreeing."""
    left_missing, right_missing = pd.isna(left), pd.isna(right)
    if left_missing or right_missing:
        return bool(left_missing and right_missing)
    if isinstance(left, float) or isinstance(right, float):
        return bool(np.isclose(float(left), float(right), rtol=0, atol=1e-6))
    return left == right


def crosswalk_drift(speeches: pd.DataFrame, crosswalk: pd.DataFrame) -> list[str]:
    """Where the attributes 02 froze into the parquet no longer match `config/`.

    `02_normalise.py` joins the crosswalk and writes `entity_type`, `iso3`, the
    UN group and the centroid into the corpus. If `config/entities.csv` has been
    edited since, this table would be built from the edited file while every
    other artefact in the payload still carries the old one — an inconsistency
    that is invisible in both. Better to stop and re-run 02.
    """
    columns = [c for c in entities.ENTITY_COLUMNS if c in speeches.columns]
    if not columns:
        return []
    observed = speeches[["country_org", *columns]].drop_duplicates("country_org")
    joined = observed.merge(
        crosswalk[["country_org", *columns]],
        on="country_org",
        how="left",
        suffixes=("_corpus", "_config"),
        validate="one_to_one",
    )
    problems: list[str] = []
    for row in joined.itertuples(index=False):
        for column in columns:
            corpus = getattr(row, f"{column}_corpus")
            config = getattr(row, f"{column}_config")
            if not _same(corpus, config):
                problems.append(
                    f"{row.country_org}: {column} is {corpus!r} in the corpus and "
                    f"{config!r} in config/entities.csv"
                )
    return problems


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


def _count(value: object) -> int | None:
    return None if pd.isna(value) else int(value)


def _rate(value: object, digits: int) -> float | None:
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
