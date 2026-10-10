"""Apply the genocide lexicon to every speech body.

Reads speeches_norm.parquet, counts each term from config/lexicon.yml, and
writes speeches_flagged.parquet with a `n_<term>` and `has_<term>` column per
term and per derived measure, and nothing that sums over more than one term.

Three things this step reports rather than hides:

- **The OCR delta.** How many extra speeches the OCR-tolerant pattern finds,
  measured against the plain one and listed in the note, never folded into the
  headline count.
- **The check against the committed counts.** Every enabled term's speeches
  and occurrences are held to `config/lexicon.counts.json`, and a difference
  fails the step: a lexicon edit arrives with `--update-counts` and a reviewed
  diff of what it moved, and nothing else can move a published count. The
  same file gives 13, 14 and 15 the `genocide` population they assert.
- **Declared widenings, verified.** A term that declares `widened_since` at
  this version has its old rule re-run over the corpus, and the step fails if
  any span the old rule counted is lost.
- **A precision sample.** Generated candidates and human annotations are kept
  separate, then joined by stable occurrence identity for review. A pipeline
  rerun never writes the versioned annotation file.

Usage:
    python scripts/03_lexicon.py [--sample 100] [--seed 12] [--update-counts]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, audit, console, frames, lexicon, lexicon_lock, sampling
from lib.paths import (
    INTERIM,
    LEXICON,
    LEXICON_COUNTS,
    MANIFESTS,
    REFERENTS,
    ROOT,
    SPEECHES_FLAGGED,
    SPEECHES_NORM,
    ensure_dirs,
    rel,
    write_note,
)

AUDIT_CANDIDATES = INTERIM / "lexicon_audit_candidates.csv"
AUDIT_REVIEW = INTERIM / "lexicon_audit_review.csv"
AUDIT_PROBABILITY = INTERIM / "lexicon_audit_probability.csv"
AUDIT_COVERAGE = INTERIM / "lexicon_audit_coverage.csv"
AUDIT_NEGATIVE = INTERIM / "lexicon_audit_negative.csv"
AUDIT_ANNOTATIONS = ROOT / "annotations" / "lexicon" / "annotations.csv"


def build_note(
    speeches: pd.DataFrame,
    counts: pd.DataFrame,
    lex: lexicon.Lexicon,
    ocr: list[dict],
    sample_size: int,
) -> str:
    total = len(speeches)
    rows = []
    for term in sorted(lex.active, key=lambda t: -int(counts[f"{lexicon.COUNT}{t.name}"].sum())):
        n_speeches = int(counts[f"{lexicon.HAS}{term.name}"].sum())
        n_occurrences = int(counts[f"{lexicon.COUNT}{term.name}"].sum())
        rows.append(
            f"| `{term.name}` | {term.tier} | {term.register} | "
            f"{term.anchor or '—'} | {n_speeches:,} | "
            f"{n_speeches / total:.2%} | {n_occurrences:,} |"
        )

    registers = [
        f"| {register} | " + ", ".join(f"`{term.name}`" for term in terms) + " |"
        for register, terms in sorted(lex.by_register().items())
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
            "## Check against the committed counts",
            "",
            f"Every count below equals `{rel(LEXICON_COUNTS)}`; the step fails otherwise.",
            "A lexicon edit rewrites that file with `--update-counts`, and its diff is the",
            "record of what the edit moved.",
            "",
            "## Terms",
            "",
            "An anchored term is counted only where the sentence holding the match also",
            "says `genocid*`. What that is for, and why each anchored term is anchored, is",
            "in `config/lexicon.yml`; what it costs is in `docs/VALIDATION.md`.",
            "",
            "| Term | Tier | Register | Anchor | Speeches | % corpus | Occurrences |",
            "|---|---|---|---|---:|---:|---:|",
            *rows,
            "",
            "## Registers",
            "",
            "A register is a shelf label. It groups and colours the term picker so that a",
            "reader can find a word, and since lexicon v5 nothing is counted by it: a",
            "count of *the legal register* was a count of a category `config/lexicon.yml`",
            "invented, and a reader watching that line move could not tell which of six",
            "words moved it. The membership is recorded here so that the grouping is",
            "documented; the counts are in the table above, one per term.",
            "",
            "| Register | Terms |",
            "|---|---|",
            *registers,
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
            f"Up to {sample_size} cases per sampling frame were written to",
            f"`{rel(AUDIT_CANDIDATES)}` and to three frame-specific CSV files. The probability",
            "sample estimates occurrence precision; the coverage sample spans term-period",
            "strata; the negative sample inspects matches from declared disabled high-recall",
            "patterns. Human annotations remain separately",
            f"versioned at `{rel(AUDIT_ANNOTATIONS)}`; `{rel(AUDIT_REVIEW)}` is the generated",
            "join used for review. Pipeline runs never write the annotation file.",
            "",
        ]
    ) + "\n"


def run(sample_size: int, seed: int, update_counts: bool = False) -> None:
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
    # Every term's spans, the held-back ones included, found once: the counts,
    # the OCR delta and the precision sample are all read from them.
    haystack = lexicon.Haystack(bodies)
    found = lexicon.find_all(bodies, lex.terms.values(), haystack)
    counts = lexicon.apply(bodies, lex, found=found)
    console.info(f"{counts.shape[1]} lexicon columns")

    console.step("Verifying declared widenings")
    widened = [term.name for term in lex.terms.values() if term.widened_since == lex.version]
    if problems := lexicon.check_widenings(bodies, lex, haystack):
        console.fail("a declared widening loses occurrences the old rule counted", problems)
    console.info(
        f"{len(widened)} term(s) widened at v{lex.version}, every old span still counted"
        if widened
        else f"no term declares a widening at v{lex.version}"
    )

    console.step("Checking the committed counts")
    record = lexicon_lock.counts_record(counts, lex, len(speeches))
    if update_counts:
        artifacts.atomic_write_text(
            LEXICON_COUNTS, json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        )
        console.info(f"wrote {rel(LEXICON_COUNTS)}; review its diff and commit it")
    elif problems := lexicon_lock.count_problems(record, lexicon_lock.load_counts()):
        console.fail(
            f"the counts differ from {rel(LEXICON_COUNTS)}",
            [
                *problems,
                "if the lexicon or the corpus changed on purpose, re-run with "
                "--update-counts and commit the diff with the change",
            ],
        )
    else:
        console.info(f"{len(record['terms'])} terms match {rel(LEXICON_COUNTS)}")

    console.step("Measuring the OCR-tolerant patterns")
    ocr = lexicon.ocr_delta(bodies, lex, found=found)
    for entry in ocr:
        console.info(
            f"{entry['term']}: {entry['speeches']:,} speeches, {entry['extra']:,} not "
            f"already covered"
        )
        for index in entry["extra_index"][:5]:
            row = speeches.loc[index]
            console.info(f"    {row['meeting_symbol']} {row['date']:%Y-%m-%d} {row['country_org']}")

    console.step("Drawing the precision sample")
    sample = audit.audit_sample(speeches, bodies, lex, sample_size, seed, found=found)
    AUDIT_CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    review = audit.write_outputs(
        sample,
        annotation_path=AUDIT_ANNOTATIONS,
        candidate_path=AUDIT_CANDIDATES,
        review_path=AUDIT_REVIEW,
        frame_paths={
            sampling.PROBABILITY: AUDIT_PROBABILITY,
            sampling.COVERAGE: AUDIT_COVERAGE,
            sampling.NEGATIVE: AUDIT_NEGATIVE,
        },
        referent_path=REFERENTS,
        # Candidates are regenerated at the current lexicon version, so a coded
        # row keeps the version it was coded at: what decides is whether its
        # term still enumerates the same occurrences, not the version number.
        compatible=lex.compatible,
    )
    coded = review.loc[review["coder"].astype("string").str.len().gt(0)]
    annotated = len(coded.drop_duplicates(["occurrence_id", "coder"]))
    console.info(
        f"wrote {rel(AUDIT_CANDIDATES)} and {rel(AUDIT_REVIEW)} "
        f"({len(sample)} candidates, {annotated} annotations, seed {seed})"
    )

    console.step("Writing")
    flagged = pd.concat([speeches, counts], axis=1)
    flagged.attrs["lexicon_version"] = lex.version
    frames.write(flagged, SPEECHES_FLAGGED)
    note = write_note(
        "03_lexicon.md",
        build_note(speeches, counts, lex, ocr, len(sample)),
    )
    console.info(f"wrote {note.name}")
    manifest = artifacts.provenance(
        ROOT,
        "03_lexicon.py",
        inputs=[SPEECHES_NORM],
        configs=[LEXICON, LEXICON_COUNTS, AUDIT_ANNOTATIONS, REFERENTS],
        extra={
            "outputs": [
                artifacts.describe_file(SPEECHES_FLAGGED, ROOT),
                artifacts.describe_file(AUDIT_CANDIDATES, ROOT),
                artifacts.describe_file(AUDIT_REVIEW, ROOT),
                artifacts.describe_file(AUDIT_PROBABILITY, ROOT),
                artifacts.describe_file(AUDIT_COVERAGE, ROOT),
                artifacts.describe_file(AUDIT_NEGATIVE, ROOT),
            ],
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
    parser.add_argument(
        "--update-counts",
        action="store_true",
        help="rewrite config/lexicon.counts.json from this run instead of checking it",
    )
    args = parser.parse_args()
    run(args.sample, args.seed, args.update_counts)


if __name__ == "__main__":
    main()
