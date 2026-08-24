export type SliceKind = 'by_country' | 'by_period' | 'by_speaker_group';
export type CloudFacet = 'whole' | SliceKind;
export type Alignment = 'rank' | 'word';
export type KeynessView = 'matched' | 'unmatched';

export interface LanguageState {
	node: string;
	width: string;
	sliceKind: SliceKind;
	sliceA: string;
	sliceB: string;
	align: Alignment;
	cloudFacet: CloudFacet;
	cloudNode: string;
	cloudWidth: string;
	cloudMember: string;
	cloudLimit: string;
	cloudFloor: string;
	keynessView: KeynessView;
	period: string;
}

export interface LanguageChoices {
	nodes: Record<string, readonly string[]>;
	slices: Record<SliceKind, readonly string[]>;
	periods: readonly string[];
	cloudDefault: { node: string; width: string };
}

const SLICE_KINDS: readonly SliceKind[] = ['by_country', 'by_period', 'by_speaker_group'];
const CLOUD_FACETS: readonly CloudFacet[] = ['whole', ...SLICE_KINDS];
const CLOUD_LIMITS = ['25', '40', '60', '100'] as const;
const CLOUD_FLOORS = ['0', '10', '25', '50'] as const;

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
	const cloudNode = choices.nodes[choices.cloudDefault.node] ? choices.cloudDefault.node : node;
	return {
		node,
		width: widthFor(choices, node),
		sliceKind,
		sliceA,
		sliceB,
		align: 'rank',
		cloudFacet: 'whole',
		cloudNode,
		cloudWidth: widthFor(choices, cloudNode, choices.cloudDefault.width),
		cloudMember: '',
		cloudLimit: '40',
		cloudFloor: '0',
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

	const askedFacet = params.get('cloud') as CloudFacet | null;
	const cloudFacet =
		askedFacet && CLOUD_FACETS.includes(askedFacet) ? askedFacet : defaults.cloudFacet;
	const askedCloudNode = params.get('cloud-node');
	const cloudNode =
		askedCloudNode && choices.nodes[askedCloudNode] ? askedCloudNode : defaults.cloudNode;
	const cloudWidth = widthFor(choices, cloudNode, params.get('cloud-width'));
	const askedMember = params.get('cloud-member');
	const cloudMember =
		cloudFacet !== 'whole' && askedMember && choices.slices[cloudFacet].includes(askedMember)
			? askedMember
			: cloudFacet === 'whole'
				? ''
				: (choices.slices[cloudFacet][0] ?? '');

	const askedLimit = params.get('words');
	const cloudLimit =
		askedLimit && CLOUD_LIMITS.includes(askedLimit as (typeof CLOUD_LIMITS)[number])
			? askedLimit
			: defaults.cloudLimit;
	const askedFloor = params.get('floor');
	const cloudFloor =
		askedFloor && CLOUD_FLOORS.includes(askedFloor as (typeof CLOUD_FLOORS)[number])
			? askedFloor
			: defaults.cloudFloor;
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
		cloudFacet,
		cloudNode,
		cloudWidth,
		cloudMember,
		cloudLimit,
		cloudFloor,
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
	if (state.cloudFacet !== defaults.cloudFacet) params.set('cloud', state.cloudFacet);
	if (state.cloudFacet === 'whole') {
		if (state.cloudNode !== defaults.cloudNode) params.set('cloud-node', state.cloudNode);
		if (state.cloudWidth !== widthFor(choices, state.cloudNode, choices.cloudDefault.width)) {
			params.set('cloud-width', state.cloudWidth);
		}
	} else if (state.cloudMember !== choices.slices[state.cloudFacet][0]) {
		params.set('cloud-member', state.cloudMember);
	}
	if (state.cloudLimit !== defaults.cloudLimit) params.set('words', state.cloudLimit);
	if (state.cloudFloor !== defaults.cloudFloor) params.set('floor', state.cloudFloor);
	if (state.keynessView !== defaults.keynessView) params.set('comparison', state.keynessView);
	if (state.period !== defaults.period) params.set('period', state.period);
	return params;
}
