"""Download the raw corpus from Harvard Dataverse into data/raw/.

The dataset is CC0 and addressed by DOI, so it is never committed to git — this
script makes the repository self-bootstrapping. Files already present with the
right MD5 are skipped.

**The network is a consequence of missing bytes, not a precondition.** What each
file must contain is `config/dataset-pin.json`, which records Harvard's own MD5
for every file in the pinned version; a published Dataverse version is immutable,
so those are constants and belong in the repository. A corpus that is already
present is therefore verified with no request at all, and `/api/access/datafile/`
is reached only for a file that is missing or stale — using the id in the pin, so
even that needs no metadata lookup.

This used to work the other way round: the file list and its checksums were read
from the API first, which made a network call the precondition for checking a
corpus already on disk. In August 2026 a bot challenge in front of the archive
(see the comment block below) turned that into a hard stop for every deploy,
while 508 MB of already-verified corpus sat in the cache.

Only `--latest` still requires the API, because asking what Harvard published
most recently is a question no local file can answer.

Usage:
    python scripts/00_fetch_data.py               # the 2 files the pipeline needs
    python scripts/00_fetch_data.py --all         # every file recorded in the pin
    python scripts/00_fetch_data.py --force       # re-download regardless of MD5
    python scripts/00_fetch_data.py --latest      # ask the API for the newest version
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.artifacts import atomic_write_json
from lib.paths import CONFIG, DATASET_VERSION, DATAVERSE, DOI, RAW

#: Harvard's checksums for the pinned version, recorded so that verifying a
#: corpus already on disk needs nothing from the network. See the file itself
#: for how the values were obtained and what changing the pin involves.
PIN = CONFIG / "dataset-pin.json"

# The Sakamoto-Matsuoka distribution is already a pair of UTF-8 TSV tables:
# one row per speech and one row per meeting. The documentation files are not
# runtime inputs and are therefore not downloaded by default.
REQUIRED = {"speeches.tsv", "meetings.tsv"}
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
# All of which reads a *status*, and in August 2026 the refusal stopped using
# one. Every endpoint — the version lookup, the file download, the dataset
# landing page — answered `202 Accepted` with an empty body and the header
# `x-amzn-waf-action: challenge`, identically from a German workstation and a
# US-East runner, with and without an API token.
#
# That is not the archive shedding load. It is AWS WAF in front of it, asking
# the client to run a JavaScript challenge and hand back a token — which a
# browser does invisibly and a pipeline cannot. Dataverse behind it was healthy
# throughout: the same URLs returned `{"status":"OK"}` in a browser, all the
# way through the outage this script first blamed.
#
# `urlopen` raises nothing below 400, so a 202 is a success as far as it is
# concerned, and the misreading was costly in both directions. The metadata call
# reached `json.load`, died on an empty string, and blamed `json/decoder.py` for
# something Harvard's edge did; a download would have written a 0-byte file and
# failed its MD5 — two misleading accounts of one refusal. Six attempts were
# then spent on a challenge that no number of attempts satisfies.
#
# Hence two separate things below. `_refuse_if_challenged` names the WAF and
# stops at once, because a challenge is a refusal to answer *this client* rather
# than a bad moment to ask, and the fix for it is not in this repository. And a
# body that promised JSON and did not deliver one is still worth another try —
# the judgement `_shedding` already makes about a 404, extended to responses
# that never became an `HTTPError` at all.

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


class Challenged(RuntimeError):
    """The edge in front of the archive challenged this client instead of answering.

    Deliberately not a retry and deliberately not worked around. Satisfying an
    AWS WAF challenge means executing its JavaScript and replaying the token it
    issues, which is what the control exists to stop a non-browser doing; a
    reproducible pipeline that dressed itself as a browser to get past one would
    be a worse thing than a pipeline that stops and says why.
    """


def _refuse_if_challenged(resp: http.client.HTTPResponse) -> None:
    """Stop, by name, when the WAF answers in place of Dataverse.

    Checked on the response rather than in :func:`with_retry`, because this
    never becomes an exception on its own: the status is a 2xx and the body is
    empty, so every layer below treats it as a successful request that happened
    to carry nothing. The header lookup is case-insensitive, `resp.headers`
    being an `email.message.Message`.
    """
    action = resp.headers.get("x-amzn-waf-action")
    if not action:
        return
    raise Challenged(
        f"Harvard Dataverse replied HTTP {resp.status} with x-amzn-waf-action: {action} "
        "instead of data. Its bot protection is challenging this client, and no "
        "retry satisfies a challenge - it wants a browser to run JavaScript. The "
        "archive itself is healthy; the same URL opens in a browser, and an API "
        "token makes no difference because the WAF refuses before Dataverse sees "
        "it. Report it to support@dataverse.harvard.edu: it breaks every "
        "programmatic reader of the DOI, not only this one."
    )


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
                    f"one of {attempts} attempts"
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


def pinned_version() -> dict:
    """The pinned version's file list, from `config/dataset-pin.json`.

    Shaped like the API's own answer so that `main` does not care which of the
    two it is holding. The version is checked against `DATASET_VERSION` here
    rather than trusted: they are two statements of the same fact in two files,
    and a pin bumped in one and not the other would otherwise verify a corpus
    against the checksums of a different release.
    """
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    if pin["version"] != DATASET_VERSION:
        raise RuntimeError(
            f"{PIN.name} pins version {pin['version']} but lib/paths.py pins "
            f"{DATASET_VERSION} - the two must name the same release"
        )
    if pin["doi"] != DOI:
        raise RuntimeError(f"{PIN.name} pins {pin['doi']} but lib/paths.py pins {DOI}")
    major, _, minor = pin["version"].partition(".")
    return {
        "versionNumber": int(major),
        "versionMinorNumber": int(minor),
        "files": [
            {
                "dataFile": {
                    "id": entry["id"],
                    "filename": entry["filename"],
                    "filesize": entry["bytes"],
                    "checksum": {"type": "MD5", "value": entry["md5"]},
                }
            }
            for entry in pin["files"]
        ],
    }


def dataset_version(version: str) -> dict:
    """Read one explicit published dataset version, including its file list."""
    query = urlencode({"persistentId": DOI, "excludeFiles": "false"})
    url = f"{DATAVERSE}/api/datasets/:persistentId/versions/{quote(version)}?{query}"

    def once() -> dict:
        request = dataverse_request(url, accept="application/json")
        with urllib.request.urlopen(request, timeout=60) as resp:
            _refuse_if_challenged(resp)
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
            # Before the first write, so a challenge is never mistaken for a
            # download that arrived empty and failed its checksum.
            _refuse_if_challenged(resp)
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
    ap.add_argument("--all", action="store_true", help="fetch every file recorded in the pin")
    ap.add_argument("--force", action="store_true", help="re-download even if MD5 matches")
    ap.add_argument(
        "--latest",
        action="store_true",
        help=f"opt into the latest published version instead of pinned {DATASET_VERSION}",
    )
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    requested = ":latest-published" if args.latest else DATASET_VERSION
    if args.latest:
        # The only question the pin cannot answer.
        version = dataset_version(requested)
        source = "the API"
    else:
        version = pinned_version()
        source = PIN.name
    actual = f"{version['versionNumber']}.{version['versionMinorNumber']}"
    if not args.latest and actual != DATASET_VERSION:
        raise RuntimeError(f"requested dataset {DATASET_VERSION}, {source} returned {actual}")
    print(f"Dataset {DOI} version {actual}  (per {source})\nTarget  {RAW}\n")

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
            # Which of the two statements of the pin these checksums came from.
            # A reader asking whether a payload was built without contacting the
            # archive should not have to infer it from a log that has scrolled.
            "checksums_from": source,
            "files": selected,
        },
        indent=1,
    )
    print("\nWrote data/raw/dataset-manifest.json")
    print("Done. Next: python scripts/01_build_parquet.py")


if __name__ == "__main__":
    main()
