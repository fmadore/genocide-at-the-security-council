# Starter MCP Server for Genocide at the Security Council

This folder contains a minimal, read-only [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server and an accompanying [Agent Skill](https://agentskills.io) (`SKILL.md`) built on top of the static data published by **Genocide at the Security Council**.

No Harvard Dataverse download or local pipeline build is required: by default, the server fetches the public static files from GitHub Pages (`https://fmadore.github.io/genocide-at-the-security-council/`) and caches them locally in `~/.cache/unsc-genocide-mcp/`.

## Files

| File | Purpose |
| --- | --- |
| `client.py` | Stdlib-only data client reading either GitHub Pages (cached) or a local `web/static/data/` directory |
| `server.py` | Minimal `MCPServer` (official `mcp` Python SDK v2+) exposing 5 tools and 1 epistemic-rules resource |
| `SKILL.md` | Agent Skill instructing connected assistants to enforce source traceability and label unvalidated model data |
| `pyproject.toml` | Standalone Python 3.12+ project file (`mcp>=2.3.0,<3`) |

## Quick start

Inspect and test the tools interactively with the MCP Inspector:

```bash
uv run --with "mcp[cli]>=2.3.0,<3" mcp dev examples/mcp-starter/server.py
```

Or run directly over `stdio` for an MCP host (Claude Desktop, Cursor, Codex, Antigravity):

```bash
uv run --with "mcp>=2.3.0,<3" python examples/mcp-starter/server.py
```

### Offline mode (against a local build)

If you have already run `make payload` in this repository, point the server at `web/static/data/` so it makes no network requests:

```bash
UNSC_DATA_DIR=./web/static/data uv run --with "mcp>=2.3.0,<3" python examples/mcp-starter/server.py
```

### Example MCP host configuration (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "unsc-genocide": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp>=2.3.0,<3",
        "python",
        "/absolute/path/to/examples/mcp-starter/server.py"
      ]
    }
  }
}
```

## Included tools

| Tool | Epistemic layer | What it reads |
| --- | --- | --- |
| `get_catalog` | Provenance | `/data-catalog.json` (or local `data/manifest.json`) |
| `get_annual_series` | Computed from the record | `data/series/annual.json` |
| `search_concordance` | Computed from the record | `data/kwic/{term}.json` |
| `get_speech` | Computed from the record | `data/speeches/{basename}.json.gz` |
| `get_model_labels` | **Model-derived (unvalidated preview)** | `data/usage/occurrences.json` |

## Ideas for extending this starter

This starter intentionally exposes only the core surface so students and researchers can extend and audit it:

- Add delegation tools over `data/countries/countries.json`, `data/countries/speaker_keyness.json`, and `data/actor_year/actor_year.csv`.
- Add a model-disagreement audit tool that filters `data/usage/occurrences.json` for rows where `contested` is non-empty (Qwen3.8 vs. Gemma 4) and fetches the full speech for close reading.
- Build a local SQLite FTS5 index over `data/kwic/genocide.json` or a subset of `data/speeches/*.json.gz` for full-text search across debates.
- Pair new tools with updates to `SKILL.md` and evaluate how the agent handles withheld rates, translation caveats, and unvalidated labels.
