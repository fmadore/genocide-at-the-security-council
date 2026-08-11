/**
 * What a filled map may say, kept out of the component that fills it.
 *
 * `docs/PLAN.md` §7.3 argued for years that there should be no choropleth here,
 * and the argument was not that filling territory is ugly. It was that a fill is
 * keyed on ISO3 and two codes in this corpus are shared — COD by the Democratic
 * Republic of the Congo and Zaire, SRB by Serbia, Serbia and Montenegro and
 * Yugoslavia — so a fill keyed on the code paints one speaker's rate over
 * another's with nothing on screen to say it happened. The circles avoid it by
 * keying on `country_org`, which is unique.
 *
 * The view exists now because that failure is preventable rather than inherent,
 * and this module is where it is prevented. A code with more than one drawable
 * holder is not filled with either holder's number: it is `contested`, drawn as
 * a refusal, and the interface names the speakers. In the present corpus no
 * period reaches that state — of the two shared codes only one holder each ever
 * clears the minimum — so the branch is unreachable today and is tested anyway,
 * for the same reason the chronology carries an `unobserved` cell state it never
 * draws: the day it becomes reachable, the figure should not have to be changed
 * to say so.
 *
 * Three further decisions, none of which the renderer is trusted with:
 *
 * **A withheld speaker is not an absent one.** 71 mappable speakers clear no
 * minimum in the whole-corpus slice and up to 143 in a single period. Left the
 * colour of the surrounding sea they would read as states that never addressed
 * the Council, which is false of every one of them. They get their own fill and
 * their own line in the key — the distinction the chronology's grid draws
 * between a hatched cell and a white one.
 *
 * **The ramp starts at zero, not at the smallest country.** Zero is attainable
 * here: two of the 129 drawable speakers cleared 100 speeches and never used the
 * word at all. A scale anchored on the observed minimum would spend its whole
 * range above them and paint a silent delegation the same colour as a quiet one.
 * This is the one place the choropleth must not copy the circles, whose radius
 * *is* min-to-max — a marker has a floor of four pixels and cannot vanish, a
 * fill at the bottom of a ramp can.
 *
 * **Colour takes the transform; nothing else does.** `tone()` in `$lib/theme`
 * says why the ramp is square-rooted and why a length may never be.
 *
 * What this module cannot fix is the thing a choropleth is: a statement about
 * territory. A centroid is navigation — the artefact says so in `centroid_rule`
 * and both views print it — but a filled polygon is the country, and for the
 * historical speakers in this corpus the polygon is a successor's. Yugoslavia
 * fills modern Serbia. That is a claim the circles never made, it cannot be
 * removed by keying anything differently, and it is carried in the interface as
 * a caveat rather than pretended away here.
 */

import type { ActorPlan, ActorRow } from './actors';
import { tone } from './theme';

/**
 * What may be drawn over one country.
 *
 * `contested` is not a value withheld for want of evidence — that is
 * `withheld`, which means the speaker was heard from too rarely to divide by.
 * It means the opposite: the evidence exists, and there is more than one
 * speaker's worth of it under a single code, so no one number belongs there.
 */
export type PatchState = 'drawn' | 'withheld' | 'contested';

export interface Patch {
	iso3: string;
	state: PatchState;
	/**
	 * The `country_org` of the one drawable speaker at this code, for selection
	 * and for the hover box. Null unless the state is `drawn`: selecting a
	 * contested patch would mean selecting one of two speakers arbitrarily, which
	 * is the failure this module exists to prevent, in the interaction layer.
	 */
	key: string | null;
	/** The figure the fill carries, in the units the table is ranked by. */
	value: number | null;
	/** Where the value sits on the ramp, from a floor of zero. Colour only. */
	tone: number;
	/** This ISO3 is held by more than one speaker somewhere in the corpus. */
	shared: boolean;
	/** Every speaker at this code in this slice, drawable or not, in table order. */
	holders: string[];
	/**
	 * The speaker's centroid, `[longitude, latitude]`.
	 *
	 * Carried because Natural Earth's 1:110m sheet omits states below a size
	 * threshold, and 31 of the corpus's 197 coded speakers are among them —
	 * Singapore, Malta, Bahrain, Cape Verde, Mauritius, Liechtenstein, Saint
	 * Vincent and the Grenadines and 24 more. A choropleth that simply lost them
	 * would drop seven drawable speakers out of the figure and say nothing, so
	 * the view marks them at their centroid instead. See `withoutPolygon()`.
	 */
	lngLat: [number, number] | null;
}

export interface ChoroplethPlan {
	/** One per ISO3 present in this slice. Never one per speaker. */
	patches: Patch[];
	/** The top of the ramp. The bottom is zero by construction. */
	high: number;
	drawn: number;
	withheld: number;
	contested: number;
}

/**
 * Group one slice of the actor view by ISO3, and decide what each code may say.
 *
 * `figure` is the same accessor the ranking uses, so the fill and the table
 * carry the same number: a country high on the ramp is a country high in the
 * table, or the figure is lying about one of them.
 *
 * Only mappable speakers are considered, and mappability is read off the
 * artefact rather than inferred from the presence of a code: `11_countries.py`
 * sets it to "is a state, has a code, and has a centroid" precisely so that a
 * consumer excludes the UN Secretariat on purpose instead of by tripping over a
 * null.
 */
export function fills(
	plan: ActorPlan,
	shared: Set<string>,
	figure: (entry: ActorRow) => number
): ChoroplethPlan {
	const byCode = new Map<string, { drawn: ActorRow[]; under: ActorRow[] }>();
	const bucket = (code: string) => {
		const found = byCode.get(code);
		if (found) return found;
		const made = { drawn: [] as ActorRow[], under: [] as ActorRow[] };
		byCode.set(code, made);
		return made;
	};

	for (const entry of plan.rows) {
		const { iso3, mappable } = entry.speaker;
		if (mappable && iso3) bucket(iso3).drawn.push(entry);
	}
	for (const entry of plan.under) {
		const { iso3, mappable } = entry.speaker;
		if (mappable && iso3) bucket(iso3).under.push(entry);
	}

	// The top of the ramp is the largest value actually drawn. A withheld
	// speaker never enters the range — it has no number — and a contested code
	// never does either, because the number it would contribute belongs to one
	// of two speakers and the patch is refusing to choose between them.
	let high = 0;
	for (const [, holders] of byCode) {
		if (holders.drawn.length === 1) high = Math.max(high, figure(holders.drawn[0]));
	}

	const patches: Patch[] = [];
	for (const [iso3, holders] of byCode) {
		const both = [...holders.drawn, ...holders.under];
		const centroid = both[0]?.speaker.centroid ?? null;
		const common = {
			iso3,
			shared: shared.has(iso3),
			holders: both.map((entry) => entry.speaker.country_org),
			lngLat: centroid ? ([centroid[1], centroid[0]] as [number, number]) : null
		};

		if (holders.drawn.length > 1) {
			patches.push({ ...common, state: 'contested', key: null, value: null, tone: 0 });
		} else if (holders.drawn.length === 1) {
			const value = figure(holders.drawn[0]);
			patches.push({
				...common,
				state: 'drawn',
				key: holders.drawn[0].speaker.country_org,
				value,
				tone: high > 0 ? tone(Math.min(value / high, 1)) : 0
			});
		} else {
			patches.push({ ...common, state: 'withheld', key: null, value: null, tone: 0 });
		}
	}

	// Sorted so the fill expressions the renderer builds from this are stable
	// between renders; MapLibre rebuilds a paint property whenever it changes,
	// and a `match` whose arms reorder on every keystroke changes every time.
	patches.sort((a, b) => a.iso3.localeCompare(b.iso3));

	return {
		patches,
		high,
		drawn: patches.filter((patch) => patch.state === 'drawn').length,
		withheld: patches.filter((patch) => patch.state === 'withheld').length,
		contested: patches.filter((patch) => patch.state === 'contested').length
	};
}

/**
 * The patches the boundary file has no polygon for, in table order.
 *
 * `available` is what `web/static/geo/countries.json` actually carries, read
 * from the file at run time rather than from a list written down twice. The
 * caller draws these at their centroid as a fixed square, which is a legibility
 * device and not a magnitude: the square's size carries nothing, its colour
 * carries what every other patch's colour carries, and the interface says so.
 *
 * A patch with no centroid is dropped rather than placed at the origin. It
 * cannot occur — the artefact's `mappable` requires a centroid — and a speaker
 * drawn in the Gulf of Guinea is a worse failure than one absent from a figure
 * whose table holds every row.
 */
export function withoutPolygon(plan: ChoroplethPlan, available: Set<string>): Patch[] {
	return plan.patches.filter((patch) => !available.has(patch.iso3) && patch.lngLat !== null);
}
