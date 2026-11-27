import { canonicalUrl, PUBLIC_ORIGIN, REPOSITORY, SITE_NAME } from './seo.js';

export type EpistemicLayer =
	'provenance' | 'computed_from_record' | 'model_derived_unvalidated' | 'experimental_embedding';

export interface DataEndpoint {
	id: string;
	path: string;
	url: string;
	format: 'json' | 'csv' | 'json.gz';
	epistemic_layer: EpistemicLayer;
	validated: boolean;
	produced_by: string;
	description: string;
	key_fields: readonly string[];
	join_keys?: readonly string[];
	caveat?: string;
}

const dataUrl = (relative: string): string => `${PUBLIC_ORIGIN}/data/${relative}`;

export const DATA_ENDPOINTS: readonly DataEndpoint[] = [
	{
		id: 'manifest',
		path: 'data/manifest.json',
		url: dataUrl('manifest.json'),
		format: 'json',
		epistemic_layer: 'provenance',
		validated: true,
		produced_by: 'export_web.py',
		description:
			'Build timestamp, git commit, release tag (if stamped), and SHA-256 checksums for every payload part.',
		key_fields: ['generated', 'git_commit', 'parts', 'files', 'bytes']
	},
	{
		id: 'series_annual',
		path: 'data/series/annual.json',
		url: dataUrl('series/annual.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '04_series.py',
		description:
			'Annual counts, speech shares, Wilson and meeting-resampled 95% intervals, and rates per 100,000 words for all 28 lexicon terms (1946–2026).',
		key_fields: ['periods', 'corpus', 'record', 'sufficient', 'minimum_speeches', 'terms'],
		caveat:
			'Rates are null for periods below 125 speeches (only 1959). Counts are minimums in the English UN record.'
	},
	{
		id: 'series_quarterly',
		path: 'data/series/quarterly.json',
		url: dataUrl('series/quarterly.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '04_series.py',
		description:
			'Quarterly grid (322 quarters, 1946 Q1–2026 Q2) with the same structure and minimum-speech rule as annual.json.',
		key_fields: ['periods', 'corpus', 'sufficient', 'minimum_speeches', 'terms']
	},
	{
		id: 'series_monthly',
		path: 'data/series/monthly.json',
		url: dataUrl('series/monthly.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '04_series.py',
		description:
			'Monthly counts and rates on a year-by-month grid, noting months outside the recorded span.',
		key_fields: ['periods', 'corpus', 'record', 'coverage', 'terms']
	},
	{
		id: 'series_breakdowns',
		path: 'data/series/breakdowns.json',
		url: dataUrl('series/breakdowns.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '04_series.py',
		description:
			'Annual breakdowns by speaker group (P5, E10, Non-member state, UN, Non-state) and region.',
		key_fields: ['groups', 'regions', 'minimum_speeches']
	},
	{
		id: 'series_change_points',
		path: 'data/series/change_points.json',
		url: dataUrl('series/change_points.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '04_series.py',
		description:
			'Permutation-tested rate splits (binomial speech share and Poisson word rate) with meeting-block null.',
		key_fields: ['inference', 'parameters', 'terms']
	},
	{
		id: 'series_events',
		path: 'data/series/events.json',
		url: dataUrl('series/events.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '04_series.py',
		description:
			'Curated historical reference dates plotted for context beside the time series (not causal evidence).',
		key_fields: ['events']
	},
	{
		id: 'kwic_index',
		path: 'data/kwic/index.json',
		url: dataUrl('kwic/index.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '08_kwic.py',
		description:
			'Index of all 28 lexicon terms, their regex patterns, occurrence counts, speech counts, and long-sentence diagnostics.',
		key_fields: ['terms']
	},
	{
		id: 'kwic_term',
		path: 'data/kwic/{term}.json',
		url: dataUrl('kwic/{term}.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '08_kwic.py',
		description:
			'Concordance lines for one lexicon term (for example data/kwic/genocide.json holds all 8,611 occurrences of g[eé]nocid*).',
		key_fields: [
			'id',
			'spv',
			'date',
			'country',
			'group',
			'type',
			'agenda',
			'start',
			'end',
			'left',
			'kw',
			'right',
			'sent'
		],
		join_keys: ['id (speech_id#ordinal)', 'spv'],
		caveat:
			'Sentence splitting can miss boundaries in scanned transcripts; read the full speech via data/speeches/{basename}.json.gz before quoting.'
	},
	{
		id: 'meetings',
		path: 'data/meetings.json',
		url: dataUrl('meetings.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '09_export_speeches.py',
		description:
			'Index of all 9,919 meetings with speeches, linking meeting symbols (S/PV.*) to speech file basenames.',
		key_fields: [
			'basename',
			'spv',
			'date',
			'year',
			'topic',
			'region',
			'agenda',
			'speeches',
			'delegations',
			'terms',
			'occurrences'
		],
		join_keys: ['basename', 'spv']
	},
	{
		id: 'scopes',
		path: 'data/scopes.json',
		url: dataUrl('scopes.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '09_export_speeches.py',
		description: 'Definitions and totals of the three reading sets (word, vocabulary, and debate).',
		key_fields: ['scopes']
	},
	{
		id: 'speech_meeting',
		path: 'data/speeches/{basename}.json.gz',
		url: dataUrl('speeches/{basename}.json.gz'),
		format: 'json.gz',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '09_export_speeches.py',
		description:
			'Gzipped full verbatim record for one meeting (for example SC07155-01.json.gz), containing every speech text and lexicon hit offsets.',
		key_fields: [
			'basename',
			'spv',
			'date',
			'agenda',
			'speeches[].id',
			'speeches[].speaker',
			'speeches[].country',
			'speeches[].text',
			'speeches[].hits'
		],
		join_keys: ['basename (first 10 chars of speech id)', 'speeches[].id'],
		caveat:
			'Speech text is the English UN verbatim record (CC0 1.0), including UN translations of speeches delivered in other languages.'
	},
	{
		id: 'countries',
		path: 'data/countries/countries.json',
		url: dataUrl('countries/countries.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '11_countries.py',
		description:
			'Speaker affiliation totals, genocide speech shares, Wilson intervals, and Council membership breakdowns.',
		key_fields: ['countries', 'minimum_speeches'],
		caveat:
			'Affiliations reflect the source dataset’s labels and do not represent timeless national positions.'
	},
	{
		id: 'speaker_keyness',
		path: 'data/countries/speaker_keyness.json',
		url: dataUrl('countries/speaker_keyness.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '12_speaker_keyness.py',
		description:
			'Matched vocabulary keyness per delegation, comparing speeches on the same year, agenda, and speaker group.',
		key_fields: ['speakers']
	},
	{
		id: 'actor_year',
		path: 'data/actor_year/actor_year.csv',
		url: dataUrl('actor_year/actor_year.csv'),
		format: 'csv',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '20_actor_year.py',
		description:
			'Annual table per source affiliation (`country_org`), year, speech total, and genocide occurrence count.',
		key_fields: ['country_org', 'year', 'measure', 'speeches', 'occurrences']
	},
	{
		id: 'lexical_collocates',
		path: 'data/lexical/collocates.json',
		url: dataUrl('lexical/collocates.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '05_lexical.py',
		description: 'Collocates around lexicon terms ranked by logDice and G² with dispersion (DP).',
		key_fields: ['terms']
	},
	{
		id: 'lexical_keyness',
		path: 'data/lexical/keyness.json',
		url: dataUrl('lexical/keyness.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '05_lexical.py',
		description:
			'Matched and whole-corpus keyness vocabulary comparing genocide speeches with non-genocide controls.',
		key_fields: ['matched_on', 'target_speeches', 'control_speeches', 'words']
	},
	{
		id: 'lexical_network',
		path: 'data/lexical/network.json',
		url: dataUrl('lexical/network.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '05_lexical.py',
		description: 'Speech-level co-occurrence network (nPMI) across the 28 lexicon terms.',
		key_fields: ['nodes', 'edges']
	},
	{
		id: 'frames',
		path: 'data/frames/frames.json',
		url: dataUrl('frames/frames.json'),
		format: 'json',
		epistemic_layer: 'computed_from_record',
		validated: true,
		produced_by: '17_frames.py',
		description: 'Rule-based grammatical constructions surrounding genocide matches.',
		key_fields: ['frames']
	},
	{
		id: 'usage_summary',
		path: 'data/usage/usage.json',
		url: dataUrl('usage/usage.json'),
		format: 'json',
		epistemic_layer: 'model_derived_unvalidated',
		validated: false,
		produced_by: '15_usage.py',
		description:
			'Aggregated LLM classifications of referent, speaker position, and rhetorical function across all 8,611 occurrences of genocide (Qwen3.8-27B primary run; Gemma-4-31B comparison run).',
		key_fields: ['meta', 'gold', 'referents', 'positions', 'actors'],
		caveat:
			'UNVALIDATED PREVIEW. Human gold coding is pending; treat these figures as an exploratory way into passages, never as verified findings.'
	},
	{
		id: 'usage_occurrences',
		path: 'data/usage/occurrences.json',
		url: dataUrl('usage/occurrences.json'),
		format: 'json',
		epistemic_layer: 'model_derived_unvalidated',
		validated: false,
		produced_by: '15_usage.py',
		description:
			'Per-occurrence LLM labels, supporting evidence quotes, rationales, and comparison-model disagreements (`contested`, `alt`).',
		key_fields: [
			'id',
			'occurrence_id',
			'verdict',
			'quotation',
			'concrete_case',
			'speaker_position',
			'function',
			'referent',
			'evidence_quote',
			'evidence_valid',
			'rationale',
			'contested',
			'alt'
		],
		join_keys: ['id (joins kwic/genocide.json)', 'occurrence_id (joins gold sample)'],
		caveat:
			'UNVALIDATED PREVIEW. Exclude rows with evidence_valid=false from discourse aggregates, and always surface contested/alt model disagreements.'
	},
	{
		id: 'usage_referents',
		path: 'data/usage/referents.json',
		url: dataUrl('usage/referents.json'),
		format: 'json',
		epistemic_layer: 'model_derived_unvalidated',
		validated: false,
		produced_by: 'export_web.py',
		description: 'Compact map from concordance line id to model-assigned referent.',
		key_fields: ['meta', 'placements'],
		join_keys: ['id'],
		caveat: 'UNVALIDATED PREVIEW derived from usage/occurrences.json.'
	},
	{
		id: 'semantic_map',
		path: 'data/semantic/map.json',
		url: dataUrl('semantic/map.json'),
		format: 'json',
		epistemic_layer: 'experimental_embedding',
		validated: false,
		produced_by: '21_semantic_map.py',
		description: 'Two-dimensional UMAP projection of speech embeddings across the corpus.',
		key_fields: ['meta', 'points'],
		caveat:
			'EXPERIMENTAL. UMAP compresses distances and has no substantive axis units; proximity is not diplomatic alignment.'
	}
] as const;

export const EPISTEMIC_RULES: readonly string[] = [
	'Always label whether a figure comes from a computed_from_record endpoint or a model_derived_unvalidated / experimental_embedding endpoint.',
	'Never present counts as total spoken occurrences: the corpus is the English UN verbatim record (including UN translations), omits informal consultations and 717 closed/speechless meetings, and scanning errors make every count a minimum.',
	'Never present usage/* LLM labels (verdict, referent, speaker_position, accused_actor, victim_group) as verified findings while validated is false; report model disagreement fields (contested, alt) explicitly.',
	'Trace every textual claim back to its meeting symbol (spv) and full speech in data/speeches/{basename}.json.gz rather than relying on concordance snippets or LLM rationales alone.',
	'Never infer legal determinations of genocide or timeless national positions from delegation vocabulary counts.'
];

export const DATA_CATALOG = {
	schema_version: '1.0',
	name: SITE_NAME,
	site_url: canonicalUrl('/'),
	repository: REPOSITORY,
	documentation: {
		llms_txt: canonicalUrl('/llms.txt'),
		methods_page: canonicalUrl('/methods/'),
		mcp_guide: `${REPOSITORY}/blob/main/docs/MCP.md`,
		datasheet: `${REPOSITORY}/blob/main/docs/DATASHEET.md`,
		claims: `${REPOSITORY}/blob/main/docs/CLAIMS.md`,
		corpus: `${REPOSITORY}/blob/main/docs/CORPUS.md`,
		mcp_starter: `${REPOSITORY}/tree/main/examples/mcp-starter`
	},
	corpus: {
		title: 'The UNSC Meetings and Speeches',
		authors: 'Takuto Sakamoto & Takahisa Matsuoka',
		version: '6.0',
		doi: '10.7910/DVN/CKPTRB',
		licence: 'CC0-1.0',
		coverage: { start: '1946-01-17', end: '2026-06-23' },
		speeches: 182684,
		meetings_with_speeches: 9919,
		analytical_words: 92547139,
		genocide_lexicon_version: 8,
		genocide_speeches: 4576,
		genocide_occurrences: 8611
	},
	licence: {
		code: 'MIT',
		derived_data: 'CC-BY-4.0',
		speech_text: 'CC0-1.0'
	},
	epistemic_rules: EPISTEMIC_RULES,
	endpoints: DATA_ENDPOINTS
} as const;

export function dataCatalogJson(): string {
	return `${JSON.stringify(DATA_CATALOG, null, 2)}\n`;
}

export function llmsText(): string {
	return [
		`# ${SITE_NAME}`,
		'',
		'> Corpus study of how the word *genocide* and 27 neighbouring terms appear in public United Nations Security Council verbatim records (1946–2026), built on Sakamoto & Matsuoka v6.0 (CC0 1.0, doi:10.7910/DVN/CKPTRB).',
		'',
		'## Machine-readable entry points',
		'',
		`- Data catalogue (all endpoints, schemas, join keys, and epistemic status): ${canonicalUrl('/data-catalog.json')}`,
		`- Build manifest (timestamps, git commit, SHA-256 checksums): ${dataUrl('manifest.json')}`,
		`- MCP integration guide & starter server: ${REPOSITORY}/blob/main/docs/MCP.md`,
		`- Starter Python MCP server + Agent Skill (\`SKILL.md\`): ${REPOSITORY}/tree/main/examples/mcp-starter`,
		'',
		'## Key static data endpoints',
		'',
		`- Annual series (computed): ${dataUrl('series/annual.json')}`,
		`- Lexicon index (computed): ${dataUrl('kwic/index.json')}`,
		`- Genocide concordance, 8,611 occurrences (computed): ${dataUrl('kwic/genocide.json')}`,
		`- Meetings index, 9,919 meetings (computed): ${dataUrl('meetings.json')}`,
		`- Full verbatim meeting record (computed, gzipped JSON): ${dataUrl('speeches/{basename}.json.gz')}`,
		`- Delegation totals and rates (computed): ${dataUrl('countries/countries.json')}`,
		`- Annual actor table CSV (computed): ${dataUrl('actor_year/actor_year.csv')}`,
		`- LLM occurrence classifications — UNVALIDATED PREVIEW (model-derived): ${dataUrl('usage/occurrences.json')}`,
		`- LLM usage aggregates — UNVALIDATED PREVIEW (model-derived): ${dataUrl('usage/usage.json')}`,
		'',
		'## Epistemic rules for AI agents and MCP servers',
		'',
		...EPISTEMIC_RULES.map((rule) => `- ${rule}`),
		'',
		'## Documentation',
		'',
		`- Methods page: ${canonicalUrl('/methods/')}`,
		`- Claims and validation status: ${REPOSITORY}/blob/main/docs/CLAIMS.md`,
		`- Derived dataset datasheet: ${REPOSITORY}/blob/main/docs/DATASHEET.md`,
		`- Source corpus documentation: ${REPOSITORY}/blob/main/docs/CORPUS.md`,
		`- Citation metadata: ${REPOSITORY}/blob/main/CITATION.cff`,
		''
	].join('\n');
}
