"""Download the raw corpus from Harvard Dataverse into data/raw/.

The dataset is CC0 and addressed by DOI, so it is never committed to git — this
script makes the repository self-bootstrapping. Files already present with the
right MD5 are skipped.

Usage:
    python scripts/00_fetch_data.py               # the 3 files the pipeline needs
    python scripts/00_fetch_data.py --all         # including the two .RData files
    python scripts/00_fetch_data.py --force       # re-download regardless of MD5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.artifacts import atomic_write_json
from lib.paths import DATASET_VERSION, DATAVERSE, DOI, RAW

# The pipeline reads only these three. docs.RData / docs_meta.RData are
# redundant R serialisations of the same content (119 MB) — opt in with --all.
REQUIRED = {"speeches.tar", "speaker.tsv", "meta.tsv"}
USER_AGENT = (
    "genocide-at-the-security-council/1.0 "
    "(+https://github.com/fmadore/genocide-at-the-security-council)"
)


def dataverse_request(url: str, *, accept: str) -> urllib.request.Request:
    """Identify this project to Dataverse instead of using urllib's blocked default."""
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )


# --- Talking to an archive that sheds load ---------------------------------
#
# Harvard Dataverse refuses requests it does not want to serve right now by
# returning **404 with an HTML error page**, not 429 or 503, and the same URL
# succeeds seconds later. Observed on 11 August 2026: within one minute,
# `meta.tsv` returned 303 then 404 and `speaker.tsv` returned 404 then 200 with
# all 33,027,398 bytes. A single unlucky response used to fail the whole
# publish, which put the release pipeline at the mercy of one HTTP round trip
# against a third-party archive.
#
# The awkward part is that 404 is also how Dataverse says "there is no such
# version", which is a real error this script must not paper over — a mistyped
# pin would otherwise retry for two minutes and then report a network problem.
# The two are told apart by the body: a genuine refusal is JSON carrying
# `status: ERROR`, load-shedding is an HTML page. Anything that cannot be read
# as that JSON is treated as worth another try.
#
# All of which reads a *status*, and on 12 August 2026 the archive shed load
# without using one. Every endpoint — the dataset version lookup, `/api/info/
# version`, the site root — answered **202 with an empty text/html body**,
# identically from two continents and regardless of `User-Agent` or `Accept`.
# `urlopen` raises nothing below 400, so a 202 is a success as far as it is
# concerned: the response reached `json.load`, which failed on an empty string,
# and the run died in 205 ms having spent none of its six attempts. The retry
# was bypassed by the one failure mode it exists for, and the traceback blamed
# `json/decoder.py` for a Harvard outage.
#
# So the judgement `_shedding` makes about a body is also made about a body that
# never became an `HTTPError`. A response that promised JSON and did not deliver
# it is the archive declining to answer, whatever the number on the front.

#: Attempts per request, and the first pause between them. Doubling from 2s
#: gives up after about two minutes — long enough to ride out the shedding seen
#: above, short enough that a genuinely missing file still fails the run rather
#: than hanging a workflow.
MAX_ATTEMPTS = 6
BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 32.0

#: Statuses worth another attempt. 404 is here for the reason written above,
#: and only survives :func:`_shedding` deciding the body was not a real refusal.
RETRYABLE = frozenset({404, 408, 425, 429, 500, 502, 503, 504})


def _shedding(error: urllib.error.HTTPError) -> bool:
    """Whether this response is the archive declining to answer just now.

    A 404 whose body is Dataverse's own JSON error is the archive answering
    exactly: the thing asked for does not exist. Every other unreadable 404 —
    an HTML error page, an empty body, a proxy's notion of a message — is the
    server shedding load under a status that does not say so.
    """
    if error.code not in RETRYABLE:
        return False
    if error.code != 404:
        return True
    try:
        payload = json.loads(error.read())
    except (ValueError, UnicodeDecodeError, OSError):
        return True
    return str(payload.get("status", "")).upper() != "ERROR"


def _pause(error: urllib.error.HTTPError | None, fallback: float) -> float:
    """`Retry-After` when the server names a delay, else the caller's backoff."""
    header = error.headers.get("Retry-After") if error is not None else None
    try:
        return max(float(header), 0.0) if header else fallback
    except (TypeError, ValueError):
        return fallback


def with_retry(operation, describe: str, attempts: int = MAX_ATTEMPTS):
    """Run a network operation, retrying while the archive is shedding load.

    Takes the whole operation rather than wrapping `urlopen`, so that a
    connection dropped part-way through a 474 MB download is retried too — the
    failure this is most likely to meet on the largest file in the dataset.
    Each attempt restarts from the beginning; the MD5 check every download
    already passes through is what proves the bytes arrived intact.
    """
    delay = BACKOFF_SECONDS
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except urllib.error.HTTPError as error:
            if attempt == attempts or not _shedding(error):
                raise
            wait = _pause(error, delay)
            reason = f"HTTP {error.code}"
        except json.JSONDecodeError as error:
            # Re-raised as the archive's failure rather than the parser's: the
            # bare `JSONDecodeError` names a column of a string nobody wrote and
            # sends whoever reads the log to `json/decoder.py` instead of to
            # Harvard's status page. Chained, so the original is still there.
            if attempt == attempts:
                raise RuntimeError(
                    f"{describe}: the archive answered without readable JSON on every "
                    f"one of {attempts} attempts - it is shedding load or is down"
                ) from error
            wait = delay
            reason = "unreadable body"
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            if attempt == attempts:
                raise
            wait = delay
            reason = type(error).__name__
        # ASCII: this line goes to a Windows console as often as to a CI log,
        # and an em dash arrives there as a replacement character.
        print(
            f"\n    {describe}: {reason} - attempt {attempt} of {attempts}, "
            f"retrying in {wait:.0f}s",
            file=sys.stderr,
        )
        time.sleep(wait)
        delay = min(delay * 2, MAX_BACKOFF_SECONDS)
    # `attempts` is validated by the callers; a zero would fall through to here.
    raise RuntimeError(f"{describe}: gave up after {attempts} attempts")


def dataset_version(version: str) -> dict:
    """Read one explicit published dataset version, including its file list."""
    query = urlencode({"persistentId": DOI, "excludeFiles": "false"})
    url = f"{DATAVERSE}/api/datasets/:persistentId/versions/{quote(version)}?{query}"

    def once() -> dict:
        request = dataverse_request(url, accept="application/json")
        with urllib.request.urlopen(request, timeout=60) as resp:
            payload = json.load(resp)
        return payload["data"]

    return with_retry(once, f"dataset version {version}")


def expected_md5(data_file: dict) -> str:
    checksum = data_file.get("checksum") or {}
    if str(checksum.get("type", "")).upper() == "MD5":
        return str(checksum.get("value", ""))
    return str(data_file.get("md5", ""))


def md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def download(file_id: int, dest: Path, size: int) -> None:
    url = f"{DATAVERSE}/api/access/datafile/{file_id}"
    tmp = dest.with_suffix(dest.suffix + ".part")

    def once() -> None:
        done = 0
        request = dataverse_request(url, accept="application/octet-stream")
        # "wb" truncates, so a retry starts from an empty file rather than
        # appending to whatever the failed attempt managed to write.
        with urllib.request.urlopen(request, timeout=120) as resp, tmp.open("wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
                done += len(chunk)
                pct = 100 * done / size if size else 0
                print(f"\r    {done / 1e6:>8.1f} / {size / 1e6:.1f} MB  ({pct:5.1f}%)", end="")
        print()

    with_retry(once, f"datafile {file_id}")
    tmp.replace(dest)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="also fetch the .RData files")
    ap.add_argument("--force", action="store_true", help="re-download even if MD5 matches")
    ap.add_argument(
        "--latest",
        action="store_true",
        help=f"opt into the latest published version instead of pinned {DATASET_VERSION}",
    )
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    requested = ":latest-published" if args.latest else DATASET_VERSION
    version = dataset_version(requested)
    actual = f"{version['versionNumber']}.{version['versionMinorNumber']}"
    if not args.latest and actual != DATASET_VERSION:
        raise RuntimeError(f"requested dataset {DATASET_VERSION}, API returned {actual}")
    print(f"Dataset {DOI} version {actual}\nTarget  {RAW}\n")

    selected = []
    for entry in version["files"]:
        df = entry["dataFile"]
        name = df["filename"]
        if not args.all and name not in REQUIRED:
            print(f"  skip     {name}  (use --all)")
            continue

        dest = RAW / name
        expected = expected_md5(df)
        selected.append(
            {
                "id": df["id"],
                "filename": name,
                "bytes": df["filesize"],
                "md5": expected,
            }
        )

        if dest.exists() and not args.force:
            if expected and md5(dest) == expected:
                print(f"  ok       {name}  ({dest.stat().st_size / 1e6:.1f} MB)")
                continue
            print(f"  stale    {name}  — MD5 mismatch, re-downloading")

        print(f"  fetching {name}  ({df['filesize'] / 1e6:.1f} MB)")
        download(df["id"], dest, df["filesize"])

        if expected and md5(dest) != expected:
            print(f"    MD5 MISMATCH after download for {name}", file=sys.stderr)
            sys.exit(1)

    atomic_write_json(
        RAW / "dataset-manifest.json",
        {
            "doi": DOI,
            "server": DATAVERSE,
            "version": actual,
            "requested": requested,
            "files": selected,
        },
        indent=1,
    )
    print("\nWrote data/raw/dataset-manifest.json")
    print("Done. Next: python scripts/01_build_parquet.py")


if __name__ == "__main__":
    main()
