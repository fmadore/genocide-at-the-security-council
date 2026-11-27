# Machine-readable access and MCP integration

Every analytical table and verbatim meeting file loaded by the website is published statically on GitHub Pages under `https://fmadore.github.io/genocide-at-the-security-council/data/`. You can build a local [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server or scripted client directly against these static files without downloading the raw Harvard Dataverse archive or running the Python pipeline.

## Discovery entry points

| Entry point | Format | Purpose |
| --- | --- | --- |
| [`/llms.txt`](https://fmadore.github.io/genocide-at-the-security-council/llms.txt) | Plain text | Concise agent-facing overview of endpoints, caveats, and epistemic rules |
| [`/data-catalog.json`](https://fmadore.github.io/genocide-at-the-security-council/data-catalog.json) | JSON | Machine-readable inventory of all static endpoints, key fields, join keys, and epistemic status |
| [`/data/manifest.json`](https://fmadore.github.io/genocide-at-the-security-council/data/manifest.json) | JSON | Build timestamp, git commit, release tag (when stamped), and SHA-256 checksums for every payload part |

## How the static files join together

1. **Time series (`data/series/annual.json`, `quarterly.json`, `monthly.json`):** parallel arrays indexed by `periods`, with `corpus.speeches`, `corpus.words`, `sufficient` (`minimum_speeches = 125`), and `terms.<term>` counts, Wilson 95% intervals, and meeting-resampled 95% intervals.
2. **Concordance (`data/kwic/index.json` and `data/kwic/<term>.json`):** every matched occurrence carries a line identifier `id` of the form `<speech_id>#<ordinal>` (for example `SC07155-01-007#3`) and a meeting symbol `spv` (`S/PV.7155`).
3. **Full verbatim speeches (`data/meetings.json` and `data/speeches/<basename>.json.gz`):** the first ten characters of a speech identifier (`SC07155-01`) name its gzipped meeting file, which holds the full English verbatim speech texts (`CC0 1.0`) and exact match offsets.
4. **Delegations (`data/countries/countries.json`, `data/countries/speaker_keyness.json`, `data/actor_year/actor_year.csv`):** totals, shares, matched vocabulary keyness, and annual actor rows.
5. **Model-derived usage layer (`data/usage/usage.json`, `data/usage/occurrences.json`, `data/usage/referents.json`) — UNVALIDATED PREVIEW:** joins to `kwic/genocide.json` on `id` and to the gold sample on `occurrence_id`. Carries Qwen3.8-27B labels alongside Gemma-4-31B disagreements (`contested`, `alt`).

See [DATASHEET.md](DATASHEET.md) for the complete field dictionary and [CLAIMS.md](CLAIMS.md) for what each figure rests on.

## Starter MCP server and Agent Skill

[`examples/mcp-starter/`](../examples/mcp-starter/README.md) provides a minimal, read-only Python MCP server (using the official `mcp` v2+ SDK) and an accompanying [Agent Skill](../examples/mcp-starter/SKILL.md) (`SKILL.md`):

- **`client.py`** reads either the live GitHub Pages site (caching downloaded files in `~/.cache/unsc-genocide-mcp/`) or a local `web/static/data/` build when `UNSC_DATA_DIR` is set.
- **`server.py`** exposes five starter tools (`get_catalog`, `get_annual_series`, `search_concordance`, `get_speech`, and the explicitly flagged `get_model_labels`) plus an `unsc://epistemic-rules` resource.
- **`SKILL.md`** encodes the project's epistemic rules so connected assistants separate computed measures from unvalidated model labels, cite `S/PV` meeting symbols, and read full speeches before interpreting a passage.

Run the starter with the MCP Inspector in one command:

```bash
uv run --with "mcp[cli]>=2.3.0,<3" mcp dev examples/mcp-starter/server.py
```

## Non-negotiable rules for MCP servers and AI workflows

Any custom MCP server or agent workflow built on this site should preserve the boundaries documented in [CLAIMS.md](CLAIMS.md) and [DATASHEET.md](DATASHEET.md):

- **Separate epistemic layers in every tool response:** mark whether a result is `computed_from_record`, `model_derived_unvalidated`, or `experimental_embedding`.
- **Keep corpus limits attached to counts:** the text is the English UN verbatim record (including translations), excludes informal consultations and 717 meetings without speeches, and scanning errors make every count a minimum.
- **Do not present `usage/*` labels as verified findings:** human gold coding is pending; exclude rows with `evidence_valid: false` from aggregates and surface `contested`/`alt` model disagreements.
- **Ground textual claims in full speeches:** always provide a tool path from concordance or label rows to `data/speeches/{basename}.json.gz` so the model and reader can verify the quote in context.
- **Preserve provenance and licences:** return `analysis_hash` where present, keep speech text under `CC0 1.0` and derived tables under `CC BY 4.0`, and cite both [`CITATION.cff`](../CITATION.cff) and `doi:10.7910/DVN/CKPTRB`.
