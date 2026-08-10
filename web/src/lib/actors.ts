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

import type { Countries, CountryMeasure, CountryMeasureRow, CountryPeriod, Speaker } from './types';

export interface ActorRow {
	speaker: Speaker;
	row: CountryMeasureRow;
}

/** How a speaker may be ranked. Both come from the artefact; neither is derived here. */
export type Ordering = 'speech_rate' | 'token_rate' | 'speeches' | 'held';

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
	 * Speakers present in this period but under the minimum. A count, not a list
	 * of near-misses: naming them beside a ranking invites reading them as ranked.
	 */
	withheld: number;
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
	let withheld = 0;
	let seen = 0;

	for (const row of measured.rows) {
		if (row.period !== period) continue;
		seen += 1;
		const speaker = speakers.get(row.country_org);
		// A measure row for a speaker the country table does not list is a join
		// failure upstream, not a speaker to draw without a group or a type.
		if (!speaker) continue;
		if (row.sufficient) rows.push({ speaker, row });
		else withheld += 1;
	}

	rows.sort(compare(order));
	return {
		rows,
		withheld,
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
): ActorPlan => ({ rows: [], withheld: 0, absent: 0, minimum, period, order, refusal });

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
 * `atrocity_core` is a union of five overlapping terms, so a speech that says
 * both `genocide` and `war crimes` would be counted twice in any sum of their
 * occurrences. `11_countries.py` says so in as many words and withholds the
 * count rather than computing a wrong one: a set row has `held`, `speeches` and
 * `speech_rate` and no `occurrences` or `token_rate` at all.
 *
 * Read through `?? 0` — which is how every consumer reads a nullable number here
 * — a withheld figure becomes `0.00 per 100,000 words`, and a deliberate silence
 * is published as a measurement. That is the failure §7 names in one line: no
 * visual may introduce a number that does not exist in the artefact. So the
 * absence is detected once, here, and the interface drops the column, the
 * ordering and the tooltip line rather than filling them with a zero.
 *
 * Presence is read off the rows rather than inferred from `kind`, so a future
 * set measure that does carry counts is shown them without editing this.
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
 * Three rules, all of which can be got wrong in ways that look right:
 *
 * **No link when there is nothing to read.** A speaker can clear the minimum and
 * still never use the term. Offering "read the occurrences" for none of them
 * sends a reader to an empty table to discover what the row already said. The
 * test is the term-bearing speech count rather than the occurrence count,
 * because a set measure has no occurrence count at all — see `carries()` — and
 * `undefined < 1` is false, so the obvious guard would have let every set row
 * through while appearing to check.
 *
 * **A set becomes one link per member.** `atrocity_core` sums five terms and the
 * concordance shows one, so a single link would quietly present a fifth of the
 * evidence as all of it. The members are returned in the artefact's order and
 * the interface says the reading is term by term. Their individual counts are
 * not in this artefact, so a member link can land on nothing — which the
 * concordance states plainly, and which is a smaller cost than a link that
 * misrepresents its scope.
 *
 * **The period travels with the link.** The rate a reader is reading is for one
 * period, so the years bound the concordance too. Sending them to 1992–2023 from
 * a 2020–2023 rate would show lines the figure never counted.
 */
export function occurrences(data: Countries, measure: string, entry: ActorRow): ConcordanceLink[] {
	const measured = data.measures[measure];
	if (!measured || entry.row.speeches < 1) return [];
	const period = data.periods.find((candidate) => candidate.key === entry.row.period);
	if (!period) return [];

	const terms = measured.kind === 'sets' ? (measured.members ?? []) : [measure];
	return terms.map((term) => {
		const params = new URLSearchParams({
			term,
			country: entry.speaker.country_org,
			from: String(period.first_year),
			to: String(period.last_year)
		});
		return { term, query: params.toString() };
	});
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
