<script lang="ts">
	import { resolve } from '$app/paths';
	import { goto } from '$app/navigation';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import WordCloud from '$lib/WordCloud.svelte';
	import { plan } from '$lib/wordcloud';
	import {
		count,
		decimal,
		escapeHtml,
		percent,
		shortCountry,
		signed,
		termLabel
	} from '$lib/format';
	import {
		axisX,
		axisY,
		colourScheme,
		grid,
		palette,
		registerColour,
		textStyle,
		tooltip
	} from '$lib/theme';
	import type { CollocateBlock, Word } from '$lib/types';
	import type { EChartsOption } from 'echarts';
	import { untrack } from 'svelte';
	import { SvelteURLSearchParams } from 'svelte/reactivity';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const colours = $derived.by(() => {
		void $colourScheme;
		return palette();
	});

	let node = $state('genocide');
	let width = $state('5');
	let sliceKind = $state<'by_country' | 'by_period' | 'by_speaker_group'>('by_country');
	let sliceA = $state('Rwanda');
	let sliceB = $state('United States Of America');
	let period = $state('whole');
	let keynessView = $state<'matched' | 'unmatched'>('matched');

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

	type Facet = 'whole' | 'by_country' | 'by_period' | 'by_speaker_group';
	let cloudFacet = $state<Facet>('whole');
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
		const p = colours;
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
		const p = colours;
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
			What the word keeps company with. Every table here ranks by
			<strong>log-likelihood</strong> and reports <strong>log ratio</strong> beside it: on
			{count(data.collocates.meta.corpus_tokens as number)} words almost anything is statistically significant,
			so significance alone is not a finding.
		</p>
	</header>

	<Figure
		title="Collocates of the node term"
		question="Which words appear near this term far more often than chance would put them there?"
		source="05_lexical.py → lexical/collocates.json"
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
				Each point is a word. <strong>Rightwards</strong> means we are more confident its rate near
				the node differs from its rate in the rest of the corpus (G², log scale).
				<strong>Upwards</strong> means the difference is larger &mdash; a log ratio of +3 is eight times
				the corpus rate, +7 is over a hundred times.
			</p>
			<p>
				The interesting words are high <em>and</em> right. A word far right but low is common enough that
				a small difference is measurable; that is a property of the sample size, not of the discourse.
			</p>
			<p>
				Most collocates crowd into the lower left, where labels collide and the chart hides some of
				them. <strong>Scroll on the plot to zoom, drag to pan</strong>, or drag the bar under the
				axis; <em>Reset zoom</em> returns to the full extent. Nothing is filtered out by zooming &mdash;
				the axes are the same however far in you go, so a zoomed view is comparable to the whole.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				A wider window changes the question rather than refining it: &plusmn;5 words catches the
				phrase the term sits in, &plusmn;15 the argument. Compare them; do not average them.
			</p>
			<p>
				Function words are removed by a stated stoplist. Genre words &mdash; <em>council</em>,
				<em>resolution</em>, <em>president</em> &mdash; are deliberately <strong>not</strong>,
				because whether they sit close to the node is one of the things being asked.
			</p>
		{/snippet}

		<Chart
			option={scatter}
			height="440px"
			description="Scatter plot of collocate words by log-likelihood against log ratio."
			onclick={openCollocate}
		/>
		<details class="data-table">
			<summary>View the leading collocates as a table</summary>
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
		question="What is the shape of that neighbourhood, and does it hold in one mouth or one decade?"
		source={cloudSource}
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
					>{termLabel(data.sliced.term)} at &plusmn;{data.sliced.width} words &mdash; the only term and
					window the slices were counted at</span
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
			<span class="unit-note">no slice under {count(minimumSpeeches)} speeches is drawn</span>
		{/snippet}

		{#snippet reading()}
			<p>
				Every word here is a row of the table beneath it, and one call chooses both: what the cloud
				will not draw, the table does not list. <strong>Size is the log ratio</strong> &mdash; how many
				times a word's rate beside the node exceeds its rate in the rest of the corpus. Which words appear
				at all is the artefact's own ranking, by log-likelihood.
			</p>
			<p>
				A large word is therefore not a common word. The list is chosen by confidence and drawn by
				effect, so a word used two hundred times can sit beside one used thirty times and be the
				smaller of the two. <em>At least</em> raises the frequency floor, if you would rather the cloud
				stopped rewarding words the corpus barely contains.
			</p>
			<p>
				Every word is a link to its lines in the concordance, and reachable by keyboard. The scale
				is relative to what is on screen &mdash; the largest word in view holds the largest log
				ratio in view &mdash; so compare within a cloud rather than between two.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				This is drawn on <strong>surface forms</strong>. <em>crimes</em> and <em>crime</em> are two
				words here, each holding a share of the evidence they jointly support and each smaller than
				the merged word would be. A lemma layer that merges them is built and runnable but
				deliberately not adopted, because adopting it would move published figures before the human
				audit closes &mdash; <code>docs/PLAN.md</code> Phase 6. Until it is, a cloud of this corpus is
				partly a picture of English morphology rather than of the Council, and the words to trust least
				are the ones with the commonest inflections.
			</p>
			<p>
				Position and colour carry nothing. Two words are adjacent because the packer found room
				there, not because they occur together; the network figure below is the one that answers
				that. Area is not a quantity either &mdash; size is set on the height of a word, so a long
				word takes far more of the picture than a short one of the same log ratio.
			</p>
			<p>
				{count(data.collocates.meta.stopwords as number)} function words are removed by
				<code>config/stopwords.txt</code>, and no word occurring fewer than
				{count(data.collocates.meta.min_count as number)} times beside the node enters the table at all.
				Genre words &mdash; <em>council</em>, <em>resolution</em> &mdash; are deliberately kept.
			</p>
		{/snippet}

		{#if cloudSelection.refusal?.kind === 'below-minimum'}
			<p class="withheld">
				<strong>{memberLabel(cloudFacet, cloudMember)}</strong> holds
				{count(cloudSelection.refusal.speeches ?? 0)} speeches using the term, under the
				{count(cloudSelection.refusal.minimum ?? 0)} this artefact declares as the fewest it will stand
				a profile on. Nothing is drawn and nothing is tabulated. The whole corpus is a different population,
				and is not put in its place.
			</p>
		{:else if cloudSelection.refusal}
			<p class="withheld">
				Nothing in {cloudScope} occurs at least {cloudFloor} times beside the term, so there is nothing
				to draw. Lower the floor.
			</p>
		{:else}
			<WordCloud
				words={cloudSelection.rows}
				href={(word) => concordanceHref(cloudTerm, word.word)}
				label={cloudLabel}
				seed={cloudSeed}
				description="Word cloud of the leading collocates, each word sized by its log ratio and linking to its lines in the concordance."
			/>
			<p class="stated">
				{count(cloudSelection.rows.length)} words drawn, of the {count(cloudSelection.available)} rows
				this artefact holds for {cloudScope}: {count(cloudSelection.filtered)} fall below the frequency
				floor and {count(cloudSelection.truncated)} beyond the number asked for. The table below is those
				same {count(cloudSelection.rows.length)} words, in the same order.
			</p>
			<details class="data-table">
				<summary>View the same words as a table</summary>
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
			<span class="unit-note">no slice under {count(minimumSpeeches)} speeches is drawn</span>
		{/snippet}

		{#snippet reading()}
			<p>
				Two collocate profiles side by side, each computed on its own subset at &plusmn;{data.sliced
					.width} words but against the <em>same</em> whole-corpus reference. A word in one column and
				not the other is doing work in one mouth that it is not doing in the other.
			</p>
			<p>
				Try <strong>Rwanda</strong> against any other speaker: almost everyone's profile is the Rome Statute
				triad, and Rwanda's is a vocabulary of denial and prosecution.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Subsets differ enormously in size &mdash; the speech counts under each heading are there for
				that reason. A profile drawn from fifty speeches is a sketch, not a portrait.
			</p>
			<p>
				Comparing periods conflates who was speaking with when: Council membership turns over, and
				so does the agenda.
			</p>
		{/snippet}

		<div class="compare">
			{#each [{ key: sliceA, b: blockA }, { key: sliceB, b: blockB }] as side (side.key)}
				<div>
					<h4>
						{sliceLabel(side.key)}
						<span
							>{count(side.b?.speeches ?? 0)} speeches · {count(side.b?.occurrences ?? 0)} occurrences</span
						>
					</h4>
					{#if (side.b?.speeches ?? 0) < minimumSpeeches}
						<p class="withheld">
							{count(side.b?.speeches ?? 0)} speeches, under the {count(minimumSpeeches)} this artefact
							declares as its minimum. No profile is drawn for it.
						</p>
					{:else}
						<table>
							<thead>
								<tr
									><th>Word</th><th class="num">Near</th><th class="num">G²</th><th class="num"
										>Log ratio</th
									></tr
								>
							</thead>
							<tbody>
								{#each topWords(side.b) as w (w.word)}
									<tr>
										<td><a href={concordanceHref('genocide', w.word)}>{w.word}</a></td>
										<td class="num">{count(w.target)}</td>
										<td class="num">{count(Math.round(w.g2))}</td>
										<td class="num">{signed(w.log_ratio)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{/if}
				</div>
			{/each}
		</div>
	</Figure>

	<Figure
		title="Keyness against a matched control"
		question="Setting aside what the debate was about, what distinguishes a speech that says genocide?"
		source="05_lexical.py → lexical/keyness.json"
	>
		{#snippet controls()}
			<label>
				Comparison
				<select bind:value={keynessView}>
					<option value="matched">Matched control</option>
					<option value="unmatched">Whole corpus (unmatched)</option>
				</select>
			</label>
			<span class="unit-note">
				{count(data.keyness.control_speeches)} of {count(data.keyness.eligible_target_speeches)} targets
				matched ({percent(data.keyness.coverage)})
			</span>
		{/snippet}

		{#snippet reading()}
			<p>
				The table uses {count(data.keyness.target_speeches)} complete pairs drawn from
				{count(data.keyness.eligible_target_speeches)} eligible genocide-bearing speeches. Each target
				is paired with a speech from the same <strong>{data.keyness.matched_on.join(', ')}</strong> that
				does not use the term. What survives that comparison is closer to the vocabulary of the concept
				than of the occasion.
			</p>
			<p>
				Switch to <strong>unmatched</strong> to see what the matching removed. Watch
				<em>bosnia</em>, <em>herzegovina</em> and <em>tribunals</em>: near the top unmatched, gone
				once year and agenda item are held constant.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				{data.keyness.short_strata.length} strata could not be filled &mdash; debates in which nearly
				everyone used the word, so no control existed. They are left short rather than back-filled from
				elsewhere, which would have quietly biased the table towards the crisis years.
			</p>
			<p>
				The unmatched column is <strong>not a result</strong>. It is the comparison the matching
				exists to improve on, shown so the improvement can be checked.
			</p>
			<p>
				The match was repeated across {data.keyness.stability.repetitions} consecutive seeds; the artefact
				reports 5th–95th percentile effect sizes for every displayed keyword.
			</p>
		{/snippet}

		<table>
			<thead>
				<tr>
					<th>#</th>
					<th>Word</th>
					<th class="num">In target</th>
					<th class="num">G²</th>
					<th class="num">Log ratio</th>
					{#if keynessView === 'unmatched'}<th class="num">Matched</th>{/if}
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
		question="Does the lexicon have structure, or is it a list?"
		source="05_lexical.py → lexical/network.json"
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
				edge drawn where at least {data.network.min_speeches} speeches use both terms
			</span>
		{/snippet}

		{#snippet reading()}
			<p>
				Each circle is a lexicon term, sized by how many speeches use it and coloured by its
				register. An edge joins two terms used in the <em>same speech</em>, and its thickness is
				normalised pointwise mutual information: how much more often they co-occur than two
				independent terms of the same frequency would.
			</p>
			<p>Drag to rearrange, scroll to zoom, hover an edge for its numbers.</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Co-occurrence is at the level of the whole speech, so two terms count as linked even if they
				appear four hundred words apart and in unrelated sentences. This is a map of vocabularies
				that get used together, not of phrases.
			</p>
			<p>
				Normalising PMI is what stops a term used in thirty speeches dominating the graph; the raw
				measure rewards rarity.
			</p>
			<p>
				Declared nesting relationships are suppressed: for example, <em>mass atrocity</em> is not
				drawn as evidence of association with <em>atrocity</em> when the latter is already contained inside
				the phrase.
			</p>
		{/snippet}

		<Chart
			option={graph}
			height="520px"
			description="Force-directed graph of lexicon terms linked by co-occurrence within speeches."
			onclick={openNetworkTerm}
		/>
		<details class="data-table">
			<summary>View the strongest network edges as a table</summary>
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
		Every word above is an entry point: the <a href={resolve('/concordance')}>concordance</a> holds
		all {count(data.keyness.eligible_target_speeches)} speeches in the eligible target set.
	</p>
</article>

<style>
	.lede {
		max-width: 46rem;
		margin-bottom: 2rem;
	}

	.standfirst {
		font-size: 1.08rem;
		color: var(--ink-soft);
	}

	label {
		font-size: 0.83rem;
		color: var(--ink-faint);
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
	}

	select {
		background: var(--panel);
		color: var(--ink);
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0.25rem 0.4rem;
		font-size: 0.85rem;
		max-width: 15rem;
	}

	.unit-note {
		font-size: 0.78rem;
		color: var(--ink-faint);
		font-style: italic;
		margin-left: auto;
	}

	/* What the Term and Window selects would say, were the slices computed at
	   more than one of each. Stated rather than implied. */
	.fixed {
		font-size: 0.78rem;
		color: var(--ink-faint);
		font-style: italic;
		max-width: 22rem;
	}

	.withheld {
		margin: 0.4rem 0;
		padding: 0.8rem 1rem;
		border-left: 2px solid var(--rule);
		background: var(--rule-soft);
		font-size: 0.88rem;
		color: var(--ink-soft);
	}

	.stated {
		margin: 0.9rem 0 0;
		font-size: 0.78rem;
		color: var(--ink-faint);
	}

	.ghost {
		background: none;
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0.25rem 0.6rem;
		min-height: 2.1rem;
		font-size: 0.8rem;
		color: var(--ink-soft);
		cursor: pointer;
	}

	.ghost:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.compare {
		display: grid;
		gap: 1.5rem;
	}

	@media (min-width: 46rem) {
		.compare {
			grid-template-columns: 1fr 1fr;
		}
	}

	.compare h4 {
		font-size: 1rem;
		margin-bottom: 0.4rem;
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.6rem;
	}

	.compare h4 span {
		font-family: var(--sans);
		font-size: 0.75rem;
		font-weight: 400;
		color: var(--ink-faint);
	}

	.rank {
		color: var(--ink-faint);
		width: 2rem;
	}

	.gone {
		color: var(--ink-faint);
		font-style: italic;
	}

	.onward {
		font-size: 0.9rem;
		color: var(--ink-soft);
	}

	.data-table {
		margin-top: 1rem;
	}

	.data-table summary {
		cursor: pointer;
		color: var(--accent);
		font-size: 0.85rem;
	}
</style>
