/**
 * The decisions behind the actor view, kept out of the components that draw it.
 *
 * `docs/PLAN.md` §7 requires that the arithmetic a visual performs at render
 * time be tested, and §7.3 names three things this view can get wrong in ways
 * that look right on screen. All three are settled here:
 *
 * **A slice below the declared minimum is not drawn.** 468 of 601 speakers carry
 * no rate at all — `11_countries.py` writes null rather than a number, because
 * at the corpus prevalence a zero under about 96 speeches means "not heard from
 * enough", not "quieter than the Council". `plan()` partitions on the
 * artefact's own `sufficient` flag and reports how many it withheld, so the
 * interface states the exclusion instead of showing a short table.
 *
 * **Nothing is keyed on ISO3.** Two codes are shared: COD by the DRC and Zaire,
 * SRB by Serbia, Serbia and Montenegro and Yugoslavia. Those are separate
 * speakers with separate denominators, and merging them would build a
 * denominator no state ever had. Every function here keys on `country_org`,
 * which is unique, and `ambiguous()` exists so the interface can *say* the code
 * is shared rather than quietly picking one.
 *
 * **A centroid is navigation, not location.** Every speech in this corpus was
 * delivered in the Security Council chamber. The artefact says so in
 * `centroid_rule`, and the map surfaces that string rather than paraphrasing it.
 *
 * One consequence of keying on the speaker rather than the code is that the
 * three SRB speakers land on one point, because they share a centroid. They are
 * not merged; `points()` groups them and hands the interface all three, so a
 * marker that stands for more than one speaker can say how many.
 */

import { evidenceTerm } from './concordance';
import { headlineMeasure } from './headline';
import type { Countries, CountryMeasure, CountryMeasureRow, CountryPeriod, Speaker } from './types';

export interface ActorRow {
	speaker: Speaker;
	row: CountryMeasureRow;
}

/** How a speaker may be ranked. Both come from the artefact; neither is derived here. */
export type Ordering = 'speech_rate' | 'token_rate' | 'speeches' | 'held';

export interface ActorState {
	measure: string;
	period: string;
	order: Ordering;
}

/**
 * The key of the slice covering the whole corpus, as `lib/actors.py` writes it.
 *
 * Named because two things now depend on it — the default period, and the
 * corpus-wide totals `widening()` sizes a subtraction from — and a second
 * `'all'` typed into the second of them is how the two start disagreeing about
 * which rows they are reading. Every use is still guarded: an artefact that
 * declares no such period falls back rather than assuming one.
 */
export const WHOLE = 'all';

/** Defaults follow the artefact, so a later corpus extension does not create a stale URL contract. */
export function actorDefaults(data: Countries): ActorState {
	return {
		measure: headlineMeasure(Object.keys(data.measures)) ?? Object.keys(data.measures)[0] ?? '',
		period: data.periods.some((period) => period.key === WHOLE)
			? WHOLE
			: (data.periods[0]?.key ?? ''),
		order: 'speech_rate'
	};
}

/** Parse and normalize the analytical actor controls from a copied URL. */
export function readActorState(params: URLSearchParams, data: Countries): ActorState {
	const defaults = actorDefaults(data);
	const askedMeasure = params.get('measure');
	const measure = askedMeasure && data.measures[askedMeasure] ? askedMeasure : defaults.measure;
	const askedPeriod = params.get('period');
	const period =
		askedPeriod && data.periods.some((candidate) => candidate.key === askedPeriod)
			? askedPeriod
			: defaults.period;
	const askedOrder = params.get('order') as Ordering | null;
	const order =
		askedOrder && orderings(data.measures[measure]).includes(askedOrder)
			? askedOrder
			: defaults.order;
	// `view` used to choose circles or a choropleth; the choropleth went with the
	// review of 1 September 2026 and an old `view=` in a copied URL is ignored.
	return { measure, period, order };
}

/** Serialize only controls that differ from the artefact-aware defaults. */
export function actorParams(state: ActorState, data: Countries): URLSearchParams {
	const defaults = actorDefaults(data);
	const params = new URLSearchParams();
	if (state.measure !== defaults.measure) params.set('measure', state.measure);
	if (state.period !== defaults.period) params.set('period', state.period);
	if (state.order !== defaults.order) params.set('order', state.order);
	return params;
}

export interface ActorRequest {
	data: Countries;
	measure: string;
	period: string;
	order?: Ordering;
}

export interface ActorPlan {
	/** Speakers whose slice clears the minimum, ranked. The only drawable rows. */
	rows: ActorRow[];
	/**
	 * Speakers present in this period but under the minimum, unranked.
	 *
	 * They are never sorted and never handed to the ranking: naming near-misses
	 * beside a ranked table invites reading them as ranked, which is why the
	 * interface reports `under.length` and not these rows. The list itself is
	 * kept so the count can be checked against the rows it summarises, and so a
	 * later figure that must mark a withheld speaker as *withheld* rather than
	 * absent — the distinction the chronology's grid draws between a hatched
	 * cell and a white one — has them to hand.
	 */
	under: ActorRow[];
	/** Speakers the artefact has no row for in this period. */
	absent: number;
	minimum: number;
	period: CountryPeriod | undefined;
	/**
	 * What the rows were actually ranked by, which is not always what was asked
	 * for: a measure that carries no occurrence count cannot be ranked per token,
	 * and ranking on the missing figure would order 133 speakers by zero and call
	 * it a ranking. The caller is told which figure it got so the interface can
	 * name that one rather than the one in its select.
	 */
	order: Ordering;
	/** Why there is nothing to draw, when there is nothing to draw. */
	refusal: 'no-measure' | 'no-period' | 'none-sufficient' | null;
}

/**
 * Rank the drawable speakers for one measure and period.
 *
 * The partition is the artefact's `sufficient` flag rather than a comparison
 * recomputed here. `11_countries.py` derived the threshold and already applied
 * it — nulling the rates it governs — so a second implementation of the same
 * rule in TypeScript could only ever drift from the one that wrote the data.
 */
export function plan(request: ActorRequest): ActorPlan {
	const { data, measure, period, order: asked = 'speech_rate' } = request;
	const found = data.periods.find((candidate) => candidate.key === period);
	const minimum = data.minimum_speeches;
	const measured = data.measures[measure];

	if (!measured) return empty('no-measure', minimum, found, asked);
	if (!found) return empty('no-period', minimum, found, asked);

	const order = orderings(measured).includes(asked) ? asked : 'speech_rate';

	const speakers = new Map(data.countries.map((speaker) => [speaker.country_org, speaker]));
	const rows: ActorRow[] = [];
	const under: ActorRow[] = [];
	let seen = 0;

	for (const row of measured.rows) {
		if (row.period !== period) continue;
		seen += 1;
		const speaker = speakers.get(row.country_org);
		// A measure row for a speaker the country table does not list is a join
		// failure upstream, not a speaker to draw without a group or a type.
		if (!speaker) continue;
		if (row.sufficient) rows.push({ speaker, row });
		else under.push({ speaker, row });
	}

	rows.sort(compare(order));
	return {
		rows,
		under,
		absent: Math.max(0, data.countries.length - seen),
		minimum,
		period: found,
		order,
		refusal: rows.length ? null : 'none-sufficient'
	};
}

const empty = (
	refusal: ActorPlan['refusal'],
	minimum: number,
	period: CountryPeriod | undefined,
	order: Ordering
): ActorPlan => ({ rows: [], under: [], absent: 0, minimum, period, order, refusal });

/**
 * Descending by the chosen figure, then by name.
 *
 * The name breaks ties so the order is total: two speakers with the same rate
 * would otherwise swap places between renders depending on the sort's
 * stability, and a table that reorders itself is a table a reader cannot cite.
 */
function compare(order: Ordering) {
	return (a: ActorRow, b: ActorRow) => {
		const left = value(a, order);
		const right = value(b, order);
		if (left !== right) return right - left;
		return a.speaker.country_org.localeCompare(b.speaker.country_org);
	};
}

function value(entry: ActorRow, order: Ordering): number {
	if (order === 'speeches') return entry.row.speeches;
	if (order === 'held') return entry.row.held;
	// Null never reaches here for a sufficient row — the fetch boundary refuses a
	// payload where it does — but a zero is the honest fallback if one ever did.
	return (order === 'token_rate' ? entry.row.token_rate : entry.row.speech_rate) ?? 0;
}

/** The ISO3 codes more than one speaker in the corpus carries. */
export function ambiguous(data: Countries): Set<string> {
	return new Set(
		Object.entries(data.iso3_collisions)
			.filter(([, holders]) => holders.length > 1)
			.map(([code]) => code)
	);
}

export interface MapPoint {
	/**
	 * `[longitude, latitude]` — MapLibre's order.
	 *
	 * The artefact writes `[latitude, longitude]`, which `config/entities.csv`
	 * records and which reads naturally to a person. Flipping it in exactly one
	 * place is the point of this function: a component that did it inline would
	 * put Afghanistan in the Indian Ocean the first time someone forgot.
	 */
	lngLat: [number, number];
	/** Every speaker at this point. More than one when centroids coincide. */
	speakers: ActorRow[];
	/** True when any speaker here holds an ISO3 another speaker also holds. */
	shared: boolean;
}

/**
 * The drawable points, grouped so that coincident speakers are one marker.
 *
 * Only `mappable` speakers are considered, and that flag is read rather than
 * inferred from the presence of coordinates: the artefact sets it to "is a
 * state, has a code, and has a centroid" precisely so a consumer excludes the
 * UN Secretariat on purpose instead of by tripping over a null.
 *
 * Grouping is by the coordinate itself. Yugoslavia, Serbia and Montenegro and
 * Serbia share the SRB centroid, so drawn per speaker they are three markers at
 * one pixel — the reader sees one and has no way to know two are behind it.
 * One marker that knows it stands for three is the honest rendering, and it is
 * not a merge: the three rows stay separate and are all handed to the caller.
 */
export function points(rows: ActorRow[], shared: Set<string>): MapPoint[] {
	const grouped = new Map<string, MapPoint>();
	for (const entry of rows) {
		const { centroid, mappable, iso3 } = entry.speaker;
		if (!mappable || !centroid) continue;
		const [latitude, longitude] = centroid;
		const key = `${latitude},${longitude}`;
		const point = grouped.get(key);
		if (point) {
			point.speakers.push(entry);
			point.shared ||= iso3 !== null && shared.has(iso3);
		} else {
			grouped.set(key, {
				lngLat: [longitude, latitude],
				speakers: [entry],
				shared: iso3 !== null && shared.has(iso3)
			});
		}
	}
	return [...grouped.values()];
}

export interface Figures {
	/** The measure has an occurrence count, and a rate per token built on it. */
	occurrences: boolean;
}

/**
 * Which figures a measure actually carries.
 *
 * Every measure in this artefact carries an occurrence count since lexicon v5,
 * and the check stays because of what it caught. `atrocity_core` was a union of
 * five overlapping terms, so a speech saying both `genocide` and `war crimes`
 * would have been counted twice in any sum of their occurrences;
 * `11_countries.py` withheld the count rather than computing a wrong one, and a
 * set row had `held`, `speeches` and `speech_rate` and nothing else.
 *
 * Read through `?? 0` — which is how every consumer reads a nullable number here
 * — a withheld figure becomes `0.00 per 100,000 words`, and a deliberate silence
 * is published as a measurement. That is the failure §7 names in one line: no
 * visual may introduce a number that does not exist in the artefact. So the
 * absence is detected once, here, and the interface drops the column, the
 * ordering and the tooltip line rather than filling them with a zero.
 *
 * Presence is read off the rows rather than inferred from `kind`, which is why
 * R7 could remove the only measure that withheld a count without this needing
 * an edit — and why a later measure that withholds one is handled already.
 */
export function carries(measure: CountryMeasure | undefined): Figures {
	return { occurrences: measure?.rows.some((row) => row.occurrences !== undefined) ?? false };
}

/** The orderings a measure can honestly be ranked by. */
export function orderings(measure: CountryMeasure | undefined): Ordering[] {
	const base: Ordering[] = ['speech_rate', 'speeches', 'held'];
	return carries(measure).occurrences ? ['speech_rate', 'token_rate', 'speeches', 'held'] : base;
}

export interface ConcordanceLink {
	/** The lexicon term the concordance opens at. One per link: it shows one. */
	term: string;
	/** Query string for `/concordance`, without the leading `?`. */
	query: string;
}

/**
 * Where to read the occurrences a row counts.
 *
 * `docs/PLAN.md` §3 asks for "quotations linked to the concordance and source
 * reader", and a link that reaches the concordance without carrying the speaker
 * does not answer it: a reader sent from a rate arrives at every line of the
 * corpus and has to rebuild the filter by hand. The concordance already reads
 * `term`, `country`, `from` and `to` from the URL, so the filter is expressible;
 * what was missing is a caller that expresses it.
 *
 * Two rules, both of which can be got wrong in ways that look right:
 *
 * **No link when there is nothing to read.** A speaker can clear the minimum and
 * still never use the term. Offering "read the occurrences" for none of them
 * sends a reader to an empty table to discover what the row already said. The
 * test is the term-bearing speech count rather than the occurrence count: a
 * measure may withhold its occurrences, and `undefined < 1` is false, so the
 * obvious guard would let such a row through while appearing to check.
 *
 * **The period travels with the link.** The rate a reader is reading is for one
 * period, so the years bound the concordance too. Sending a period-specific rate
 * to the full corpus range would show lines the figure never counted.
 *
 * One link or none. It returned a list until R7, because `atrocity_core` summed
 * five terms while the concordance shows one, and a single link would have
 * presented a fifth of the evidence as all of it. Every measure is one term now,
 * so the list would have exactly one member on every row that has any, and a
 * shape that can only be one thing should say so.
 *
 * **The measure is not always the term.** The measure this table opens on is
 * the derived `genocide_qualification`, which no concordance enumerates —
 * `08_kwic.py` writes a file per active lexicon term and a subtraction is not
 * one. Naming the measure in the URL named a file that was never written, on
 * every row. The link resolves through `derived_from` instead, which widens what
 * opens; `widening()` is what the interface names that widening by. The raw term
 * is a selectable measure here too, and for it the resolution is the identity.
 */
export function occurrences(
	data: Countries,
	measure: string,
	entry: ActorRow
): ConcordanceLink | null {
	const measured = data.measures[measure];
	if (!measured || entry.row.speeches < 1) return null;
	const period = data.periods.find((candidate) => candidate.key === entry.row.period);
	if (!period) return null;

	const term = evidenceTerm(measure, measured);
	const params = new URLSearchParams({
		term,
		country: entry.speaker.country_org,
		from: String(period.first_year),
		to: String(period.last_year)
	});
	return { term, query: params.toString() };
}

/**
 * What a derived measure subtracts, and how much of it.
 *
 * Null for a measure that is its own term, so the raw term selected beside the
 * derived one carries no such statement — there is no subtraction to describe.
 * For a derived measure it names the term the concordance holds, what is taken
 * out of it, and the size of that removal, so the interface can say both that
 * the evidence is a superset of the figure and how much wider it is.
 *
 * **The size comes out of the payload.** `countries.json` published the derived
 * measure alone until the raw term joined it, and this returned no size at all:
 * the difference was simply not in the artefact, and a component that stated
 * one would have been quoting itself. Both are now published, so the difference
 * is the minuend's whole-corpus rows less the derived measure's — recomputed on
 * every render, and moved by a re-cut corpus rather than by an edit here.
 *
 * The two figures are different quantities and the interface must not merge
 * them. `occurrences` is what the subtraction removes outright. `speeches` is
 * smaller: a speech that says both words keeps its place in the derived
 * measure, so only the speeches whose *sole* match was the subtracted term
 * leave the count. Either is null where the artefact cannot support it — the
 * minuend absent, as in an archived payload, or an occurrence count withheld.
 */
export interface Widening {
	/** The term whose concordance actually opens. */
	term: string;
	/** What the measure subtracts from it, and what those lines therefore still hold. */
	subtracted: string[];
	/** Speeches that fall out of the count entirely, corpus-wide. */
	speeches: number | null;
	/** Occurrences the subtraction removes, corpus-wide. */
	occurrences: number | null;
}

/**
 * A measure's whole-corpus totals, summed from the rows it publishes.
 *
 * `11_countries.py` reconciles every measure's whole-corpus rows against the
 * corpus itself before writing them, so this sum is the corpus figure and not
 * an approximation of it. `occurrences` is null rather than zero when any row
 * withholds one: a measure without an occurrence count has no total, and `?? 0`
 * would publish that silence as a number.
 */
function corpusTotals(measure: CountryMeasure | undefined): {
	speeches: number;
	occurrences: number | null;
} | null {
	if (!measure) return null;
	let speeches = 0;
	let occurrences: number | null = 0;
	let seen = false;
	for (const row of measure.rows) {
		if (row.period !== WHOLE) continue;
		seen = true;
		speeches += row.speeches;
		if (row.occurrences == null) occurrences = null;
		else if (occurrences !== null) occurrences += row.occurrences;
	}
	return seen ? { speeches, occurrences } : null;
}

export function widening(data: Countries, measure: string): Widening | null {
	const measured = data.measures[measure];
	if (!measured?.derived_from) return null;
	const from = corpusTotals(data.measures[measured.derived_from]);
	const derived = corpusTotals(measured);
	const both = from !== null && derived !== null;
	return {
		term: measured.derived_from,
		subtracted: measured.derived_minus ?? [],
		speeches: both ? from.speeches - derived.speeches : null,
		occurrences:
			both && from.occurrences !== null && derived.occurrences !== null
				? from.occurrences - derived.occurrences
				: null
	};
}

/**
 * Where a value sits in the drawn range, 0 to 1, for sizing a marker.
 *
 * Computed across what is on screen, so a marker is comparable within one view
 * and not across two — the same rule the word cloud states about its type sizes,
 * and for the same reason. A range of zero puts everything at the middle rather
 * than at nothing: there is no comparison to draw, and hiding the points would
 * not say so.
 */
export function scale(values: number[]): (value: number) => number {
	if (values.length === 0) return () => 0.5;
	const low = Math.min(...values);
	const high = Math.max(...values);
	if (high - low < 1e-12) return () => 0.5;
	return (value: number) => (value - low) / (high - low);
}
