"""Build the offline coding page for the genocide gold sample.

    python tools/coding_page.py            # writes data/interim/genocide_coding.html

The coders' work was a 22-column CSV edited by hand, with evidence recorded as
character offsets typed from a count. This writes one self-contained HTML file
from the blinded packet (`13_gold_sample.py`) that shows each passage inside its
whole speech, takes the evidence as a text selection, applies the codebook's
cascade as the coder goes, keeps progress in the browser, and exports rows in
the exact column order of `annotations/genocide/annotations.csv`
(docs/ROADMAP.md, RV16).

Nothing here decides a label. The page carries no model output, no frame, no
stratum and no cue, because the packet carries none; it is the packet made
workable. The exported rows are pasted into the versioned annotation file and
validated there by `lib.audit`, exactly as hand-typed rows are.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, audit, console, frames, llm, model_runs, usage
from lib.paths import INTERIM, SPEECHES_NORM, rel

PACKET = INTERIM / "genocide_gold_packet.csv"
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
        "verdict": audit.VERDICTS, "source_checked": audit.SOURCE_CHECKED,
        "quotation": audit.QUOTATIONS, "concrete_case": audit.CONCRETE_CASE,
        "speaker_position": audit.POSITIONS, "referent_source": audit.REFERENT_SOURCES,
        "own_state_accused": audit.OWN_STATE_ACCUSED, "salience": audit.SALIENCE,
        "confidence": audit.CONFIDENCE,
    }
    for field, values in expected.items():
        if set(VOCABULARIES[field]) != set(values):
            console.fail(f"the page's {field} list differs from lib.audit", [str(sorted(values))])


def data() -> dict[str, object]:
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
        {"id": item.id, "label": item.label, "kind": item.kind, "years": item.years}
        for item in llm.read_referent_table(model_runs.REFERENTS)
    ]
    return {
        "columns": list(audit.ANNOTATION_FIELDS),
        "coders": [*usage.CODERS, usage.ADJUDICATOR],
        "vocabularies": VOCABULARIES,
        "functions": sorted(audit.FUNCTIONS),
        "referents": referents,
        "items": packet.drop(columns=["left", "right"]).to_dict(orient="records"),
        "bodies": bodies,
    }


def main() -> None:
    check_vocabularies()
    payload = json.dumps(data(), ensure_ascii=False).replace("</", "<\\/")
    template = (Path(__file__).with_name("coding_page.html")).read_text(encoding="utf-8")
    artifacts.atomic_write_text(OUTPUT, template.replace("/*DATA*/null", payload, 1))
    console.info(f"wrote {rel(OUTPUT)}; open it in a browser, code, then export the CSV")


if __name__ == "__main__":
    main()
