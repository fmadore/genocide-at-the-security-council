"""Re-derive a committed run's effort figures from the raw record it left behind.

    python tools/recount_run.py 2026-08-31-gemini-v1
    python tools/recount_run.py 2026-08-31-gemini-v1 --write

The review of 1 September 2026 (§4.5, item 1) found the manifest's `requests`
block counting intentions rather than work. Every pass added the number of
speeches it *meant* to ask about, so the Gemini run of 31 August reports 7,966
requests over a corpus of 3,273; `returned: 4,474` counts answers a `--poll`
downloaded twice; and the token totals were accumulated over the same
re-downloads, because the duplicate-row guard that stops rows being appended
twice arrived at commit 2fbd205, part-way through the run, and the tokens were
added before it. `lib.annotate` fixes the counters for the next run. This fixes
the manifest of the last one, as far as the record allows.

**What the record allows.** A batch job's answers are written to
`data/interim/llm_raw/<run_id>/<job>.output.jsonl`, one line per request, as the
job is drained. Those files are the run's own receipt: eleven of them for the
Gemini run, holding 3,273 lines and 3,273 distinct `custom_id`s between them,
which is exactly one request per speech in the documented population. Each line
carries the response's own `usageMetadata`, so the token totals are recomputable
to the token. A live pass leaves `live-*.jsonl` with one line per *successful*
call.

**What it does not allow.** A live call that failed leaves nothing, and a pass
whose first chunk the quota refused leaves nothing either — no job, no file, no
line. The Gemini manifest's 7,966 decomposes as 3,273 + 2,473 + 1,673 + 473 over
four batch passes plus 74 more from one or two live passes, of which exactly one
call is evidenced. So the recounted `sent` is a floor of 3,274 and the per-pass
history is unrecoverable; both are said in the manifest's own `recount` block
rather than reconstructed. `docs/VALIDATION.md` §7 carries the same statement.

The raw directory is under `data/interim/`, which `.gitignore` excludes: it is
large and holds nothing the validated rows do not. A run whose raw directory has
been deleted cannot be recounted, and this says so instead of guessing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import artifacts, console, gemini, llm
from lib.paths import INTERIM, MODEL_ANNOTATIONS, rel

TERM = "genocide"
RUNS = MODEL_ANNOTATIONS / TERM / "runs"
RAW = INTERIM / "llm_raw"


def read_raw(directory: Path) -> tuple[int, set[str], dict[str, int]]:
    """Requests, the identities they answered, and the tokens they cost.

    Both providers' raw files are one JSON object per line keyed by the speech,
    and `lib.gemini.read_result_line` reads the Gemini spelling; the OpenAI
    spelling is read here in the four lines it takes, rather than importing a
    numbered script for them. A line that carries no readable body is still a
    request that was sent and paid for, and is counted as one.
    """
    requests = 0
    answered: set[str] = set()
    tokens = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    for path in sorted(directory.glob("*.jsonl")):
        if path.name.endswith(".input.jsonl"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            requests += 1
            record = json.loads(line)
            if "custom_id" in record:
                # The OpenAI batch spelling: {custom_id, response: {body}}. The
                # Gemini one keys the speech as `key` and carries the response
                # directly, which is what tells the two files apart here.
                identifier = str(record.get("custom_id", ""))
                body = record["response"].get("body") or {}
                usage = body.get("usage") if isinstance(body, dict) else None
                if isinstance(usage, dict):
                    details = usage.get("output_tokens_details")
                    tokens["input_tokens"] += int(usage.get("input_tokens") or 0)
                    tokens["output_tokens"] += int(usage.get("output_tokens") or 0)
                    tokens["reasoning_tokens"] += int(
                        (details or {}).get("reasoning_tokens") or 0
                    )
            else:
                identifier, body, _ = gemini.read_result_line(line)
                if body is not None:
                    for key, value in gemini.usage_of(body).items():
                        tokens[key] += value
            if identifier:
                answered.add(identifier)
    return requests, answered, tokens


def recount(run_id: str) -> dict[str, object]:
    """The repaired manifest, not written."""
    manifest_path = RUNS / run_id / "manifest.json"
    if not manifest_path.is_file():
        console.fail(f"no manifest at {rel(manifest_path)}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    raw = RAW / run_id
    if not raw.is_dir():
        console.fail(
            f"no raw record at {rel(raw)}",
            [
                "the run's receipts are under data/interim/, which is not committed",
                "a run whose raw directory is gone cannot be recounted; leave the "
                "manifest alone and record what is unrecoverable in VALIDATION.md",
            ],
        )
    requests, answered, tokens = read_raw(raw)
    rows = llm.read_rows(RUNS / run_id / "annotations.jsonl")
    relocated = sum(1 for row in rows if row.get("evidence_relocated"))

    before = manifest.get("requests") or {}
    repaired = dict(manifest)
    repaired["requests"] = {
        "planned": int(before.get("planned", 0)),
        "sent": requests,
        "returned": len(answered),
        "complete": int(before.get("complete", 0)),
    }
    repaired["usage"] = tokens
    repaired["recount"] = {
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "by": "tools/recount_run.py",
        "from": f"data/interim/llm_raw/{run_id}/ (not committed)",
        "was": {
            "requests": {
                key: value for key, value in before.items() if key in {"submitted", "returned"}
            },
            "usage": manifest.get("usage"),
        },
        "unrecoverable": [
            "the per-pass history: a pass the batch quota refused created no job and "
            "left no file, and a live call that failed left no line",
            "`sent` is therefore a floor — the requests the raw record evidences",
        ],
    }
    if relocated:
        repaired["evidence_relocated"] = relocated
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="e.g. 2026-08-31-gemini-v1")
    parser.add_argument("--write", action="store_true", help="rewrite the manifest in place")
    args = parser.parse_args()

    repaired = recount(args.run_id)
    path = RUNS / args.run_id / "manifest.json"
    before = json.loads(path.read_text(encoding="utf-8"))
    console.table(
        [
            ("requests sent", f"{before['requests'].get('submitted', '—')} → "
             f"{repaired['requests']['sent']:,}"),
            ("returned", f"{before['requests'].get('returned', '—')} → "
             f"{repaired['requests']['returned']:,}"),
            *(
                (f"{key}", f"{before['usage'].get(key, 0):,} → {value:,}")
                for key, value in repaired["usage"].items()
            ),
        ]
    )
    if args.write:
        artifacts.atomic_write_json(path, repaired, indent=1)
        console.info(f"rewrote {rel(path)} — review the diff")
    else:
        console.info("nothing written; pass --write to rewrite the manifest")


if __name__ == "__main__":
    main()
