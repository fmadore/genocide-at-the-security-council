<script lang="ts">
	import { resolve } from '$app/paths';
	import { goto, replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Chart from '$lib/Chart.svelte';
	import Contents from '$lib/Contents.svelte';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import PageMeta from '$lib/PageMeta.svelte';
	import DotPlot from '$lib/DotPlot.svelte';
	import FrameProfile from '$lib/FrameProfile.svelte';
	import TermMatrix from '$lib/TermMatrix.svelte';
	import {
		facetLabel,
		frameLabel,
		frameDescription,
		facets,
		member as frameMemberOf,
		members as frameMembers,
		morphology,
		movers,
		profile as frameProfile
	} from '$lib/nodeframes';
	import {
		languageParams,
		profilePlan,
		readLanguageState,
		type Alignment,
		type KeynessView,
		type LanguageChoices,
		type ProfileFacet,
		type SliceKind
	} from '$lib/language';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import {
		count,
		decimal,
		escapeHtml,
		matchedOn,
		percent,
		shortCountry,
		signed,
		termLabel
	} from '$lib/format';
	import { axisX, axisY, colours, grid, textStyle, tooltip } from '$lib/theme';
	import { PAGE_METADATA } from '$lib/seo';
	import type { CollocateBlock, Word } from '$lib/types';
	import type { EChartsOption } from 'echarts';
	import { onMount, tick, untrack } from 'svelte';
	import { SvelteURLSearchParams } from 'svelte/reactivity';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	/* Live chart handles, for the image half of the export. */
	let scatterFigure = $state<Chart | null>(null);
	let dotFigure = $state<DotPlot | null>(null);
	let matrixFigure = $state<TermMatrix | null>(null);
	let frameFigure = $state<FrameProfile | null>(null);

	/** Every node at every window, not the one pair on screen. */
	function collocateTable(): ExportRequest {
		const rows: (string | number | boolean | null)[][] = [];
		for (const [name, node] of Object.entries(data.collocates.nodes)) {
			for (const [span, block] of Object.entries(node.widths)) {
				for (const word of block.collocates) {
					rows.push([
						name,
						span,
						word.word,
						word.target,
						word.reference,
						word.g2,
						word.log_ratio,
						word.log_dice ?? null,
						word.documents,
						word.meetings,
						word.dp,
						block.occurrences,
						block.window_tokens
					]);
				}
			}
		}
		return {
			title: 'The words that sit near a term',
			columns: [
				'node',
				'window',
				'word',
				'target',
				'reference',
				'g2',
				'log_ratio',
				'log_dice',
				'documents',
				'meetings',
				'dp',
				'node_occurrences',
				'window_tokens'
			],
			rows,
			provenance: provenanceOf(data.collocates.meta, 'lexical/collocates.json'),
			filters: [`node: ${termLabel(node)}`, `window: ±${width}`],
			scope: 'every node term at every window width the artefact holds'
		};
	}

	/** Every slice of every facet, with the speeches behind each so the minimum is checkable. */
	function slicedTable(): ExportRequest {
		const rows: (string | number | boolean | null)[][] = [];
		const facets = ['by_period', 'by_speaker_group', 'by_country'] as const;
		for (const facet of facets) {
			for (const [member, block] of Object.entries(data.sliced[facet])) {
				for (const word of block.collocates) {
					rows.push([
						facet,
						member,
						block.speeches ?? null,
						word.word,
						word.target,
						word.reference,
						word.g2,
						word.log_ratio,
						word.log_dice ?? null,
						word.documents,
						word.meetings,
						word.dp,
						block.occurrences,
						block.window_tokens,
						(block.speeches ?? 0) >= data.sliced.minimum_speeches
					]);
				}
			}
		}
		return {
			title: 'The same word in two mouths',
			columns: [
				'facet',
				'member',
				'speeches',
				'word',
				'target',
				'reference',
				'g2',
				'log_ratio',
				'log_dice',
				'documents',
				'meetings',
				'dp',
				'occurrences',
				'window_tokens',
				'meets_minimum'
			],
			rows,
			provenance: provenanceOf(data.sliced.meta, 'lexical/collocates_sliced.json'),
			filters: [`facet: ${sliceKind}`, `compared: ${sliceA} against ${sliceB}`],
			scope:
				`every member of every facet, including those under the ` +
				`${data.sliced.minimum_speeches}-speech minimum that the figure refuses to draw`
		};
	}

	/** Both readings — matched and unmatched — so the comparison survives the download. */
	function keynessTable(): ExportRequest {
		const rows: (string | number | boolean | null)[][] = [];
		const readings: [string, typeof data.keyness.keywords][] = [
			['matched', data.keyness.keywords],
			['unmatched', data.keyness.keywords_unmatched]
		];
		for (const [reading, words] of readings) {
			for (const word of words ?? []) {
				rows.push([
					reading,
					word.word,
					word.target,
					word.reference,
					word.g2,
					word.log_ratio,
					word.documents,
					word.meetings,
					word.dp
				]);
			}
		}
		return {
			title: 'Compared with a like-for-like speech',
			columns: [
				'reading',
				'word',
				'target',
				'reference',
				'g2',
				'log_ratio',
				'documents',
				'meetings',
				'dp'
			],
			rows,
			provenance: provenanceOf(data.keyness.meta, 'lexical/keyness.json'),
			filters: [
				`comparison: ${keynessView}`,
				`matched on: ${data.keyness.matched_on}`,
				`seed: ${data.keyness.seed}`,
				`coverage: ${percent(data.keyness.coverage)}`
			],
			scope: 'both comparisons: like-for-like and whole corpus'
		};
	}

	/** Whole-corpus and per-period edges, plus the edges the lexicon nests. */
	function networkTable(): ExportRequest {
		const rows: (string | number | boolean | null)[][] = [];
		for (const edge of data.network.edges) {
			rows.push(['all', edge.source, edge.target, edge.speeches, edge.pmi, edge.npmi, false]);
		}
		for (const [key, block] of Object.entries(data.network.by_period)) {
			for (const edge of block.edges) {
				rows.push([key, edge.source, edge.target, edge.speeches, edge.pmi, edge.npmi, false]);
			}
		}
		// A suppressed edge is published as endpoints only — the artefact drops its
		// statistics rather than shipping a number nothing may draw. Blank, not zero.
		for (const edge of data.network.suppressed_nested_edges ?? []) {
			rows.push(['all', edge.source, edge.target, null, null, null, true]);
		}
		return {
			title: 'Which terms travel together',
			columns: ['period', 'source', 'target', 'speeches', 'pmi', 'npmi', 'suppressed_as_nested'],
			rows,
			provenance: provenanceOf(data.network.meta, 'lexical/network.json'),
			filters: [`minimum: ${data.network.min_speeches} speeches`],
			scope:
				'whole-corpus and per-period edges, plus the nested edges the figure suppresses, ' +
				'flagged rather than omitted'
		};
	}

	/** Every frame in every slice of every facet, with the counts behind each. */
	function frameTable(): ExportRequest {
		const rows: (string | number | boolean | null)[][] = [];
		for (const row of data.frames.totals.frames) {
			rows.push([
				'whole corpus',
				'',
				data.frames.occurrences,
				row.frame,
				row.occurrences,
				row.share,
				row.share_low,
				row.share_high,
				row.matched ?? null,
				true
			]);
		}
		for (const [facet, slices] of Object.entries(data.frames.slices)) {
			for (const slice of slices) {
				for (const row of slice.frames) {
					rows.push([
						facet,
						slice.member,
						slice.occurrences,
						row.frame,
						row.occurrences,
						row.share,
						row.share_low,
						row.share_high,
						null,
						slice.sufficient
					]);
				}
			}
		}
		return {
			title: 'What the word is doing',
			columns: [
				'facet',
				'member',
				'member_occurrences',
				'frame',
				'occurrences',
				'share',
				'share_low',
				'share_high',
				'matched_before_precedence',
				'sufficient'
			],
			rows,
			provenance: provenanceOf(data.frames.meta, 'frames/frames.json'),
			filters: [`facet: ${facetLabel(frameFacet)}`, `member: ${frameMember}`],
			scope: 'every frame in every slice of every facet, the withheld ones included'
		};
	}

	let node = $state('genocide');
	let width = $state('5');
	let sliceKind = $state<SliceKind>('by_country');
	let sliceA = $state('Rwanda');
	let sliceB = $state('United States Of America');
	let period = $state('whole');
	let keynessView = $state<KeynessView>('matched');
	let urlReady = $state(false);

	const nodes = $derived(Object.keys(data.collocates.nodes));
	const widths = $derived(data.collocates.widths.map(String));
	const block = $derived(data.collocates.nodes[node].widths[width]);

	const sliceOptions = $derived(Object.keys(data.sliced[sliceKind]));
	const blockA = $derived<CollocateBlock | undefined>(data.sliced[sliceKind][sliceA]);
	const blockB = $derived<CollocateBlock | undefined>(data.sliced[sliceKind][sliceB]);

	$effect(() => {
		// Switching the kind of slice invalidates the two chosen members.
		const options = Object.keys(data.sliced[sliceKind]);
		if (!options.includes(sliceA)) sliceA = options[0];
		if (!options.includes(sliceB)) sliceB = options[1] ?? options[0];
	});

	/* The sliced artefact declares the fewest speeches it will stand a profile
	   on. Below it nothing is drawn — neither a cloud nor a table, and never the
	   whole corpus quietly substituted for the slice that was asked for. */
	const minimumSpeeches = $derived(data.sliced.minimum_speeches);

	/** Members of a slice read by their kind; only countries need shortening. */
	const memberLabel = (kind: string, name: string) =>
		kind === 'by_country' ? shortCountry(name) : name;

	/* --- What the word is doing -------------------------------------------- */

	/* Not in the URL state `language.ts` carries. Those four controls choose
	   which population a keyness table is computed over, and a reader sharing a
	   link means to share that; these two choose which slice is drawn beside a
	   baseline that never moves, and a link to the whole figure is the same
	   figure. */
	let frameFacet = $state(untrack(() => facets(data.frames)[0] ?? 'period'));
	let frameMember = $state(
		untrack(() => frameMembers(data.frames, facets(data.frames)[0] ?? 'period')[0]?.member ?? '')
	);

	$effect(() => {
		// Changing the facet invalidates the member chosen inside the old one.
		const options = frameMembers(data.frames, frameFacet).map((row) => row.member);
		if (options.length > 0 && !options.includes(frameMember)) frameMember = options[0];
	});

	const frameSlice = $derived(frameMemberOf(data.frames, frameFacet, frameMember));
	const frameRows = $derived(frameProfile(data.frames, frameSlice));
	const frameMovers = $derived(movers(frameRows));
	const frameForms = $derived(morphology(data.frames));

	/* The one category that is not the word applied to an event. Named here so
	   the two numbers the study quotes — the whole enumeration and the headline
	   count — are visibly one subtraction apart rather than two facts. */
	const perpetratorNoun = $derived(
		data.frames.morphology.categories.find((row) => row.category === 'perpetrator_noun')
			?.occurrences ?? 0
	);

	/* --- The same table, drawn as a cloud --------------------------------- */

	let profileFacet = $state<ProfileFacet>('whole');
	/* Opened on the term and window the sliced artefact was counted at, so that
	   the whole-corpus cloud and any facet of it are the same question put to
	   different populations rather than two different questions. Read once and
	   untracked: these are the initial positions of controls the reader then
	   owns, not a derivation of the payload. */
	let profileNode = $state(untrack(() => data.sliced.term));
	let profileWidth = $state(untrack(() => String(data.sliced.width)));
	let profileMember = $state('');
	let profileLimit = $state('40');
	let profileFloor = $state('0');

	const profileMembers = $derived(
		profileFacet === 'whole' ? [] : Object.keys(data.sliced[profileFacet])
	);

	$effect(() => {
		// Changing the facet invalidates the member chosen inside the old one.
		const options = profileFacet === 'whole' ? [] : Object.keys(data.sliced[profileFacet]);
		if (options.length > 0 && !options.includes(profileMember)) profileMember = options[0];
	});

	const profileBlock = $derived<CollocateBlock | undefined>(
		profileFacet === 'whole'
			? data.collocates.nodes[profileNode]?.widths[profileWidth]
			: data.sliced[profileFacet][profileMember]
	);

	/* One call chooses the rows. The cloud draws them and the table lists them,
	   so there is no arrangement of the controls under which the two disagree. */
	const profileSelection = $derived(
		profilePlan({
			block: profileBlock,
			minimumSpeeches: profileFacet === 'whole' ? null : minimumSpeeches,
			limit: Number(profileLimit),
			floor: Number(profileFloor)
		})
	);

	/* Slices exist for one term at one width only, and the controls say so
	   rather than implying the facet follows the Term and Window above. */
	const profileTerm = $derived(profileFacet === 'whole' ? profileNode : data.sliced.term);
	const profileSource = $derived(
		profileFacet === 'whole'
			? '05_lexical.py → lexical/collocates.json'
			: '05_lexical.py → lexical/collocates_sliced.json'
	);
	const profileScope = $derived(
		profileFacet === 'whole' ? 'the whole corpus' : memberLabel(profileFacet, profileMember)
	);

	const keywords = $derived(
		keynessView === 'matched' ? data.keyness.keywords : data.keyness.keywords_unmatched
	);
	/** The dispersion cell: speeches / meetings, with a dash where no meeting was counted. */
	const spread = (word: { documents: number; meetings: number | null }) =>
		`${count(word.documents)} / ${word.meetings == null ? '—' : count(word.meetings)}`;

	const matchedByWord = $derived(new Map(data.keyness.keywords.map((w) => [w.word, w.log_ratio])));

	/* Zoom is held here rather than left inside ECharts so that "Reset" can put it
	   back. Assigning a fresh object rebuilds the option, and Chart.svelte applies
	   options with `notMerge`, so the chart returns to the full extent even from a
	   view the reader zoomed by hand. Changing term or window resets it for the
	   same reason — a window kept across a change of data would frame nothing. */
	const FULL = { start: 0, end: 100 };
	let zoomWindow = $state({ x: { ...FULL }, y: { ...FULL } });
	const resetZoom = () => {
		zoomWindow = { x: { ...FULL }, y: { ...FULL } };
	};

	/* Effect size against significance. Every word is a point; the ones that
	   matter are up and to the right, and the ones that only look significant
	   are far right and low. */
	const scatter: EChartsOption = $derived.by(() => {
		const p = $colours;
		const words = block.collocates;
		return {
			textStyle,
			grid: { ...grid(), top: 20, right: 28, bottom: 56 },
			tooltip: {
				...tooltip(p),
				trigger: 'item',
				formatter: (params) => {
					const d = params as unknown as { data: [number, number, string, number] };
					return (
						`<b>${escapeHtml(d.data[2])}</b><br>${count(d.data[3])} in window` +
						`<br>G² ${count(Math.round(d.data[0]))}<br>log ratio ${signed(d.data[1])}`
					);
				}
			},
			xAxis: {
				...axisX(p),
				type: 'log',
				name: 'G² (frequency difference)',
				nameLocation: 'middle',
				nameGap: 28,
				nameTextStyle: { color: p.inkFaint, fontSize: 11 },
				splitLine: { show: true, lineStyle: { color: p.ruleSoft } }
			},
			yAxis: {
				...axisY(p),
				type: 'value',
				name: 'log ratio (relative frequency)',
				nameLocation: 'middle',
				nameGap: 34,
				nameTextStyle: { color: p.inkFaint, fontSize: 11 }
			},
			// Most collocates crowd into the low-G² corner, where `hideOverlap` drops
			// the labels of whatever it has to and the words that survive are chosen
			// by draw order rather than by interest. Zoom is the honest fix: no point
			// is removed, and a reader who wants the dense corner can go and read it.
			// `filterMode: 'none'` clips rather than filters, so the other axis keeps
			// its scale and a zoomed view stays comparable to the full one.
			dataZoom: [
				{ type: 'inside', xAxisIndex: 0, filterMode: 'none', ...zoomWindow.x },
				{ type: 'inside', yAxisIndex: 0, filterMode: 'none', ...zoomWindow.y },
				{
					type: 'slider',
					xAxisIndex: 0,
					filterMode: 'none',
					height: 16,
					bottom: 4,
					borderColor: p.rule,
					fillerColor: p.accent + '22',
					handleStyle: { color: p.accent },
					textStyle: { color: p.inkFaint, fontSize: 11 },
					...zoomWindow.x
				}
			],
			series: [
				{
					type: 'scatter',
					symbolSize: 7,
					data: words.map((w) => [Math.max(w.g2, 1), w.log_ratio, w.word, w.target]),
					itemStyle: { color: p.inkSoft, opacity: 0.55 },
					label: {
						show: true,
						formatter: (params) =>
							String((params as unknown as { data: [number, number, string] }).data[2]),
						position: 'right',
						color: p.inkSoft,
						fontSize: 11
					},
					labelLayout: { hideOverlap: true },
					emphasis: { itemStyle: { opacity: 1 } }
				}
			]
		};
	});

	const periods = $derived(['whole', ...Object.keys(data.network.by_period)]);

	/* The matrix's rows: every active term, with the period's own speech counts
	   where a period is chosen, so the diagonal says what the cells divide by. */
	const matrixTerms = $derived.by(() => {
		const periodBlock = period === 'whole' ? null : data.network.by_period[period];
		const periodCounts = new Map(periodBlock?.terms.map((term) => [term.name, term.speeches]));
		return data.network.terms.map((term) => ({
			name: term.name,
			register: term.register,
			speeches: periodCounts.get(term.name) ?? term.speeches
		}));
	});
	const matrixEdges = $derived(
		period === 'whole' ? data.network.edges : (data.network.by_period[period]?.edges ?? [])
	);

	function topWords(b: CollocateBlock | undefined, n = 18): Word[] {
		return b?.collocates.slice(0, n) ?? [];
	}

	/**
	 * Two ways to set the two profiles against each other, because they answer
	 * different questions.
	 *
	 *   rank   each column's own strongest collocates, in its own order. Rows do
	 *          not correspond, and the finding is that the two *sets* differ.
	 *   word   one word per row, both sides' figures for it. Rows correspond, and
	 *          the finding is how far apart the two are on the same word — with
	 *          an em dash where the word is not in the other profile at all.
	 */
	let align = $state<Alignment>('rank');

	const urlChoices: LanguageChoices = $derived.by(() => ({
		nodes: Object.fromEntries(
			Object.entries(data.collocates.nodes).map(([name, block]) => [
				name,
				Object.keys(block.widths)
			])
		),
		slices: {
			by_country: Object.keys(data.sliced.by_country),
			by_period: Object.keys(data.sliced.by_period),
			by_speaker_group: Object.keys(data.sliced.by_speaker_group)
		},
		periods: ['whole', ...Object.keys(data.network.by_period)],
		profileDefault: { node: data.sliced.term, width: String(data.sliced.width) }
	}));

	onMount(() => {
		const state = readLanguageState(page.url.searchParams, urlChoices);
		node = state.node;
		width = state.width;
		sliceKind = state.sliceKind;
		sliceA = state.sliceA;
		sliceB = state.sliceB;
		align = state.align;
		profileFacet = state.profileFacet;
		profileNode = state.profileNode;
		profileWidth = state.profileWidth;
		profileMember = state.profileMember;
		profileLimit = state.profileLimit;
		profileFloor = state.profileFloor;
		keynessView = state.keynessView;
		period = state.period;
		void tick().then(() => {
			urlReady = true;
		});
	});

	$effect(() => {
		if (!urlReady) return;
		const params = languageParams(
			{
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
			},
			urlChoices
		);
		const search = params.toString();
		replaceState(`${page.url.pathname}${search ? `?${search}` : ''}`, page.state);
	});

	const alignedRows = $derived.by(() => {
		const inA = new Map((blockA?.collocates ?? []).map((w) => [w.word, w]));
		const inB = new Map((blockB?.collocates ?? []).map((w) => [w.word, w]));
		const words = [
			...new Set([...topWords(blockA).map((w) => w.word), ...topWords(blockB).map((w) => w.word)])
		];
		return words
			.map((word) => ({ word, a: inA.get(word) ?? null, b: inB.get(word) ?? null }))
			.sort(
				(x, y) =>
					Math.max(y.a?.log_ratio ?? 0, y.b?.log_ratio ?? 0) -
					Math.max(x.a?.log_ratio ?? 0, x.b?.log_ratio ?? 0)
			);
	});

	/**
	 * One scale for both columns. Normalising each side to its own maximum would
	 * make two bars of equal length mean two different numbers, which is the one
	 * thing a side-by-side comparison must not do.
	 */
	const compareTop = $derived(
		Math.max(
			...(align === 'word'
				? alignedRows.flatMap((r) => [r.a?.log_ratio ?? 0, r.b?.log_ratio ?? 0])
				: [...topWords(blockA), ...topWords(blockB)].map((w) => w.log_ratio)),
			0
		) || 1
	);

	const barWidth = (value: number | null | undefined) =>
		value == null ? '0%' : `${Math.max(1.5, (value / compareTop) * 100)}%`;

	const sliceLabel = (name: string) => memberLabel(sliceKind, name);
	const concordanceHref = (term: string, query = '') => {
		const params = new SvelteURLSearchParams({ term });
		if (query) params.set('q', query);
		return `${resolve('/concordance')}?${params}`;
	};
	const openCollocate = (params: { value?: unknown }) => {
		const value = params.value as [number, number, string] | undefined;
		if (value?.[2]) void goto(concordanceHref(node, value[2]));
	};
</script>

<PageMeta meta={PAGE_METADATA['/language/']} />

<article>
	<header class="lede">
		<h1>Words in context</h1>
		<p class="standfirst">
			Examine the phrases around <em>genocide</em>, the words commonly used nearby and the terms
			found in the same speech. Compare periods and speakers, then follow a word to its passages to
			assess how it was used.
		</p>
		<p class="standfirst">
			A <strong>collocate</strong> is a word found near a selected term. <strong>Keyness</strong>
			measures how much more frequent a word is in one set of speeches than in a comparison set. These
			measures identify passages to investigate; they do not determine a speaker's position.
			<a href="{resolve('/methods')}#lexical-measures">Guide to the table measures</a>.
		</p>
	</header>

	<Contents
		figures={[
			{ title: 'What the word is doing' },
			{ title: 'The words that sit near a term' },
			{ title: 'The profile of a term' },
			{ title: 'The same word in two mouths' },
			{ title: 'Compared with a like-for-like speech' },
			{ title: 'Which terms travel together' }
		]}
	/>

	<Figure
		title="What the word is doing"
		question="What construction is the word in when it is said, and does that differ by period or by speaker?"
		source="17_frames.py → frames/frames.json"
		download={{
			name: ['unsc', 'frames', frameFacet, frameMember],
			table: frameTable,
			chart: () => frameFigure?.svg() ?? null
		}}
	>
		{#snippet controls()}
			<label>
				Compare by
				<select bind:value={frameFacet}>
					{#each facets(data.frames) as facet (facet)}
						<option value={facet}>{facetLabel(facet)}</option>
					{/each}
				</select>
			</label>
			<label>
				Group or period
				<select bind:value={frameMember}>
					{#each frameMembers(data.frames, frameFacet) as slice (slice.member)}
						<option value={slice.member}>{slice.member} ({count(slice.occurrences)})</option>
					{/each}
				</select>
			</label>
			<span class="unit-note">
				{count(data.frames.occurrences)} occurrences of
				<em>{data.frames.term}</em>, ±{data.frames.window} characters read round each
			</span>
		{/snippet}

		{#snippet reading()}
			<p>
				Each row is a phrase pattern, such as <em>acts of genocide</em>, ranked by its share of all {count(
					data.frames.occurrences
				)} matches. The open dot shows the whole corpus; the filled dot shows your selected group or period.
				Whiskers show 95% intervals. A blue mark flags intervals that exclude the whole-corpus share.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				The denominator is occurrences of the word. Patterns follow written rules and can miss
				context. Blue marks are exploratory: intervals are not adjusted for comparing many rows or
				for repeated mentions within meetings. They do not establish differences in political
				positions.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				Rules are tested in a fixed order; the first matching pattern receives the occurrence. <em
					>Matched</em
				>
				counts matches before that priority rule. <em>No pattern matched</em> contains occurrences that
				no pattern captures, so changes in that category can affect the others' shares.
			</p>
			<p>
				Groups below {count(data.frames.minimum_occurrences)} occurrences show counts only. The spelling
				breakdown separately identifies {count(perpetratorNoun)} uses of <em>génocidaire</em> or
				<em>génocidaires</em>, words for perpetrators, out of {count(data.frames.occurrences)} matches.
			</p>
		{/snippet}

		<FrameProfile
			bind:this={frameFigure}
			rows={frameRows}
			slice={frameSlice?.member ?? ''}
			description="Dot plot of the constructions the word genocide appears in, each row showing its share of all occurrences beside its share in the chosen period or speaker group, with a 95% interval."
		/>
		{#if frameMovers.length}
			<p class="note-line mover">
				Furthest from the corpus profile here:
				{#each frameMovers as row, index (row.frame)}{index > 0 ? ', ' : ''}{frameLabel(row.frame)}
					{percent(row.share ?? 0)} against {percent(row.overall)}{/each}.
			</p>
		{/if}

		<details class="data-table">
			<summary><Icon icon={ChevronRight} />Phrase patterns, explanations and examples</summary>
			<table>
				<thead
					><tr
						><th>Phrase pattern</th><th class="num">Assigned occurrences</th><th class="num"
							>Pattern matches</th
						><th>How to interpret it</th><th>Example</th></tr
					></thead
				>
				<tbody>
					{#each frameRows as row (row.frame)}
						<tr>
							<td>{frameLabel(row.frame)}</td>
							<td class="num">{count(row.overallOccurrences)}</td>
							<td class="num"
								>{count(
									data.frames.totals.frames.find((f) => f.frame === row.frame)?.matched ?? 0
								)}</td
							>
							<td>{frameDescription(row.frame, row.gloss)}</td>
							<td class="quote"
								>{data.frames.codebook.find((entry) => entry.frame === row.frame)?.example ??
									'—'}</td
							>
						</tr>
					{/each}
				</tbody>
			</table>
		</details>

		<details class="data-table">
			<summary
				><Icon icon={ChevronRight} />View the word itself: noun, adjective, perpetrator noun</summary
			>
			<table>
				<thead
					><tr
						><th>Form</th><th class="num">Occurrences</th><th class="num">Share</th><th
							>Spellings in the corpus</th
						></tr
					></thead
				>
				<tbody>
					{#each frameForms as row (row.category)}
						<tr>
							<td>{termLabel(row.category)}</td>
							<td class="num">{count(row.occurrences)}</td>
							<td class="num">{percent(row.share)}</td>
							<td class="quote">{row.forms.join(', ')}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</details>
	</Figure>

	<Figure
		fullscreen
		onfullscreenchange={() => scatterFigure?.resize()}
		title="The words that sit near a term"
		question="Which words appear near this term far more often than chance would put them there?"
		source="05_lexical.py → lexical/collocates.json"
		download={{
			name: ['unsc', 'collocates', node, `w${width}`],
			table: collocateTable,
			chart: () => scatterFigure?.svg() ?? null
		}}
	>
		{#snippet controls()}
			<label>
				Term
				<select bind:value={node}>
					{#each nodes as n (n)}<option value={n}>{termLabel(n)}</option>{/each}
				</select>
			</label>
			<label>
				Window
				<select bind:value={width}>
					{#each widths as w (w)}<option value={w}>&plusmn;{w} words</option>{/each}
				</select>
			</label>
			<button type="button" class="ghost" onclick={resetZoom}>Reset zoom</button>
			<span class="unit-note"
				>{count(block.occurrences)} occurrences, {count(block.window_tokens)} words in window</span
			>
		{/snippet}

		{#snippet reading()}
			<p>
				Each point is a nearby word. Higher points have a larger relative frequency (log ratio): +3
				means eight times the comparison rate. Further right means a larger G² statistic, which
				tests a difference in frequency. The horizontal axis is logarithmic. Hover for values;
				select a word to read passages.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				G² is sensitive to the number of words counted: a large value can accompany a small
				difference. A ±5-word window focuses on nearby phrasing; ±15 includes more surrounding text.
				Neither window captures the meaning of a whole speech.
			</p>
		{/snippet}

		<Chart
			bind:this={scatterFigure}
			option={scatter}
			height="440px"
			description="Scatter plot of the words near the term, G² along the horizontal axis and log ratio on the vertical axis."
			onclick={openCollocate}
		/>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View the leading collocates as a table</summary>
			<table>
				<thead
					><tr
						><th>Word</th><th class="num">Near</th><th
							class="num"
							title="Tests a difference in word frequency; a larger value can also reflect more text."
							>G²</th
						><th
							class="num"
							title="+1 means twice as frequent; +2 means four times. Negative values mean less frequent."
							>Log ratio</th
						><th
							class="num"
							title="Association score adjusted for term and word frequencies. Higher means a stronger association."
							>logDice</th
						><th class="num">Speeches / meetings</th><th
							class="num"
							title="Dispersion: near 0 is broadly distributed relative to speech length; near 1 is concentrated."
							>Spread (DP)</th
						></tr
					></thead
				>
				<tbody>
					{#each block.collocates.slice(0, 30) as word (word.word)}
						<tr>
							<td><a href={concordanceHref(node, word.word)}>{word.word}</a></td>
							<td class="num">{count(word.target)}</td>
							<td class="num">{count(Math.round(word.g2))}</td>
							<td class="num">{signed(word.log_ratio)}</td>
							<td class="num">{word.log_dice == null ? '—' : decimal(word.log_dice)}</td>
							<td class="num">{spread(word)}</td>
							<td class="num">{decimal(word.dp)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</details>
	</Figure>

	<Figure
		title="The profile of a term"
		question="Which words mark this term's neighbourhood, and does the profile hold for one speaker or one decade?"
		source={profileSource}
		download={{
			name: ['unsc', 'collocates', 'profile', profileFacet],
			table: collocateTable,
			chart: () => dotFigure?.svg() ?? null
		}}
	>
		{#snippet controls()}
			<label>
				Drawn from
				<select bind:value={profileFacet}>
					<option value="whole">Whole corpus</option>
					<option value="by_country">One speaker</option>
					<option value="by_speaker_group">One speaker group</option>
					<option value="by_period">One period</option>
				</select>
			</label>
			{#if profileFacet === 'whole'}
				<label>
					Term
					<select bind:value={profileNode}>
						{#each nodes as n (n)}<option value={n}>{termLabel(n)}</option>{/each}
					</select>
				</label>
				<label>
					Window
					<select bind:value={profileWidth}>
						{#each widths as w (w)}<option value={w}>&plusmn;{w} words</option>{/each}
					</select>
				</label>
			{:else}
				<label>
					Which
					<select bind:value={profileMember}>
						{#each profileMembers as m (m)}<option value={m}>{memberLabel(profileFacet, m)}</option
							>{/each}
					</select>
				</label>
				<span class="fixed"
					>{termLabel(data.sliced.term)} at &plusmn;{data.sliced.width} words, the only term and window
					these breakdowns were counted at</span
				>
			{/if}
			<label>
				Words
				<select bind:value={profileLimit}>
					<option value="25">25</option>
					<option value="40">40</option>
					<option value="60">60</option>
					<option value="100">100</option>
				</select>
			</label>
			<label>
				At least
				<select bind:value={profileFloor}>
					<option value="0">any frequency</option>
					<option value="10">10 beside the term</option>
					<option value="25">25 beside the term</option>
					<option value="50">50 beside the term</option>
				</select>
			</label>
			<span class="unit-note"
				>nothing is drawn for a set of fewer than {count(minimumSpeeches)} speeches</span
			>
		{/snippet}

		{#snippet reading()}
			<p>
				Words are ranked by logDice, an association score that accounts for how often each word
				occurs. Dot position shows relative frequency (log ratio); dot size shows the count near the
				term. The spread marker fills as usage becomes more evenly distributed across speeches.
				Select a word to read its passages.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Word forms are separate: <em>crime</em> and <em>crimes</em> occupy different rows. Profiles based
				on few speeches may be dominated by particular meetings or topics. Check the speech and meeting
				counts before generalising about a period or delegation.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				The analysis removes {count(data.collocates.meta.stopwords as number)} common function words listed
				in <code>config/stopwords.txt</code>. Words such as <em>council</em> and <em>resolution</em>
				remain. A word needs at least {count(data.collocates.meta.min_count as number)} occurrences near
				the term and G² above {decimal(data.collocates.meta.g2_floor as number)} to enter the published
				list.
				<a href="{resolve('/methods')}#lexical-measures"
					>Definitions of G², log ratio, logDice and spread (DP)</a
				>.
			</p>
		{/snippet}

		{#if profileSelection.refusal?.kind === 'below-minimum'}
			<p class="withheld">
				<strong>{memberLabel(profileFacet, profileMember)}</strong> has {count(
					profileSelection.refusal.speeches ?? 0
				)} speeches using the term, below the minimum of {count(
					profileSelection.refusal.minimum ?? 0
				)}. Choose another group or the whole corpus to view a profile.
			</p>
		{:else if profileSelection.refusal}
			<p class="withheld">
				No word in {profileScope} occurs at least {profileFloor} times beside the term, so there is nothing
				to draw. Lower the minimum frequency.
			</p>
		{:else}
			<DotPlot
				bind:this={dotFigure}
				rows={profileSelection.rows}
				term={termLabel(profileTerm)}
				href={(word) => concordanceHref(profileTerm, word.word)}
				description="Dot plot of the words that sit near the term: position by log ratio, area by frequency, a spread mark per word; each word links to its lines in the concordance."
			/>
			<p class="stated">
				{count(profileSelection.rows.length)} words drawn, out of {count(
					profileSelection.available
				)}
				held for {profileScope}: {count(profileSelection.filtered)} fall below the minimum frequency and
				{count(profileSelection.truncated)} beyond the number asked for. The table holds the same words,
				in the same order.
			</p>
			<details class="data-table">
				<summary><Icon icon={ChevronRight} />View the same words as a table</summary>
				<table>
					<thead
						><tr
							><th>Word</th><th class="num">Near</th><th
								class="num"
								title="Tests a difference in word frequency; a larger value can also reflect more text."
								>G²</th
							><th
								class="num"
								title="+1 means twice as frequent; +2 means four times. Negative values mean less frequent."
								>Log ratio</th
							><th
								class="num"
								title="Association score adjusted for term and word frequencies. Higher means a stronger association."
								>logDice</th
							><th class="num">Speeches / meetings</th><th
								class="num"
								title="Dispersion: near 0 is broadly distributed relative to speech length; near 1 is concentrated."
								>Spread (DP)</th
							></tr
						></thead
					>
					<tbody>
						{#each profileSelection.rows as word (word.word)}
							<tr>
								<td><a href={concordanceHref(profileTerm, word.word)}>{word.word}</a></td>
								<td class="num">{count(word.target)}</td>
								<td class="num">{count(Math.round(word.g2))}</td>
								<td class="num">{signed(word.log_ratio)}</td>
								<td class="num">{word.log_dice == null ? '—' : decimal(word.log_dice)}</td>
								<td class="num">{spread(word)}</td>
								<td class="num">{decimal(word.dp)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</details>
		{/if}
	</Figure>

	<Figure
		title="The same word in two mouths"
		question="Do different speakers, groups or decades use it to do different work?"
		source="05_lexical.py → lexical/collocates_sliced.json"
		download={{ name: ['unsc', 'collocates-sliced', sliceKind], table: slicedTable }}
	>
		{#snippet controls()}
			<label>
				Compare by
				<select bind:value={sliceKind}>
					<option value="by_country">Speaker</option>
					<option value="by_speaker_group">Speaker group</option>
					<option value="by_period">Period</option>
				</select>
			</label>
			<label>
				Left
				<select bind:value={sliceA}>
					{#each sliceOptions as o (o)}<option value={o}>{sliceLabel(o)}</option>{/each}
				</select>
			</label>
			<label>
				Right
				<select bind:value={sliceB}>
					{#each sliceOptions as o (o)}<option value={o}>{sliceLabel(o)}</option>{/each}
				</select>
			</label>
			<div class="view">
				<span class="label" id="align-view">Align</span>
				<div class="segmented" role="group" aria-labelledby="align-view">
					<button
						type="button"
						aria-pressed={align === 'rank'}
						title="Each column's own strongest collocates, in its own order"
						onclick={() => (align = 'rank')}>By rank</button
					>
					<button
						type="button"
						aria-pressed={align === 'word'}
						title="One word per row, with both sides' figures for it"
						onclick={() => (align = 'word')}>By word</button
					>
				</div>
			</div>
			<span class="unit-note"
				>nothing is drawn for a set of fewer than {count(minimumSpeeches)} speeches</span
			>
		{/snippet}

		{#snippet reading()}
			<p>
				Both profiles count words within ±{data.sliced.width} words of <em>genocide</em>. Bar length
				shows log ratio against the corpus on a shared scale. <strong>By rank</strong> shows each
				side's top words; <strong>by word</strong> aligns the same word across both sides. A dash means
				it is absent from that side's published list.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				These sets of speeches differ enormously in size, which is why each heading prints its
				count; a list from fifty speeches is a sketch. Comparing two periods mixes who was speaking
				with when: membership and the agenda both turn over.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				Compare the same word on both sides, then open its passages. Differences may reflect
				recurring topics, unequal speech totals or choices of expression. A word missing from a
				published list may fall below its frequency or G² threshold; it need not be absent from the
				speeches.
			</p>
		{/snippet}

		{#if align === 'rank'}
			<!-- Parallel text: the oldest scholarly layout there is. One profile per
			     column, a rule down the middle. Rows do not correspond, and the
			     finding is that the two sets of words differ. -->
			<div class="compare">
				{#each [{ key: sliceA, b: blockA }, { key: sliceB, b: blockB }] as side, i (side.key)}
					{#if i === 1}<div class="gutter" aria-hidden="true"></div>{/if}
					<div class="side">
						<h4>
							<span class="who">{sliceLabel(side.key)}</span>
							<span class="symbol"
								>{count(side.b?.speeches ?? 0)} speeches · {count(side.b?.occurrences ?? 0)} occurrences</span
							>
						</h4>
						{#if (side.b?.speeches ?? 0) < minimumSpeeches}
							<p class="withheld">
								{count(side.b?.speeches ?? 0)} speeches, fewer than the {count(minimumSpeeches)} required
								before a list is drawn. Nothing is shown for this side.
							</p>
						{:else}
							<ol class="profile">
								{#each topWords(side.b) as w (w.word)}
									<li>
										<a href={concordanceHref('genocide', w.word)}>{w.word}</a>
										<span
											class="bar"
											style:width={barWidth(w.log_ratio)}
											title="{count(w.target)} beside the term · G² {count(Math.round(w.g2))}"
										></span>
										<span class="symbol">{signed(w.log_ratio)}</span>
									</li>
								{/each}
							</ol>
						{/if}
					</div>
				{/each}
			</div>
		{:else if (blockA?.speeches ?? 0) < minimumSpeeches || (blockB?.speeches ?? 0) < minimumSpeeches}
			<p class="withheld">
				One of these two sets holds fewer than the {count(minimumSpeeches)} speeches required before a
				list is drawn, so there is nothing to line the other one up against.
			</p>
		{:else}
			<!-- One word per row, read outwards from the middle: the same layout a
			     parallel text uses for a shared lemma, and the only arrangement in
			     which the two bars on a row mean the same thing. -->
			<div class="pyramid">
				<div class="prow head">
					<span class="symbol">{count(blockA?.speeches ?? 0)} sp.</span>
					<span class="who left">{sliceLabel(sliceA)}</span>
					<span></span>
					<span class="who">{sliceLabel(sliceB)}</span>
					<span class="symbol">{count(blockB?.speeches ?? 0)} sp.</span>
				</div>
				{#each alignedRows as row (row.word)}
					<div class="prow">
						<span class="symbol">{row.a ? signed(row.a.log_ratio) : '—'}</span>
						<span class="track left">
							{#if row.a}
								<span
									class="bar"
									style:width={barWidth(row.a.log_ratio)}
									title="{count(row.a.target)} beside the term · G² {count(Math.round(row.a.g2))}"
								></span>
							{/if}
						</span>
						<a class="word" href={concordanceHref('genocide', row.word)}>{row.word}</a>
						<span class="track">
							{#if row.b}
								<span
									class="bar"
									style:width={barWidth(row.b.log_ratio)}
									title="{count(row.b.target)} beside the term · G² {count(Math.round(row.b.g2))}"
								></span>
							{/if}
						</span>
						<span class="symbol">{row.b ? signed(row.b.log_ratio) : '—'}</span>
					</div>
				{/each}
			</div>
		{/if}

		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View both profiles as a table</summary>
			<table>
				<thead>
					<tr
						><th>Profile</th><th>Word</th><th class="num">Near</th><th
							class="num"
							title="Tests a difference in word frequency; a larger value can also reflect more text."
							>G²</th
						><th
							class="num"
							title="+1 means twice as frequent; +2 means four times. Negative values mean less frequent."
							>Log ratio</th
						><th
							class="num"
							title="Association score adjusted for term and word frequencies. Higher means a stronger association."
							>logDice</th
						><th class="num">Speeches / meetings</th><th
							class="num"
							title="Dispersion: near 0 is broadly distributed relative to speech length; near 1 is concentrated."
							>Spread (DP)</th
						></tr
					>
				</thead>
				<tbody>
					{#each [{ key: sliceA, b: blockA }, { key: sliceB, b: blockB }] as side (side.key)}
						{#each topWords(side.b) as w (w.word)}
							<tr>
								<td>{sliceLabel(side.key)}</td>
								<td>{w.word}</td>
								<td class="num">{count(w.target)}</td>
								<td class="num">{count(Math.round(w.g2))}</td>
								<td class="num">{signed(w.log_ratio)}</td>
								<td class="num">{w.log_dice == null ? '—' : decimal(w.log_dice)}</td>
								<td class="num">{spread(w)}</td>
								<td class="num">{decimal(w.dp)}</td>
							</tr>
						{/each}
					{/each}
				</tbody>
			</table>
		</details>
	</Figure>

	<Figure
		title="Compared with a like-for-like speech"
		question="Which words are more frequent in speeches mentioning genocide than in the selected comparison set?"
		source="05_lexical.py → lexical/keyness.json"
		download={{ name: ['unsc', 'keyness', keynessView], table: keynessTable }}
	>
		{#snippet controls()}
			<label>
				Comparison
				<select bind:value={keynessView}>
					<option value="matched">A like-for-like speech</option>
					<option value="unmatched">The whole corpus</option>
				</select>
			</label>
			<span class="unit-note">
				{count(data.keyness.control_speeches)} of {count(data.keyness.eligible_target_speeches)} speeches
				found a partner ({percent(data.keyness.coverage)})
			</span>
		{/snippet}

		{#snippet reading()}
			<p>
				{#if keynessView === 'matched'}Each speech mentioning genocide is paired with one without
					it, sharing its {matchedOn(data.keyness.matched_on)}.{:else}Speeches mentioning genocide
					are compared with the rest of the corpus, without matching.{/if} Rows rank relative word frequency
				(log ratio), after a G² threshold. Speech and meeting counts show how widely each word occurs.
				<a href="{resolve('/methods')}#keyness">Matching details</a>.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Matching reduces differences in the recorded context but cannot isolate the meaning of
				genocide or remove all topic differences. {data.keyness.short_strata.length} groups have fewer
				available partners than target speeches. The whole-corpus comparison is more exposed to differences
				in agenda and period.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				Switch comparisons to see which words remain distinctive after matching. The partner
				selection was repeated {data.keyness.stability.repetitions} times to assess sensitivity to the
				draw; the source data record the resulting ranges. The
				<a href="{resolve('/actors')}#speaker-keyness">Actors page</a> makes a separate comparison for
				each delegation's vocabulary.
			</p>
		{/snippet}

		<table>
			<thead>
				<tr>
					<th>#</th>
					<th>Word</th>
					<th class="num">In these speeches</th>
					<th
						class="num"
						title="Tests a difference in word frequency; a larger value can also reflect more text."
						>G²</th
					>
					<th
						class="num"
						title="+1 means twice as frequent; +2 means four times. Negative values mean less frequent."
						>Log ratio</th
					>
					<th class="num">Speeches / meetings</th>
					<th
						class="num"
						title="Dispersion: near 0 is broadly distributed relative to speech length; near 1 is concentrated."
						>Spread (DP)</th
					>
					{#if keynessView === 'unmatched'}<th class="num">Like-for-like</th>{/if}
				</tr>
			</thead>
			<tbody>
				{#each keywords.slice(0, 30) as w, i (w.word)}
					<tr>
						<td class="num rank">{i + 1}</td>
						<td><a href={concordanceHref('genocide', w.word)}>{w.word}</a></td>
						<td class="num">{count(w.target)}</td>
						<td class="num">{count(Math.round(w.g2))}</td>
						<td class="num">{signed(w.log_ratio)}</td>
						<td class="num">{spread(w)}</td>
						<td class="num">{decimal(w.dp)}</td>
						{#if keynessView === 'unmatched'}
							<td class="num" class:gone={!matchedByWord.has(w.word)}>
								{matchedByWord.has(w.word) ? signed(matchedByWord.get(w.word)!) : 'drops out'}
							</td>
						{/if}
					</tr>
				{/each}
			</tbody>
		</table>
	</Figure>

	<Figure
		title="Which terms travel together"
		question="Does this vocabulary hold together in groups, or is it just a list?"
		source="05_lexical.py → lexical/network.json"
		download={{
			name: ['unsc', 'network'],
			table: networkTable,
			chart: () => matrixFigure?.svg() ?? null
		}}
	>
		{#snippet controls()}
			<label>
				Period
				<select bind:value={period}>
					{#each periods as p (p)}
						<option value={p}>{p === 'whole' ? 'Whole corpus' : p}</option>
					{/each}
				</select>
			</label>
			<span class="unit-note">
				a pair is shaded where at least {data.network.min_speeches} speeches use both terms
			</span>
		{/snippet}

		{#snippet reading()}
			<p>
				Each cell compares two terms. Darker shading means a stronger association within speeches,
				measured by nPMI relative to their individual frequencies. Hatched cells have fewer than {data
					.network.min_speeches} shared speeches. Crossed cells mark overlapping search patterns, such
				as a word within a longer phrase. Hover for counts and scores.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Terms can occur anywhere in the same speech; they need not form a phrase or express the same
				position. The score adjusts for individual frequencies, but rare pairs can still be
				unstable. Read the shared-speech count alongside the shading.
			</p>
		{/snippet}

		<TermMatrix
			bind:this={matrixFigure}
			terms={matrixTerms}
			edges={matrixEdges}
			suppressed={data.network.suppressed_nested_edges ?? []}
			minimum={data.network.min_speeches}
			href={(term) => concordanceHref(term)}
			description="Matrix of the word list's terms, ordered by register, with each cell shaded by how much more often two terms share a speech than chance would put them together."
		/>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View the strongest term associations as a table</summary>
			<table>
				<thead
					><tr
						><th>Source</th><th>Target</th><th class="num">Shared speeches</th><th class="num"
							>nPMI</th
						></tr
					></thead
				>
				<tbody>
					{#each (period === 'whole' ? data.network.edges : (data.network.by_period[period]?.edges ?? [])).slice(0, 30) as edge (edge.source + edge.target)}
						<tr>
							<td><a href={concordanceHref(edge.source)}>{termLabel(edge.source)}</a></td>
							<td><a href={concordanceHref(edge.target)}>{termLabel(edge.target)}</a></td>
							<td class="num">{count(edge.speeches)}</td>
							<td class="num">{decimal(edge.npmi)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</details>
	</Figure>

	<p class="onward">
		The <a href={resolve('/concordance')}>Concordance</a> lets you inspect matching passages and open
		their full speeches. Its search covers the displayed context around each match, so a linked word elsewhere
		in a long speech may not appear in the results.
	</p>
</article>

<style>
	.lede {
		max-width: var(--measure);
		margin-bottom: var(--sp-6);
	}

	.standfirst {
		font-size: var(--step-1);
		line-height: 1.5;
		color: var(--ink-2);
	}

	label {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	select {
		max-width: 15rem;
	}

	/* Reads on after the controls rather than being flung to the right edge —
	   see the same note in the chronology page. */
	.unit-note {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.view {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	.view .label {
		display: inline;
	}

	/* What the Term and Window selects would say, were the slices computed at
	   more than one of each. Stated rather than implied. */
	.fixed {
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
		max-width: 22rem;
	}

	.withheld {
		margin: var(--sp-2) 0;
		padding: var(--sp-3) var(--sp-4);
		border-left: 2px solid var(--reg-contentious);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.stated {
		margin: var(--sp-3) 0 0;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	/* 2.5rem is the height every select and button on the site already has.
	   These sit in the same bar as the selects, so a shorter box put them on a
	   different centre line and read as crooked next to them. */
	.ghost {
		background: none;
		border: var(--hair) solid var(--rule-strong);
		padding: var(--sp-1) var(--sp-3);
		min-height: 2.5rem;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
		cursor: pointer;
	}

	.ghost:hover {
		border-color: var(--blue);
		color: var(--blue);
	}

	/* ---- parallel text ----------------------------------------------------
	   Two profiles set as facing columns with a rule between them, so the two
	   rankings are read straight across rather than by scrolling between two
	   tables. The bars are ink: they are a datum, and the accent is not. */

	.compare {
		display: grid;
		gap: var(--sp-5);
		border-top: var(--hair) solid var(--rule-strong);
		padding-top: var(--sp-4);
	}

	@media (min-width: 46rem) {
		.compare {
			grid-template-columns: minmax(0, 1fr) 1px minmax(0, 1fr);
			gap: 0;
		}

		.compare .side:first-of-type {
			padding-right: var(--sp-5);
		}

		.compare .side:last-of-type {
			padding-left: var(--sp-5);
		}
	}

	.gutter {
		display: none;
		background: var(--rule-strong);
	}

	@media (min-width: 46rem) {
		.gutter {
			display: block;
		}
	}

	.compare h4 {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--sp-3);
		margin-bottom: var(--sp-3);
	}

	.compare .who {
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 700;
		letter-spacing: 0.02em;
	}

	.compare h4 .symbol {
		font-weight: 400;
		color: var(--ink-3);
	}

	.profile {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--sp-1);
	}

	.profile li {
		display: grid;
		grid-template-columns: 6.5rem minmax(0, 1fr) 3rem;
		gap: var(--sp-3);
		align-items: center;
	}

	.profile a {
		font-family: var(--serif);
		font-size: var(--step-0);
		text-decoration: none;
		color: var(--ink);
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.profile a:hover {
		color: var(--blue);
		text-decoration: underline;
	}

	.bar {
		height: 0.5rem;
		background: var(--ink-3);
		opacity: 0.55;
	}

	.profile .symbol {
		text-align: right;
		color: var(--ink-3);
	}

	/* ---- the aligned view -------------------------------------------------
	   One word per row, both profiles reading outwards from it. Because the two
	   bars share a scale, the row is a direct comparison rather than two rankings
	   that happen to be adjacent. */

	.pyramid {
		border-top: var(--hair) solid var(--rule-strong);
	}

	.prow {
		display: grid;
		grid-template-columns: 3.4rem minmax(0, 1fr) 9rem minmax(0, 1fr) 3.4rem;
		gap: var(--sp-3);
		align-items: center;
		padding: 0.15rem 0;
		border-bottom: var(--hair) solid var(--rule);
	}

	.prow:last-child {
		border-bottom-color: var(--rule-strong);
	}

	.prow.head {
		padding-bottom: var(--sp-2);
		border-bottom-color: var(--rule-strong);
	}

	.prow.head .who {
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 700;
		letter-spacing: 0.02em;
	}

	.prow.head .who.left {
		text-align: right;
	}

	.prow.head .symbol {
		color: var(--ink-3);
	}

	.prow .symbol {
		text-align: right;
		color: var(--ink-3);
	}

	.prow .symbol:last-child {
		text-align: left;
	}

	.track {
		display: flex;
		justify-content: flex-start;
	}

	.track.left {
		justify-content: flex-end;
	}

	.word {
		font-family: var(--serif);
		font-size: var(--step-0);
		text-align: center;
		text-decoration: none;
		color: var(--ink);
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.word:hover {
		color: var(--blue);
		text-decoration: underline;
	}

	@media (max-width: 46rem) {
		.prow {
			grid-template-columns: 3rem minmax(0, 1fr) 7rem minmax(0, 1fr) 3rem;
			gap: var(--sp-1);
			font-size: var(--step--1);
		}

		.word {
			font-size: var(--step--1);
		}
	}

	.rank {
		color: var(--ink-3);
		width: 2rem;
	}

	.gone {
		color: var(--ink-3);
		font-style: italic;
	}

	.onward {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
		max-width: var(--measure);
	}
</style>
