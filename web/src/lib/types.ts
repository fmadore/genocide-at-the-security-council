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
	/**
	 * Wilson 95% bounds of `speech_rate`, period by period, written by
	 * `lib/series.py::measure` beside the rate itself. A share of 60 speeches
	 * and a share of 6,000 are not the same number, and the band is how a
	 * chart says so.
	 */
	speech_rate_low: number[];
	speech_rate_high: number[];
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
	corpus: { speeches: number[]; words: number[]; meetings: number[] };
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
	/** Null exactly where `speech_rate` is: one withholding rule blanks all three. */
	speech_rate_low: (number | null)[];
	speech_rate_high: (number | null)[];
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
	words: number[];
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
	corpus: { speeches: number[]; words: number[]; meetings: number[] };
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
	/** Wilson 95% bounds of `speech_rate` over this row's own `held`. */
	speech_rate_low: number;
	speech_rate_high: number;
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

/**
 * What the rate test's p-value was calibrated against. `meeting_block_permutation`
 * moves whole meetings between years, so a debate that used the word two
 * hundred times is one draw; `independent_parametric` is the older null in
 * which every speech is an independent coin flip, kept beside the block
 * p-value so the size of the clustering is visible.
 */
export type RateNull = 'meeting_block_permutation' | 'independent_parametric';

export interface RateBreak {
	index: number;
	label: string;
	family: 'binomial' | 'poisson';
	gain: number;
	null: RateNull;
	/** Meetings the block null permuted; null when the independent null was used. */
	blocks: number | null;
	/** Under `null`. `accepted` follows this one. */
	p_value: number;
	/** Under the independent-speech null, whatever `null` says. */
	p_value_independent: number;
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
		null: RateNull;
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

/**
 * One row of a collocate or keyword table.
 *
 * G² is a floor the row cleared, never its rank: tables are ordered by effect
 * (`log_dice` for collocates, `log_ratio` for keywords). The three dispersion
 * fields say how evenly the word is spread over the speeches the table was
 * cut from — `documents` it appears in, distinct `meetings` (null only where
 * the pipeline had no meeting to count), and Gries's DP, 0 for a word spread
 * as the text is and 1 for one confined to a vanishing corner of it.
 */
export interface Word {
	word: string;
	target: number;
	reference: number;
	g2: number;
	log_ratio: number;
	/** logDice (Rychlý 2008), collocate tables only; 14 is a pair never seen apart. */
	log_dice?: number;
	documents: number;
	meetings: number | null;
	dp: number;
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
	/** Pairs the graph never draws: nested, or one term matching another's example. */
	suppressed_nested_edges: { source: string; target: string; reason?: string }[];
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
	words: number;
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
	words: number;
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
	words: number;
	/** Speeches bearing the measure's terms. */
	speeches: number;
	/** Null whenever `sufficient` is false, so a withheld slice cannot be drawn. */
	speech_rate: number | null;
	/** Wilson 95% bounds of `speech_rate`; null exactly when the rate is. */
	speech_rate_low: number | null;
	speech_rate_high: number | null;
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
	/** Dispersion over the speaker's matched speeches; see `Word`. */
	documents: number;
	meetings: number | null;
	dp: number;
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

/* --- 14_llm_annotate.py → 15_usage.py ------------------------------------- *
 *
 * The experimental layer, and the one place in this file where the shapes below
 * were not written by a person. A model read every occurrence of `genocide` and
 * said two things about each: which genocide it refers to, and what the speaker
 * is doing with the word. 15 aggregates those labels; nothing upstream of it
 * changes, and no figure elsewhere on this site reads any of it.
 *
 * `meta` is `BaseMeta` rather than `LexiconMeta` deliberately. The occurrence
 * identifiers are numbered by the lexicon, so a version is analytically
 * meaningful here — but the interface reads provenance through
 * `provenanceOf()`, which is total, and typing a field as present that the
 * pipeline may not write is the failure this file's own header warns about.
 */

/**
 * What a speaker is doing with the word, from the codebook's controlled list.
 *
 * Seven values, exhaustive and mutually exclusive, and the order below is the
 * order the codebook states them in — which is also the order the stacked bar
 * draws, so a reader comparing two delegations reads the same bands in the same
 * places. `not_applicable` belongs to false positives alone.
 */
export type Stance =
	| 'asserts'
	| 'attributes_or_reports'
	| 'rejects_or_denies'
	| 'hypothetical_or_conditional'
	| 'neutral_legal_reference'
	| 'unclear'
	| 'not_applicable';

/** Every stance, always. An absent key and a measured zero cannot be confused. */
export type StanceCounts = Record<Stance, number>;

/** What produced the labels, in enough detail to run it again or to reject it. */
export interface UsageModel {
	/** The exact API model identifier. Shown in mono, never paraphrased. */
	id: string;
	run_id: string;
	run_date: string;
	prompt_version: string;
	/** 64 hex characters over the prompt text below. A changed prompt is a new run. */
	prompt_sha256: string;
	reasoning_effort: string;
	requests: number;
	occurrences_total: number;
	occurrences_annotated: number;
	parse_failures: number;
	evidence_invalid: number;
	/** Occurrences the model declined to place, by the field it declined on. */
	abstention: { verdict_uncertain: number; referent_unclear: number; stance_unclear: number };
	tokens: { input: number; output: number };
}

/**
 * One entry of the controlled referent list.
 *
 * `iso3` and `years` are always strings and are often empty: they are
 * documentation on the list rather than coding, and the Holocaust has no
 * country code. `kind` is `case`, `historical` or `meta` in the list as
 * published; only `meta` is load-bearing here, because a meta referent is not a
 * genocide but a way of talking about the category, and the matrix groups those
 * columns apart rather than ranking them beside Rwanda.
 */
export interface UsageReferent {
	id: string;
	label: string;
	kind: string;
	iso3: string;
	years: string;
	/** Assigned occurrences carrying this referent, across every speaker. */
	occurrences: number;
}

/**
 * One speaker, with the three denominators this view distinguishes.
 *
 * `occurrences` is every match; `eligible` is those the model judged a real use
 * of the word with a quotable evidence span behind it; `assigned` is the
 * eligible ones it could place on a concrete referent. The matrix counts
 * `assigned`, the stance profile counts `eligible`, and the gap between the
 * three is stated rather than closed.
 */
export interface UsageActor {
	country_org: string;
	/** Null for the organisations, which hold no country code. */
	iso3: string | null;
	group: string;
	entity_type: string;
	occurrences: number;
	eligible: number;
	assigned: number;
	/** Whether `eligible` clears `minimum_occurrences`. Shares are withheld below it. */
	sufficient: boolean;
}

/** One filled square of the actor × referent table. Sparse: written only above zero. */
export interface UsageMatrixCell {
	/** The speaker's `country_org`, which is what every table here is keyed on. */
	actor: string;
	/** A `UsageReferent.id`. */
	referent: string;
	count: number;
	/** The same occurrences divided by stance. Sums to `count`. */
	stances: StanceCounts;
}

/** One speaker's whole stance profile, over its eligible occurrences. */
export interface UsageStanceRow {
	actor: string;
	eligible: number;
	sufficient: boolean;
	stances: StanceCounts;
	/** Null — never absent — wherever `sufficient` is false. */
	share_rejects: number | null;
}

/**
 * The three moments the diffusion figure counts, in the order they rank.
 *
 * They are not three kinds of occurrence but three *firsts*, per delegation and
 * per referent: the first time it placed the word on that genocide at all, the
 * first time it asserted the characterisation, and the first time it refused the
 * word for it. One occurrence can be two of them — a delegation whose first
 * placed use already asserts crosses `mention` and `asserts` on the same line —
 * which is why the rank exists: it settles the order of two events a date and an
 * identifier cannot separate.
 */
export type UsageMilestone = 'mention' | 'asserts' | 'rejects_or_denies';

/** One delegation's first crossing of one milestone, for one referent. */
export interface UsageDiffusionEvent {
	/** `YYYY-MM-DD`, the meeting's date. */
	date: string;
	/** The speaker's `country_org`, as everywhere else in this layer. */
	actor: string;
	milestone: UsageMilestone;
	/**
	 * The stance of that first occurrence. Fixed under the last two milestones
	 * and any of the seven under `mention`, which is what makes it worth carrying
	 * — a first mention that is a rejection is a different fact from one that is
	 * a neutral legal reference.
	 */
	stance: string;
	/** `<speech>#<ordinal>` — joins `KwicLine.id`. The locator for the event. */
	id: string;
}

/** One referent's whole chronology. Only referents with at least one event appear. */
export interface UsageDiffusionReferent {
	/** A `UsageReferent.id`. */
	id: string;
	/** Sorted by date, then identifier, then milestone rank. */
	events: UsageDiffusionEvent[];
}

/**
 * When each delegation first said it, first asserted it, first refused it.
 *
 * The milestones are declared by the artefact rather than assumed by the
 * interface: a later run could count a fourth, and a figure that had the three
 * written into it would draw two of them and lose the third without saying so.
 */
export interface UsageDiffusion {
	milestones: UsageMilestone[];
	referents: UsageDiffusionReferent[];
}

/**
 * One field two runs were compared on, over the occurrences both of them read.
 *
 * `observed` and `kappa` are the statistics `UsageAgreement` carries between the
 * two human coders, computed upstream by the same functions so that the two
 * tables can be read against each other — and null on the same degenerate
 * inputs, because "kappa could not be computed on one category" and "the two
 * runs agreed by chance" are different findings. `contested` is the count of
 * compared occurrences the two labelled differently, which is the number a
 * reader can go and look at.
 */
export interface UsageComparisonField {
	field: string;
	/** Occurrences both runs reached. The same for every field of one comparison. */
	n: number;
	observed: number | null;
	kappa: number | null;
	contested: number;
}

/**
 * A second model's answers to the same questionnaire — or the empty block that
 * says none was bought.
 *
 * The keys are the same in both states: under `none` the strings are empty, the
 * counts are zero and `fields` is an empty array, the idiom `UsageGold` uses to
 * leave its own tables empty until they can be computed. Nothing downstream has
 * to special-case an absence that is the ordinary case.
 *
 * **What agreement here is.** Two models agreeing measures the stability of a
 * label across instruments and never its accuracy: both can be wrong about a
 * passage in the same way, and neither has been checked against anything. The
 * human gold sample is the only calibration in this artefact, and every surface
 * that prints one of these numbers has to say so.
 *
 * The counts describing the *run* — `occurrences_annotated`, `abstention`,
 * `evidence_invalid` — are over all of its rows. The ones describing the
 * *comparison* are over `overlap` alone, because a run that annotated half the
 * corpus and agreed on all of it is not the finding a run that annotated all of
 * it and agreed on half is.
 */
export interface UsageComparison {
	state: 'computed' | 'none';
	run_id: string;
	/** The comparison model's own API identifier. Empty under `none`. */
	model: string;
	run_date: string;
	reasoning_effort: string;
	/**
	 * The prompt the comparison was made with.
	 *
	 * Equal to the published run's, byte for byte: a second opinion made from
	 * different instructions is an answer to a different question, and 15 refuses
	 * to publish one. Carried anyway so the page can state it rather than assume it.
	 */
	prompt_sha256: string;
	occurrences_annotated: number;
	/** Occurrences carrying a label from both runs. Every statistic below is over these. */
	overlap: number;
	evidence_invalid: number;
	abstention: { verdict_uncertain: number; referent_unclear: number; stance_unclear: number };
	/** The four single-label fields. Empty where the two runs overlap nowhere. */
	fields: UsageComparisonField[];
	/** `function` is multi-label and carries no kappa; this is its mean set overlap. */
	function_jaccard: number | null;
	function_contested: number;
	/** Compared occurrences the two runs differ on in at least one of the five fields. */
	contested_any: number;
}

/** Agreement between two coders on one field, or null while it cannot be computed. */
export interface UsageAgreement {
	field: string;
	observed: number;
	kappa: number | null;
	n: number;
}

/** How the model did against the human labels for one class of one field. */
export interface UsageClassScore {
	label: string;
	precision: number;
	recall: number;
	f1: number;
	support: number;
}

export interface UsageModelScore {
	field: string;
	n: number;
	accuracy: number;
	macro_f1: number | null;
	abstention_rate: number;
	classes: UsageClassScore[];
}

/**
 * The human evaluation set, and its honest state.
 *
 * The arrays are empty until there is something to put in them, and the state
 * says which of the three situations that is. An empty `human_agreement` under
 * `not_started` means nobody has coded yet; the interface says so rather than
 * drawing an empty table that reads as a measured zero.
 */
export interface UsageGold {
	sample_size: number;
	unique_occurrences: number;
	coders: { coder: string; rows: number }[];
	double_coded: number;
	adjudicated: number;
	human_agreement: UsageAgreement[];
	model_vs_human: UsageModelScore[];
	/**
	 * The comparison run against the same human labels, scored the same way.
	 *
	 * Beside `model_vs_human` rather than instead of it: the published run is the
	 * one every count on the page is made of, and the second opinion is scored
	 * here only so that the two can be read against the same reference. Empty
	 * until there is both a coded sample and a comparison run.
	 */
	model_vs_human_comparison: UsageModelScore[];
	state: 'not_started' | 'in_progress' | 'complete';
}

export interface Usage {
	meta: BaseMeta;
	model: UsageModel;
	/** The prompt the run was made with, verbatim. Published, not summarised. */
	prompt: string;
	/** Sorted by occurrences, descending. */
	referents: UsageReferent[];
	/** Sorted by assigned occurrences, descending. */
	actors: UsageActor[];
	/** Below this many eligible occurrences, a speaker's shares are withheld. */
	minimum_occurrences: number;
	matrix: UsageMatrixCell[];
	stance_by_actor: UsageStanceRow[];
	diffusion: UsageDiffusion;
	/** A second model over the same occurrences, or the block that says none was run. */
	comparison: UsageComparison;
	gold: UsageGold;
}

/**
 * The comparison run's own five labels for one occurrence.
 *
 * Carried in full rather than only for the fields that differ, so that a reader
 * told an occurrence is contested can see the other reading whole without
 * loading a second run. `function` is pipe-joined without spaces, as the
 * published field is.
 */
export interface UsageAlternative {
	verdict: string;
	quotation: string;
	stance: string;
	function: string;
	referent: string;
}

/**
 * One annotated occurrence, fetched only when a reader opens a cell.
 *
 * `id` is the KWIC line identifier and the only join this artefact offers: the
 * sentence, the date, the delegation and the record symbol all come from
 * `kwic/genocide.json`, and are not duplicated here.
 */
export interface UsageOccurrence {
	/** `<speech>#<ordinal>` — joins `KwicLine.id`. */
	id: string;
	/** 64 hex characters, stable across runs. The annotation's own key. */
	occurrence_id: string;
	verdict: string;
	quotation: string;
	stance: string;
	/** One or more rhetorical functions, pipe-joined without spaces. */
	function: string;
	referent: string;
	/** A referent the model proposed but the controlled list does not carry. */
	proposed_referent: string;
	confidence: string;
	/** The span the model says supports its labels, verbatim from the speech. */
	evidence_quote: string;
	/** False when that span could not be found in the speech it names. */
	evidence_valid: boolean;
	/**
	 * The fields a second opinion read differently: a subset of `verdict`,
	 * `quotation`, `stance`, `function` and `referent`, in that order.
	 *
	 * Empty in three different situations — no comparison run, a comparison run
	 * that never reached this occurrence, and one that reached it and agreed —
	 * because the state of a whole run does not belong in 6,092 rows. The
	 * `comparison` block's `state` and `overlap` are what tell those apart.
	 */
	contested: string[];
	/** The second reading, non-null exactly where `contested` is not empty. */
	alt: UsageAlternative | null;
}

export interface UsageOccurrences {
	meta: BaseMeta;
	occurrences: UsageOccurrence[];
}
