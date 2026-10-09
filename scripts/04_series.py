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
the wrong story by default. Annual speech volume varies substantially across
1946-2024; anything not divided by that is partly a chart of the Council's growth. Every
speech rate also carries its Wilson 95% interval, so a share is published with
the width its denominator gives it rather than as a bare point.

The change-point pass is where that becomes a finding rather than a caveat. It
is run on the raw count *and* on the rate, and the note reports both, so the
difference between "genocide was said more often" and "genocide was said more
often than other things" is on the page rather than in a footnote. The rate
test's null permutes meetings across years rather than treating every speech
as an independent draw — one debate can hold two hundred occurrences — and the
p-value under the older independent null is published beside it, so the size
of that clustering is a number rather than a sentence.

Usage:
    python scripts/04_series.py [--top-agenda 20] [--trials 2000] [--seed 20260807]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, frames, lexicon, series
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

# The artefacts' builders live in lib.series_payload; this script reads,
# writes and narrates. Every name imported with a redundant `as` is a
# re-export, kept importable from this module for the callers and tests that
# still reach it here; new code imports it from where it is defined.
from lib.series_payload import (
    BREAKDOWNS,
    MIN_SPEECHES_PER_MONTH,
    MONTH_NAMES,
    build_breakdowns,
    build_change_points,
    build_decomposition,
    build_monthly,
    build_series,
)
from lib.series_payload import CALENDAR_AGENDA_COLUMN as CALENDAR_AGENDA_COLUMN
from lib.series_payload import CALENDAR_AGENDA_ITEMS as CALENDAR_AGENDA_ITEMS
from lib.series_payload import CALENDAR_CONTROL_YEARS as CALENDAR_CONTROL_YEARS
from lib.series_payload import DECOMPOSED as DECOMPOSED
from lib.series_payload import DECOMPOSED_TERM as DECOMPOSED_TERM
from lib.series_payload import TRACKED as TRACKED
from lib.series_payload import agenda_behind as agenda_behind
from lib.series_payload import build_month_of_year as build_month_of_year
from lib.series_payload import measures as measures

#: The corpus columns this step reads besides the lexicon's own. It counts
#: speeches and words and never reads what was said, so the speech text — most
#: of the parquet's size — stays on disk.
CORPUS_COLUMNS = [
    "row_id",
    "year",
    "date",
    "meeting_symbol",
    "country_org",
    "iso3",
    "tokens",
    "words",
    *(column for column, _ in BREAKDOWNS),
]


def read_columns(lex: lexicon.Lexicon) -> list[str]:
    """Every column to read: the corpus columns, then each measure's two."""
    names = [*(term.name for term in lex.active), *lex.derived]
    return [
        *CORPUS_COLUMNS,
        *(column for name in names for column in series.columns_for("terms", name)),
    ]


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

    def shown(rate: float | None) -> str:
        return "withheld" if rate is None else f"{rate:.2%}"

    commemorative = [row for row in rows if row["month"] in ("April", "July")]
    top_names = {row["month"] for row in top}
    # Derived, not asserted: the review of 1 September 2026 found the sentence
    # "the elevated months are not the commemorative ones" written
    # unconditionally, so it would have stayed true in prose whatever the data
    # said. It is now a reading of the ranking, and a withheld month is named
    # as withheld rather than formatted as a number it does not have.
    if any(row["month"] in top_names for row in commemorative):
        heading = "**A commemorative month is among the elevated ones.** "
    else:
        heading = "**The elevated months are not the commemorative ones.** "
    verdict = [
        heading
        + ", ".join(f"{row['month']} is at {shown(row['rate'])}" for row in commemorative)
        + f", against a corpus rate of {corpus:.2%}. What stands out is "
        + " and ".join(f"**{row['month']} at {shown(row['rate'])}**" for row in top)
        + ", and dropping "
        + " and ".join(str(y) for y in monthly["month_of_year"]["excluded_years"])
        + " leaves "
        + " and ".join(shown(row["without"]) for row in top)
        + (
            ", so it is not the largest years leaking into a monthly view."
            if all(row["without"] is not None for row in top)
            else "; with a month withheld, whether the pattern survives cannot be read here."
        ),
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
            f"{shown(row['rate'])} | {shown(row['without'])} | "
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


UNIT_NAMES = {"speech_rate": "share of speeches", "token_rate": "rate per 100k words"}


def inference_lines(inference: dict) -> list[str]:
    """The corrected rate tests, in words that are true by construction."""
    clustered = inference.get("null") == series.NULL_MEETING_BLOCK
    lines = [
        "### Rate tests",
        "",
        f"Threshold {inference['per_test_alpha']:.4g} per test ({inference['correction']}), "
        f"{inference['trials']:,} trials, null: `{inference.get('null', 'unstated')}`.",
        "",
    ]
    for name, by_measure in inference["series"].items():
        for measure, result in by_measure.items():
            unit = UNIT_NAMES.get(measure, measure)
            if result is None:
                lines.append(f"- `{name}`, {unit}: no two-rate partition improves on one rate.")
                continue
            scale = 100_000 if measure == "token_rate" else 1
            before = result["before"] * scale
            after = result["after"] * scale
            shown = (
                f"{before:.2%} → {after:.2%}" if scale == 1 else f"{before:.2f} → {after:.2f}"
            )
            ratio = "" if result["ratio"] is None else f", x{result['ratio']:.2f}"
            calibration = f"p = {result['p_value']:.4f}"
            if clustered:
                calibration += (
                    f" under the meeting-block null, against "
                    f"{result['p_value_independent']:.4f} with speeches treated as independent"
                )
            outcome = (
                "clears the corrected threshold"
                if result["accepted"]
                else "does not clear the corrected threshold"
            )
            lines.append(
                f"- `{name}`, {unit}: best partition starts in **{result['label']}** "
                f"({shown}{ratio}); {calibration}; **{outcome}**."
            )
    lines.append("")
    accepted = [
        (name, measure)
        for name, by_measure in inference["series"].items()
        for measure, result in by_measure.items()
        if result is not None and result["accepted"]
    ]
    if not accepted:
        lines += [
            "No rate test clears its threshold: one steady rate is not rejected for any "
            "measure, and any break in the raw counts is the Council's growth.",
            "",
        ]
    # The paragraph that used to stand here said "only the wider set rejects a
    # single rate" whenever `atrocity_core` was accepted and `genocide` was not.
    # The wider set is gone with lexicon v5, and there is nothing to say in its
    # place: the tested measure is named on every line above.
    return lines


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

    # The verdict is read off the corrected `inference` block — the numbers the
    # site publishes — and every sentence is built from the result rather than
    # written in advance. The previous version narrated the exploratory block
    # with years typed into the prose ("after 2013", "remains 1994"), which
    # would have stayed true in words whatever the data said.
    inference = change["inference"]
    verdict = inference_lines(inference)

    change_lines: list[str] = [
        "### Exploratory segmentation",
        "",
        "Not a result. Kept visible as a diagnostic of where a reordering of the same "
        "annual values would and would not split.",
        "",
    ]
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
            "Every series here is one term. Since lexicon v5 there are no register or",
            "set roll-ups: a line summed over a family of words could not be attributed",
            "to any of them by the reader watching it move, and the picker has always",
            "taken several terms at once. R8's genocide-free atrocity corpus is the one",
            "thing below that spans several terms, and it is a population rather than a",
            "measure — a speech enters it once however many of the three phrases it uses.",
            "",
            "## `genocide`, per year",
            "",
            "| Year | Speeches held | With `genocid*` | Occurrences | Rate | Per 100k words |",
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
    lex = lexicon.load()
    speeches = frames.read(SPEECHES_FLAGGED, columns=read_columns(lex))
    console.info(f"lexicon version {lex.version}, {len(lex.active)} active terms")

    console.step("Building annual series")
    annual, computed = build_series(speeches, lex, "year")
    console.info(
        f"{len(annual['periods'])} years x "
        f"{len(annual['terms'])} measures"
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

    console.step("Decomposing the genocide rate, decade to decade")
    decomposition = build_decomposition(speeches)
    for block in decomposition["splits"].values():  # type: ignore[union-attr]
        latest = block[-1]
        console.info(
            f"{block[0]['group_column']}: {latest['from']}s → {latest['to']}s change "
            f"{latest['change']:+.4f} = composition {latest['composition']:+.4f} "
            f"+ within {latest['within']:+.4f}"
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
        speeches=speeches,
    )
    for name, by_measure in change["inference"]["series"].items():  # type: ignore[index]
        for measure, result in by_measure.items():
            if result is None:
                console.info(f"{name}/{measure}: no partition improves on one rate")
                continue
            console.info(
                f"{name}/{measure}: {result['label']} "
                f"p={result['p_value']:.4f} (independent null {result['p_value_independent']:.4f}) "
                f"{'accepted' if result['accepted'] else 'not accepted'}"
            )
    for name, found in change["series"].items():  # type: ignore[union-attr]
        for column, breaks in found.items():
            if breaks:
                console.info(
                    f"exploratory {name}/{column}: "
                    + ", ".join(f"{b['label']} (p={b['p_value']:.4f})" for b in breaks)
                )
            else:
                console.info(f"exploratory {name}/{column}: no significant break")

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
            "words": int(speeches["words"].sum()),
            "codebook_tokens": int(speeches["tokens"].sum()),
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
        write_json(decomposition, staged / "decomposition.json", meta)
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
