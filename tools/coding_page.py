"""Build the offline coding page for the genocide gold sample.

    python tools/coding_page.py            # writes data/interim/genocide_coding.html
    python tools/coding_page.py --coder RA1  # one coder's page: genocide_coding_RA1.html

The coders' work was a 22-column CSV edited by hand, with evidence recorded as
character offsets typed from a count. This writes one self-contained HTML file
from the blinded packet (`13_gold_sample.py`) that shows each passage inside its
whole speech, asks the codebook's fields as plain-language questions, records the
sentence around the match as evidence, applies the codebook's cascade as the coder goes,
keeps progress in the browser, and exports rows in the exact column order of
`annotations/genocide/annotations.csv` (docs/ROADMAP.md, RV16).

`--coder` builds the page for one coder: the identifier is fixed in the page, so
the person it is sent to cannot pick somebody else's. Without it the page offers
the protocol's coders and the adjudicator.

Nothing here decides a label. The page carries no model output, no frame, no
stratum and no cue, because the packet carries none; it is the packet made
workable.

    python tools/coding_page.py --import genocide-finished-RA1-....csv          # check only
    python tools/coding_page.py --import genocide-finished-RA1-....csv --write  # and save

`--import` folds a coder's exported rows into the versioned annotation file
after `lib.audit.merge` has passed every one of them, exactly as hand-typed rows
are held, and writes the file in one atomic step. It refuses a row that would
revise a reading already on file unless `--replace` says so. This is the one
place a script writes into `annotations/`, and only when a person asks it to.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import (
    artifacts,
    audit,
    console,
    frames,
    gold_estimates,
    lexicon,
    llm,
    model_runs,
    schema,
    text,
)
from lib.paths import INTERIM, SPEECHES_NORM, rel

PACKET = model_runs.GOLD_PACKET
OUTPUT = INTERIM / "genocide_coding.html"

#: The codebook's vocabularies, in the order a coder reads them.
VOCABULARIES = {
    "verdict": ["true_positive", "false_positive", "uncertain"],
    "source_checked": ["yes", "no"],
    "quotation": ["not_quoted", "direct_quotation", "attributed_or_reported", "unclear", "not_applicable"],
    "concrete_case": ["yes", "no", "unclear", "not_applicable"],
    "speaker_position": [
        "asserts", "rejects", "conditional", "reports_without_position", "no_position",
        "unclear", "not_applicable",
    ],
    "referent_source": ["passage", "speech", "header", "not_applicable"],
    "own_state_accused": ["yes", "no", "not_applicable"],
    "salience": ["passing", "substantive", "not_applicable"],
    "confidence": ["high", "medium", "low"],
}


def check_vocabularies() -> None:
    """The page's lists are the codebook's, or the page is not built."""
    expected = {
        "verdict": schema.VERDICTS, "source_checked": schema.SOURCE_CHECKED,
        "quotation": schema.QUOTATIONS, "concrete_case": schema.CONCRETE_CASE,
        "speaker_position": schema.POSITIONS, "referent_source": schema.REFERENT_SOURCES,
        "own_state_accused": schema.OWN_STATE_ACCUSED, "salience": schema.SALIENCE,
        "confidence": schema.CONFIDENCE,
    }
    for field, values in expected.items():
        if set(VOCABULARIES[field]) != set(values):
            console.fail(f"the page's {field} list differs from lib.schema", [str(sorted(values))])


def data(coder: str | None = None) -> dict[str, object]:
    if not PACKET.is_file():
        console.fail(f"{rel(PACKET)} is missing", ["run scripts/13_gold_sample.py first"])
    packet = pd.read_csv(PACKET, dtype="string", keep_default_na=False)
    speeches = frames.read(SPEECHES_NORM, columns=["filename", "text", "body_start"])
    speeches = speeches.loc[speeches["filename"].isin(set(packet["filename"]))]
    bodies = dict(zip(speeches["filename"], frames.body(speeches), strict=True))
    for row in packet.itertuples():
        body = bodies.get(row.filename)
        if body is None or body[int(row.start):int(row.end)].lower() != row.keyword.lower():
            console.fail(f"{row.occurrence_id} does not sit where the packet says in {row.filename}")
    # The evidence span each row records by default: the pipeline's own sentence
    # segmentation, so `Mr.`, `U.N.` and `S/PV.3137` do not cut it short, as the
    # page's punctuation scan did. Segmented once per speech.
    spans = {name: text.sentence_spans(body) for name, body in bodies.items()}
    bounds = [
        text.sentence_bounds(bodies[row.filename], int(row.start), int(row.end), spans[row.filename])
        for row in packet.itertuples()
    ]
    packet = packet.assign(
        sentence_start=[str(left) for left, _ in bounds],
        sentence_end=[str(right) for _, right in bounds],
    )
    referents = [
        {
            "id": item.id, "label": item.label, "kind": item.kind, "years": item.years,
            "description": item.description,
        }
        for item in llm.read_referent_table(model_runs.REFERENTS)
    ]
    return {
        "columns": list(schema.ANNOTATION_FIELDS),
        "coders": [coder] if coder else [*gold_estimates.CODERS, gold_estimates.ADJUDICATOR],
        "vocabularies": VOCABULARIES,
        "functions": sorted(schema.FUNCTIONS),
        "referents": referents,
        "items": packet.drop(columns=["left", "right"]).to_dict(orient="records"),
        "bodies": bodies,
    }


def read_export(path: Path) -> pd.DataFrame:
    """A file the page exported, possibly re-saved by Excel.

    `utf-8-sig` drops the byte-order mark Excel writes, which would otherwise
    stick to the first header. Blank rows are dropped; columns are put in the
    annotation file's order, and a file missing any of them is refused.
    """
    rows = pd.read_csv(path, dtype="string", keep_default_na=False, encoding="utf-8-sig")
    missing = [field for field in schema.ANNOTATION_FIELDS if field not in rows.columns]
    if missing:
        raise console.Refusal(
            f"{path.name} is not a file exported by the coding page",
            [f"missing columns: {', '.join(missing)}"],
        )
    rows = rows.loc[:, list(schema.ANNOTATION_FIELDS)]
    return rows.loc[rows.apply(lambda row: row.str.strip().ne("").any(), axis=1)].reset_index(
        drop=True
    )


def combine(
    existing: pd.DataFrame, incoming: pd.DataFrame, *, replace: bool
) -> tuple[pd.DataFrame, dict[str, int]]:
    """The annotation file with a coder's export folded in.

    A row is one coder's reading of one occurrence. A row already in the file
    unchanged is skipped. A row that differs from the one on file is a revision,
    and is refused unless `replace` says the coder meant to revise: the file is
    human-owned, and no import should rewrite a reading silently.
    """
    key = ["occurrence_id", "coder"]
    if incoming.duplicated(key).any():
        doubled = incoming.loc[incoming.duplicated(key, keep=False), "occurrence_id"]
        raise console.Refusal(
            "the export reads the same occurrence twice for one coder",
            sorted(set(doubled))[:5],
        )
    on_file = existing.set_index(key)
    added, unchanged, revised = [], 0, []
    for row in incoming.itertuples(index=False):
        record = row._asdict()
        index = (record["occurrence_id"], record["coder"])
        if index not in on_file.index:
            added.append(record)
        elif on_file.loc[index].astype(str).to_dict() == {
            field: str(record[field]) for field in on_file.columns
        }:
            unchanged += 1
        else:
            revised.append(record)
    if revised and not replace:
        raise console.Refusal(
            f"{len(revised)} rows revise a reading already in the annotation file",
            [
                *sorted({str(r['occurrence_id']) for r in revised})[:5],
                "pass --replace if the coder meant to revise them",
            ],
        )
    kept = existing
    if revised:
        drop = {(str(r["occurrence_id"]), str(r["coder"])) for r in revised}
        kept = existing.loc[
            [(o, c) not in drop for o, c in zip(existing["occurrence_id"], existing["coder"], strict=True)]
        ]
    combined = pd.concat([kept, pd.DataFrame(added + revised, columns=existing.columns)], ignore_index=True)
    combined = combined.sort_values(key, kind="stable").reset_index(drop=True)
    return combined, {"added": len(added), "unchanged": unchanged, "revised": len(revised)}


def import_export(source: Path, *, write: bool, replace: bool) -> dict[str, int]:
    """Validate a coder's export against the gold sample and fold it into the file.

    Validation is `lib.audit.merge`, the check every annotated row is held to:
    known occurrences, compatible schema and lexicon, the codebook's labels and
    cascade, and an evidence span that contains the match. Nothing is written
    unless every row passes, and then the file is replaced in one atomic write.
    """
    if not model_runs.GOLD_CANDIDATES.is_file():
        raise console.Refusal(
            f"{rel(model_runs.GOLD_CANDIDATES)} is missing", ["run scripts/13_gold_sample.py first"]
        )
    target = model_runs.GOLD_ANNOTATIONS
    combined, counts = combine(audit.read_annotations(target), read_export(source), replace=replace)
    candidates = pd.read_csv(model_runs.GOLD_CANDIDATES, dtype="string", keep_default_na=False)
    lex = lexicon.load()
    try:
        audit.merge(
            candidates,
            combined,
            referents=audit.read_referents(model_runs.REFERENTS),
            compatible=lex.compatible,
        )
    except ValueError as error:
        raise console.Refusal(f"{source.name} does not pass the annotation checks", [str(error)]) from error
    if write:
        artifacts.atomic_write_csv(target, combined, fieldnames=list(schema.ANNOTATION_FIELDS))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--coder", help="build the page for this coder identifier only")
    parser.add_argument(
        "--import", dest="source", type=Path, metavar="CSV",
        help="check a file the page exported against the gold sample (add --write to save it)",
    )
    parser.add_argument("--write", action="store_true", help="with --import: write the merged file")
    parser.add_argument(
        "--replace", action="store_true",
        help="with --import: let rows revise a coder's earlier reading of the same passage",
    )
    args = parser.parse_args()
    if args.source:
        counts = import_export(args.source, write=args.write, replace=args.replace)
        summary = f"{counts['added']} new, {counts['revised']} revised, {counts['unchanged']} already on file"
        if args.write:
            console.info(f"wrote {rel(model_runs.GOLD_ANNOTATIONS)}: {summary}")
        else:
            console.info(f"{args.source.name} passes every check: {summary}; add --write to save it")
        return
    if args.coder and not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", args.coder):
        console.fail("a coder identifier is 1 to 20 letters, digits, hyphens or underscores")
    check_vocabularies()
    payload = json.dumps(data(args.coder), ensure_ascii=False).replace("</", "<\\/")
    template = (Path(__file__).with_name("coding_page.html")).read_text(encoding="utf-8")
    output = OUTPUT.with_name(f"genocide_coding_{args.coder}.html") if args.coder else OUTPUT
    artifacts.atomic_write_text(output, template.replace("/*DATA*/null", payload, 1))
    console.info(f"wrote {rel(output)}; open it in a browser, code, then save a copy to file")


if __name__ == "__main__":
    console.main(main)
