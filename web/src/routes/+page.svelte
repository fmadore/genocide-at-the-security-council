<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import SmallMultiples from '$lib/SmallMultiples.svelte';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, decimal, escapeHtml, isoDate, percent } from '$lib/format';
	import {
		axisX,
		axisY,
		colourScheme,
		endLabel,
		grid,
		markLine,
		palette,
		registerColour,
		textStyle,
		tooltip
	} from '$lib/theme';
	import type { Measure } from '$lib/types';
	import type { EChartsOption } from 'echarts';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	/* Live chart handles, for the image half of the export. */
	let contrastFigure = $state<Chart | null>(null);
	let registerFigure = $state<Chart | null>(null);

	/**
	 * Both overview figures read the same annual artefact, so both export it
	 * whole: every term, every register, every set, in all four units. The two
	 * figures are two readings of one table, and handing over two different
	 * subsets would hide exactly the relationship they are here to show.
	 */
	function annualTable(title: string, filters: string[]): ExportRequest {
		const rows: (string | number | null)[][] = [];
		const groups: [string, Record<string, Measure>][] = [
			['term', data.series.terms],
			['register', data.series.registers],
			['set', data.series.sets]
		];
		for (const [kind, block] of groups) {
			for (const [name, measure] of Object.entries(block)) {
				data.series.periods.forEach((period, index) => {
					rows.push([
						String(period),
						name,
						kind,
						measure.register ?? null,
						data.series.corpus.speeches[index],
						data.series.corpus.tokens[index],
						measure.speeches[index] ?? null,
						measure.speech_rate[index] ?? null,
						measure.occurrences?.[index] ?? null,
						measure.token_rate?.[index] ?? null
					]);
				});
			}
		}
		return {
			title,
			columns: [
				'year',
				'measure',
				'kind',
				'register',
				'corpus_speeches',
				'corpus_tokens',
				'speeches',
				'speech_rate',
				'occurrences',
				'token_rate_per_100k'
			],
			rows,
			provenance: provenanceOf(data.series.meta, 'series/annual.json'),
			filters,
			scope: 'every term, register and set in the annual artefact, in all four units'
		};
	}
	const colours = $derived.by(() => {
		void $colourScheme;
		return palette();
	});

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
	const index1994 = $derived(years.indexOf(1994));

	const rateInference = $derived(data.breaks.inference.series.genocide?.speech_rate ?? null);
	const atrocityInference = $derived(
		data.breaks.inference.series.atrocity_core?.speech_rate ?? null
	);

	/* The central figure: the same phenomenon counted two ways, on one pair of
	   axes, so the disagreement between them is the thing you see first.

	   Both series are drawn in ink and labelled where they end. The accent is
	   for what a reader can act on, so it never enters the plot; the two series
	   are told apart by mark and by weight, which survives greyscale and print
	   in a way a two-colour key does not. */
	const contrast: EChartsOption = $derived.by(() => {
		const p = colours;
		return {
			textStyle,
			// No end labels here: the two axis names already sit at the two ends of
			// the plot and name a series each, and the right-hand axis owns the
			// margin an end label would need.
			grid: grid(false),
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
					// Muted, but still a series rather than a background: --rule is
					// all but invisible against the dark panel.
					itemStyle: { color: p.inkFaint, opacity: 0.32 },
					barMaxWidth: 22,
					tooltip: { valueFormatter: (v) => count(v as number) },
					markLine: undefined
				},
				{
					name: 'Share of speeches',
					type: 'line',
					yAxisIndex: 1,
					data: genocide.speech_rate,
					smooth: false,
					symbol: 'circle',
					symbolSize: 5,
					lineStyle: { color: p.ink, width: 2 },
					itemStyle: { color: p.ink },
					tooltip: { valueFormatter: (v) => percent(v as number) }
				}
			]
		};
	});

	/* Registers overlap, so they are never a stack — and six lines crossing each
	   other is a picture of the crossing rather than of any one of them. They
	   are drawn as six small multiples on a shared axis instead, each named in
	   place and ending in the period share its own scaling throws away.

	   The colours are CSS custom properties rather than resolved literals: this
	   figure is markup, not a canvas, so it follows the theme without redrawing. */
	const REGISTER_ORDER = [
		'accountability',
		'legal',
		'preventive',
		'commemorative',
		'core',
		'contentious'
	];

	const registerRows = $derived.by(() => {
		const present = Object.keys(data.series.registers);
		const ordered = [
			...REGISTER_ORDER.filter((r) => present.includes(r)),
			...present.filter((r) => !REGISTER_ORDER.includes(r)).sort()
		];
		return ordered.map((name) => {
			const series = data.series.registers[name];
			const bearing = series.speeches.reduce((a, b) => a + b, 0);
			const held = corpus.speeches.reduce((a, b) => a + b, 0);
			return {
				name,
				values: series.speech_rate,
				colour: `var(--reg-${name})`,
				summary: percent(held ? bearing / held : 0)
			};
		});
	});

	/**
	 * Which year columns carry a reference date, and what those dates were.
	 * A year can carry several, so they are gathered rather than the last one
	 * silently winning.
	 */
	const eventTicks = $derived.by(() => {
		// A plain record, not a Map: this is an accumulator built and consumed
		// inside one derivation, so it never needs to be reactive.
		const byIndex: Record<number, string[]> = {};
		for (const event of data.overlay.events) {
			const index = years.indexOf(event.year);
			if (index < 0) continue;
			(byIndex[index] ??= []).push(`${isoDate(event.date)} — ${event.label}`);
		}
		return Object.entries(byIndex)
			.map(([index, labels]) => ({ index: Number(index), title: labels.join('\n') }))
			.sort((a, b) => a.index - b.index);
	});

	/**
	 * Two readings of the same six series, because they answer different
	 * questions. Rows show each register's shape without the others crossing it;
	 * lines put them on one scale, which is the only way to see that
	 * accountability runs an order of magnitude above the core word — and is
	 * where the reference dates can carry a tooltip worth reading.
	 */
	let registerView = $state<'rows' | 'lines'>('rows');

	const registerLines: EChartsOption = $derived.by(() => {
		const p = colours;
		const names = registerRows.map((r) => r.name);
		const byYear: Record<string, string[]> = {};
		for (const event of data.overlay.events) {
			(byYear[String(event.year)] ??= []).push(`${isoDate(event.date)} ${event.label}`);
		}
		return {
			textStyle,
			grid: grid(true),
			tooltip: {
				...tooltip(p),
				trigger: 'axis',
				// The reference rules are silent marks, so the axis tooltip carries
				// what they stand for: every year is hoverable, rather than a
				// one-pixel line being the only way to read a date.
				formatter: (params) => {
					const rows = (Array.isArray(params) ? params : [params]) as {
						axisValue?: string;
						marker?: string;
						seriesName?: string;
						value?: unknown;
					}[];
					const year = rows[0]?.axisValue ?? '';
					const series = rows
						.map(
							(r) =>
								`${r.marker ?? ''}${escapeHtml(r.seriesName ?? '')} <b>${percent(Number(r.value ?? 0))}</b>`
						)
						.join('<br>');
					const dates = byYear[year] ?? [];
					const note = dates.length
						? '<hr style="opacity:.2">' +
							`<span style="opacity:.7">Reference ${dates.length === 1 ? 'date' : 'dates'}</span><br>` +
							dates.map((d) => escapeHtml(d)).join('<br>')
						: '';
					return `<b>${escapeHtml(year)}</b><br>${series}${note}`;
				}
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
			series: names.map((name, i) => ({
				name,
				type: 'line',
				data: data.series.registers[name].speech_rate,
				symbol: 'none',
				lineStyle: { width: 2, color: registerColour(name, p) },
				itemStyle: { color: registerColour(name, p) },
				endLabel: endLabel(registerColour(name, p), name),
				emphasis: { focus: 'series' },
				markLine:
					i === 0 && eventTicks.length
						? {
								...markLine(p),
								label: { show: false },
								lineStyle: { color: p.inkFaint, width: 1, type: 'solid' as const, opacity: 0.35 },
								data: eventTicks.map((t) => ({ xAxis: String(years[t.index]) }))
							}
						: undefined
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

	function drillYear(params: { name?: string }) {
		if (!params.name) return;
		void goto(`${resolve('/concordance')}?term=genocide&from=${params.name}&to=${params.name}`);
	}
</script>

<svelte:head>
	<title>Genocide at the Security Council</title>
</svelte:head>

<article>
	<header class="lede">
		<h1>The word, and what it was doing there</h1>
		<p class="standfirst">
			Between 1992 and 2023 the corpus contains {count(totals.meetings)} distinct meeting symbols and
			heard
			{count(totals.speeches)} speeches. In {count(totals.bearing)} of them &mdash; {percent(
				totals.bearing / totals.speeches
			)} &mdash; someone said <em>genocide</em>. This site is about which ones, and what the word
			was doing when they did.
		</p>
	</header>

	<dl class="figures">
		<div>
			<dt class="label">Speeches in the corpus</dt>
			<dd>{count(totals.speeches)}</dd>
			<p>
				across {count(totals.meetings)} meeting symbols, {decimal(totals.tokens / 1e6)} M words
			</p>
		</div>
		<div>
			<dt class="label">Containing <code>genocid*</code></dt>
			<dd>{count(totals.bearing)}</dd>
			<p>{percent(totals.bearing / totals.speeches)} of the corpus</p>
		</div>
		<div>
			<dt class="label">Occurrences of the word</dt>
			<dd>{count(totals.occurrences)}</dd>
			<p>{decimal(totals.occurrences / totals.bearing)} per speech that uses it</p>
		</div>
		<div>
			<dt class="label">Densest year</dt>
			<dd>{densest}</dd>
			<p>not {loudest}, which had the most occurrences</p>
		</div>
	</dl>

	<section class="finding">
		<h2>The peak that is not there</h2>
		<p>
			The best-known fact about this corpus is that 2014 out-says 1994: {count(
				Math.max(...(genocide.occurrences ?? []))
			)} occurrences against {count(genocide.occurrences?.[index1994] ?? 0)}. It is true, and it is
			an artefact of the Council talking more about everything. Speeches per year roughly
			<strong
				>{decimal(corpus.speeches[corpus.speeches.length - 1] / corpus.speeches[0])}&times;</strong
			> over the period.
		</p>
	</section>

	<Figure
		title="Occurrences and share of speeches, {years[0]}&ndash;{years[years.length - 1]}"
		question="Did the Council come to talk about genocide more, or simply to talk more?"
		source="04_series.py → series/annual.json, series/change_points.json"
		download={{
			name: ['unsc', 'occurrences-and-share'],
			table: () =>
				annualTable('Occurrences and share of speeches', [
					'drawn: genocide — occurrences and share of speeches'
				]),
			chart: () => contrastFigure?.svg() ?? null
		}}
	>
		{#snippet reading()}
			<p>
				<strong>The bars</strong> count every occurrence of <code>genocid*</code> in a year, on the
				left-hand axis. The <strong>line</strong> is the share of that year's speeches containing it,
				on the right-hand axis. Select a year to open its concordance evidence.
			</p>
			<p>
				The denominator-aware binomial scan
				{#if rateInference?.accepted}supports its strongest two-rate partition at <strong
						>{rateInference.label}</strong
					>, with the later aggregate {decimal(rateInference.ratio ?? 0)}&times; the earlier one.{:else}<strong
						>does not reject a constant annual rate</strong
					> after the planned correction.{/if}
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				A share of speeches is not a measure of intensity: a speech that says the word once counts
				the same as a speech that repeats it many times. Both views are here for that reason.
			</p>
			<p>
				The scan preserves annual speech denominators and repeats the full search under a
				constant-rate null. It cannot distinguish an abrupt break from a smooth trend, treats annual
				bins as independent, and does not model clustering by meeting. The partition is not a causal
				date.
			</p>
		{/snippet}
		<Chart
			bind:this={contrastFigure}
			option={contrast}
			height="400px"
			description="Bar and line chart. Occurrences of genocide peak in 2014 while the share of speeches peaks in 1994."
			onclick={drillYear}
		/>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View annual values as a table</summary>
			<table>
				<thead
					><tr
						><th>Year</th><th class="num">Occurrences</th><th class="num">Share of speeches</th></tr
					></thead
				><tbody
					>{#each years as year, index (year)}<tr
							><td
								><a href={`${resolve('/concordance')}?term=genocide&from=${year}&to=${year}`}
									>{year}</a
								></td
							><td class="num">{count(genocide.occurrences?.[index] ?? 0)}</td><td class="num"
								>{percent(genocide.speech_rate[index])}</td
							></tr
						>{/each}</tbody
				>
			</table>
		</details>
	</Figure>

	<section class="finding">
		<h2>What does move</h2>
		<p>
			{#if rateInference?.accepted}For <em>genocide</em>, the strongest corrected two-rate partition
				begins in <strong>{rateInference.label}</strong> and the later aggregate is {decimal(
					rateInference.ratio ?? 0
				)}&times; the earlier rate.{:else}The single word does not reject a constant annual
				prevalence after correction.{/if}
			For the wider <em>atrocity core</em> &mdash; genocide, ethnic cleansing, crimes against
			humanity, war crimes, mass atrocity &mdash;
			{#if atrocityInference?.accepted}the corresponding partition begins in <strong
					>{atrocityInference.label}</strong
				>, with a ratio of {decimal(atrocityInference.ratio ?? 0)}&times;.{:else}the model likewise
				finds no corrected two-rate contrast.{/if}
			These are model-based period contrasts, not proof that discourse changed abruptly in either year.
		</p>
	</section>

	<Figure
		title="Register share, {years[0]}&ndash;{years[years.length - 1]}"
		question="Which vocabulary is the word embedded in, and does that mix change?"
		source="05_lexical.py registers via 03_lexicon.py → series/annual.json"
		note={registerView === 'rows'
			? 'Each row is scaled to its own maximum · the figure at the right is the period share'
			: 'One shared scale · hover a year for its values and any reference date it carries'}
		download={{
			name: ['unsc', 'register-share', registerView],
			table: () =>
				annualTable('Register share', [
					`view: ${registerView === 'rows' ? 'each row to its own maximum' : 'one shared scale'}`,
					'drawn: the six registers'
				]),
			chart: () => registerFigure?.svg() ?? null
		}}
	>
		{#snippet controls()}
			<div class="view">
				<span class="label" id="register-view">View</span>
				<div class="segmented" role="group" aria-labelledby="register-view">
					<button
						type="button"
						aria-pressed={registerView === 'rows'}
						title="Each register on its own axis, scaled to its own maximum"
						onclick={() => (registerView = 'rows')}>Rows</button
					>
					<button
						type="button"
						aria-pressed={registerView === 'lines'}
						title="All six on one shared axis, with the reference dates"
						onclick={() => (registerView = 'lines')}>Lines</button
					>
				</div>
			</div>
		{/snippet}

		{#snippet reading()}
			<p>
				Each row is the share of a year's speeches using at least one term from one of the lexicon's
				six registers: the <em>core</em> word itself, the
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
				<strong>These rows are not a composition and do not sum to anything.</strong> One speech can use
				four registers at once and is counted in all four. A stacked version of this figure would be wrong.
			</p>
			<p>
				<strong>Each row is scaled to its own maximum</strong>, so the shapes are comparable and the
				levels are not — read the level off the share at the right of each row.
			</p>
			<p>
				Register assignment is a hypothesis about how the vocabulary groups, recorded in
				<code>config/lexicon.yml</code>, not a finding.
			</p>
		{/snippet}
		{#if registerView === 'rows'}
			<SmallMultiples
				rows={registerRows}
				periods={years}
				events={eventTicks}
				eventsLabel="{data.overlay.events.length} reference dates"
				description="Six rows, one per lexical register, each showing the share of speeches per year that use it, scaled to its own maximum."
			/>
		{:else}
			<Chart
				bind:this={registerFigure}
				option={registerLines}
				height="380px"
				description="Six lines on one shared axis showing the share of speeches per year using each lexical register, with faint rules on the years carrying a reference date."
			/>
		{/if}
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View register shares as a table</summary>
			<table>
				<thead
					><tr
						><th>Year</th>{#each Object.keys(data.series.registers).sort() as name (name)}<th
								class="num">{name}</th
							>{/each}</tr
					></thead
				><tbody
					>{#each years as year, index (year)}<tr
							><td>{year}</td>{#each Object.keys(data.series.registers).sort() as name (name)}<td
									class="num">{percent(data.series.registers[name].speech_rate[index])}</td
								>{/each}</tr
						>{/each}</tbody
				>
			</table>
		</details>
	</Figure>

	<section class="onward">
		<h2>Where to go from here</h2>
		<ul class="onward-list">
			<li>
				<a href={resolve('/chronology')}>
					<strong>Chronology</strong>
					<span
						>Every term and register over time, against {data.overlay.events.length} reference dates &mdash;
						{kinds.map(([k, n]) => `${n} ${k}`).join(', ')}.</span
					>
					<Icon icon={ArrowRight} />
				</a>
			</li>
			<li>
				<a href={resolve('/language')}>
					<strong>Language</strong>
					<span
						>What the word travels with, how that differs by speaker and period, and which terms
						co-occur.</span
					>
					<Icon icon={ArrowRight} />
				</a>
			</li>
			<li>
				<a href={resolve('/concordance')}>
					<strong>Concordance</strong>
					<span
						>All {count(totals.occurrences)} occurrences in context, sortable, and expandable to the full
						speech.</span
					>
					<Icon icon={ArrowRight} />
				</a>
			</li>
			<li>
				<a href={resolve('/methods')}>
					<strong>Methods</strong>
					<span>How each figure was produced, sourced and bounded.</span>
					<Icon icon={ArrowRight} />
				</a>
			</li>
		</ul>
	</section>
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

	.standfirst em {
		color: var(--ink);
		font-style: italic;
	}

	/* Rule 05: numbers are set, not styled. A band of type between two rules,
	   with hairlines between the columns — no tile, no panel, no radius. */
	.figures {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
		margin: 0 0 var(--sp-7);
		border-top: var(--hair) solid var(--rule-strong);
		border-bottom: var(--hair) solid var(--rule-strong);
	}

	.figures > div {
		padding: var(--sp-4) var(--sp-5) var(--sp-4) 0;
		border-left: var(--hair) solid var(--rule);
		padding-left: var(--sp-5);
	}

	.figures > div:first-child {
		border-left: 0;
		padding-left: 0;
	}

	.figures dd {
		margin: var(--sp-1) 0 0;
		font-family: var(--serif);
		font-size: var(--step-4);
		font-variant-numeric: tabular-nums lining-nums;
		line-height: 1.05;
	}

	.figures p {
		margin: 0;
		font-size: var(--step--1);
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

	.finding {
		max-width: var(--measure);
		margin: 0 0 var(--sp-5);
	}

	.finding h2 {
		margin-bottom: 0.25em;
	}

	.onward {
		margin-top: var(--sp-6);
	}

	.onward h2 {
		font-size: var(--step-2);
	}

	/* Rule 01: separated by rules and space, never by boxes. */
	.onward-list {
		list-style: none;
		margin: 0;
		padding: 0;
		border-top: var(--hair) solid var(--rule-strong);
	}

	.onward-list li {
		border-bottom: var(--hair) solid var(--rule);
	}

	.onward-list a {
		display: grid;
		grid-template-columns: 9rem minmax(0, 1fr) auto;
		gap: var(--sp-4);
		align-items: baseline;
		padding: var(--sp-3) 0;
		text-decoration: none;
		color: inherit;
	}

	.onward-list strong {
		font-family: var(--serif);
		font-size: var(--step-1);
		font-weight: 600;
		color: var(--blue);
	}

	.onward-list span {
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.5;
		color: var(--ink-2);
	}

	.onward-list a:hover strong {
		color: var(--ink);
	}

	/* The arrow leads the eye out of the row; it is the only thing that moves. */
	.onward-list a :global(.icon) {
		color: var(--ink-3);
		transition: transform var(--dur) var(--ease);
	}

	.onward-list a:hover :global(.icon) {
		color: var(--blue);
		transform: translateX(0.25rem);
	}

	@media (max-width: 44rem) {
		.onward-list a {
			grid-template-columns: minmax(0, 1fr) auto;
		}

		.onward-list strong {
			grid-column: 1 / -1;
		}
	}

	/* `.data-table` itself is in `app.css`: three routes open a table this way. */
</style>
