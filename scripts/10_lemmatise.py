"""Build a lemma layer over the corpus, aligned to the tokens 05 counts.

Reads speeches_flagged.parquet and writes data/derived/lemmas/:

    lemmas.parquet   row_id -> one lemma per token of the speech body
    mapping.csv      every surface form that changed, and what it became
    manifest.json    model, model version, alignment failures, package versions

**Numbered 10 although it feeds 05.** The numbering is creation order, and 00-09
were already fixed and referenced from the dashboard, the notes and CI before
this existed. Renumbering to put it where its dependencies suggest would have
moved five committed steps to make room for an optional one. The dependency is
stated instead: this needs 03, and enables `05_lexical.py --vocabulary lemma`.

**It does not touch the lexicon.** `config/lexicon.yml` matches surface forms and
docs/PLAN.md §1.1 gates a human audit on those patterns; folding `genocides` into
`genocide` before step 03 would move every count and restart that audit. The
lemma layer is derived *from* the flagged corpus and feeds only the vocabulary
side of the analysis.

Lemmas cover the speech **body** — the text minus its opening form of address,
as `lib.frames.body` reconstructs it — because that is the text 05 counts.

Usage:
    python scripts/10_lemmatise.py [--model en_core_web_sm] [--limit N] [--processes 8]
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, frames, lemmas, lexical
from lib.paths import (
    DERIVED,
    LEMMAS,
    ROOT,
    SPEECHES_FLAGGED,
    STOPWORDS,
    ensure_dirs,
    rel,
    write_note,
)

COLUMNS = ["row_id", "text", "body_start"]

#: A --limit run writes here, so a smoke test cannot replace a real layer.
SMOKE = DERIVED / "lemmas_smoke"

#: Rows kept in the audit table. The tail is a long list of hapaxes whose
#: collapse moves nothing; the head is where a wrong lemma does damage.
MAPPING_LIMIT = 5_000

REPORT_EVERY = 10_000


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    artifacts.atomic_write_text(path, buffer.getvalue())


def build_note(
    frame: pd.DataFrame,
    surface_types: int,
    lemma_types: int,
    failures: int,
    changed: int,
    refused: int,
    total: int,
    pairs: list[dict],
    leaks: list[str],
    model: str,
    model_version: str,
    elapsed: float,
) -> str:
    reduction = 1 - (lemma_types / surface_types) if surface_types else 0.0
    top = pairs[:15]
    return "\n".join(
        [
            "# 10 — Lemma layer",
            "",
            f"{len(frame):,} speeches lemmatised with `{model}` {model_version} in "
            f"{elapsed / 60:.1f} minutes.",
            "",
            "| | |",
            "|---|---:|",
            f"| Tokens changed | {changed:,} of {total:,} ({changed / max(total, 1):.1%}) |",
            f"| Distinct surface forms | {surface_types:,} |",
            f"| Distinct lemmas | {lemma_types:,} |",
            f"| Vocabulary reduction | {reduction:.1%} of types |",
            f"| Lemmas offered and refused | {refused:,} ({refused / max(total, 1):.1%} of tokens) |",
            f"| Speeches that failed to align | {failures:,} |",
            f"| Surface forms that changed | {len(pairs):,} (top {MAPPING_LIMIT:,} kept) |",
            "",
            "## What this is for",
            "",
            "**Read the token figure, not the type figure.** Most of a 112,000-type OCR",
            "vocabulary is hapax garble that cannot lemmatise, so the reduction in *types* is",
            "small and says little. The words a collocate list has room for are the frequent,",
            "regularly inflected ones, and those are what the token figure counts.",
            "",
            "Inflection splits every table in 05. `killing`, `killed` and `kills` compete for",
            "rows in a list with room for a hundred, and each carries a fraction of the",
            "evidence they jointly support. Collapsing them buys resolution — which is only",
            "worth having if the collapse can be inspected, so `mapping.csv` records every",
            "merge, most frequent first.",
            "",
            "## The largest merges",
            "",
            "| Surface | Lemma | Occurrences |",
            "|---|---|---:|",
            *[
                f"| `{row['surface']}` | `{row['lemma']}` | {row['occurrences']:,} |"
                for row in top
            ],
            "",
            "## What does not collapse, and why",
            "",
            "A lemma is accepted only when the tagger and `lib.lexical.tokenise` agree on where",
            "the token starts *and ends*, and when the lemma is itself a word by the same",
            "definition. The two tokenisers disagree in both directions, and each disagreement",
            "is a way for a word to quietly become a different word:",
            "",
            "- **The tagger splits on hyphens; TOKEN_RE keeps them.** `Secretary-General` is",
            "  three tagger tokens against one of ours. Reading the lemma at the token's first",
            "  character would turn the corpus's most frequent title into `secretary`, merged",
            "  with every unrelated secretary. Hyphenated compounds therefore keep their surface",
            "  form and do not collapse.",
            "- **The tagger keeps symbols whole; TOKEN_RE reads letters out of them.** In",
            "  `S/24232` and `US$` it sees one token, we see `s` and `us`. Requiring the lemma",
            "  to be a well-formed word keeps document symbols out of the vocabulary.",
            "",
            "Both rules cost the same thing — a missed merge — and prevent the same thing. That",
            "trade is deliberate: a table missing a collapse is incomplete, a table with a wrong",
            "one is false.",
            "",
            "## Alignment",
            "",
            "Each speech gets exactly one lemma per token `lib.lexical.tokenise` finds, in the",
            "same order. That invariant is what lets a lemma sequence be used with the",
            "*surface* character offsets, so a collocate window still excludes the node's own",
            "span exactly. A speech whose counts do not line up keeps its surface forms and is",
            "counted here rather than being shifted by one token, which would move every",
            "window in it.",
            "",
            f"{failures:,} of {len(frame):,} speeches "
            f"({failures / max(len(frame), 1):.2%}) fell back to surface forms.",
            "",
            "## Stoplist",
            "",
            (
                "Every stopword's lemma is also a stopword, so the filter survives "
                "lemmatisation."
                if not leaks
                else "**Leaks.** These stopwords lemmatise to something the stoplist does not "
                "cover, so they would reappear at the top of every lemma table:\n\n"
                + "\n".join(f"- `{leak}`" for leak in leaks)
            ),
            "",
            "## What this does not change",
            "",
            "Nothing in `config/lexicon.yml`, and therefore nothing in the counts behind the",
            "published figures. The lexicon matches surface forms, and docs/PLAN.md §1.1 gates",
            "a human audit on exactly those patterns. This layer is built *from* the flagged",
            "corpus, and 05 reads it only when asked with `--vocabulary lemma`, writing to its",
            "own directory.",
            "",
        ]
    ) + "\n"


def run(model: str, limit: int, processes: int, batch_size: int) -> None:
    ensure_dirs()

    console.step("Reading the flagged corpus")
    speeches = frames.read(SPEECHES_FLAGGED, columns=COLUMNS)
    target = LEMMAS
    if limit:
        speeches = speeches.head(limit)
        target = SMOKE
        console.warn(f"--limit {limit}: a smoke test, not a corpus artefact")
        console.warn(f"writing to {rel(target)} so {rel(LEMMAS)} is left alone")
    speeches = speeches.reset_index(drop=True)
    bodies = frames.body(speeches).tolist()

    console.step(f"Lemmatising with {model}")
    console.info(f"{processes} process(es), batch {batch_size}")
    started = time.monotonic()
    rows: list[str] = []
    failures = changed = refused = total = 0
    for index, result in enumerate(
        lemmas.lemmatise(bodies, model, batch_size=batch_size, processes=processes), start=1
    ):
        rows.append(lemmas.encode(result.lemmas))
        failures += not result.aligned
        changed += result.changed
        refused += result.refused
        total += len(result.lemmas)
        if index % REPORT_EVERY == 0:
            rate = index / max(time.monotonic() - started, 1e-9)
            console.info(f"{index:,} / {len(bodies):,} speeches  ({rate:.0f}/s)")
    elapsed = time.monotonic() - started
    console.info(f"{len(rows):,} speeches in {elapsed / 60:.1f} min; {failures:,} unaligned")

    failure_rate = failures / max(len(rows), 1)
    if failure_rate > lemmas.MAX_FAILURE_RATE:
        console.fail(
            f"{failure_rate:.2%} of speeches failed to align "
            f"(limit {lemmas.MAX_FAILURE_RATE:.2%})",
            [
                "the tagger and lexical.tokenise have diverged on this corpus",
                "a table built from this layer would mix lemmas and surface forms",
            ],
        )

    console.step("Measuring the collapse")
    surface_counts = lexical.vocabulary(bodies)
    lemma_counts = lemmas.vocabulary(rows)
    console.info(
        f"{len(surface_counts):,} surface types -> {len(lemma_counts):,} lemma types "
        f"({1 - len(lemma_counts) / max(len(surface_counts), 1):.1%} fewer)"
    )
    # The type figure understates the effect and the token figure is what a table
    # actually sees: most of a 112,000-type OCR vocabulary is hapax garble that
    # cannot lemmatise, while the words a collocate list has room for are exactly
    # the frequent, regularly inflected ones.
    console.info(
        f"{changed:,} of {total:,} tokens changed ({changed / max(total, 1):.1%} of running text)"
    )
    console.info(
        f"{refused:,} tokens ({refused / max(total, 1):.1%}) had a lemma offered and refused "
        f"— boundary disagreements and malformed lemmas"
    )

    pairs = lemmas.mapping(bodies, rows, limit=MAPPING_LIMIT)
    console.info(f"{len(pairs):,} surface forms changed")

    stopwords = lexical.load_stopwords()
    leaks = lemmas.stopword_check(stopwords, pairs)
    # Capped: a systematic fault produces hundreds of these, and a log that
    # scrolls for a screen is a log nobody reads to the end. The full list goes
    # to the manifest and the note.
    for leak in leaks[:10]:
        console.warn(f"stopword leaks through lemmatisation: {leak}")
    if len(leaks) > 10:
        console.warn(f"... and {len(leaks) - 10} more (all of them are in the note)")

    console.step("Writing")
    try:
        model_version = version(model)
    except PackageNotFoundError:
        model_version = "unknown"

    packages = {}
    for package in ("spacy", model):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            continue

    meta = artifacts.provenance(
        ROOT,
        "10_lemmatise.py",
        inputs=[SPEECHES_FLAGGED],
        configs=[STOPWORDS],
        extra={
            "model": model,
            "model_version": model_version,
            "packages": packages,
            "speeches": len(rows),
            "unaligned_speeches": failures,
            "surface_types": len(surface_counts),
            "lemma_types": len(lemma_counts),
            "tokens": total,
            "tokens_changed": changed,
            "lemmas_refused": refused,
            "stopword_leaks": leaks,
            "limit": limit,
            "seconds": round(elapsed, 1),
        },
    )
    table = pd.DataFrame({"row_id": speeches["row_id"].to_numpy(), "lemmas": rows})

    with artifacts.atomic_directory(target) as staged:
        table.to_parquet(staged / "lemmas.parquet", index=False, compression="zstd")
        write_csv(staged / "mapping.csv", pairs)
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)
    size = (target / "lemmas.parquet").stat().st_size / 1e6
    console.info(f"wrote {rel(target)}  {len(table):,} rows ({size:.0f} MB)")

    note = write_note(
        "10_lemmatise.md",
        build_note(
            speeches,
            len(surface_counts),
            len(lemma_counts),
            failures,
            changed,
            refused,
            total,
            pairs,
            leaks,
            model,
            model_version,
            elapsed,
        ),
    )
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="en_core_web_sm", help="spaCy pipeline to load")
    parser.add_argument("--limit", type=int, default=0, help="lemmatise only the first N speeches")
    parser.add_argument("--processes", type=int, default=1, help="spaCy worker processes")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    run(args.model, args.limit, args.processes, args.batch_size)


if __name__ == "__main__":
    main()
