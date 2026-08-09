"""Apply the genocide lexicon to every speech body.

Reads speeches_norm.parquet, counts each term from config/lexicon.yml, and
writes speeches_flagged.parquet with a `n_<term>` and `has_<term>` column per
term, plus per-register and per-set roll-ups.

Three things this step reports rather than hides:

- **The OCR delta.** How many extra speeches the OCR-tolerant pattern finds,
  measured against the plain one and listed in the note, never folded into the
  headline count.
- **The check against the documented figures.** `genocid*` is documented at
  3,273 speeches / 6,092 occurrences (docs/CORPUS.md §8). Counting on the body
  instead of the raw text should not move that; a difference means the form of
  address is eating real words.
- **A precision sample.** 100 random occurrences with their context, written to
  data/interim/ with an empty `verdict` column, for the hand audit the plan
  calls for.

Usage:
    python scripts/03_lexicon.py [--sample 100] [--seed 12]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, frames, lexicon, text
from lib.paths import (
    INTERIM,
    LEXICON,
    MANIFESTS,
    ROOT,
    SPEECHES_FLAGGED,
    SPEECHES_NORM,
    ensure_dirs,
    rel,
    write_note,
)

#: docs/CORPUS.md §8, measured over the raw texts during reconnaissance with
#: ad-hoc patterns. The formalised lexicon should reproduce these; where it does
#: not, the difference is a change in what the pattern *means* and has to be
#: stated rather than left for a reader to trip over. Speeches, occurrences.
DOCUMENTED: dict[str, tuple[int, int]] = {
    "impunity": (9_662, 13_616),
    "icc": (4_744, 6_590),
    "war_crimes": (4_664, 6_588),
    "atrocity": (3_775, 5_087),
    "crimes_against_humanity": (3_465, 4_136),
    "genocide": (3_273, 6_092),
    "responsibility_to_protect": (1_353, 1_773),
    "ethnic_cleansing": (1_229, 1_705),
    "mass_atrocity": (532, 649),
    "ethnic_hatred": (477, 523),
    "never_again": (305, 338),
    "extermination": (224, 281),
    "holocaust": (181, 242),
    "genocide_convention": (135, 153),
}

AUDIT_SAMPLE = INTERIM / "lexicon_audit_sample.csv"


def check_documented(counts: pd.DataFrame) -> list[tuple[str, int, int, int, int, bool]]:
    """Compare each term against the figure published in docs/CORPUS.md.

    Returns ``(term, speeches, expected_speeches, occurrences,
    expected_occurrences, agrees)`` per documented term.
    """
    rows = []
    for term, (want_speeches, want_occurrences) in DOCUMENTED.items():
        if f"{lexicon.HAS}{term}" not in counts:
            continue
        speeches = int(counts[f"{lexicon.HAS}{term}"].sum())
        occurrences = int(counts[f"{lexicon.COUNT}{term}"].sum())
        rows.append(
            (
                term,
                speeches,
                want_speeches,
                occurrences,
                want_occurrences,
                speeches == want_speeches and occurrences == want_occurrences,
            )
        )
    return rows


def _period(year: int) -> str:
    return f"{year // 10 * 10}s"


def _stratified_sample(frame: pd.DataFrame, size: int, seed: int) -> pd.DataFrame:
    """Cover term-period strata once, then fill remaining places at random."""
    anchors = frame.groupby(["term", "period"], sort=True, group_keys=False).sample(
        n=1, random_state=seed
    )
    if len(anchors) > size:
        anchors = anchors.sample(size, random_state=seed)
    remaining = frame.drop(index=anchors.index)
    needed = min(max(size - len(anchors), 0), len(remaining))
    if needed:
        anchors = pd.concat([anchors, remaining.sample(needed, random_state=seed + 1)])
    return anchors.sort_values(["term", "index", "start"])


def audit_sample(
    speeches: pd.DataFrame,
    bodies: pd.Series,
    counts: pd.DataFrame,
    lex: lexicon.Lexicon,
    size: int,
    seed: int,
) -> pd.DataFrame:
    """Term/period-stratified occurrence and speech samples for human review."""
    rows = []
    years = speeches["year"].to_dict()
    for term in lex.active:
        holders = counts.index[counts[f"{lexicon.HAS}{term.name}"]]
        for index, body in bodies.loc[holders].items():
            for match in term.regex.finditer(body):
                rows.append(
                    {
                        "term": term.name,
                        "tier": term.tier,
                        "register": term.register,
                        "index": index,
                        "start": match.start(),
                        "end": match.end(),
                        "period": _period(int(years[index])),
                    }
                )
    if not rows:
        return pd.DataFrame()

    occurrences = pd.DataFrame(rows)
    occurrence_sample = _stratified_sample(occurrences, size, seed).assign(
        unit="occurrence", strategy="term-period stratified"
    )
    speech_candidates = occurrences.drop_duplicates(["term", "index"], keep="first")
    speech_sample = _stratified_sample(speech_candidates, size, seed + 2).assign(
        unit="speech", strategy="term-period stratified"
    )

    out = []
    for row in pd.concat([occurrence_sample, speech_sample]).itertuples():
        left, keyword, right = text.window(bodies.loc[row.index], row.start, row.end)
        meta = speeches.loc[row.index]
        out.append(
            {
                "unit": row.unit,
                "strategy": row.strategy,
                "term": row.term,
                "tier": row.tier,
                "register": row.register,
                "period": row.period,
                "filename": meta["filename"],
                "meeting_symbol": meta["meeting_symbol"],
                "date": f"{meta['date']:%Y-%m-%d}",
                "country_org": meta["country_org"],
                "agenda": meta["agenda_item_manual"],
                "left": left,
                "keyword": keyword,
                "right": right,
                "verdict": "",  # fill in: ok / false-positive
                "source_checked": "",  # yes / no
                "phenomenon": "",  # direct / quoted / title / negated / OCR / other
                "comment": "",
            }
        )
    return pd.DataFrame(out)


def build_note(
    speeches: pd.DataFrame,
    counts: pd.DataFrame,
    lex: lexicon.Lexicon,
    documented: list[tuple[str, int, int, int, int, bool]],
    ocr: list[dict],
    sample_size: int,
) -> str:
    total = len(speeches)
    rows = []
    for term in sorted(lex.active, key=lambda t: -int(counts[f"{lexicon.COUNT}{t.name}"].sum())):
        n_speeches = int(counts[f"{lexicon.HAS}{term.name}"].sum())
        n_occurrences = int(counts[f"{lexicon.COUNT}{term.name}"].sum())
        rows.append(
            f"| `{term.name}` | {term.tier} | {term.register} | {n_speeches:,} | "
            f"{n_speeches / total:.2%} | {n_occurrences:,} |"
        )

    registers = [
        f"| {register} | {int(counts[f'{lexicon.HAS}register_{register}'].sum()):,} | "
        f"{int(counts[f'{lexicon.COUNT}register_{register}'].sum()):,} |"
        for register in sorted(lex.by_register())
    ]
    sets = [
        f"| `{name}` | {int(counts[f'{lexicon.HAS}set_{name}'].sum()):,} |"
        for name in lex.sets
        if f"{lexicon.HAS}set_{name}" in counts
    ]

    ocr_lines = []
    for entry in ocr:
        ocr_lines.append(
            f"- `{entry['term']}` matches {entry['speeches']:,} speeches, of which "
            f"**{entry['extra']:,}** are not already found by the enabled terms of the "
            f"same tier."
        )

    return "\n".join(
        [
            "# 03 — Lexicon",
            "",
            f"Lexicon version **{lex.version}** ({lex.updated}), "
            f"{len(lex.active)} active terms, {len(lex.disabled)} held back.",
            f"Counted over {total:,} speech bodies, with the opening form of address removed.",
            "",
            "## Check against the documented figures",
            "",
            "docs/CORPUS.md §8 was measured over the raw texts with ad-hoc patterns. The",
            "formalised lexicon is counted over speech bodies. Terms marked *differs* are",
            "where the pattern's meaning changed, not where the corpus did.",
            "",
            "| Term | Speeches | Documented | Occurrences | Documented | |",
            "|---|---:|---:|---:|---:|---|",
            *[
                f"| `{term}` | {speeches:,} | {want_s:,} | {occurrences:,} | {want_o:,} | "
                f"{'✅' if agrees else '⚠️ differs'} |"
                for term, speeches, want_s, occurrences, want_o, agrees in documented
            ],
            "",
            f"{sum(1 for row in documented if row[5])} of {len(documented)} reproduce "
            "exactly. See `docs/VALIDATION.md` for what accounts for the rest.",
            "",
            "## Terms",
            "",
            "| Term | Tier | Register | Speeches | % corpus | Occurrences |",
            "|---|---|---|---:|---:|---:|",
            *rows,
            "",
            "## Registers",
            "",
            "| Register | Speeches | Occurrences |",
            "|---|---:|---:|",
            *registers,
            "",
            "## Sets",
            "",
            "| Set | Speeches |",
            "|---|---:|",
            *sets,
            "",
            "## OCR-tolerant patterns (held back)",
            "",
            *(ocr_lines or ["- none defined"]),
            "",
            "These are reported, not counted. See `docs/VALIDATION.md` for the individual",
            "records to check against the original PDFs.",
            "",
            "## Precision audit",
            "",
            f"Up to {sample_size} occurrence-level and {sample_size} speech-level cases were",
            f"written to `{rel(AUDIT_SAMPLE)}`. Sampling covers each term-period stratum before",
            "filling the remainder randomly. Human reviewers must fill `verdict`, record whether",
            "the primary source was checked, and classify quotation, title, negation and OCR cases.",
            "",
        ]
    ) + "\n"


def run(sample_size: int, seed: int) -> None:
    ensure_dirs()

    console.step("Reading the normalised corpus")
    speeches = frames.read(SPEECHES_NORM)
    bodies = frames.body(speeches)

    console.step("Loading the lexicon")
    lex = lexicon.load()
    console.info(
        f"version {lex.version} ({lex.updated}): {len(lex.active)} active, "
        f"{len(lex.disabled)} held back"
    )

    console.step("Counting terms")
    counts = lexicon.apply(bodies, lex)
    console.info(f"{counts.shape[1]} lexicon columns")

    documented = check_documented(counts)
    agreed = sum(1 for row in documented if row[5])
    console.info(f"{agreed}/{len(documented)} terms reproduce docs/CORPUS.md §8 exactly")
    for term, n_speeches, want_s, n_occurrences, want_o, agrees in documented:
        if not agrees:
            console.warn(
                f"{term}: {n_speeches:,}/{n_occurrences:,} vs documented "
                f"{want_s:,}/{want_o:,} — the pattern's meaning changed"
            )

    console.step("Measuring the OCR-tolerant patterns")
    ocr = lexicon.ocr_delta(bodies, lex)
    for entry in ocr:
        console.info(
            f"{entry['term']}: {entry['speeches']:,} speeches, {entry['extra']:,} not "
            f"already covered"
        )
        for index in entry["extra_index"][:5]:
            row = speeches.loc[index]
            console.info(f"    {row['meeting_symbol']} {row['date']:%Y-%m-%d} {row['country_org']}")

    console.step("Drawing the precision sample")
    sample = audit_sample(speeches, bodies, counts, lex, sample_size, seed)
    AUDIT_SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    artifacts.atomic_write_text(AUDIT_SAMPLE, sample.to_csv(index=False))
    console.info(f"wrote {rel(AUDIT_SAMPLE)} ({len(sample)} rows, seed {seed})")

    console.step("Writing")
    flagged = pd.concat([speeches, counts], axis=1)
    flagged.attrs["lexicon_version"] = lex.version
    frames.write(flagged, SPEECHES_FLAGGED)
    note = write_note(
        "03_lexicon.md",
        build_note(speeches, counts, lex, documented, ocr, len(sample)),
    )
    console.info(f"wrote {note.name}")
    manifest = artifacts.provenance(
        ROOT,
        "03_lexicon.py",
        inputs=[SPEECHES_NORM],
        configs=[LEXICON],
        extra={
            "outputs": [artifacts.describe_file(SPEECHES_FLAGGED, ROOT)],
            "lexicon_version": lex.version,
            "terms": {
                term.name: {
                    "speeches": int(counts[f"{lexicon.HAS}{term.name}"].sum()),
                    "occurrences": int(counts[f"{lexicon.COUNT}{term.name}"].sum()),
                }
                for term in lex.active
            },
        },
    )
    artifacts.atomic_write_json(MANIFESTS / "03_lexicon.json", manifest, indent=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=100, help="precision audit size")
    parser.add_argument("--seed", type=int, default=12, help="sampling seed")
    args = parser.parse_args()
    run(args.sample, args.seed)


if __name__ == "__main__":
    main()
