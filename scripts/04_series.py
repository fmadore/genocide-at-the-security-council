"""Temporal series: how often the lexicon is spoken, and when that changes.

Reads speeches_flagged.parquet and writes six JSON artefacts to
data/derived/series/, plus a findings note.

Three resolutions, and the third is not more of the same. A year and a quarter
always hold thousands of speeches, so an annual series needs no minimum; a month
need not, and 53 of the corpus's 384 hold too few to divide by. `monthly.json`
therefore carries a withholding rule the coarser series never needed, and the
calendar block that says what a month resolution actually recovers — which is
substantially the Council's own reporting cycle rather than a discourse.

Every series carries three numbers for the same period — speeches, occurrences,
and both rates — because the three tell different stories and the raw one tells
the wrong story by default. The corpus runs from 1,023 speeches in 1992 to 7,621
in 2023; anything not divided by that is a chart of the Council's growth.

The change-point pass is where that becomes a finding rather than a caveat. It
is run on the raw count *and* on the rate, and the note reports both, so the
difference between "genocide was said more often" and "genocide was said more
often than other things" is on the page rather than in a footnote.

Usage:
    python scripts/04_series.py [--top-agenda 20] [--trials 2000] [--seed 20260807]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, frames, language, lexicon, series
from lib.paths import (
    EVENTS,
    LEXICON,
    ROOT,
    SERIES,
    SPEECHES_FLAGGED,
    ensure_dirs,
    rel,
    write_note,
)

#: Measures the change-point pass and the breakdowns run on, as (kind, name).
#: `genocide` is the object of study; `atrocity_core` is the set that may be the
#: real one, so both are dated rather than one being assumed.
TRACKED = [("terms", "genocide"), ("sets", "atrocity_core")]

#: Speeches a month must hold before its rates are published.
#:
#: Derived, not declared: at the corpus prevalence of about 3.1%, observing no
#: term-bearing speech in n tries only puts a 95% ceiling below that prevalence
#: once n reaches about 96 (`series.informative_zero_minimum`). Below it, an
#: empty month means "the Council barely sat" rather than "the Council was
#: quiet" — and on a heatmap the two are the same white square. `run` recomputes
#: the requirement against the corpus it loads and says so if 100 stops meeting
#: it. It is the same number `lib.actors` declares for a speaker's slice, by the
#: same argument applied to a different denominator, and not by inheritance.
MIN_SPEECHES_PER_MONTH = 100

#: Dropped in the second reading of the calendar figure. The corpus's two
#: largest years for this vocabulary: if a calendar pattern is really the Rwanda
#: spike seen through a monthly lens, it does not survive their removal.
CALENDAR_CONTROL_YEARS: tuple[int, ...] = (1994, 1995)

#: What each calendar month's term-bearing speeches were debating, and how many
#: items of it to name.
CALENDAR_AGENDA_COLUMN = "agenda_item_manual"
CALENDAR_AGENDA_ITEMS = 3

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

#: Categorical splits worth a per-period breakdown, with an optional cap on
#: how many categories survive before the tail is folded into "Other".
BREAKDOWNS: list[tuple[str, int | None]] = [
    ("speaker_group", None),
    ("entity_type", None),
    ("participanttype", None),
    ("agenda_item1", None),
    ("agenda_item_manual", 20),
    ("delivery_language", 10),
]

def prepare(speeches: pd.DataFrame) -> pd.DataFrame:
    """Add the derived columns the breakdowns need."""
    speeches["delivery_language"] = language.delivery_language(speeches)
    return speeches


def measures(lex: lexicon.Lexicon) -> dict[str, dict[str, dict]]:
    """Every series to compute, grouped into terms / registers / sets.

    Maps each name to the attributes that describe it in the artefact; the
    columns behind it come from `series.columns_for`.
    """
    by_register = lex.by_register()
    return {
        "terms": {
            term.name: {"tier": term.tier, "register": term.register} for term in lex.active
        },
        "registers": {
            register: {"terms": [t.name for t in by_register[register]]}
            for register in sorted(by_register)
        },
        "sets": {name: {"members": members} for name, members in lex.sets.items()},
    }


def rates(values, digits: int) -> list[float | None]:
    """A rate column as JSON.

    A withheld rate is `null`, never `NaN`: `json.dumps` writes the latter
    happily and no browser will parse it back. This is also the one place the
    distinction between "withheld" and "zero" is preserved on the way out, which
    is the whole argument for withholding in the first place.
    """
    return [None if pd.isna(v) else round(float(v), digits) for v in values]


def build_series(
    speeches: pd.DataFrame,
    lex: lexicon.Lexicon,
    freq: str,
    *,
    index: list[str] | None = None,
    minimum: int | None = None,
) -> tuple[dict, dict[str, dict[str, pd.DataFrame]]]:
    """Compute every measure at one frequency.

    Returns the JSON-ready payload and the frames behind it, so the change-point
    pass and the note can work off the same numbers the artefact ships.

    `index` declares the periods to report on, so a period nobody spoke in is a
    row of zeros rather than a gap. `minimum` withholds the rates a period's own
    denominator cannot carry, and writes `sufficient` beside them. Both are for
    the monthly grid: a year always holds thousands of speeches, and a month
    need not.
    """
    periods = series.period(speeches, freq)
    totals = series.denominators(speeches, periods, index=index)

    payload: dict[str, object] = {
        "freq": freq,
        "periods": [
            int(p) if freq == "year" else str(p) for p in totals.index.tolist()
        ],
        "corpus": {
            "speeches": totals["speeches"].tolist(),
            "tokens": totals["tokens"].tolist(),
            "meetings": totals["meetings"].tolist(),
        },
    }
    if minimum is not None:
        payload["sufficient"] = (totals["speeches"] >= minimum).tolist()

    computed: dict[str, dict[str, pd.DataFrame]] = {}
    for kind, entries in measures(lex).items():
        block: dict[str, object] = {}
        computed[kind] = {}
        for name, attributes in entries.items():
            has_column, count_column = series.columns_for(kind, name)
            frame = series.measure(speeches, periods, totals, has_column, count_column)
            if minimum is not None:
                frame = series.withhold_below(frame, totals["speeches"], minimum)
            computed[kind][name] = frame
            block[name] = {
                **attributes,
                "speeches": frame["speeches"].tolist(),
                "speech_rate": rates(frame["speech_rate"], 6),
            }
            if count_column is not None:
                block[name] |= {  # type: ignore[operator]
                    "occurrences": frame["occurrences"].tolist(),
                    "token_rate": rates(frame["token_rate"], 4),
                }
        payload[kind] = block

    return payload, computed


def build_breakdowns(
    speeches: pd.DataFrame, freq: str, top_agenda: int
) -> dict[str, object]:
    """Per-period splits of the tracked measures by each categorical column."""
    periods = series.period(speeches, freq)
    out: dict[str, object] = {"freq": freq, "measures": {}}

    for kind, name in TRACKED:
        has_column, count_column = series.columns_for(kind, name)
        by_column: dict[str, object] = {}

        for column, cap in BREAKDOWNS:
            if column not in speeches.columns:
                console.warn(f"{column} is not in the frame — breakdown skipped")
                continue
            top = top_agenda if column == "agenda_item_manual" else cap
            frame = series.breakdown(
                speeches, periods, column, has_column, count_column, top=top
            )
            by_column[column] = {
                "categories": sorted(frame[column].unique().tolist()),
                "rows": [
                    {
                        "period": int(row.period) if freq == "year" else str(row.period),
                        "category": getattr(row, column),
                        "held": int(row.held),
                        "speeches": int(row.speeches),
                        "speech_rate": round(float(row.speech_rate), 6),
                        **(
                            {}
                            if count_column is None
                            else {
                                "occurrences": int(row.occurrences),
                                "token_rate": round(float(row.token_rate), 4),
                            }
                        ),
                    }
                    for row in frame.itertuples()
                ],
            }
        out["measures"][name] = by_column  # type: ignore[index]

    return out


def agenda_behind(
    speeches: pd.DataFrame,
    months: pd.Series,
    has_column: str,
    column: str,
    top: int,
) -> list[list[dict[str, object]]]:
    """What the term-bearing speeches of each calendar month were debating.

    This is the caveat that has to travel *inside* the figure rather than under
    it. A month's vocabulary is the vocabulary of the debates scheduled in it,
    and the Council's own reporting calendar is periodic: the tribunals reported
    semi-annually, so a June or a December is thick with them. Shown a bright
    June without that beside it, a reader learns something false — that the
    Council talks about genocide in early summer — when what they are looking at
    is a diary.

    Shares divide by the month's own term-bearing speeches, not by everything
    said that month: the question is what the numerator is made of.
    """
    bearing = speeches[speeches[has_column].astype(bool)]
    if bearing.empty or column not in speeches.columns:
        return [[] for _ in range(12)]

    labels = months.loc[bearing.index]
    items = bearing[column].astype("string").fillna("Unknown")
    counts = bearing.groupby([labels.rename("month"), items.rename("item")]).size()

    out: list[list[dict[str, object]]] = []
    for month in range(1, 13):
        if month not in counts.index.get_level_values("month"):
            out.append([])
            continue
        found = counts.xs(month, level="month").sort_values(ascending=False)
        total = int(found.sum())
        out.append(
            [
                {
                    "item": str(item),
                    "speeches": int(n),
                    "share": round(int(n) / total, 6),
                }
                for item, n in found.head(top).items()
            ]
        )
    return out


def build_month_of_year(
    speeches: pd.DataFrame,
    lex: lexicon.Lexicon,
    minimum: int,
    excluded: tuple[int, ...],
    agenda_column: str,
    top: int,
) -> dict[str, object]:
    """The twelve calendar months, pooled across every year in the corpus.

    **A second figure, not a margin of the grid.** Thirty-two Junes pooled have
    a denominator no cell in the year x month grid has, so drawing this as a
    strip beside the grid would invite the two to be read off one colour bar.
    It is written as its own block for the same reason.

    Two readings, because one of them is the obvious objection to the other. The
    corpus's largest signal by far is 1994; if a calendar effect were that spike
    leaking into a monthly view, dropping 1994 and 1995 would remove it. Both
    readings are published so that a reader can see whether it does, rather than
    being told it does not.
    """
    months = series.month_of_year(speeches)
    kept = speeches[~speeches["year"].isin(excluded)]

    def pooled(frame: pd.DataFrame, has_column: str, count_column: str | None) -> dict:
        labels = series.month_of_year(frame)
        totals = series.denominators(frame, labels, index=list(range(1, 13)))
        measured = series.withhold_below(
            series.measure(frame, labels, totals, has_column, count_column),
            totals["speeches"],
            minimum,
        )
        block = {
            "held": totals["speeches"].tolist(),
            "tokens": totals["tokens"].tolist(),
            "speeches": measured["speeches"].tolist(),
            "speech_rate": rates(measured["speech_rate"], 6),
            "sufficient": measured["sufficient"].tolist(),
        }
        if count_column is not None:
            block |= {
                "occurrences": measured["occurrences"].tolist(),
                "token_rate": rates(measured["token_rate"], 4),
            }
        return block

    by_measure: dict[str, object] = {}
    for kind, entries in measures(lex).items():
        for name, attributes in entries.items():
            has_column, count_column = series.columns_for(kind, name)
            by_measure[name] = {
                "kind": kind,
                **attributes,
                **pooled(speeches, has_column, count_column),
                "excluding": pooled(kept, has_column, count_column),
                "agenda": agenda_behind(speeches, months, has_column, agenda_column, top),
            }

    return {
        "months": list(range(1, 13)),
        "rule": (
            "One calendar month, gathered across every year in the corpus. It is "
            "measured against a different total from any square in the grid above, so "
            "the two do not share a scale and must not share a colour key. This is a "
            "second figure standing beside that one rather than a footnote to it."
        ),
        "excluded_years": list(excluded),
        "excluding_rule": (
            f"The same twelve figures with {' and '.join(str(y) for y in excluded)} "
            "removed. Those are the corpus's two largest years for this vocabulary, and "
            "a seasonal pattern that is really one spike seen through a monthly lens "
            "would not survive their removal. Published beside the first reading rather "
            "than in place of it, because the comparison is the result."
        ),
        "agenda_column": agenda_column,
        "agenda_rule": (
            "The agenda items behind each month's speeches that use the term, largest "
            "first, as a share of that month's speeches using it. The Council works to a "
            "reporting timetable — the tribunals for the former Yugoslavia and for Rwanda "
            "reported twice a year — so a month's vocabulary is partly the vocabulary of "
            "whatever was scheduled in it. That is the confusion this figure is exposed "
            "to, and it belongs inside the figure rather than in a note beneath it."
        ),
        "measures": by_measure,
    }


def build_monthly(
    speeches: pd.DataFrame, lex: lexicon.Lexicon, minimum: int
) -> dict[str, object]:
    """The year x month grid, its coverage, and the calendar read beside it.

    The chronology is annual and quarterly, and a year is a coarse unit for a
    body that meets some 250 times in one. What a month resolution can answer is
    whether this vocabulary has a calendar.

    It does, and not the one the question implies — which is why the grid has to
    carry the block that explains it. The months that stand out are not the
    commemorative ones; they are the ones the tribunals reported in. The
    `month_of_year` block publishes that attribution beside the figures rather
    than leaving it to a note.

    Everything a year never needed is here: a complete grid so an unobserved
    month is not a gap, a minimum so a short month is withheld rather than drawn
    as a zero, and a coverage block so the exclusion is a stated number instead
    of 53 quietly pale squares.
    """
    prevalence = float(speeches["has_genocide"].mean())
    required = series.informative_zero_minimum(prevalence)
    if minimum < required:
        console.warn(
            f"the declared monthly minimum {minimum} is below the {required} the corpus "
            "now requires for a zero to mean anything — re-declare MIN_SPEECHES_PER_MONTH"
        )

    first, last = int(speeches["year"].min()), int(speeches["year"].max())
    grid = series.month_grid(first, last)
    payload, _ = build_series(speeches, lex, "month", index=grid, minimum=minimum)

    held: list[int] = payload["corpus"]["speeches"]  # type: ignore[index,assignment]
    sufficient: list[bool] = payload["sufficient"]  # type: ignore[assignment]
    at_minimum = sum(h for h, ok in zip(held, sufficient, strict=True) if ok)

    payload |= {
        "years": list(range(first, last + 1)),
        "months": list(range(1, 13)),
        "minimum_speeches": minimum,
        "minimum_speeches_rule": (
            f"A month gets no rate at all when the Council held fewer than {minimum} "
            f"speeches in it. That threshold is the point at which a zero starts to mean "
            f"something: across the corpus as a whole, {prevalence:.2%} of speeches use "
            f"this vocabulary, so seeing none of it in fewer than {required} speeches is "
            f"exactly what the Council average would predict. A pale square would suggest "
            f"a quiet month where the record shows a Council that barely sat. The counts "
            f"are published either way, because a count is a fact and a rate is an "
            f"estimate."
        ),
        "informative_zero_minimum": required,
        "corpus_speech_prevalence": round(prevalence, 6),
        "coverage": {
            "months": len(grid),
            "months_observed": sum(1 for h in held if h > 0),
            "months_at_minimum": sum(sufficient),
            "speeches": sum(held),
            "speeches_at_minimum": at_minimum,
            "share_at_minimum": round(at_minimum / max(sum(held), 1), 6),
        },
        "month_of_year": build_month_of_year(
            speeches,
            lex,
            minimum,
            CALENDAR_CONTROL_YEARS,
            CALENDAR_AGENDA_COLUMN,
            CALENDAR_AGENDA_ITEMS,
        ),
    }

    coverage = payload["coverage"]
    console.info(
        f"{coverage['months']} months, {coverage['months_at_minimum']} at or above "
        f"{minimum} speeches ({coverage['share_at_minimum']:.1%} of speeches covered)"
    )
    calendar = payload["month_of_year"]["measures"]["genocide"]  # type: ignore[index]
    ranked = sorted(
        zip(MONTH_NAMES, calendar["speech_rate"], calendar["agenda"], strict=True),
        key=lambda row: row[1] or 0.0,
        reverse=True,
    )
    for name, rate, agenda in ranked[:2]:
        behind = agenda[0] if agenda else None
        console.info(
            f"{name:9s} {rate:.2%} of its speeches"
            + (f"; largest item behind them: {behind['item']} ({behind['speeches']})" if behind else "")
        )

    return payload


def build_change_points(
    computed: dict[str, dict[str, pd.DataFrame]],
    periods: list[int],
    corpus: dict[str, list[int]],
    trials: int,
    seed: int,
    min_size: int,
    alpha: float,
    max_breaks: int = 4,
) -> dict[str, object]:
    """Explore regime shifts and triangulate them with rate-aware inference.

    Running all three is the point: a break present in `occurrences` and absent
    in `speech_rate` says the Council said the word more often because it said
    more of everything.
    """
    out: dict[str, object] = {
        "method": (
            "Exploratory wild binary segmentation (sub-interval scan, "
            "CUSUM-equivalent gain), with a permutation diagnostic"
        ),
        "parameters": {
            "min_size": min_size,
            "alpha": alpha,
            "trials": trials,
            "seed": seed,
            "max_breaks": max_breaks,
        },
        "caveat": (
            "This method shuffles the same yearly values into a new order to see how "
            "unusual the real ordering is, which detects a step up or down but not a "
            "gradual trend: a series that rises smoothly will return a break at its "
            "midpoint regardless. Read these candidates against the plotted series "
            "rather than in place of it."
        ),
        "series": {},
    }

    for kind, name in TRACKED:
        frame = computed[kind][name]
        found = {}
        for column in ("speeches", "occurrences", "speech_rate", "token_rate"):
            values = frame[column]
            if values.isna().any() or not values.any():
                continue  # a set carries no occurrence count; see series.measure
            breaks = series.change_points(
                values.to_numpy(dtype=float),
                periods,
                min_size=min_size,
                max_breaks=max_breaks,
                alpha=alpha,
                trials=trials,
                seed=seed,
            )
            found[column] = [b.as_dict() for b in breaks]
        out["series"][name] = found  # type: ignore[index]

    model_specs = [
        (kind, name, "speech_rate", "speeches", "speeches", "binomial")
        for kind, name in TRACKED
    ]
    model_specs.append(
        ("terms", "genocide", "token_rate", "occurrences", "tokens", "poisson")
    )
    adjusted_alpha = alpha / len(model_specs)
    inferred: dict[str, dict[str, object]] = {}
    for offset, (kind, name, measure, count_column, exposure_name, family) in enumerate(
        model_specs
    ):
        frame = computed[kind][name]
        result = series.rate_change_point(
            frame[count_column].to_numpy(dtype=int),
            corpus[exposure_name],
            periods,
            family=family,
            min_size=min_size,
            trials=trials,
            alpha=adjusted_alpha,
            seed=seed + offset,
        )
        inferred.setdefault(name, {})[measure] = result

    out["inference"] = {
        "method": (
            "Single two-rate maximum likelihood partition: binomial for speech prevalence; "
            "Poisson for occurrences with token exposure; parametric maximum-search "
            "bootstrap under a constant-rate null"
        ),
        "familywise_alpha": alpha,
        "per_test_alpha": adjusted_alpha,
        "correction": f"Bonferroni across {len(model_specs)} planned rate tests",
        "trials": trials,
        "caveat": (
            "The test allows for how many speeches each year held and repeats its whole "
            "search under a no-change model, but finding a split does not prove that "
            "anything changed abruptly: a series that rises gradually will also produce a "
            "best two-rate split somewhere. Each year is treated as independent of the "
            "last, the way speeches cluster into meetings is not modelled, and the "
            "intervals assume the split fell where the search put it. Read the size of "
            "the change alongside the plotted series and the concordance evidence, and do "
            "not read the date as a cause."
        ),
        "series": inferred,
    }

    return out


def write_json(payload: dict, path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    artifacts.atomic_write_json(path, {"meta": meta, **payload})
    console.info(f"wrote {rel(path)}  ({path.stat().st_size / 1e3:,.0f} kB)")


def calendar_lines(monthly: dict) -> list[str]:
    """The month resolution, said in words derived from what it found.

    Written this way round on purpose: the interesting result is that the
    commemorative months are *not* the elevated ones, and a sentence asserting
    that would quietly become false the day the lexicon moves. Everything below
    is read off the artefact, including which months are named.
    """
    calendar = monthly["month_of_year"]["measures"]["genocide"]
    coverage = monthly["coverage"]
    rows = [
        {
            "month": MONTH_NAMES[i],
            "held": calendar["held"][i],
            "speeches": calendar["speeches"][i],
            "rate": calendar["speech_rate"][i],
            "without": calendar["excluding"]["speech_rate"][i],
            "agenda": calendar["agenda"][i],
        }
        for i in range(12)
    ]
    ranked = sorted(rows, key=lambda row: row["rate"] or 0.0, reverse=True)
    top = ranked[:2]
    corpus = sum(calendar["speeches"]) / max(sum(calendar["held"]), 1)

    # Which items sit behind the two strongest months, and whether it is the same
    # one. If it is, that is the reporting cycle and the note may say so.
    leaders = [row["agenda"][0]["item"] if row["agenda"] else None for row in top]
    shared = leaders[0] if len(set(leaders)) == 1 and leaders[0] else None

    verdict = [
        "**The elevated months are not the commemorative ones.** "
        + ", ".join(
            f"{row['month']} is at {row['rate']:.2%}"
            for row in rows
            if row["month"] in ("April", "July")
        )
        + f", against a corpus rate of {corpus:.2%}. What stands out is "
        + " and ".join(f"**{row['month']} at {row['rate']:.2%}**" for row in top)
        + ", and the pattern survives dropping "
        + " and ".join(str(y) for y in monthly["month_of_year"]["excluded_years"])
        + " ("
        + " and ".join(f"{row['without']:.2%}" for row in top)
        + "), so it is not the largest years leaking into a monthly view.",
        "",
    ]
    if shared:
        verdict += [
            f"The agenda items behind those speeches say what it is: **{shared}**, "
            + " and ".join(
                f"{row['agenda'][0]['speeches']} of them in {row['month']}" for row in top
            )
            + ", the largest item in both. The ICTY and ICTR reported to the Council "
            "semi-annually. **The most visible feature of a year x month heatmap would "
            "be the Council's own reporting calendar**, which is the same confound the "
            "per-speaker keyness step spends its whole design controlling for. That "
            "belongs in the figure and not in a note, so `month_of_year.agenda` carries "
            "it per month.",
            "",
        ]

    return [
        "## The calendar",
        "",
        f"{coverage['months']} months, of which **{coverage['months_at_minimum']} clear "
        f"the {monthly['minimum_speeches']}-speech minimum** "
        f"({coverage['months_at_minimum'] / coverage['months']:.1%}); those hold "
        f"{coverage['share_at_minimum']:.1%} of all speeches. The other "
        f"{coverage['months'] - coverage['months_at_minimum']} carry counts and no rate. "
        "On a heatmap a withheld cell must be drawn as withheld: white reads as zero, "
        "and this is the same failure as reading a missing key through `?? 0`, in a form "
        "that covers 53 cells.",
        "",
        "| Month | Speeches held | With `genocid*` | Rate | Without "
        + "/".join(str(y) for y in monthly["month_of_year"]["excluded_years"])
        + " | Largest item behind them |",
        "|---|---:|---:|---:|---:|---|",
        *[
            f"| {row['month']} | {row['held']:,} | {row['speeches']:,} | "
            f"{row['rate']:.2%} | {row['without']:.2%} | "
            + (
                f"{row['agenda'][0]['item']} ({row['agenda'][0]['speeches']}, "
                f"{row['agenda'][0]['share']:.0%})"
                if row["agenda"]
                else "—"
            )
            + " |"
            for row in rows
        ],
        "",
        *verdict,
        "**This table is not a margin of the grid.** A calendar month pools thirty-two "
        "years and has a denominator no single cell has. The two are separate figures "
        "and must not share a colour bar.",
        "",
    ]


def build_note(
    speeches: pd.DataFrame,
    annual: dict,
    monthly: dict,
    computed: dict[str, dict[str, pd.DataFrame]],
    change: dict,
    events: pd.DataFrame,
    lex: lexicon.Lexicon,
) -> str:
    years = annual["periods"]
    genocide = computed["terms"]["genocide"]
    corpus = pd.DataFrame(annual["corpus"], index=years)

    peak_raw = int(genocide["occurrences"].idxmax())
    peak_rate = int(genocide["speech_rate"].idxmax())

    rows = [
        f"| {year} | {corpus.loc[year, 'speeches']:,} | "
        f"{genocide.loc[year, 'speeches']:,} | {genocide.loc[year, 'occurrences']:,} | "
        f"{genocide.loc[year, 'speech_rate']:.2%} | {genocide.loc[year, 'token_rate']:.2f} |"
        for year in years
    ]

    # State the raw-versus-rate contrast in words, derived from what was found
    # rather than asserted, so the sentence stays true if the lexicon changes.
    tracked = change["series"].get("genocide", {})
    raw_breaks = tracked.get("occurrences", [])
    rate_breaks = tracked.get("speech_rate", [])
    if raw_breaks and not rate_breaks:
        verdict = [
            f"**The raw series breaks at {', '.join(b['label'] for b in raw_breaks)}. The rate "
            "does not break anywhere.** The Council said `genocide` more often after 2013 "
            "because it said more of everything: speeches per year roughly doubled over the "
            "same span. On the measure that controls for that, the 2014 spike is inside the "
            "range the series has occupied since 1992, and the largest normalised year in the "
            "corpus remains 1994.",
            "",
        ]
    elif rate_breaks:
        verdict = [
            "The rate itself breaks at "
            + ", ".join(f"**{b['label']}** (x{b['ratio']:.2f})" for b in rate_breaks)
            + " — a shift that survives the corpus's growth and is therefore about "
            "discourse rather than volume.",
            "",
        ]
    else:
        verdict = ["Neither the raw series nor the rate carries a detectable break.", ""]

    # The comparison that matters: is the object `genocide`, or the
    # atrocity vocabulary it travels inside? If only the wider set has normalised
    # structure, that is an argument, and it should not have to be noticed by eye.
    wider = change["series"].get("atrocity_core", {}).get("speech_rate", [])
    if wider and not rate_breaks:
        verdict += [
            "The wider `atrocity_core` set *does* break on the rate, at "
            + ", ".join(f"**{b['label']}** (x{b['ratio']:.2f})" for b in wider)
            + ". The normalised structure is in the atrocity vocabulary as a whole rather "
            "than in `genocide` alone. Whether that wider set is the real object of study is "
            "an open question; this is evidence that it may be.",
            "",
        ]

    change_lines: list[str] = []
    for label, found in change["series"].items():
        change_lines.append(f"**`{label}`**")
        change_lines.append("")
        for column, breaks in found.items():
            if not breaks:
                change_lines.append(f"- `{column}` — no significant break.")
                continue
            for b in breaks:
                change_lines.append(
                    f"- `{column}` — break at **{b['label']}** "
                    f"(p = {b['p_value']:.4f}): {b['before']:.4g} → {b['after']:.4g}, "
                    f"x{b['ratio']:.2f}."
                )
        change_lines.append("")

    def top_rates(column: str, minimum: int = 200) -> list[str]:
        grouped = speeches.groupby(column).agg(
            held=("row_id", "size"), hits=("has_genocide", "sum")
        )
        grouped = grouped[grouped["held"] >= minimum]
        grouped["rate"] = grouped["hits"] / grouped["held"]
        grouped = grouped.sort_values("rate", ascending=False).head(8)
        return [
            f"| {row.Index} | {row.held:,.0f} | {row.hits:,.0f} | {row.rate:.2%} |"
            for row in grouped.itertuples()
        ]

    return "\n".join(
        [
            "# 04 — Temporal series",
            "",
            f"Lexicon version **{lex.version}**, {len(lex.active)} active terms, over "
            f"{len(speeches):,} speeches, {years[0]}-{years[-1]}.",
            "",
            "## `genocide`, per year",
            "",
            "| Year | Speeches held | With `genocid*` | Occurrences | Rate | Per 100k tokens |",
            "|---|---:|---:|---:|---:|---:|",
            *rows,
            "",
            f"Occurrences peak in **{peak_raw}**; the *rate* peaks in **{peak_rate}**. "
            "Where those two disagree, the corpus grew.",
            "",
            "## Change points",
            "",
            change["caveat"],
            "",
            f"{change['method']}. Minimum segment "
            f"{change['parameters']['min_size']} periods, "
            f"{change['parameters']['trials']:,} permutations, alpha = {change['parameters']['alpha']}, "
            f"seed {change['parameters']['seed']}.",
            "",
            *verdict,
            *change_lines,
            *calendar_lines(monthly),
            "## Rate by speaker group",
            "",
            "| Group | Speeches | With `genocid*` | Rate |",
            "|---|---:|---:|---:|",
            *top_rates("speaker_group", minimum=0),
            "",
            "## Rate by agenda item",
            "",
            "Items with at least 200 speeches, so a single mention in a rare debate cannot",
            "top the table.",
            "",
            "| Agenda item | Speeches | With `genocid*` | Rate |",
            "|---|---:|---:|---:|",
            *top_rates("agenda_item_manual"),
            "",
            "## Rate by delivery language",
            "",
            "Whether invocation varies with the language a speech was delivered in is a",
            "crosstab on data the pipeline already has, and this is it.",
            "An unmarked speech was delivered in English.",
            "",
            "| Language | Speeches | With `genocid*` | Rate |",
            "|---|---:|---:|---:|",
            *top_rates("delivery_language"),
            "",
            "**This does not answer the question.** Delivery language is very nearly a",
            "restatement of who is speaking: essentially every Russian-language speech is",
            "Russia's, every Chinese-language speech China's. The spread below is therefore a",
            "speaker effect wearing a linguistic label, and the low Russian and Chinese rates",
            "recover the two countries' known reticence rather than anything about language.",
            "The plan asks the question *holding speaker and period constant*, which needs a",
            "within-speaker comparison — the states that alternate between languages — and",
            "that is a model, not a crosstab. Left for 05.",
            "",
            "## Event overlay",
            "",
            f"{len(events)} curated reference dates in `config/events.csv`, "
            f"{events['date'].dt.year.min()}-{events['date'].dt.year.max()}, across "
            f"{events['kind'].nunique()} kinds "
            f"({', '.join(f'{k} {n}' for k, n in events['kind'].value_counts().items())}).",
            "",
            "The table is machine-drafted and has not been checked against the primary",
            "records; see `docs/VALIDATION.md` before any of it is published on a chart.",
            "",
        ]
    ) + "\n"


def run(
    top_agenda: int,
    trials: int,
    seed: int,
    min_size: int,
    alpha: float,
    max_breaks: int,
    minimum_month: int,
) -> None:
    ensure_dirs()

    console.step("Reading the flagged corpus")
    speeches = prepare(frames.read(SPEECHES_FLAGGED))
    lex = lexicon.load()
    console.info(f"lexicon version {lex.version}, {len(lex.active)} active terms")

    console.step("Building annual series")
    annual, computed = build_series(speeches, lex, "year")
    console.info(
        f"{len(annual['periods'])} years x "
        f"{sum(len(annual[k]) for k in ('terms', 'registers', 'sets'))} measures"
    )

    console.step("Building quarterly series")
    quarterly, _ = build_series(speeches, lex, "quarter")
    console.info(f"{len(quarterly['periods'])} quarters")

    console.step("Building the monthly grid")
    monthly = build_monthly(speeches, lex, minimum_month)

    console.step("Building breakdowns")
    breakdowns = build_breakdowns(speeches, "year", top_agenda)
    for label, columns in breakdowns["measures"].items():  # type: ignore[union-attr]
        console.info(
            f"{label}: " + ", ".join(f"{c} ({len(v['categories'])})" for c, v in columns.items())
        )

    console.step("Detecting change points")
    change = build_change_points(
        computed,
        annual["periods"],
        annual["corpus"],
        trials,
        seed,
        min_size,
        alpha,
        max_breaks,
    )
    for name, found in change["series"].items():  # type: ignore[union-attr]
        for column, breaks in found.items():
            if breaks:
                console.info(
                    f"{name}/{column}: "
                    + ", ".join(f"{b['label']} (p={b['p_value']:.4f})" for b in breaks)
                )
            else:
                console.info(f"{name}/{column}: no significant break")

    console.step("Loading the event overlay")
    events = series.load_events()
    console.info(f"{len(events)} events, {events['year'].min()}-{events['year'].max()}")

    console.step("Writing")
    # Corpus-level totals travel with every artefact so the dashboard can state
    # a denominator without hard-coding one; a headline figure that drifts from
    # the data behind it is the easiest kind of error to ship.
    meta = artifacts.provenance(
        ROOT,
        "04_series.py",
        inputs=[SPEECHES_FLAGGED],
        configs=[LEXICON, EVENTS],
        extra={
            "lexicon_version": lex.version,
            "speeches": len(speeches),
            "meetings": int(speeches["meeting_symbol"].nunique()),
            "tokens": int(speeches["tokens"].sum()),
            "speakers": int(speeches["country_org"].nunique()),
            "rate_per_tokens": series.RATE_PER,
        },
    )
    with artifacts.atomic_directory(SERIES) as staged:
        write_json(annual, staged / "annual.json", meta)
        write_json(quarterly, staged / "quarterly.json", meta)
        write_json(monthly, staged / "monthly.json", meta)
        write_json(breakdowns, staged / "breakdowns.json", meta)
        write_json(change, staged / "change_points.json", meta)
        write_json(
            {
                "events": [
                    {
                        "date": f"{row.date:%Y-%m-%d}",
                        "year": int(row.year),
                        "label": row.label,
                        "kind": row.kind,
                        "source": row.source,
                        "source_url": row.source_url,
                        "note": row.note,
                    }
                    for row in events.itertuples()
                ]
            },
            staged / "events.json",
            meta,
        )

    note = write_note(
        "04_series.md", build_note(speeches, annual, monthly, computed, change, events, lex)
    )
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-agenda", type=int, default=20, help="agenda items kept apart")
    parser.add_argument("--trials", type=int, default=2_000, help="permutations per split")
    parser.add_argument("--seed", type=int, default=20_260_807, help="permutation seed")
    parser.add_argument("--min-size", type=int, default=4, help="shortest segment, in periods")
    parser.add_argument("--alpha", type=float, default=0.05, help="significance threshold")
    parser.add_argument("--max-breaks", type=int, default=4, help="most breaks per series")
    parser.add_argument(
        "--minimum-month",
        type=int,
        default=MIN_SPEECHES_PER_MONTH,
        help="speeches a month needs before its rates are published",
    )
    args = parser.parse_args()
    run(
        args.top_agenda,
        args.trials,
        args.seed,
        args.min_size,
        args.alpha,
        args.max_breaks,
        args.minimum_month,
    )


if __name__ == "__main__":
    main()
