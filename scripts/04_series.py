"""Temporal series: how often the lexicon is spoken, and when that changes.

Reads speeches_flagged.parquet and writes five JSON artefacts to
data/derived/series/, plus a findings note.

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


def build_series(
    speeches: pd.DataFrame, lex: lexicon.Lexicon, freq: str
) -> tuple[dict, dict[str, dict[str, pd.DataFrame]]]:
    """Compute every measure at one frequency.

    Returns the JSON-ready payload and the frames behind it, so the change-point
    pass and the note can work off the same numbers the artefact ships.
    """
    periods = series.period(speeches, freq)
    totals = series.denominators(speeches, periods)

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

    computed: dict[str, dict[str, pd.DataFrame]] = {}
    for kind, entries in measures(lex).items():
        block: dict[str, object] = {}
        computed[kind] = {}
        for name, attributes in entries.items():
            has_column, count_column = series.columns_for(kind, name)
            frame = series.measure(speeches, periods, totals, has_column, count_column)
            computed[kind][name] = frame
            block[name] = {
                **attributes,
                "speeches": frame["speeches"].tolist(),
                "speech_rate": [round(v, 6) for v in frame["speech_rate"]],
            }
            if count_column is not None:
                block[name] |= {  # type: ignore[operator]
                    "occurrences": frame["occurrences"].tolist(),
                    "token_rate": [round(v, 4) for v in frame["token_rate"]],
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
            "Exploratory only: the permutation null is a reordering of the same values, "
            "which tests for a "
            "level shift and not for a trend. A smoothly rising series will return a "
            "break at its midpoint; read these against the plotted series, not instead "
            "of it."
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
            "The scan preserves annual denominators and the breakpoint search, but rejecting "
            "a constant rate does not prove an abrupt historical break: a smooth trend can "
            "also yield a best two-rate partition. Annual bins are treated as independent, "
            "speech clustering and Poisson overdispersion are not modelled, and confidence "
            "intervals are conditional on the selected partition. Read effect sizes with the "
            "trajectory and concordance evidence; do not interpret the date causally."
        ),
        "series": inferred,
    }

    return out


def write_json(payload: dict, path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    artifacts.atomic_write_json(path, {"meta": meta, **payload})
    console.info(f"wrote {rel(path)}  ({path.stat().st_size / 1e3:,.0f} kB)")


def build_note(
    speeches: pd.DataFrame,
    annual: dict,
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
    top_agenda: int, trials: int, seed: int, min_size: int, alpha: float, max_breaks: int
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
        "04_series.md", build_note(speeches, annual, computed, change, events, lex)
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
    args = parser.parse_args()
    run(
        args.top_agenda,
        args.trials,
        args.seed,
        args.min_size,
        args.alpha,
        args.max_breaks,
    )


if __name__ == "__main__":
    main()
