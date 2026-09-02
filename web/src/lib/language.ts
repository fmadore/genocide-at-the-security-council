export type SliceKind = 'by_country' | 'by_period' | 'by_speaker_group';
export type ProfileFacet = 'whole' | SliceKind;
export type Alignment = 'rank' | 'word';
export type KeynessView = 'matched' | 'unmatched';

export interface LanguageState {
	node: string;
	width: string;
	sliceKind: SliceKind;
	sliceA: string;
	sliceB: string;
	align: Alignment;
	profileFacet: ProfileFacet;
	profileNode: string;
	profileWidth: string;
	profileMember: string;
	profileLimit: string;
	profileFloor: string;
	keynessView: KeynessView;
	period: string;
}

export interface LanguageChoices {
	nodes: Record<string, readonly string[]>;
	slices: Record<SliceKind, readonly string[]>;
	periods: readonly string[];
	profileDefault: { node: string; width: string };
}

const SLICE_KINDS: readonly SliceKind[] = ['by_country', 'by_period', 'by_speaker_group'];
const PROFILE_FACETS: readonly ProfileFacet[] = ['whole', ...SLICE_KINDS];
const PROFILE_LIMITS = ['25', '40', '60', '100'] as const;
const PROFILE_FLOORS = ['0', '10', '25', '50'] as const;

const firstNode = (choices: LanguageChoices) =>
	choices.nodes.genocide ? 'genocide' : (Object.keys(choices.nodes)[0] ?? '');

const widthFor = (choices: LanguageChoices, node: string, asked?: string | null) => {
	const available = choices.nodes[node] ?? [];
	if (asked && available.includes(asked)) return asked;
	return available.includes('5') ? '5' : (available[0] ?? '');
};

const pairFor = (choices: LanguageChoices, kind: SliceKind): [string, string] => {
	const available = choices.slices[kind];
	if (kind === 'by_country') {
		const left = available.includes('Rwanda') ? 'Rwanda' : (available[0] ?? '');
		const right = available.includes('United States Of America')
			? 'United States Of America'
			: (available.find((name) => name !== left) ?? left);
		return [left, right];
	}
	return [available[0] ?? '', available[1] ?? available[0] ?? ''];
};

export function languageDefaults(choices: LanguageChoices): LanguageState {
	const node = firstNode(choices);
	const sliceKind: SliceKind = 'by_country';
	const [sliceA, sliceB] = pairFor(choices, sliceKind);
	const profileNode = choices.nodes[choices.profileDefault.node]
		? choices.profileDefault.node
		: node;
	return {
		node,
		width: widthFor(choices, node),
		sliceKind,
		sliceA,
		sliceB,
		align: 'rank',
		profileFacet: 'whole',
		profileNode,
		profileWidth: widthFor(choices, profileNode, choices.profileDefault.width),
		profileMember: '',
		profileLimit: '40',
		profileFloor: '0',
		keynessView: 'matched',
		period: choices.periods.includes('whole') ? 'whole' : (choices.periods[0] ?? '')
	};
}

/** Parse every control that changes a Language figure's analytical reading. */
export function readLanguageState(
	params: URLSearchParams,
	choices: LanguageChoices
): LanguageState {
	const defaults = languageDefaults(choices);
	const askedNode = params.get('node');
	const node = askedNode && choices.nodes[askedNode] ? askedNode : defaults.node;
	const width = widthFor(choices, node, params.get('width'));

	const askedKind = params.get('slice') as SliceKind | null;
	const sliceKind = askedKind && SLICE_KINDS.includes(askedKind) ? askedKind : defaults.sliceKind;
	const [defaultA, defaultB] = pairFor(choices, sliceKind);
	const members = choices.slices[sliceKind];
	const askedA = params.get('left');
	const askedB = params.get('right');
	const sliceA = askedA && members.includes(askedA) ? askedA : defaultA;
	const sliceB = askedB && members.includes(askedB) ? askedB : defaultB;

	const askedFacet = params.get('cloud') as ProfileFacet | null;
	const profileFacet =
		askedFacet && PROFILE_FACETS.includes(askedFacet) ? askedFacet : defaults.profileFacet;
	const askedCloudNode = params.get('cloud-node');
	const profileNode =
		askedCloudNode && choices.nodes[askedCloudNode] ? askedCloudNode : defaults.profileNode;
	const profileWidth = widthFor(choices, profileNode, params.get('cloud-width'));
	const askedMember = params.get('cloud-member');
	const profileMember =
		profileFacet !== 'whole' && askedMember && choices.slices[profileFacet].includes(askedMember)
			? askedMember
			: profileFacet === 'whole'
				? ''
				: (choices.slices[profileFacet][0] ?? '');

	const askedLimit = params.get('words');
	const profileLimit =
		askedLimit && PROFILE_LIMITS.includes(askedLimit as (typeof PROFILE_LIMITS)[number])
			? askedLimit
			: defaults.profileLimit;
	const askedFloor = params.get('floor');
	const profileFloor =
		askedFloor && PROFILE_FLOORS.includes(askedFloor as (typeof PROFILE_FLOORS)[number])
			? askedFloor
			: defaults.profileFloor;
	const align = params.get('align') === 'word' ? 'word' : defaults.align;
	const keynessView = params.get('comparison') === 'unmatched' ? 'unmatched' : defaults.keynessView;
	const askedPeriod = params.get('period');
	const period =
		askedPeriod && choices.periods.includes(askedPeriod) ? askedPeriod : defaults.period;

	return {
		node,
		width,
		sliceKind,
		sliceA,
		sliceB,
		align,
		profileFacet,
		profileNode,
		profileWidth,
		profileMember,
		profileLimit,
		profileFloor,
		keynessView,
		period
	};
}

export function languageParams(state: LanguageState, choices: LanguageChoices): URLSearchParams {
	const defaults = languageDefaults(choices);
	const [defaultA, defaultB] = pairFor(choices, state.sliceKind);
	const params = new URLSearchParams();
	if (state.node !== defaults.node) params.set('node', state.node);
	if (state.width !== widthFor(choices, state.node)) params.set('width', state.width);
	if (state.sliceKind !== defaults.sliceKind) params.set('slice', state.sliceKind);
	if (state.sliceA !== defaultA) params.set('left', state.sliceA);
	if (state.sliceB !== defaultB) params.set('right', state.sliceB);
	if (state.align !== defaults.align) params.set('align', state.align);
	if (state.profileFacet !== defaults.profileFacet) params.set('cloud', state.profileFacet);
	if (state.profileFacet === 'whole') {
		if (state.profileNode !== defaults.profileNode) params.set('cloud-node', state.profileNode);
		if (state.profileWidth !== widthFor(choices, state.profileNode, choices.profileDefault.width)) {
			params.set('cloud-width', state.profileWidth);
		}
	} else if (state.profileMember !== choices.slices[state.profileFacet][0]) {
		params.set('cloud-member', state.profileMember);
	}
	if (state.profileLimit !== defaults.profileLimit) params.set('words', state.profileLimit);
	if (state.profileFloor !== defaults.profileFloor) params.set('floor', state.profileFloor);
	if (state.keynessView !== defaults.keynessView) params.set('comparison', state.keynessView);
	if (state.period !== defaults.period) params.set('period', state.period);
	return params;
}

/* --- The collocate profile: which rows a figure shows --------------------
   One decision serves the dot plot and the table under it, so there is no
   arrangement of the controls under which the two disagree. It used to live
   with the word cloud; the cloud went (review of 1 September 2026, §5.2) and
   the decision stayed, because it was never about the drawing. */

import type { CollocateBlock, Word } from './types';

/**
 * Why nothing is drawn. `speeches` and `minimum` are both carried because the
 * interface has to name the slice's size *and* the threshold it fell under —
 * a message with only one of them cannot be checked by a reader.
 */
export interface Refusal {
	kind: 'missing' | 'below-minimum' | 'no-rows';
	/** Speeches behind the slice, where there is a slice. */
	speeches: number | null;
	/** The minimum the artefact declares. */
	minimum: number | null;
	/** The frequency floor in force, where that is what emptied the table. */
	floor: number | null;
}

export interface ProfileRequest {
	/** The block asked for. `undefined` when the facet holds no such member. */
	block: CollocateBlock | undefined;
	/**
	 * The minimum speeches the artefact declares for a slice, or `null` for the
	 * whole corpus, which is not a slice and has no minimum to fall under.
	 */
	minimumSpeeches: number | null;
	/** Rows drawn, at most. */
	limit: number;
	/** Words occurring fewer times than this near the node are not drawn. */
	floor: number;
}

export interface ProfilePlan {
	/** The rows drawn, and the rows listed. One array, so the two agree. */
	rows: Word[];
	/** Rows the artefact holds for this slice, before any filter. */
	available: number;
	/** Rows removed by the frequency floor. */
	filtered: number;
	/** Rows removed by the limit, after the floor. Stated, never silent. */
	truncated: number;
	refusal: Refusal | null;
}

const nothing = (refusal: Refusal, available: number): ProfilePlan => ({
	rows: [],
	available,
	filtered: 0,
	truncated: 0,
	refusal
});

/**
 * Choose the rows the figure shows, or say why it shows none.
 *
 * A refusal empties `rows`, so the table under the plot is gated by the same
 * decision the plot is. A withheld slice is withheld in both, which is the
 * point of there being one function.
 */
export function profilePlan(request: ProfileRequest): ProfilePlan {
	const { block, minimumSpeeches, limit, floor } = request;

	if (!block) {
		return nothing({ kind: 'missing', speeches: null, minimum: minimumSpeeches, floor: null }, 0);
	}

	// The gate, before anything is counted. A slice below the declared minimum
	// is not drawn, and the whole corpus is not put in its place.
	if (minimumSpeeches !== null && (block.speeches ?? 0) < minimumSpeeches) {
		return nothing(
			{
				kind: 'below-minimum',
				speeches: block.speeches ?? 0,
				minimum: minimumSpeeches,
				floor: null
			},
			block.collocates.length
		);
	}

	const available = block.collocates.length;
	const kept = block.collocates.filter((word) => word.target >= floor);
	const rows = kept.slice(0, Math.max(0, limit));

	if (rows.length === 0) {
		return nothing(
			{ kind: 'no-rows', speeches: block.speeches ?? null, minimum: null, floor },
			available
		);
	}

	return {
		rows,
		available,
		filtered: available - kept.length,
		truncated: kept.length - rows.length,
		refusal: null
	};
}
