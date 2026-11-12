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
workable. The exported rows are pasted into the versioned annotation file and
validated there by `lib.audit`, exactly as hand-typed rows are.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, console, frames, gold_estimates, llm, model_runs, schema
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--coder", help="build the page for this coder identifier only")
    args = parser.parse_args()
    if args.coder and not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", args.coder):
        console.fail("a coder identifier is 1 to 20 letters, digits, hyphens or underscores")
    check_vocabularies()
    payload = json.dumps(data(args.coder), ensure_ascii=False).replace("</", "<\\/")
    template = (Path(__file__).with_name("coding_page.html")).read_text(encoding="utf-8")
    output = OUTPUT.with_name(f"genocide_coding_{args.coder}.html") if args.coder else OUTPUT
    artifacts.atomic_write_text(output, template.replace("/*DATA*/null", payload, 1))
    console.info(f"wrote {rel(output)}; open it in a browser, code, then save a copy to file")


if __name__ == "__main__":
    main()
