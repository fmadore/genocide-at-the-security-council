"""Lexicometry: what the word travels with, and what distinguishes its speeches.

Reads speeches_flagged.parquet and writes four JSON artefacts to
data/derived/lexical/, plus a findings note.

    collocates.json         node terms at three window widths, whole corpus
    collocates_sliced.json  `genocide` at one width, by period / group / country
    keyness.json            genocide speeches against a matched control set
    network.json            PMI between the lexicon's terms, whole corpus and by period

The word clouds docs/PLAN.md §3.2 asks for are a rendering of these tables, not
a separate artefact: a cloud sized by log-likelihood over a stated stoplist is
the collocate table drawn differently, and shipping it as its own file would
invite it to drift from the numbers it claims to depict.

Usage:
    python scripts/05_lexical.py [--limit 100] [--countries 8] [--seed 20260807]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, frames, lexical, lexicon
from lib.paths import (
    LEXICAL,
    ROOT,
    SPEECHES_FLAGGED,
    STOPWORDS,
    ensure_dirs,
    rel,
    write_note,
)
from lib.paths import (
    LEXICON as LEXICON_CONFIG,
)

#: Nodes to profile. `genocide` is the object; the two neighbours are there to
#: give its profile something to be different from.
NODES = ["genocide", "ethnic_cleansing", "crimes_against_humanity"]

#: docs/PLAN.md §3.2 asks for several windows. ±5 is the phrase, ±15 the
#: argument the phrase sits in; ±8 is the compromise the slices use.
WIDTHS = [5, 8, 15]
SLICE_WIDTH = 8
MIN_PROFILE_SPEECHES = 20

#: Periods for the sliced views. Round decades, so the boundaries are not
#: chosen to flatter a result — 04's change points are the empirical dating,
#: and these are deliberately not them.
PERIODS: list[tuple[str, int, int]] = [
    ("1992-1999", 1992, 1999),
    ("2000-2009", 2000, 2009),
    ("2010-2019", 2010, 2019),
    ("2020-2023", 2020, 2023),
]

#: What a control speech has to match on. Year holds the occasion constant,
#: agenda item the subject, speaker group the institutional position.
MATCH_ON = ["year", "agenda_item_manual", "speaker_group"]

COLUMNS = [
    "row_id",
    "year",
    "country_org",
    "agenda_item_manual",
    "speaker_group",
    "text",
    "body_start",
]


def node_terms(lex: lexicon.Lexicon) -> list[lexicon.Term]:
    missing = [n for n in NODES if n not in lex.terms]
    if missing:
        console.fail(f"nodes not in config/lexicon.yml: {', '.join(missing)}")
    return [lex.terms[n] for n in NODES]


def build_collocates(
    bodies: pd.Series,
    terms: list[lexicon.Term],
    reference,
    reference_total: int,
    stopwords: frozenset[str],
    limit: int,
) -> dict[str, object]:
    """Each node at each window width, over the whole corpus."""
    out: dict[str, object] = {}
    for term in terms:
        widths: dict[str, object] = {}
        for width in WIDTHS:
            rows, occurrences, tokens = lexical.collocates(
                bodies, term, width, reference, reference_total, stopwords, limit=limit
            )
            widths[str(width)] = {
                "occurrences": occurrences,
                "window_tokens": tokens,
                "collocates": rows,
            }
            console.info(
                f"{term.name:26s} ±{width:<3d} {occurrences:>6,} occurrences  "
                f"{tokens:>8,} window tokens  {len(rows)} kept"
            )
        out[term.name] = {"pattern": term.pattern, "register": term.register, "widths": widths}
    return out


def build_slices(
    speeches: pd.DataFrame,
    term: lexicon.Term,
    reference,
    reference_total: int,
    stopwords: frozenset[str],
    limit: int,
    countries: int,
) -> dict[str, object]:
    """`genocide` sliced by period, speaker group and speaker.

    The per-speaker slice is the one docs/PLAN.md §3.2 expects to be a headline:
    Rwanda, Russia and Liechtenstein use the same word to do different things.
    """
    flag = f"{lexicon.HAS}{term.name}"
    holders = speeches[speeches[flag]]

    def profile(subset: pd.DataFrame) -> dict[str, object]:
        rows, occurrences, tokens = lexical.collocates(
            frames.body(subset),
            term,
            SLICE_WIDTH,
            reference,
            reference_total,
            stopwords,
            limit=limit,
        )
        return {
            "speeches": len(subset),
            "occurrences": occurrences,
            "window_tokens": tokens,
            "collocates": rows,
        }

    by_period = {}
    for label, first, last in PERIODS:
        subset = holders[holders["year"].between(first, last)]
        if len(subset):
            by_period[label] = profile(subset)
            console.info(f"period {label}: {len(subset):,} speeches")

    by_group = {}
    for group, subset in holders.groupby("speaker_group"):
        by_group[str(group)] = profile(subset)
        console.info(f"group {group}: {len(subset):,} speeches")

    ranked = holders["country_org"].value_counts()
    ranked = ranked[ranked >= MIN_PROFILE_SPEECHES].head(countries)
    by_country = {}
    for country, count in ranked.items():
        by_country[str(country)] = profile(holders[holders["country_org"] == country])
        console.info(f"speaker {country}: {count:,} speeches")

    return {
        "term": term.name,
        "width": SLICE_WIDTH,
        "minimum_speeches": MIN_PROFILE_SPEECHES,
        "by_period": by_period,
        "by_speaker_group": by_group,
        "by_country": by_country,
    }


def build_keyness(
    speeches: pd.DataFrame,
    term: lexicon.Term,
    reference,
    reference_total: int,
    stopwords: frozenset[str],
    limit: int,
    seed: int,
    repetitions: int,
) -> dict[str, object]:
    """Genocide speeches against a year/agenda/group-matched control set.

    The same comparison is also run against the whole corpus, unmatched. That
    second table is not a result — it is the thing the matching is supposed to
    improve on, and shipping both is what lets a reader see whether it did.
    """
    flag = f"{lexicon.HAS}{term.name}"
    control = lexical.matched_control(speeches, flag, MATCH_ON, seed)
    console.info(
        f"matched {control.matched:,} of {control.wanted:,} targets "
        f"({control.coverage:.1%}); {len(control.short_strata)} strata short"
    )

    target_body = frames.body(speeches.loc[control.target_index])
    control_body = frames.body(speeches.loc[control.control_index])

    target_counts = lexical.vocabulary(target_body)
    control_counts = lexical.vocabulary(control_body)
    target_total = sum(target_counts.values())
    control_total = sum(control_counts.values())

    # `compare` subtracts the target from its reference, so the control counts
    # are handed over as-is: the two corpora are already disjoint.
    combined = target_counts + control_counts
    rows = lexical.compare(
        target_counts,
        combined,
        target_total,
        control_total,
        stopwords,
        limit=limit,
    )

    unmatched = lexical.compare(
        target_counts,
        reference,
        target_total,
        max(reference_total - target_total, 1),
        stopwords,
        limit=limit,
    )

    primary_words = [str(row["word"]) for row in rows]
    effects = {word: [] for word in primary_words}
    coverages = []
    for repetition in range(repetitions):
        sampled = lexical.matched_control(speeches, flag, MATCH_ON, seed + repetition)
        sampled_targets = lexical.vocabulary(frames.body(speeches.loc[sampled.target_index]))
        sampled_controls = lexical.vocabulary(frames.body(speeches.loc[sampled.control_index]))
        target_size = sum(sampled_targets.values())
        control_size = sum(sampled_controls.values())
        coverages.append(sampled.coverage)
        for word in primary_words:
            effects[word].append(
                lexical.log_ratio(
                    sampled_targets.get(word, 0),
                    sampled_controls.get(word, 0),
                    target_size,
                    control_size,
                )
            )

    stability = [
        {
            "word": word,
            "median": round(float(pd.Series(values).median()), 3),
            "p05": round(float(pd.Series(values).quantile(0.05)), 3),
            "p95": round(float(pd.Series(values).quantile(0.95)), 3),
        }
        for word, values in effects.items()
    ]

    return {
        "term": term.name,
        "matched_on": MATCH_ON,
        "seed": seed,
        "target_speeches": control.matched,
        "eligible_target_speeches": control.wanted,
        "control_speeches": control.matched,
        "coverage": round(control.coverage, 4),
        "target_tokens": target_total,
        "control_tokens": control_total,
        "short_strata": [
            {"key": list(map(str, key)), "wanted": wanted, "found": found}
            for key, wanted, found in control.short_strata
        ],
        "keywords": rows,
        "keywords_unmatched": unmatched,
        "stability": {
            "repetitions": repetitions,
            "seed_first": seed,
            "coverage_min": round(min(coverages), 4) if coverages else 0.0,
            "coverage_max": round(max(coverages), 4) if coverages else 0.0,
            "keyword_log_ratio": stability,
        },
    }


def build_network(speeches: pd.DataFrame, lex: lexicon.Lexicon, minimum: int) -> dict[str, object]:
    """PMI between lexicon terms, whole corpus and per period."""
    whole = lexical.pmi_network(speeches, lex, minimum)
    console.info(f"whole corpus: {len(whole)} edges over {len(lex.active)} terms")

    by_period = {}
    for label, first, last in PERIODS:
        subset = speeches[speeches["year"].between(first, last)]
        edges = lexical.pmi_network(subset, lex, minimum)
        by_period[label] = {
            "terms": [
                {
                    "name": term.name,
                    "speeches": int(subset[f"{lexicon.HAS}{term.name}"].sum()),
                }
                for term in lex.active
            ],
            "edges": edges,
        }
        console.info(f"{label}: {len(edges)} edges over {len(subset):,} speeches")

    return {
        "min_speeches": minimum,
        "terms": [
            {
                "name": t.name,
                "tier": t.tier,
                "register": t.register,
                "speeches": int(speeches[f"{lexicon.HAS}{t.name}"].sum()),
            }
            for t in lex.active
        ],
        "edges": whole,
        "by_period": by_period,
        "suppressed_nested_edges": [
            {"source": term.nested_under, "target": term.name}
            for term in lex.active
            if term.nested_under is not None
        ],
    }


def write_json(payload: dict, path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    artifacts.atomic_write_json(path, {"meta": meta, **payload})
    console.info(f"wrote {rel(path)}  ({path.stat().st_size / 1e3:,.0f} kB)")


def _matching_pairs(keyness: dict, top: int = 15) -> list[tuple[str, float, float]]:
    """Top unmatched keywords, with their matched effect size beside them.

    Words the matching drops below the reporting threshold entirely count as
    zero: a word that no longer distinguishes the target at all is the clearest
    case of the control having done its job.
    """
    matched = {r["word"]: float(r["log_ratio"]) for r in keyness["keywords"]}
    return [
        (str(r["word"]), float(r["log_ratio"]), matched.get(str(r["word"]), 0.0))
        for r in keyness["keywords_unmatched"][:top]
    ]


def matching_effect(keyness: dict) -> list[str]:
    return [
        f"| `{word}` | {before:+.2f} | {after:+.2f} | {after - before:+.2f} |"
        for word, before, after in _matching_pairs(keyness)
    ]


def median_drop(keyness: dict) -> float:
    pairs = _matching_pairs(keyness)
    if not pairs:
        return 0.0
    return float(pd.Series([before - after for _, before, after in pairs]).median())


def build_note(
    collocate_payload: dict,
    slices: dict,
    keyness: dict,
    network: dict,
    stopwords: frozenset[str],
    limit: int,
) -> str:
    def table(rows: list[dict], top: int = 15) -> list[str]:
        return [
            f"| {i} | `{r['word']}` | {r['target']:,} | {r['g2']:,.0f} | {r['log_ratio']:+.2f} |"
            for i, r in enumerate(rows[:top], start=1)
        ]

    genocide = collocate_payload["genocide"]["widths"]
    contrast = []
    for name in NODES[1:]:
        top = [r["word"] for r in collocate_payload[name]["widths"]["5"]["collocates"][:10]]
        contrast.append(f"- `{name}`: {', '.join(f'`{w}`' for w in top)}")

    speaker_lines = []
    for country, block in slices["by_country"].items():
        top = [r["word"] for r in block["collocates"][:8]]
        speaker_lines.append(
            f"| {country} | {block['speeches']:,} | {', '.join(f'`{w}`' for w in top)} |"
        )

    period_lines = []
    for label, block in slices["by_period"].items():
        top = [r["word"] for r in block["collocates"][:8]]
        period_lines.append(
            f"| {label} | {block['speeches']:,} | {', '.join(f'`{w}`' for w in top)} |"
        )

    short = keyness["short_strata"]
    shortfall = sum(s["wanted"] - s["found"] for s in short)

    return "\n".join(
        [
            "# 05 — Lexicometry",
            "",
            f"Stoplist: {len(stopwords)} function words "
            "(`config/stopwords.txt` — function words only, and the file says why).",
            f"Top {limit} rows kept per table. Every row carries **G²** (how confidently the",
            "rates differ) and **log ratio** (by how much). On 59 million tokens almost",
            "everything is significant, so the second column is the one that decides whether",
            "a row is a finding.",
            "",
            "## Collocates of `genocide`",
            "",
            f"±5 tokens, {genocide['5']['occurrences']:,} occurrences, "
            f"{genocide['5']['window_tokens']:,} tokens in window.",
            "",
            "| # | Word | In window | G² | Log ratio |",
            "|---:|---|---:|---:|---:|",
            *table(genocide["5"]["collocates"]),
            "",
            f"At ±15 ({genocide['15']['window_tokens']:,} tokens): "
            + ", ".join(f"`{r['word']}`" for r in genocide["15"]["collocates"][:12])
            + ".",
            "",
            "### The neighbours, for contrast",
            "",
            "Same statistic, same reference, ±5:",
            "",
            *contrast,
            "",
            "## Collocates by period",
            "",
            f"±{slices['width']} tokens.",
            "",
            "| Period | Speeches | Strongest collocates |",
            "|---|---:|---|",
            *period_lines,
            "",
            "## Collocates by speaker",
            "",
            "docs/PLAN.md §3.2 expects this to be a headline: the same word, doing different",
            "work in different mouths.",
            "",
            "| Speaker | Speeches | Strongest collocates |",
            "|---|---:|---|",
            *speaker_lines,
            "",
            "## Keyness against a matched control",
            "",
            f"The comparison uses {keyness['target_speeches']:,} complete target-control pairs, "
            f"with a speech from the same **{'**, **'.join(keyness['matched_on'])}** that does "
            "not use the term.",
            "",
            f"- **{keyness['control_speeches']:,} of "
            f"{keyness['eligible_target_speeches']:,} eligible targets matched** "
            f"({keyness['coverage']:.1%} coverage), seed {keyness['seed']}.",
            f"- {len(short)} strata could not be filled, {shortfall:,} speeches short. These "
            "are debates in which nearly everyone used the word — which is itself informative, "
            "and is why the shortfall is reported rather than back-filled from elsewhere.",
            f"- {keyness['target_tokens']:,} target tokens against "
            f"{keyness['control_tokens']:,} control tokens.",
            f"- Stability rerun across {keyness['stability']['repetitions']:,} consecutive "
            "seeds; the JSON reports the 5th, median and 95th percentile log ratios.",
            "",
            "| # | Word | In target | G² | Log ratio |",
            "|---:|---|---:|---:|---:|",
            *table(keyness["keywords"], 20),
            "",
            "### What the matching actually removed",
            "",
            "The same target set against the *whole corpus*, unmatched, is not a result — it",
            "is the comparison the matching is meant to improve on. Reading the two side by",
            "side is the only way to see whether it did. A word whose effect size collapses",
            "was vocabulary of the occasion; a word that holds up belongs to the concept.",
            "",
            "| Word | Log ratio, unmatched | Log ratio, matched | Change |",
            "|---|---:|---:|---:|",
            *matching_effect(keyness),
            "",
            f"Median effect size across the top {len(matching_effect(keyness))} unmatched "
            "keywords falls by "
            f"{median_drop(keyness):.2f} on the log2 scale once year, agenda item and speaker "
            "group are held constant — a factor of "
            f"{2 ** median_drop(keyness):.1f} in rate.",
            "",
            "## Co-occurrence network",
            "",
            f"{len(network['edges'])} edges between {len(network['terms'])} terms, at speech "
            f"level, minimum {network['min_speeches']} shared speeches. Normalised PMI, so a "
            "rare term cannot buy an edge with rarity alone.",
            "",
            "| Source | Target | Speeches | PMI | nPMI |",
            "|---|---|---:|---:|---:|",
            *[
                f"| `{e['source']}` | `{e['target']}` | {e['speeches']:,} | "
                f"{e['pmi']:.2f} | {e['npmi']:.3f} |"
                for e in network["edges"][:15]
            ],
            "",
        ]
    ) + "\n"


def run(limit: int, countries: int, seed: int, min_edge: int, repetitions: int) -> None:
    ensure_dirs()

    lex = lexicon.load()
    stopwords = lexical.load_stopwords()
    console.info(
        f"lexicon version {lex.version}, {len(lex.active)} terms; "
        f"{len(stopwords)} stopwords"
    )

    console.step("Reading the flagged corpus")
    flags = [f"{lexicon.HAS}{t.name}" for t in lex.active]
    speeches = frames.read(SPEECHES_FLAGGED, columns=[*COLUMNS, *flags])

    console.step("Counting the corpus vocabulary")
    bodies = frames.body(speeches)
    reference = lexical.vocabulary(bodies)
    reference_total = sum(reference.values())
    console.info(f"{reference_total:,} tokens, {len(reference):,} types")

    terms = node_terms(lex)

    console.step("Collocates, whole corpus")
    holders = speeches[speeches[[f"{lexicon.HAS}{t.name}" for t in terms]].any(axis=1)]
    collocate_payload = build_collocates(
        frames.body(holders), terms, reference, reference_total, stopwords, limit
    )

    console.step("Collocates, sliced")
    slices = build_slices(
        speeches, lex.terms["genocide"], reference, reference_total, stopwords, limit, countries
    )

    console.step("Keyness against a matched control")
    keyness = build_keyness(
        speeches,
        lex.terms["genocide"],
        reference,
        reference_total,
        stopwords,
        limit,
        seed,
        repetitions,
    )

    console.step("Co-occurrence network")
    network = build_network(speeches, lex, min_edge)

    console.step("Writing")
    meta = artifacts.provenance(
        ROOT,
        "05_lexical.py",
        inputs=[SPEECHES_FLAGGED],
        configs=[LEXICON_CONFIG, STOPWORDS],
        extra={
            "lexicon_version": lex.version,
            "corpus_tokens": reference_total,
            "corpus_types": len(reference),
            "stopwords": len(stopwords),
            "min_count": lexical.MIN_COUNT,
            "limit": limit,
        },
    )
    with artifacts.atomic_directory(LEXICAL) as staged:
        write_json(
            {"nodes": collocate_payload, "widths": WIDTHS}, staged / "collocates.json", meta
        )
        write_json(slices, staged / "collocates_sliced.json", meta)
        write_json(keyness, staged / "keyness.json", meta)
        write_json(network, staged / "network.json", meta)

    note = write_note(
        "05_lexical.md",
        build_note(collocate_payload, slices, keyness, network, stopwords, limit),
    )
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="rows kept per table")
    parser.add_argument("--countries", type=int, default=8, help="speakers profiled")
    parser.add_argument("--seed", type=int, default=20_260_807, help="control-sampling seed")
    parser.add_argument("--min-edge", type=int, default=20, help="shared speeches for an edge")
    parser.add_argument(
        "--matching-repetitions",
        type=int,
        default=20,
        help="consecutive seeds used for matched-keyness stability intervals",
    )
    args = parser.parse_args()
    run(args.limit, args.countries, args.seed, args.min_edge, args.matching_repetitions)


if __name__ == "__main__":
    main()
