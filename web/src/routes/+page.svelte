<script lang="ts">
	import { resolve } from '$app/paths';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import { count, decimal, percent } from '$lib/format';
	import {
		axisX,
		axisY,
		grid,
		legend,
		palette,
		registerColour,
		textStyle,
		tooltip
	} from '$lib/theme';
	import type { EChartsOption } from 'echarts';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const years = $derived(data.series.periods as number[]);
	const corpus = $derived(data.series.corpus);
	const genocide = $derived(data.series.terms.genocide);

	const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);

	const totals = $derived({
		speeches: sum(corpus.speeches),
		tokens: sum(corpus.tokens),
		meetings: sum(corpus.meetings),
		bearing: sum(genocide.speeches),
		occurrences: sum(genocide.occurrences ?? []),
		speakers: (data.series.meta.speakers as number) ?? 0
	});

	const densest = $derived(years[genocide.speech_rate.indexOf(Math.max(...genocide.speech_rate))]);
	const loudest = $derived(
		years[(genocide.occurrences ?? []).indexOf(Math.max(...(genocide.occurrences ?? [])))]
	);

	const rawBreaks = $derived(data.breaks.series.genocide?.occurrences ?? []);
	const rateBreaks = $derived(data.breaks.series.genocide?.speech_rate ?? []);
	const atrocityBreaks = $derived(data.breaks.series.atrocity_core?.speech_rate ?? []);

	/* The central figure: the same phenomenon counted two ways, on one pair of
	   axes, so the disagreement between them is the thing you see first. */
	const contrast: EChartsOption = $derived.by(() => {
		const p = palette();
		return {
			textStyle,
			grid: grid(),
			legend: { ...legend(p), data: ['Occurrences', 'Share of speeches'] },
			tooltip: { ...tooltip(p), trigger: 'axis', axisPointer: { type: 'shadow' } },
			xAxis: { ...axisX(p), type: 'category', data: years },
			yAxis: [
				{
					...axisY(p),
					type: 'value',
					name: 'occurrences',
					nameTextStyle: { color: p.inkFaint, fontSize: 11, align: 'left' }
				},
				{
					...axisY(p),
					type: 'value',
					name: 'share of speeches',
					nameTextStyle: { color: p.inkFaint, fontSize: 11, align: 'right' },
					splitLine: { show: false },
					axisLabel: {
						color: p.inkFaint,
						fontSize: 12,
						formatter: (v: number) => `${(v * 100).toFixed(0)}%`
					}
				}
			],
			series: [
				{
					name: 'Occurrences',
					type: 'bar',
					data: genocide.occurrences,
					// Muted, but still a series rather than a background: --rule-soft is
					// all but invisible against the dark panel.
					itemStyle: { color: p.inkFaint, opacity: 0.32 },
					barMaxWidth: 22,
					tooltip: { valueFormatter: (v) => count(v as number) },
					markLine: rawBreaks.length
						? {
								silent: true,
								symbol: 'none',
								lineStyle: { color: p.inkFaint, type: 'dashed', width: 1 },
								label: {
									formatter: (d: { name: string }) => `break ${d.name}`,
									color: p.inkFaint,
									fontSize: 11
								},
								data: rawBreaks.map((b) => ({ xAxis: String(b.label), name: b.label }))
							}
						: undefined
				},
				{
					name: 'Share of speeches',
					type: 'line',
					yAxisIndex: 1,
					data: genocide.speech_rate,
					smooth: false,
					symbol: 'circle',
					symbolSize: 5,
					lineStyle: { color: p.accent, width: 2.2 },
					itemStyle: { color: p.accent },
					tooltip: { valueFormatter: (v) => percent(v as number) }
				}
			]
		};
	});

	/* Registers overlap, so these are separate lines rather than a stack. */
	const registers: EChartsOption = $derived.by(() => {
		const p = palette();
		const names = Object.keys(data.series.registers).sort();
		return {
			textStyle,
			grid: grid(),
			legend: legend(p),
			tooltip: {
				...tooltip(p),
				trigger: 'axis',
				valueFormatter: (v) => percent(v as number)
			},
			xAxis: { ...axisX(p), type: 'category', data: years },
			yAxis: {
				...axisY(p),
				type: 'value',
				axisLabel: {
					color: p.inkFaint,
					fontSize: 12,
					formatter: (v: number) => `${(v * 100).toFixed(0)}%`
				}
			},
			series: names.map((name) => ({
				name,
				type: 'line',
				data: data.series.registers[name].speech_rate,
				symbol: 'none',
				lineStyle: { width: 2, color: registerColour(name, p) },
				itemStyle: { color: registerColour(name, p) },
				emphasis: { focus: 'series' }
			}))
		};
	});

	const kinds = $derived(
		Object.entries(
			data.overlay.events.reduce<Record<string, number>>((acc, e) => {
				acc[e.kind] = (acc[e.kind] ?? 0) + 1;
				return acc;
			}, {})
		).sort((a, b) => b[1] - a[1])
	);
</script>

<svelte:head>
	<title>Genocide at the Security Council</title>
</svelte:head>

<article>
	<header class="lede">
		<h1>The word, and what it was doing there</h1>
		<p class="standfirst">
			Between 1992 and 2023 the Security Council held {count(totals.meetings)} meetings and heard
			{count(totals.speeches)} speeches. In {count(totals.bearing)} of them &mdash; {percent(
				totals.bearing / totals.speeches
			)} &mdash; someone said <em>genocide</em>. This site is about which ones, and what the word
			was doing when they did.
		</p>
	</header>

	<dl class="figures">
		<div>
			<dt>Speeches in the corpus</dt>
			<dd>{count(totals.speeches)}</dd>
			<p>across {count(totals.meetings)} meetings, {decimal(totals.tokens / 1e6)} M words</p>
		</div>
		<div>
			<dt>Containing <code>genocid*</code></dt>
			<dd>{count(totals.bearing)}</dd>
			<p>{percent(totals.bearing / totals.speeches)} of the corpus</p>
		</div>
		<div>
			<dt>Occurrences of the word</dt>
			<dd>{count(totals.occurrences)}</dd>
			<p>{decimal(totals.occurrences / totals.bearing)} per speech that uses it</p>
		</div>
		<div>
			<dt>Densest year</dt>
			<dd>{densest}</dd>
			<p>not {loudest}, which had the most occurrences</p>
		</div>
	</dl>

	<section class="finding">
		<h2>The peak that is not there</h2>
		<p>
			The best-known fact about this corpus is that 2014 out-says 1994: {count(
				Math.max(...(genocide.occurrences ?? []))
			)} occurrences against {count(genocide.occurrences?.[2] ?? 0)}. It is true, and it is an
			artefact of the Council talking more about everything. Speeches per year roughly
			<strong
				>{decimal(corpus.speeches[corpus.speeches.length - 1] / corpus.speeches[0])}&times;</strong
			> over the period.
		</p>
	</section>

	<Figure
		title="Occurrences and share of speeches, {years[0]}&ndash;{years[years.length - 1]}"
		question="Did the Council come to talk about genocide more, or simply to talk more?"
		source="04_series.py → series/annual.json, series/change_points.json"
	>
		{#snippet reading()}
			<p>
				<strong>Grey bars</strong> count every occurrence of <code>genocid*</code> in a year. The
				<strong>red line</strong>
				is the share of that year's speeches containing it, read on the right-hand axis. The dashed rule
				marks a
				<strong>change point</strong>: a shift in level that survives a permutation test against
				2,000 reorderings of the same values.
			</p>
			<p>
				The bars break at {rawBreaks.map((b) => b.label).join(' and ') || 'no point'}. The line
				breaks
				{#if rateBreaks.length}at {rateBreaks.map((b) => b.label).join(' and ')}{:else}<strong
						>nowhere</strong
					>{/if}.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				A share of speeches is not a measure of intensity: a speech that says the word once counts
				the same as the 1994 session that says it {count(Math.max(...(genocide.occurrences ?? [])))} times
				across the room. Both views are here for that reason.
			</p>
			<p>
				The change-point test asks whether a series has a step in it, not whether it has a trend
				&mdash; a smoothly rising line would be reported as breaking at its middle. Read the marks
				against the shape, not instead of it.
			</p>
		{/snippet}
		<Chart
			option={contrast}
			height="400px"
			description="Bar and line chart. Occurrences of genocide peak in 2014 while the share of speeches peaks in 1994."
		/>
	</Figure>

	<section class="finding">
		<h2>What does move</h2>
		<p>
			The single word has no detectable regime shift once normalised. The vocabulary it belongs to
			does. Counting the <em>atrocity core</em> &mdash; genocide, ethnic cleansing, crimes against
			humanity, war crimes, mass atrocity &mdash; as a share of speeches gives
			{atrocityBreaks.length} change points:
			{#each atrocityBreaks as b, i (b.label)}{i === 0
					? ''
					: i === atrocityBreaks.length - 1
						? ' and '
						: ', '}<strong>{b.label}</strong> ({b.ratio < 1 ? 'down' : 'up'}
				{decimal(b.ratio)}&times;){/each}. Whatever changes in this discourse does not change at the
			level of the single word.
		</p>
	</section>

	<Figure
		title="Register share over time"
		question="Which vocabulary is the word embedded in, and does that mix change?"
		source="05_lexical.py registers via 03_lexicon.py → series/annual.json"
	>
		{#snippet reading()}
			<p>
				Each line is the share of a year's speeches using at least one term from one of the
				lexicon's six registers: the <em>core</em> word itself, the
				<em>legal</em>
				vocabulary of qualification, <em>preventive</em> language, <em>commemorative</em>,
				<em>contentious</em> (denial, glorification), and <em>accountability</em> (courts, tribunals,
				impunity).
			</p>
			<p>
				Accountability and legal language dominate throughout; the core word runs an order of
				magnitude below them.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>These lines are not a composition and do not sum to anything.</strong> One speech can
				use four registers at once and is counted in all four, which is why they are drawn as separate
				lines rather than stacked. A stacked version of this chart would be wrong.
			</p>
			<p>
				Register assignment is a hypothesis about how the vocabulary groups, recorded in
				<code>config/lexicon.yml</code>, not a finding.
			</p>
		{/snippet}
		<Chart
			option={registers}
			height="360px"
			description="Six lines showing the share of speeches per year using each lexical register."
		/>
	</Figure>

	<section class="onward">
		<h2>Where to go from here</h2>
		<div class="cards">
			<a href={resolve('/chronology')}>
				<strong>Chronology</strong>
				<span
					>Every term and register over time, against {data.overlay.events.length} reference dates &mdash;
					{kinds.map(([k, n]) => `${n} ${k}`).join(', ')}.</span
				>
			</a>
			<a href={resolve('/language')}>
				<strong>Language</strong>
				<span
					>What the word travels with, how that differs by speaker and period, and which terms
					co-occur.</span
				>
			</a>
			<a href={resolve('/concordance')}>
				<strong>Concordance</strong>
				<span
					>All {count(totals.occurrences)} occurrences in context, sortable, and expandable to the full
					speech.</span
				>
			</a>
			<a href={resolve('/methods')}>
				<strong>Methods</strong>
				<span>How each figure was produced, and what is still unverified.</span>
			</a>
		</div>
	</section>
</article>

<style>
	.lede {
		max-width: 46rem;
		margin-bottom: 2.5rem;
	}

	.standfirst {
		font-size: 1.14rem;
		line-height: 1.62;
		color: var(--ink-soft);
	}

	.standfirst em {
		color: var(--ink);
		font-style: italic;
	}

	.figures {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
		gap: 1px;
		margin: 0 0 3rem;
		background: var(--rule);
		border: 1px solid var(--rule);
		border-radius: 6px;
		overflow: hidden;
	}

	.figures > div {
		background: var(--panel);
		padding: 1.1rem 1.2rem;
	}

	.figures dt {
		font-size: 0.76rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--ink-faint);
	}

	.figures dd {
		margin: 0.15rem 0 0.2rem;
		font-family: var(--serif);
		font-size: 1.9rem;
		font-variant-numeric: tabular-nums;
		line-height: 1.1;
	}

	.figures p {
		margin: 0;
		font-size: 0.8rem;
		color: var(--ink-faint);
	}

	.finding {
		max-width: 46rem;
		margin: 0 0 1.6rem;
	}

	.finding h2 {
		margin-bottom: 0.3em;
	}

	.onward {
		margin-top: 1rem;
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
		gap: 1rem;
	}

	.cards a {
		display: block;
		padding: 1rem 1.1rem;
		background: var(--panel);
		border: 1px solid var(--rule);
		border-radius: 6px;
		text-decoration: none;
		color: inherit;
	}

	.cards a:hover {
		border-color: var(--accent);
	}

	.cards strong {
		display: block;
		font-family: var(--serif);
		font-size: 1.05rem;
		margin-bottom: 0.25rem;
		color: var(--accent);
	}

	.cards span {
		font-size: 0.85rem;
		color: var(--ink-soft);
	}
</style>
