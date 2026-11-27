"""Minimal Model Context Protocol (MCP) server for Genocide at the Security Council.

Run locally with the official MCP Python SDK (v2+):
    uv run --with "mcp[cli]>=2.3.0,<3" mcp dev examples/mcp-starter/server.py
or over stdio:
    uv run --with "mcp>=2.3.0,<3" python examples/mcp-starter/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running directly as `python examples/mcp-starter/server.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from client import EPISTEMIC_RULES, UnscDataClient
from mcp.server import MCPServer

mcp = MCPServer("genocide-at-the-security-council")
data = UnscDataClient()


@mcp.resource("unsc://epistemic-rules")
def epistemic_rules() -> str:
    """Non-negotiable epistemic rules for interpreting this dataset."""
    return "\n".join(f"- {rule}" for rule in EPISTEMIC_RULES)


@mcp.tool()
def get_catalog() -> str:
    """Return the site's data catalogue, endpoints, schemas, and epistemic status."""
    return json.dumps(data.get_catalog(), ensure_ascii=False, indent=2)


@mcp.tool()
def get_annual_series(
    term: str = "genocide",
    start_year: int = 1946,
    end_year: int = 2026,
) -> str:
    """Return computed annual counts, speech shares, and 95% intervals for a lexicon term."""
    result = data.get_annual_series(term=term, start_year=start_year, end_year=end_year)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def search_concordance(
    term: str = "genocide",
    country: str | None = None,
    year: int | None = None,
    query: str | None = None,
    limit: int = 15,
) -> str:
    """Search computed concordance lines by lexicon term, delegation, year, and sentence text."""
    result = data.search_concordance(
        term=term,
        country=country,
        year=year,
        query=query,
        limit=limit,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_speech(speech_id: str) -> str:
    """Fetch the full verbatim UN Security Council speech for a speech or occurrence id."""
    result = data.get_speech(speech_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_model_labels(identifier: str) -> str:
    """Fetch unvalidated experimental LLM labels (Qwen3.8 + Gemma 4 disagreements) for one genocide occurrence."""
    result = data.get_model_labels(identifier)
    return json.dumps(result, ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
