"""Stdlib-only client for the static data published by Genocide at the Security Council.

Reads either a local `web/static/data/` directory (`UNSC_DATA_DIR`) or the live
GitHub Pages site (`UNSC_DATA_BASE_URL`, cached on disk in `UNSC_CACHE_DIR`).
Kept separate from `server.py` so the retrieval and filtering logic can be
tested and reused without importing the MCP SDK.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://fmadore.github.io/genocide-at-the-security-council"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "unsc-genocide-mcp"

TERM_RE = re.compile(r"^[a-z0-9_]+$")
BASENAME_RE = re.compile(r"^SC\d{5}-\d{2}$")
SPEECH_ID_RE = re.compile(r"^(SC\d{5}-\d{2})-\d{3}(?:#\d+)?$")

EPISTEMIC_RULES: tuple[str, ...] = (
    "Always state whether a figure comes from a computed_from_record endpoint or a "
    "model_derived_unvalidated endpoint.",
    "Counts are minimums in the English UN verbatim record (including UN translations) "
    "and exclude informal consultations and 717 meetings without speeches.",
    "LLM labels in data/usage/occurrences.json are an unvalidated preview: never report "
    "them as verified findings, and always surface contested/alt comparison-model labels.",
    "Verify textual claims by reading the full verbatim speech in "
    "data/speeches/{basename}.json.gz and citing its S/PV meeting symbol.",
    "Do not infer legal determinations of genocide or timeless national positions from "
    "vocabulary counts.",
)


def parse_meeting_basename(identifier: str) -> str:
    """Extract the meeting file basename (e.g. `SC07155-01`) from a speech or occurrence id."""
    cleaned = identifier.strip()
    if BASENAME_RE.fullmatch(cleaned):
        return cleaned
    match = SPEECH_ID_RE.fullmatch(cleaned)
    if match:
        return match.group(1)
    raise ValueError(
        f"Expected a meeting basename (SC07155-01), speech id (SC07155-01-007), "
        f"or occurrence id (SC07155-01-007#1); got {identifier!r}"
    )


def validate_term(term: str) -> str:
    cleaned = term.strip().lower()
    if not TERM_RE.fullmatch(cleaned):
        raise ValueError(f"Invalid lexicon term identifier: {term!r}")
    return cleaned


class UnscDataClient:
    """Read-only client over the static JSON and gzipped speech files."""

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        base_url: str | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        env_dir = os.environ.get("UNSC_DATA_DIR")
        self.data_dir = data_dir or (Path(env_dir) if env_dir else None)
        self.base_url = (base_url or os.environ.get("UNSC_DATA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        env_cache = os.environ.get("UNSC_CACHE_DIR")
        self.cache_dir = cache_dir or (Path(env_cache) if env_cache else DEFAULT_CACHE_DIR)

    def _read_bytes(self, relative_site_path: str) -> bytes:
        clean = relative_site_path.lstrip("/")
        if self.data_dir is not None:
            local_rel = clean.removeprefix("data/")
            local_path = (self.data_dir / local_rel).resolve()
            if not local_path.is_relative_to(self.data_dir.resolve()):
                raise ValueError(f"Path escapes UNSC_DATA_DIR: {relative_site_path!r}")
            return local_path.read_bytes()

        cached = (self.cache_dir / clean).resolve()
        if not cached.is_relative_to(self.cache_dir.resolve()):
            raise ValueError(f"Path escapes cache directory: {relative_site_path!r}")
        if cached.is_file():
            return cached.read_bytes()

        url = f"{self.base_url}/{clean}"
        request = urllib.request.Request(url, headers={"User-Agent": "unsc-genocide-mcp-starter/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload: bytes = response.read()
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(payload)
        return payload

    def read_json(self, relative_site_path: str) -> Any:
        raw = self._read_bytes(relative_site_path)
        if relative_site_path.endswith(".gz"):
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))

    def get_catalog(self) -> dict[str, Any]:
        """Return `/data-catalog.json` when remote, or a local manifest summary."""
        if self.data_dir is not None:
            manifest = self.read_json("data/manifest.json")
            return {
                "mode": "local",
                "data_dir": str(self.data_dir),
                "manifest": manifest,
                "epistemic_rules": list(EPISTEMIC_RULES),
            }
        catalog: dict[str, Any] = self.read_json("data-catalog.json")
        return catalog

    def get_annual_series(
        self,
        term: str = "genocide",
        start_year: int = 1946,
        end_year: int = 2026,
    ) -> dict[str, Any]:
        term_key = validate_term(term)
        annual = self.read_json("data/series/annual.json")
        terms = annual.get("terms", {})
        if term_key not in terms:
            available = sorted(terms)
            raise KeyError(f"Unknown term {term_key!r}. Available terms: {', '.join(available)}")

        series = terms[term_key]
        periods = annual["periods"]
        corpus_speeches = annual["corpus"]["speeches"]
        corpus_words = annual["corpus"]["words"]
        sufficient = annual["sufficient"]

        rows = []
        for idx, year in enumerate(periods):
            if start_year <= int(year) <= end_year:
                rows.append(
                    {
                        "year": year,
                        "corpus_speeches": corpus_speeches[idx],
                        "corpus_words": corpus_words[idx],
                        "sufficient": sufficient[idx],
                        "speeches": series["speeches"][idx],
                        "occurrences": series["occurrences"][idx],
                        "speech_rate": series["speech_rate"][idx],
                        "speech_rate_wilson95": [
                            series["speech_rate_low"][idx],
                            series["speech_rate_high"][idx],
                        ],
                        "speech_rate_meeting95": [
                            series["speech_rate_cluster_low"][idx],
                            series["speech_rate_cluster_high"][idx],
                        ],
                        "token_rate_per_100k": series["token_rate"][idx],
                    }
                )

        return {
            "epistemic_layer": "computed_from_record",
            "validated": True,
            "term": term_key,
            "minimum_speeches": annual.get("minimum_speeches"),
            "record": annual.get("record"),
            "analysis_hash": annual.get("meta", {}).get("analysis_hash"),
            "rows": rows,
        }

    def search_concordance(
        self,
        term: str = "genocide",
        country: str | None = None,
        year: int | None = None,
        query: str | None = None,
        limit: int = 15,
    ) -> dict[str, Any]:
        term_key = validate_term(term)
        bounded_limit = max(1, min(limit, 50))
        kwic = self.read_json(f"data/kwic/{term_key}.json")

        country_needle = country.strip().lower() if country else None
        year_prefix = f"{year:04d}-" if year is not None else None
        query_needle = query.strip().lower() if query else None

        matches = []
        total_matches = 0
        for row in kwic.get("lines", []):
            if country_needle and country_needle not in str(row.get("country", "")).lower():
                continue
            if year_prefix and not str(row.get("date", "")).startswith(year_prefix):
                continue
            if query_needle and query_needle not in str(row.get("sent", "")).lower():
                continue
            total_matches += 1
            if len(matches) < bounded_limit:
                line_id = str(row["id"])
                matches.append(
                    {
                        "id": line_id,
                        "speech_id": line_id.split("#", 1)[0],
                        "meeting_basename": parse_meeting_basename(line_id),
                        "spv": row.get("spv"),
                        "date": row.get("date"),
                        "country": row.get("country"),
                        "group": row.get("group"),
                        "participant_type": row.get("type"),
                        "agenda": row.get("agenda"),
                        "keyword": row.get("kw"),
                        "sentence": row.get("sent"),
                    }
                )

        return {
            "epistemic_layer": "computed_from_record",
            "validated": True,
            "term": term_key,
            "total_in_corpus": kwic.get("count"),
            "total_matching_filters": total_matches,
            "returned": len(matches),
            "analysis_hash": kwic.get("meta", {}).get("analysis_hash"),
            "matches": matches,
        }

    def get_speech(self, speech_id: str) -> dict[str, Any]:
        clean_id = speech_id.strip().split("#", 1)[0]
        basename = parse_meeting_basename(clean_id)
        meeting = self.read_json(f"data/speeches/{basename}.json.gz")

        for speech in meeting.get("speeches", []):
            if speech.get("id") == clean_id:
                return {
                    "epistemic_layer": "computed_from_record",
                    "validated": True,
                    "licence": "CC0-1.0 (speech text from Sakamoto & Matsuoka v6.0)",
                    "basename": meeting.get("basename"),
                    "spv": meeting.get("spv"),
                    "date": meeting.get("date"),
                    "agenda": meeting.get("agenda"),
                    "speech": speech,
                }
        raise KeyError(f"Speech {clean_id!r} not found in meeting {basename}")

    def get_model_labels(self, identifier: str) -> dict[str, Any]:
        """Look up experimental, unvalidated LLM labels by line id or checksum occurrence_id."""
        needle = identifier.strip()
        usage = self.read_json("data/usage/occurrences.json")
        meta = usage.get("meta", {})
        for row in usage.get("occurrences", []):
            if row.get("id") == needle or row.get("occurrence_id") == needle:
                return {
                    "epistemic_layer": "model_derived_unvalidated",
                    "validated": False,
                    "warning": (
                        "UNVALIDATED PREVIEW: generated by an open-weight LLM without human "
                        "gold validation. Do not present as a verified finding; read the full "
                        "speech via get_speech and report any contested/alt disagreements."
                    ),
                    "run_id": meta.get("run_id"),
                    "model": meta.get("model"),
                    "comparison_run": meta.get("comparison_run"),
                    "labels": row,
                }
        raise KeyError(f"No model annotation found for {needle!r}")
