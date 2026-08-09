/**
 * The shapes the Python pipeline writes.
 *
 * These are hand-kept in step with `scripts/`, and the file names below say
 * which script owns each one. If a field here is wrong the failure is a blank
 * chart, not an error, so keep the two in sync deliberately.
 */

export interface Meta {
	script: string;
	generated: string;
	lexicon_version: number;
	[key: string]: unknown;
}

/* --- 04_series.py -------------------------------------------------------- */

export interface Measure {
	speeches: number[];
	speech_rate: number[];
	/** Absent for sets: a union has no occurrence count of its own. */
	occurrences?: number[];
	token_rate?: number[];
	tier?: string;
	register?: string;
	terms?: string[];
	members?: string[];
}

export interface AnnualSeries {
	meta: Meta;
	freq: 'year' | 'quarter';
	periods: (number | string)[];
	corpus: { speeches: number[]; tokens: number[]; meetings: number[] };
	terms: Record<string, Measure>;
	registers: Record<string, Measure>;
	sets: Record<string, Measure>;
}

export interface BreakdownRow {
	period: number | string;
	category: string;
	held: number;
	speeches: number;
	speech_rate: number;
	occurrences?: number;
	token_rate?: number;
}

export interface Breakdowns {
	meta: Meta;
	freq: string;
	measures: Record<string, Record<string, { categories: string[]; rows: BreakdownRow[] }>>;
}

export interface Break {
	index: number;
	label: string;
	gain: number;
	p_value: number;
	before: number;
	after: number;
	ratio: number;
	interval_start: number;
	interval_stop: number;
}

export interface RateBreak {
	index: number;
	label: string;
	family: 'binomial' | 'poisson';
	gain: number;
	p_value: number;
	alpha: number;
	accepted: boolean;
	before: number;
	before_ci95: [number, number];
	after: number;
	after_ci95: [number, number];
	ratio: number | null;
	counts: [number, number];
	exposure: [number, number];
}

export interface ChangePoints {
	meta: Meta;
	method: string;
	parameters: Record<string, number>;
	caveat: string;
	series: Record<string, Record<string, Break[]>>;
	inference: {
		method: string;
		familywise_alpha: number;
		per_test_alpha: number;
		correction: string;
		trials: number;
		caveat: string;
		series: Record<string, Record<string, RateBreak | null>>;
	};
}

export type EventKind =
	'atrocity' | 'conflict' | 'council' | 'institutional' | 'legal' | 'contested';

export interface CouncilEvent {
	date: string;
	year: number;
	label: string;
	kind: EventKind;
	source: string;
	source_url: string;
	note: string;
}

export interface Events {
	meta: Meta;
	events: CouncilEvent[];
}

/* --- 05_lexical.py ------------------------------------------------------- */

export interface Word {
	word: string;
	target: number;
	reference: number;
	g2: number;
	log_ratio: number;
}

export interface CollocateBlock {
	occurrences: number;
	window_tokens: number;
	collocates: Word[];
	speeches?: number;
}

export interface Collocates {
	meta: Meta;
	widths: number[];
	nodes: Record<
		string,
		{ pattern: string; register: string; widths: Record<string, CollocateBlock> }
	>;
}

export interface SlicedCollocates {
	meta: Meta;
	term: string;
	width: number;
	minimum_speeches: number;
	by_period: Record<string, CollocateBlock>;
	by_speaker_group: Record<string, CollocateBlock>;
	by_country: Record<string, CollocateBlock>;
}

export interface Keyness {
	meta: Meta;
	term: string;
	matched_on: string[];
	seed: number;
	target_speeches: number;
	eligible_target_speeches: number;
	control_speeches: number;
	coverage: number;
	target_tokens: number;
	control_tokens: number;
	short_strata: { key: string[]; wanted: number; found: number }[];
	keywords: Word[];
	keywords_unmatched: Word[];
	stability: {
		repetitions: number;
		seed_first: number;
		coverage_min: number;
		coverage_max: number;
		keyword_log_ratio: { word: string; median: number; p05: number; p95: number }[];
	};
}

export interface Edge {
	source: string;
	target: string;
	speeches: number;
	pmi: number;
	npmi: number;
}

export interface Network {
	meta: Meta;
	min_speeches: number;
	terms: { name: string; tier: string; register: string; speeches: number }[];
	edges: Edge[];
	by_period: Record<string, { terms: { name: string; speeches: number }[]; edges: Edge[] }>;
	suppressed_nested_edges: { source: string; target: string }[];
}

/* --- 08_kwic.py ---------------------------------------------------------- */

export interface KwicLine {
	/** `<speech filename without .txt>#<occurrence ordinal>` */
	id: string;
	spv: string;
	date: string;
	country: string;
	iso3: string | null;
	group: string;
	type: string;
	agenda: string;
	/** Offsets into the whole speech text, form of address included. */
	start: number;
	end: number;
	left: string;
	kw: string;
	right: string;
	sent: string;
}

export interface KwicFile {
	meta: Meta;
	term: string;
	pattern: string;
	tier: string;
	register: string;
	count: number;
	lines: KwicLine[];
}

export interface KwicIndexEntry {
	term: string;
	tier: string;
	register: string;
	file: string;
	count: number;
	speeches: number;
	bytes: number;
	sentence_median: number;
	sentence_p95: number;
	sentence_max: number;
	long_sentences: number;
}

export interface KwicIndex {
	meta: Meta;
	terms: KwicIndexEntry[];
}

/* --- 09_export_speeches.py ----------------------------------------------- */

export interface Speech {
	id: string;
	n: number;
	speaker: string | null;
	role: string | null;
	country: string;
	iso3: string | null;
	entity_type: string;
	group: string;
	type: string;
	language: string | null;
	tokens: number;
	/** Where the speech proper begins, past its opening form of address. */
	body_start: number;
	text: string;
	/** term → whole-text `[start, end]` spans. Absent terms are omitted. */
	hits: Record<string, [number, number][]>;
}

export interface Meeting {
	meta: Meta;
	basename: string;
	spv: string;
	date: string;
	year: number;
	topic: string;
	region: string;
	agenda: string;
	speeches: Speech[];
}

export interface MeetingSummary {
	basename: string;
	spv: string;
	date: string;
	year: number;
	topic: string;
	region: string;
	agenda: string;
	speeches: number;
	terms: string[];
	occurrences: number;
}

export interface MeetingIndex {
	meta: Meta;
	meetings: MeetingSummary[];
}
