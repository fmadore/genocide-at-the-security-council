/**
 * The shapes the Python pipeline writes.
 *
 * These are hand-kept in step with `scripts/`, and the file names below say
 * which script owns each one. If a field here is wrong the failure is a blank
 * chart, not an error, so keep the two in sync deliberately.
 */

export interface BaseMeta {
	script: string;
	generated: string;
	/** Stable across regeneration time and Git dirtiness; present on newly written artifacts. */
	analysis_hash?: string;
	[key: string]: unknown;
}

/** Provenance for an artifact whose analytical meaning depends on the lexicon. */
export interface LexiconMeta extends BaseMeta {
	lexicon_version: number;
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
	meta: LexiconMeta;
	freq: 'year' | 'quarter';
	periods: (number | string)[];
	corpus: { speeches: number[]; tokens: number[]; meetings: number[] };
	terms: Record<string, Measure>;
	registers: Record<string, Measure>;
	sets: Record<string, Measure>;
}

/**
 * A measure at month resolution, where a rate can be withheld.
 *
 * Deliberately not `Measure`. The annual and quarterly series never need a null
 * — the thinnest year in the corpus holds a thousand speeches — so widening
 * that type would make every consumer of a figure that cannot have a gap handle
 * one. A month can hold four speeches, and 53 of the 384 hold too few to divide
 * by, so here the null is part of the contract rather than an accident.
 */
export interface MonthlyMeasure {
	speeches: number[];
	/** Null wherever `MonthlySeries.sufficient` is false. Never `NaN`. */
	speech_rate: (number | null)[];
	occurrences?: number[];
	token_rate?: (number | null)[];
	tier?: string;
	register?: string;
	terms?: string[];
	members?: string[];
}

/** One agenda item behind a calendar month's term-bearing speeches. */
export interface AgendaItem {
	item: string;
	speeches: number;
	/** Of that month's term-bearing speeches — not of everything said in it. */
	share: number;
}

interface CalendarReading {
	held: number[];
	tokens: number[];
	speeches: number[];
	speech_rate: (number | null)[];
	sufficient: boolean[];
	occurrences?: number[];
	token_rate?: (number | null)[];
}

export interface CalendarMeasure extends CalendarReading {
	kind: 'terms' | 'registers' | 'sets';
	tier?: string;
	register?: string;
	terms?: string[];
	members?: string[];
	/** The same twelve figures with the artefact's control years dropped. */
	excluding: CalendarReading;
	/** Twelve entries, largest item first. The confound, per month. */
	agenda: AgendaItem[][];
}

/**
 * The twelve calendar months pooled across every year.
 *
 * A second figure beside the grid, never a margin of it: pooling thirty-two
 * Junes gives a denominator no single cell has, so the two must not share a
 * colour bar. The artefact says so in `rule`, and the interface prints that
 * string rather than paraphrasing it.
 */
export interface MonthOfYear {
	months: number[];
	rule: string;
	excluded_years: number[];
	excluding_rule: string;
	agenda_column: string;
	agenda_rule: string;
	measures: Record<string, CalendarMeasure>;
}

export interface MonthlySeries {
	meta: LexiconMeta;
	freq: 'month';
	/** `YYYY-MM`, the complete grid: `years.length * 12` of them, in order. */
	periods: string[];
	corpus: { speeches: number[]; tokens: number[]; meetings: number[] };
	/** Per period, whether its denominator clears `minimum_speeches`. */
	sufficient: boolean[];
	terms: Record<string, MonthlyMeasure>;
	registers: Record<string, MonthlyMeasure>;
	sets: Record<string, MonthlyMeasure>;
	years: number[];
	months: number[];
	minimum_speeches: number;
	minimum_speeches_rule: string;
	informative_zero_minimum: number;
	corpus_speech_prevalence: number;
	coverage: {
		months: number;
		months_observed: number;
		months_at_minimum: number;
		speeches: number;
		speeches_at_minimum: number;
		share_at_minimum: number;
	};
	month_of_year: MonthOfYear;
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
	meta: LexiconMeta;
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
	meta: LexiconMeta;
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
	meta: LexiconMeta;
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
	meta: LexiconMeta;
	widths: number[];
	nodes: Record<
		string,
		{ pattern: string; register: string; widths: Record<string, CollocateBlock> }
	>;
}

export interface SlicedCollocates {
	meta: LexiconMeta;
	term: string;
	width: number;
	minimum_speeches: number;
	by_period: Record<string, CollocateBlock>;
	by_speaker_group: Record<string, CollocateBlock>;
	by_country: Record<string, CollocateBlock>;
}

export interface Keyness {
	meta: LexiconMeta;
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
		/**
		 * Percentiles only. 12 writes the observed range beside these for its
		 * per-speaker tables, because that figure is printed next to one draw;
		 * this one is not, and 05 has not been re-run.
		 */
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
	meta: LexiconMeta;
	min_speeches: number;
	terms: { name: string; tier: string; register: string; speeches: number }[];
	edges: Edge[];
	by_period: Record<string, { terms: { name: string; speeches: number }[]; edges: Edge[] }>;
	suppressed_nested_edges: { source: string; target: string }[];
}

/* --- 08_kwic.py ---------------------------------------------------------- */

export interface KwicLine {
	/** `<speech filename without .txt>#<one-based occurrence ordinal>` */
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
	meta: LexiconMeta;
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
	meta: LexiconMeta;
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
	meta: LexiconMeta;
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
	meta: LexiconMeta;
	meetings: MeetingSummary[];
}

/* --- 11_countries.py ------------------------------------------------------ */

export interface CountryPeriod {
	key: string;
	label: string;
	first_year: number;
	last_year: number;
	speeches: number;
	tokens: number;
	speakers: number;
	/** Speakers in this period that clear `minimum_speeches`. The rest are null. */
	speakers_at_minimum: number;
	speeches_at_minimum: number;
}

export interface Speaker {
	country_org: string;
	entity_type: 'state' | 'igo' | 'ngo' | 'un' | 'civil_society' | 'academia' | 'company' | 'other';
	iso3: string | null;
	un_regional_group: string | null;
	/**
	 * `[latitude, longitude]`, the order `config/entities.csv` records and
	 * `11_countries.py` writes. MapLibre wants the opposite; `actors.ts` is the
	 * one place that flips it, so no component has to remember.
	 */
	centroid: [number, number] | null;
	/**
	 * "Is a state, has a code, and has a centroid" — not "has coordinates". The
	 * distinction is deliberate upstream: the UN Secretariat is among the largest
	 * speakers in the corpus and belongs on no globe.
	 */
	mappable: boolean;
	speeches: number;
	first_year: number;
	last_year: number;
}

export interface CountryMeasureRow {
	country_org: string;
	period: string;
	/** The speaker's own denominator: speeches it delivered in this period. */
	held: number;
	tokens: number;
	/** Speeches bearing the measure's terms. */
	speeches: number;
	/** Null whenever `sufficient` is false, so a withheld slice cannot be drawn. */
	speech_rate: number | null;
	sufficient: boolean;
	/**
	 * Absent on a set measure, and deliberately so: `atrocity_core` is a union of
	 * overlapping terms, so a speech saying both `genocide` and `war crimes`
	 * would be counted twice. `lib/series.py` withholds the count rather than
	 * summing the members, and these two fields are optional here so that a
	 * consumer has to decide what to show instead of reading a fabricated zero.
	 */
	occurrences?: number;
	token_rate?: number | null;
}

export interface CountryMeasure {
	/**
	 * `terms` for a single lexicon pattern, `sets` for a named group of them.
	 * The two carry different metadata, which is why the rest is optional: a
	 * term measure declares the `tier` and `register` its pattern sits in, and a
	 * set measure declares its `members` instead. Typing both as required would
	 * promise `atrocity_core.tier` a string it has never had.
	 */
	kind: 'terms' | 'sets';
	tier?: string;
	register?: string;
	/** The lexicon terms a set measure sums. Absent on a term measure. */
	members?: string[];
	rows: CountryMeasureRow[];
}

/** One row of a speaker's keyness table. `self_reference` is a mark, not a filter. */
export interface Keyword {
	word: string;
	/** Occurrences in the speaker's own matched speeches. */
	target: number;
	/** Occurrences in the control set, or in the rest of the corpus when unmatched. */
	reference: number;
	g2: number;
	log_ratio: number;
	/**
	 * True when the word appears in the speaker's own canonical name. Mechanical
	 * and therefore partial upstream — it catches `federation` and misses
	 * `french` — so a false here is not a guarantee, and nothing may filter on it.
	 */
	self_reference: boolean;
}

export interface SpeakerAgenda {
	held: number;
	items: number;
	top: { item: string; speeches: number; share: number }[];
	other: { speeches: number; share: number };
	/** Share of the speaker's speeches in its three commonest agenda items. */
	concentration: number;
}

export interface SpeakerKeynessRow {
	country_org: string;
	/** Target speeches that found a control. The comparison's real denominator. */
	pairs: number;
	/** The speaker's own speeches, whether or not they could be matched. */
	held: number;
	coverage: number;
	short_strata: number;
	shortfall: number;
	sufficient: boolean;
	/**
	 * Which gate closed: `pairs`, `coverage`, or both. Empty when published.
	 * Two different objections, and a view that reported one for the other would
	 * tell a reader something untrue.
	 */
	withheld_because: string[];
	/**
	 * Null — never absent — whenever `sufficient` is false. The artefact writes
	 * every key at every row so that a missing table and a measured zero cannot
	 * be confused downstream.
	 */
	target_tokens: number | null;
	control_tokens: number | null;
	keywords: Keyword[] | null;
	/** The same target against the whole corpus: what the matching improved on. */
	keywords_unmatched: Keyword[] | null;
	stability?: {
		repetitions: number;
		coverage_min: number;
		coverage_max: number;
		/**
		 * `low`/`high` are the observed range across the draws, and the figure
		 * prints those rather than the percentiles: at ten draws `p05` is
		 * interpolated above the smallest value, so a published draw that is the
		 * extreme of its own sample would sit outside a bracket beside it. The
		 * percentiles are kept because 05 reports the same pair for the
		 * whole-corpus keyness and the two should stay comparable.
		 */
		keyword_log_ratio: {
			word: string;
			median: number;
			low: number;
			high: number;
			p05: number;
			p95: number;
		}[];
	};
	agenda: SpeakerAgenda;
}

export interface SpeakerKeyness {
	meta: BaseMeta;
	matched_on: string[];
	minimum_pairs: number;
	minimum_pairs_rule: string;
	minimum_coverage: number;
	minimum_coverage_rule: string;
	control_rule: string;
	unmatched_rule: string;
	reading_rule: string;
	self_reference_rule: string;
	seed: number;
	repetitions: number;
	limit: number;
	speakers_total: number;
	speakers_considered: number;
	speakers_published: number;
	speakers_withheld: number;
	speakers: SpeakerKeynessRow[];
}

/**
 * How one speaker's own speeches divide across the five speaker groups.
 *
 * Counts and `seated_share` are written at every denominator, unlike the rates
 * in `measures`, and the asymmetry is deliberate rather than an oversight: a
 * share of a speaker's own known speeches is a fact about the record, not an
 * estimate from a sample. "Of the twelve speeches it gave, twelve were from a
 * seat" is exactly true at n=12; "33% of its speeches used the word" over three
 * speeches is not. The minimum guards the second and has nothing to say about
 * the first.
 */
export interface StandingRow {
	country_org: string;
	period: string;
	/** The speaker's own denominator. The five group counts sum to it. */
	held: number;
	seated: number;
	seated_share: number | null;
	/** Every declared group, including the zeros. An absent key would mean two things. */
	groups: Record<string, number>;
}

export interface Standing {
	groups: string[];
	/** The Charter's two kinds of membership. The other three are not one thing. */
	seated_groups: string[];
	seated_rule: string;
	membership_rule: string;
	rows: StandingRow[];
}

export interface Countries {
	meta: LexiconMeta;
	/** Below this many speeches in a period, a speaker's rates are withheld. */
	minimum_speeches: number;
	minimum_speeches_rule: string;
	rate_per_tokens: number;
	centroid_rule: string;
	/** ISO3 → the speakers sharing it. Never key a drawing on the code alone. */
	iso3_collisions: Record<string, string[]>;
	periods: CountryPeriod[];
	countries: Speaker[];
	standing: Standing;
	measures: Record<string, CountryMeasure>;
}
