"""Step 04's artefacts: what each series, grid and test publishes, and how.

`scripts/04_series.py` reads the flagged corpus, calls these and writes what
they return; the arithmetic underneath them is :mod:`lib.series`'s. Each
builder returns a JSON-ready block, and `build_series` also returns the frames
behind it, so the change-point pass and the note work off the same numbers the
artefact ships.
"""

from __future__ import annotations

import pandas as pd

from . import console, lexicon, scopes, series

#: Measures the change-point pass and the breakdowns run on, as (kind, name).
#: One, since lexicon v5 retired the sets: `atrocity_core` used to be dated
#: beside it as "the set that may be the real object of study", and a category
#: this project invented is not a candidate for that — a reader watching its
#: line could not tell which of its five phrases had moved. The three atrocity
#: phrases are dated one at a time in the artefact like every other term, and
#: R8's genocide-free corpus is published beside them as a population.
#:
#: All headline tests use the full word-family count, matching the concordance.
TRACKED = [("terms", "genocide")]

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
MIN_SPEECHES_PER_MONTH = 125

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
]

def measures(lex: lexicon.Lexicon) -> dict[str, dict[str, dict]]:
    """Every series to compute, all of them over a single term.

    Maps each name to the attributes that describe it in the artefact; the
    columns behind it come from `series.columns_for`.

    Until v5 this also returned a series per register and per named set. They
    were roll-ups over several terms, published as though the grouping were a
    property of the corpus rather than a choice made in `config/lexicon.yml`,
    and a reader could not tell which word moved when one of those lines moved.
    A term's `register` survives here as an attribute, because the picker groups
    and colours by it; nothing is counted by it.
    """
    return {
        "terms": {
            **{
                term.name: {"tier": term.tier, "register": term.register}
                for term in lex.active
            },
            # A derived measure travels with the terms because it is a term's
            # series minus another's and a reader picks it from the same list.
            # It carries `derived_from` so that list can say so.
            **{
                measure.name: {
                    "tier": measure.tier,
                    "register": measure.register,
                    "derived_from": measure.minuend,
                    "derived_minus": list(measure.subtrahends),
                }
                for measure in lex.derived.values()
            },
        },
    }


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
            "words": totals["words"].tolist(),
            "meetings": totals["meetings"].tolist(),
        },
    }
    if minimum is not None:
        payload["sufficient"] = (totals["speeches"] >= minimum).tolist()
    payload["corpora"] = scopes.comparison_corpora(
        speeches,
        periods,
        totals,
        minimum=minimum,
    )

    # Meeting-clustered bands for the annual and quarterly series, where every
    # period holds enough meetings to resample; the monthly grid keeps Wilson.
    clustered: dict[str, tuple] = {}
    if freq in {"year", "quarter"}:
        flags = {
            name: series.columns_for(kind, name)[0]
            for kind, entries in measures(lex).items()
            for name in entries
        }
        clustered = series.meeting_bootstrap(speeches, periods, totals.index, flags)
        payload["cluster_interval"] = {
            "resamples": series.CLUSTER_RESAMPLES,
            "seed": series.CLUSTER_SEED,
            "unit": "meeting",
            "method": "percentile interval over whole meetings resampled within each period",
        }

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
                "speech_rate": series.rates(frame["speech_rate"], 6),
                "speech_rate_low": series.rates(frame["speech_rate_low"], 6),
                "speech_rate_high": series.rates(frame["speech_rate_high"], 6),
            }
            if name in clustered:
                low, high = clustered[name]
                block[name] |= {  # type: ignore[operator]
                    "speech_rate_cluster_low": series.rates(pd.Series(low), 6),
                    "speech_rate_cluster_high": series.rates(pd.Series(high), 6),
                }
            if count_column is not None:
                block[name] |= {  # type: ignore[operator]
                    "occurrences": frame["occurrences"].tolist(),
                    "token_rate": series.rates(frame["token_rate"], 4),
                }
        payload[kind] = block

    return payload, computed


#: The splits the rate change is decomposed along, and the measure decomposed.
DECOMPOSED = ("agenda_item_manual", "speaker_group")
DECOMPOSED_TERM = "genocide"


def build_decomposition(speeches: pd.DataFrame) -> dict[str, object]:
    """The decade-to-decade change in the genocide speech rate, taken apart.

    Is the word rising because the Council spends more of its time on the
    situations it is used about, or because it is used more within them? One
    Kitagawa decomposition per split: by agenda item, which separates agenda
    composition from use, and by speaker group, which separates who holds the
    floor from how they speak (docs/ROADMAP.md, RV18).
    """
    decades = (speeches["year"] // 10 * 10).astype(int)
    has_column = series.columns_for("terms", DECOMPOSED_TERM)[0]
    splits = {}
    for column in DECOMPOSED:
        rows = series.rate_decomposition(speeches, decades, has_column, column)
        splits[column] = [{**row, "group_column": column} for row in rows]
    return {
        "term": DECOMPOSED_TERM,
        "unit": "speech_rate",
        "periods": "decade",
        "method": (
            "Kitagawa (1955) two-factor decomposition of the change in the share of "
            "speeches carrying the term between consecutive decades: composition "
            "(the groups' shares of speeches) plus within (the rate inside each "
            "group). A group present in one decade only contributes composition."
        ),
        "splits": splits,
    }


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
                        "speech_rate_low": round(float(row.speech_rate_low), 6),
                        "speech_rate_high": round(float(row.speech_rate_high), 6),
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
            "words": totals["words"].tolist(),
            "speeches": measured["speeches"].tolist(),
            "speech_rate": series.rates(measured["speech_rate"], 6),
            "speech_rate_low": series.rates(measured["speech_rate_low"], 6),
            "speech_rate_high": series.rates(measured["speech_rate_high"], 6),
            "sufficient": measured["sufficient"].tolist(),
        }
        if count_column is not None:
            block |= {
                "occurrences": measured["occurrences"].tolist(),
                "token_rate": series.rates(measured["token_rate"], 4),
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

    held: list[int] = payload["corpus"]["speeches"]
    sufficient: list[bool] = payload["sufficient"]
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
    calendar = payload["month_of_year"]["measures"]["genocide"]
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
    speeches: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Explore regime shifts and triangulate them with rate-aware inference.

    Running all three is the point: a break present in `occurrences` and absent
    in `speech_rate` says the Council said the word more often because it said
    more of everything.

    `speeches` is the flagged corpus the annual frames were built from. When it
    is given, the rate tests are calibrated against a null that permutes
    meetings across years (`series.meeting_blocks`); without it they fall back
    to the independent-speech null, which the artefact then says in `null`.
    The pipeline always passes it; the parameter is optional so the function
    can be exercised on aggregated fixtures.
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
                continue  # a withheld or all-zero column has nothing to split
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
        ("terms", "genocide", "token_rate", "occurrences", "words", "poisson")
    )
    adjusted_alpha = alpha / len(model_specs)
    position = {label: index for index, label in enumerate(periods)}
    year_of = series.period(speeches, "year") if speeches is not None else None
    inferred: dict[str, dict[str, object]] = {}
    for offset, (kind, name, measure, count_column, exposure_name, family) in enumerate(
        model_specs
    ):
        frame = computed[kind][name]
        blocks = None
        if speeches is not None:
            has_column, raw_count_column = series.columns_for(kind, name)
            # Every measure is a term and every term has a count column, but
            # `columns_for` is typed for a kind of measure that would not.
            blocks = series.meeting_blocks(
                speeches,
                year_of,
                has_column if family == "binomial" else raw_count_column,  # type: ignore[arg-type]
                None if family == "binomial" else "words",
            )
            blocks["period"] = blocks["period"].map(position)
        result = series.rate_change_point(
            frame[count_column].to_numpy(dtype=int),
            corpus[exposure_name],
            periods,
            family=family,
            min_size=min_size,
            trials=trials,
            alpha=adjusted_alpha,
            seed=seed + offset,
            blocks=blocks,
        )
        inferred.setdefault(name, {})[measure] = result

    clustered = speeches is not None
    out["inference"] = {
        "method": (
            "Single two-rate maximum likelihood partition: binomial for speech prevalence; "
            "Poisson for occurrences with token exposure; "
            + (
                "calibrated by permuting meetings across years under a constant-rate null, "
                "with the independent-speech parametric bootstrap reported beside it"
                if clustered
                else "parametric maximum-search bootstrap under a constant-rate null"
            )
        ),
        "null": series.NULL_MEETING_BLOCK if clustered else series.NULL_INDEPENDENT,
        "familywise_alpha": alpha,
        "per_test_alpha": adjusted_alpha,
        "correction": f"Bonferroni across {len(model_specs)} planned rate tests",
        "trials": trials,
        "caveat": (
            "The test allows for how many speeches each year held and repeats its whole "
            "search under a no-change model, but finding a split does not prove that "
            "anything changed abruptly: a series that rises gradually will also produce a "
            "best two-rate split somewhere. "
            + (
                "The null moves whole meetings between years, so a single debate that "
                "used the word two hundred times counts as one draw rather than two "
                "hundred; the p-value under the older assumption that every speech is "
                "independent is kept beside it, and the gap between the two is the size "
                "of that clustering. "
                if clustered
                else "Each year is treated as independent of the last and the way speeches "
                "cluster into meetings is not modelled. "
            )
            + "The intervals assume the split fell where the search put it. Read the size "
            "of the change alongside the plotted series and the concordance evidence, and "
            "do not read the date as a cause."
        ),
        "series": inferred,
    }

    return out

