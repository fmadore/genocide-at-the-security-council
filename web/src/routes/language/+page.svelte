<script lang="ts">
	import { resolve } from '$app/paths';
	import { goto, replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import WordCloud from '$lib/WordCloud.svelte';
	import {
		languageParams,
		readLanguageState,
		type Alignment,
		type CloudFacet,
		type KeynessView,
		type LanguageChoices,
		type SliceKind
	} from '$lib/language';
	import { plan } from '$lib/wordcloud';
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
	import { axisX, axisY, colours, grid, registerColour, textStyle, tooltip } from '$lib/theme';
	import type { CollocateBlock, Word } from '$lib/types';
	import type { EChartsOption } from 'echarts';
	import { onMount, tick, untrack } from 'svelte';
	import { SvelteURLSearchParams } from 'svelte/reactivity';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	/* Live chart handles, for the image half of the export. */
	let scatterFigure = $state<Chart | null>(null);
	let graphFigure = $state<Chart | null>(null);

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
				rows.push([reading, word.word, word.target, word.reference, word.g2, word.log_ratio]);
			}
		}
		return {
			title: 'Compared with a like-for-like speech',
			columns: ['reading', 'word', 'target', 'reference', 'g2', 'log_ratio'],
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

	/* --- The same table, drawn as a cloud --------------------------------- */

	let cloudFacet = $state<CloudFacet>('whole');
	/* Opened on the term and window the sliced artefact was counted at, so that
	   the whole-corpus cloud and any facet of it are the same question put to
	   different populations rather than two different questions. Read once and
	   untracked: these are the initial positions of controls the reader then
	   owns, not a derivation of the payload. */
	let cloudNode = $state(untrack(() => data.sliced.term));
	let cloudWidth = $state(untrack(() => String(data.sliced.width)));
	let cloudMember = $state('');
	let cloudLimit = $state('40');
	let cloudFloor = $state('0');

	const cloudMembers = $derived(cloudFacet === 'whole' ? [] : Object.keys(data.sliced[cloudFacet]));

	$effect(() => {
		// Changing the facet invalidates the member chosen inside the old one.
		const options = cloudFacet === 'whole' ? [] : Object.keys(data.sliced[cloudFacet]);
		if (options.length > 0 && !options.includes(cloudMember)) cloudMember = options[0];
	});

	const cloudBlock = $derived<CollocateBlock | undefined>(
		cloudFacet === 'whole'
			? data.collocates.nodes[cloudNode]?.widths[cloudWidth]
			: data.sliced[cloudFacet][cloudMember]
	);

	/* One call chooses the rows. The cloud draws them and the table lists them,
	   so there is no arrangement of the controls under which the two disagree. */
	const cloudSelection = $derived(
		plan({
			block: cloudBlock,
			minimumSpeeches: cloudFacet === 'whole' ? null : minimumSpeeches,
			limit: Number(cloudLimit),
			floor: Number(cloudFloor)
		})
	);

	/* The slice's own name, so one selection always draws one picture. */
	const cloudSeed = $derived(
		cloudFacet === 'whole' ? `whole:${cloudNode}:${cloudWidth}` : `${cloudFacet}:${cloudMember}`
	);
	/* Slices exist for one term at one width only, and the controls say so
	   rather than implying the facet follows the Term and Window above. */
	const cloudTerm = $derived(cloudFacet === 'whole' ? cloudNode : data.sliced.term);
	const cloudSource = $derived(
		cloudFacet === 'whole'
			? '05_lexical.py → lexical/collocates.json'
			: '05_lexical.py → lexical/collocates_sliced.json'
	);
	const cloudLabel = (word: Word) =>
		`${word.word}: ${count(word.target)} near ${termLabel(cloudTerm)}, ` +
		`G² ${count(Math.round(word.g2))}, log ratio ${signed(word.log_ratio)}`;
	const cloudScope = $derived(
		cloudFacet === 'whole' ? 'the whole corpus' : memberLabel(cloudFacet, cloudMember)
	);

	const keywords = $derived(
		keynessView === 'matched' ? data.keyness.keywords : data.keyness.keywords_unmatched
	);
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
				name: 'G² (confidence)',
				nameLocation: 'middle',
				nameGap: 28,
				nameTextStyle: { color: p.inkFaint, fontSize: 11 },
				splitLine: { show: true, lineStyle: { color: p.ruleSoft } }
			},
			yAxis: {
				...axisY(p),
				type: 'value',
				name: 'log ratio (size of the effect)',
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
					itemStyle: { color: p.accent, opacity: 0.55 },
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

	/* The lexicon as a graph. Edge weight is normalised PMI so a rare term
	   cannot buy a thick edge with rarity alone. */
	const graph: EChartsOption = $derived.by(() => {
		const p = $colours;
		const periodBlock = period === 'whole' ? null : data.network.by_period[period];
		const edges = periodBlock?.edges ?? data.network.edges;
		const used = new Set(edges.flatMap((e) => [e.source, e.target]));
		const periodCounts = new Map(periodBlock?.terms.map((term) => [term.name, term.speeches]));
		const terms = data.network.terms
			.filter((term) => used.has(term.name))
			.map((term) => ({ ...term, speeches: periodCounts.get(term.name) ?? term.speeches }));
		const maxSpeeches = Math.max(1, ...terms.map((t) => t.speeches));
		return {
			textStyle,
			tooltip: {
				...tooltip(p),
				trigger: 'item',
				formatter: (params) => {
					const d = params as unknown as { dataType?: string; data: Record<string, unknown> };
					return d.dataType === 'edge'
						? `<b>${escapeHtml(termLabel(String(d.data.source)))}</b> &amp; <b>${escapeHtml(termLabel(String(d.data.target)))}</b>` +
								`<br>${count(Number(d.data.speeches))} speeches use both` +
								`<br>nPMI ${decimal(Number(d.data.npmi))}`
						: `<b>${escapeHtml(termLabel(String(d.data.name)))}</b><br>${count(Number(d.data.speeches))} speeches`;
				}
			},
			series: [
				{
					type: 'graph',
					layout: 'force',
					roam: true,
					draggable: true,
					center: ['50%', '50%'],
					force: { repulsion: 340, edgeLength: [60, 190], gravity: 0.16 },
					label: {
						show: true,
						position: 'right',
						color: p.ink,
						fontSize: 12,
						formatter: (params) => termLabel(String((params as unknown as { name: string }).name))
					},
					labelLayout: { hideOverlap: true },
					emphasis: { focus: 'adjacency', lineStyle: { width: 5 } },
					data: terms.map((t) => ({
						name: t.name,
						speeches: t.speeches,
						symbolSize: 10 + 30 * Math.sqrt(t.speeches / maxSpeeches),
						itemStyle: { color: registerColour(t.register, p) }
					})),
					links: edges.map((e) => ({
						source: e.source,
						target: e.target,
						speeches: e.speeches,
						npmi: e.npmi,
						lineStyle: {
							width: Math.max(0.6, e.npmi * 7),
							opacity: 0.25 + e.npmi * 0.5,
							color: p.inkFaint,
							curveness: 0.06
						}
					}))
				}
			]
		};
	});

	const periods = $derived(['whole', ...Object.keys(data.network.by_period)]);

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
		cloudDefault: { node: data.sliced.term, width: String(data.sliced.width) }
	}));

	onMount(() => {
		const state = readLanguageState(page.url.searchParams, urlChoices);
		node = state.node;
		width = state.width;
		sliceKind = state.sliceKind;
		sliceA = state.sliceA;
		sliceB = state.sliceB;
		align = state.align;
		cloudFacet = state.cloudFacet;
		cloudNode = state.cloudNode;
		cloudWidth = state.cloudWidth;
		cloudMember = state.cloudMember;
		cloudLimit = state.cloudLimit;
		cloudFloor = state.cloudFloor;
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
				cloudFacet,
				cloudNode,
				cloudWidth,
				cloudMember,
				cloudLimit,
				cloudFloor,
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
	const openNetworkTerm = (params: { name?: string; dataType?: string }) => {
		if (params.dataType !== 'edge' && params.name) void goto(concordanceHref(params.name));
	};
</script>

<svelte:head>
	<title>Language — Genocide at the Security Council</title>
</svelte:head>

<article>
	<header class="lede">
		<h1>Language</h1>
		<p class="standfirst">
			The company the word keeps. Every table here uses two measures side by side.
			<strong>Log-likelihood</strong> (written G²) says how confident we can be that a word turns up
			at a rate chance alone would not produce; <strong>log ratio</strong> says how large that
			difference is. Across {count(data.collocates.meta.corpus_tokens as number)} words almost anything
			reaches statistical significance, so confidence on its own is not a finding &mdash; the tables rank
			by confidence and report the size beside it.
		</p>
	</header>

	<Figure
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
				Each point is a word that appears within the chosen window of the term &mdash; corpus
				linguists call such words <em>collocates</em>. <strong>Further right</strong> means more
				confidence that the word turns up near the term at a different rate from the rest of the
				corpus. <strong>Further up</strong> means a larger difference: a log ratio of +3 is eight times
				the corpus rate, +7 is more than a hundred times.
			</p>
			<p>
				The words worth attention are high <em>and</em> right. A word far right but low is simply common
				enough that even a small difference can be measured, which says more about how often it occurs
				than about how the Council speaks.
			</p>
			<p>
				Most collocates crowd into the lower left, where labels collide and the chart hides some of
				them. <strong>Scroll on the plot to zoom, drag to pan</strong>, or drag the bar under the
				axis; <em>Reset zoom</em> returns to the full view. Zooming filters nothing out and the axes never
				move, so a close-up remains comparable with the whole.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				A wider window asks a different question rather than a better one: &plusmn;5 words catches
				the phrase the term sits in, &plusmn;15 catches the argument around it. Compare the two; do
				not average them.
			</p>
			<p>
				Function words &mdash; <em>the</em>, <em>of</em>, <em>and</em> &mdash; are removed using a
				published list. Words belonging to the setting, such as <em>council</em>,
				<em>resolution</em>
				and <em>president</em>, are deliberately kept, because whether they sit close to the term is
				one of the things being asked.
			</p>
		{/snippet}

		<Chart
			bind:this={scatterFigure}
			option={scatter}
			height="440px"
			description="Scatter plot of the words near the term, confidence along the horizontal axis and size of effect up the vertical one."
			onclick={openCollocate}
		/>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View the leading collocates as a table</summary>
			<table>
				<thead
					><tr
						><th>Word</th><th class="num">Near</th><th class="num">G²</th><th class="num"
							>Log ratio</th
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
						</tr>
					{/each}
				</tbody>
			</table>
		</details>
	</Figure>

	<Figure
		title="The same table as a cloud"
		question="What shape does that neighbourhood have, and does it hold for a single speaker or a single decade?"
		source={cloudSource}
		download={{ name: ['unsc', 'collocates', 'cloud', cloudFacet], table: collocateTable }}
	>
		{#snippet controls()}
			<label>
				Drawn from
				<select bind:value={cloudFacet}>
					<option value="whole">Whole corpus</option>
					<option value="by_country">One speaker</option>
					<option value="by_speaker_group">One speaker group</option>
					<option value="by_period">One period</option>
				</select>
			</label>
			{#if cloudFacet === 'whole'}
				<label>
					Term
					<select bind:value={cloudNode}>
						{#each nodes as n (n)}<option value={n}>{termLabel(n)}</option>{/each}
					</select>
				</label>
				<label>
					Window
					<select bind:value={cloudWidth}>
						{#each widths as w (w)}<option value={w}>&plusmn;{w} words</option>{/each}
					</select>
				</label>
			{:else}
				<label>
					Which
					<select bind:value={cloudMember}>
						{#each cloudMembers as m (m)}<option value={m}>{memberLabel(cloudFacet, m)}</option
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
				<select bind:value={cloudLimit}>
					<option value="25">25</option>
					<option value="40">40</option>
					<option value="60">60</option>
					<option value="100">100</option>
				</select>
			</label>
			<label>
				At least
				<select bind:value={cloudFloor}>
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
				Every word drawn here is a row of the table beneath it, and one decision governs both: what
				the cloud leaves out, the table leaves out too. <strong>Size carries the log ratio</strong>
				&mdash; how many times a word's rate beside the term exceeds its rate in the rest of the corpus.
				Which words appear at all is decided by the other measure, log-likelihood.
			</p>
			<p>
				A large word is therefore not a common word. The list is chosen by confidence and drawn by
				size of effect, so a word used two hundred times can sit beside one used thirty times and be
				the smaller of the two. <em>At least</em> raises the minimum frequency, if you would rather the
				cloud stopped rewarding words the corpus barely contains.
			</p>
			<p>
				Every word links to its lines in the concordance and can be reached by keyboard. The scale
				is relative to what is on screen: the largest word in view holds the largest log ratio in
				view, so compare within one cloud rather than between two.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Words are counted <strong>exactly as they appear</strong>. <em>crime</em> and
				<em>crimes</em>
				are two separate words here, each carrying part of the evidence for the same idea and each smaller
				than a merged entry would be. A step that merges such forms exists and runs, but it is deliberately
				not used yet: switching it on would move figures already published here before the hand-check
				of the word list is finished. Until then, a cloud of this corpus is partly a picture of English
				word endings rather than of the Council, and the words to trust least are those with the commonest
				variants.
			</p>
			<p>
				Position and colour carry nothing. Two words sit next to each other because the layout found
				room there, not because they occur together; the network figure below is the one that
				answers that question. Area carries nothing either: size is set on a word's height, so a
				long word takes up far more of the picture than a short one with the same log ratio.
			</p>
			<p>
				{count(data.collocates.meta.stopwords as number)} function words are removed using
				<code>config/stopwords.txt</code>, and a word occurring fewer than
				{count(data.collocates.meta.min_count as number)} times beside the term never enters the table
				at all. Words belonging to the setting &mdash; <em>council</em>, <em>resolution</em> &mdash; are
				deliberately kept.
			</p>
		{/snippet}

		{#if cloudSelection.refusal?.kind === 'below-minimum'}
			<p class="withheld">
				<strong>{memberLabel(cloudFacet, cloudMember)}</strong> has
				{count(cloudSelection.refusal.speeches ?? 0)} speeches using the term, fewer than the
				{count(cloudSelection.refusal.minimum ?? 0)} needed before a profile is drawn at all. Nothing
				is drawn and nothing is listed. The whole corpus is a different set of speeches, so it is not
				shown here instead.
			</p>
		{:else if cloudSelection.refusal}
			<p class="withheld">
				No word in {cloudScope} occurs at least {cloudFloor} times beside the term, so there is nothing
				to draw. Lower the minimum frequency.
			</p>
		{:else}
			<WordCloud
				words={cloudSelection.rows}
				href={(word) => concordanceHref(cloudTerm, word.word)}
				label={cloudLabel}
				seed={cloudSeed}
				description="Cloud of the words that sit near the term, each sized by its log ratio and linking to its lines in the concordance."
			/>
			<p class="stated">
				{count(cloudSelection.rows.length)} words drawn, out of {count(cloudSelection.available)} held
				for
				{cloudScope}: {count(cloudSelection.filtered)} fall below the minimum frequency and
				{count(cloudSelection.truncated)} fall beyond the number of words asked for. The table below holds
				those same {count(cloudSelection.rows.length)} words, in the same order.
			</p>
			<details class="data-table">
				<summary><Icon icon={ChevronRight} />View the same words as a table</summary>
				<table>
					<thead
						><tr
							><th>Word</th><th class="num">Near</th><th class="num">G²</th><th class="num"
								>Log ratio</th
							></tr
						></thead
					>
					<tbody>
						{#each cloudSelection.rows as word (word.word)}
							<tr>
								<td><a href={concordanceHref(cloudTerm, word.word)}>{word.word}</a></td>
								<td class="num">{count(word.target)}</td>
								<td class="num">{count(Math.round(word.g2))}</td>
								<td class="num">{signed(word.log_ratio)}</td>
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
				Two lists of neighbouring words, each worked out from its own set of speeches at &plusmn;{data
					.sliced.width} words, but both measured against the <em>same</em> whole-corpus background.
				The two columns share <strong>one scale</strong>, so a longer bar is a larger log ratio
				wherever it appears.
			</p>
			<p>
				<strong>By rank</strong> puts each column's own strongest words in its own order. Rows do
				not line up, and what the figure shows is that the two <em>sets</em> of words differ.
				<strong>By word</strong> gives each word a single row with both sides' figures on it, so what
				the figure shows is how far apart the two speakers are on the same word. A dash means the word
				does not appear in that speaker's list at all.
			</p>
			<p>
				Try <strong>Rwanda</strong> against any other speaker. Most delegations return the three crimes
				named in the Rome Statute of the International Criminal Court &mdash; genocide, crimes against
				humanity, war crimes. Rwanda returns a vocabulary of denial and prosecution.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				These sets of speeches differ enormously in size, which is why the speech count is printed
				under each heading. A list drawn from fifty speeches is a sketch, not a portrait.
			</p>
			<p>
				Comparing two periods mixes up who was speaking with when they spoke: Council membership
				turns over, and so does the agenda.
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
						><th>Profile</th><th>Word</th><th class="num">Near</th><th class="num">G²</th><th
							class="num">Log ratio</th
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
							</tr>
						{/each}
					{/each}
				</tbody>
			</table>
		</details>
	</Figure>

	<Figure
		title="Compared with a like-for-like speech"
		question="Setting aside what the debate was about, what marks out a speech that says genocide?"
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
				The table rests on {count(data.keyness.target_speeches)} complete pairs, drawn from
				{count(data.keyness.eligible_target_speeches)} speeches that use the word. Each of those is paired
				with a speech that does not use it but shares its
				<strong>{matchedOn(data.keyness.matched_on)}</strong>. What survives the comparison is
				closer to the vocabulary of the idea than of the occasion.
			</p>
			<p>
				Switch to <strong>the whole corpus</strong> to see what the pairing removed. Watch
				<em>bosnia</em>, <em>herzegovina</em> and <em>tribunals</em>: near the top of the unpaired
				table, and gone once year and agenda item are held constant.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				{data.keyness.short_strata.length} groups could not be filled. These are debates in which nearly
				everyone used the word, so no comparable speech was left over. They are left short rather than
				filled from elsewhere, which would have tilted the table quietly towards the crisis years.
			</p>
			<p>
				The whole-corpus column is <strong>not a result</strong>. It is the comparison the pairing
				exists to improve on, shown so that the improvement can be checked.
			</p>
			<p>
				Because the partner speech is drawn at random, the pairing was repeated across
				{data.keyness.stability.repetitions} consecutive draws, and the range those draws produced is
				available for every word in the table.
			</p>
		{/snippet}

		<table>
			<thead>
				<tr>
					<th>#</th>
					<th>Word</th>
					<th class="num">In these speeches</th>
					<th class="num">G²</th>
					<th class="num">Log ratio</th>
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
			chart: () => graphFigure?.svg() ?? null
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
				a line is drawn where at least {data.network.min_speeches} speeches use both terms
			</span>
		{/snippet}

		{#snippet reading()}
			<p>
				Each circle is a term from the word list, sized by how many speeches use it and coloured by
				its register. A line joins two terms that appear in the <em>same speech</em>, and its
				thickness shows how much more often the two turn up together than two unrelated terms of the
				same frequency would.
			</p>
			<p>Drag to rearrange, scroll to zoom, hover over a line for its numbers.</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Two terms count as linked if they appear anywhere in the same speech, even four hundred
				words apart and in unrelated sentences. This is a map of vocabularies used on the same
				occasion, not of phrases.
			</p>
			<p>
				The thickness measure is adjusted for how often each term occurs. Without that adjustment, a
				term appearing in only thirty speeches would dominate the picture, because the raw measure
				rewards rarity.
			</p>
			<p>
				A phrase is never drawn as evidence of association with a word already inside it: <em
					>mass atrocity</em
				>
				and <em>atrocity</em> are not linked on the strength of the second sitting within the first.
			</p>
		{/snippet}

		<Chart
			bind:this={graphFigure}
			option={graph}
			height="520px"
			description="Network of terms from the word list, with a line joining two terms wherever they appear in the same speech."
			onclick={openNetworkTerm}
		/>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View the strongest network edges as a table</summary>
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
		Every word above is a way in: the <a href={resolve('/concordance')}>concordance</a> holds all
		{count(data.keyness.eligible_target_speeches)} speeches these tables were built from.
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
