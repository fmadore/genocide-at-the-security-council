<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import PageMeta from '$lib/PageMeta.svelte';
	import SmallMultiples from '$lib/SmallMultiples.svelte';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, decimal, escapeHtml, isoDate, percent } from '$lib/format';
	import { headlineMeasure } from '$lib/headline';
	import { PAGE_METADATA, STRUCTURED_DATA_JSON } from '$lib/seo';
	import {
		axisX,
		axisY,
		colours,
		endLabel,
		grid,
		markLine,
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
						data.series.corpus.words[index],
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

	const years = $derived(data.series.periods as number[]);
	const corpus = $derived(data.series.corpus);
	/* The published headline since lexicon v4: `genocide` minus its
	   `genocidaires` actor label. Calling the ex-FAR génocidaires names who did
	   it rather than qualifying the event, and 31 of the raw term's 6,092
	   occurrences are that. The raw term is still in the artefact and still what
	   the concordance enumerates; the figure below says so in one line — and only
	   when the derived measure is what it draws, since an artefact cut before v4
	   carries the raw term alone and this page must still open on it. */
	const headline = $derived(headlineMeasure(Object.keys(data.series.terms)) ?? 'genocide');
	const qualified = $derived(headline === 'genocide_qualification');
	const genocide = $derived(data.series.terms[headline]);

	const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);

	const totals = $derived({
		speeches: sum(corpus.speeches),
		words: sum(corpus.words),
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

	const rateInference = $derived(data.breaks.inference.series[headline]?.speech_rate ?? null);
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
		const p = $colours;
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
		'contentious',
		'descriptive'
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
		const p = $colours;
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

<PageMeta meta={PAGE_METADATA['/']} structuredData={STRUCTURED_DATA_JSON} />

<article>
	<header class="lede">
		<h1>The word, and what it was doing there</h1>
		<p class="standfirst">
			Between 1992 and 2023 the UN Security Council produced {count(totals.meetings)} meeting records
			holding {count(totals.speeches)} speeches. In {count(totals.bearing)} of them &mdash; {percent(
				totals.bearing / totals.speeches
			)} &mdash; someone said <em>genocide</em>. This site asks which speeches those were, and what
			the word was doing in them.
		</p>
	</header>

	<dl class="figures">
		<div>
			<dt class="label">Speeches in the corpus</dt>
			<dd>{count(totals.speeches)}</dd>
			<p>
				across {count(totals.meetings)} meeting records, {decimal(totals.words / 1e6)} million words
			</p>
		</div>
		<div>
			<dt class="label">Speeches using <code>genocid*</code></dt>
			<dd>{count(totals.bearing)}</dd>
			<p>
				{percent(totals.bearing / totals.speeches)} of the corpus; the asterisk catches
				<em>genocide</em>, <em>genocidal</em> and <em>genocides</em> alike
			</p>
		</div>
		<div>
			<dt class="label">Occurrences of the word</dt>
			<dd>{count(totals.occurrences)}</dd>
			<p>{decimal(totals.occurrences / totals.bearing)} per speech that uses it</p>
		</div>
		<div>
			<dt class="label">Peak year by share</dt>
			<dd>{densest}</dd>
			<p>the largest proportion of speeches; {loudest} had the most occurrences</p>
		</div>
	</dl>

	<section class="finding">
		<h2>Why {loudest} tops the raw count</h2>
		<p>
			{loudest} carries more occurrences of the word than 1994 does: {count(
				Math.max(...(genocide.occurrences ?? []))
			)} against {count(genocide.occurrences?.[index1994] ?? 0)}. That is true, and it is mostly a
			side effect of a Council that talks more about everything. The number of speeches held each
			year grew roughly
			<strong
				>{decimal(corpus.speeches[corpus.speeches.length - 1] / corpus.speeches[0])}&times;</strong
			>
			across the period, so a raw count can rise while the habit behind it stays flat. Dividing by the
			speeches actually held is what every figure below does.
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
					`drawn: ${headline} — occurrences and share of speeches`
				]),
			chart: () => contrastFigure?.svg() ?? null
		}}
	>
		{#snippet reading()}
			<p>
				<strong>Bars</strong> count qualifying uses of <code>genocid*</code> in a year (left axis);
				the <strong>line</strong> is the share of that year's speeches using it (right axis). Select a
				year for its lines.
			</p>
			<p>
				{#if rateInference?.accepted}A test allowing for the Council's growth splits the share at
					<strong>{rateInference.label}</strong>, the later rate {decimal(
						rateInference.ratio ?? 0
					)}&times; the earlier.{:else}The same test finds <strong>one steady rate</strong>: no
					split survives it.{/if}
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				A share says nothing about intensity: a speech saying the word once counts the same as one
				repeating it twenty times. The split describes the series; it is not a date on which
				something happened.{#if qualified}
					<em>Genocidaires</em>, an actor label, is counted separately and excluded here.{/if}
				<a href="{resolve('/methods')}#change-points">Method: change points &rarr;</a>
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
		<h2>Where the rate does change</h2>
		<p>
			{#if rateInference?.accepted}For <em>genocide</em> on its own, the best-supported split falls
				at
				<strong>{rateInference.label}</strong>, and the rate after it is {decimal(
					rateInference.ratio ?? 0
				)}&times; the rate before.{:else}For <em>genocide</em> on its own, a single steady rate survives
				the test.{/if}
			The wider <em>atrocity core</em> gathers five phrases at once: genocide, ethnic cleansing,
			crimes against humanity, war crimes and mass atrocity.
			{#if atrocityInference?.accepted}Its split falls at <strong>{atrocityInference.label}</strong
				>, with a ratio of {decimal(atrocityInference.ratio ?? 0)}&times;.{:else}It too is best
				described by one steady rate.{/if}
			Both results compare one stretch of years with another. Neither shows that Council language turned
			a corner in the year named.
		</p>
	</section>

	<Figure
		title="Register share, {years[0]}&ndash;{years[years.length - 1]}"
		question="Which family of words does genocide sit in, and does that mix change over time?"
		source="05_lexical.py registers via 03_lexicon.py → series/annual.json"
		note={registerView === 'rows'
			? 'Each row is scaled to its own maximum · the number at the right is the share across the whole period'
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
				The word list is sorted into six <em>registers</em>, families of vocabulary that do similar
				work: the <em>core</em> word; <em>legal</em>; <em>preventive</em>; <em>commemorative</em>;
				<em>contentious</em> (denial, glorification); <em>accountability</em> (courts, tribunals, impunity).
				Each row is the share of a year's speeches using at least one word of that family. Accountability
				and legal language dominate; the core word runs about ten times lower.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>These rows do not add up to a whole:</strong> one speech can use four registers and
				is counted in all four. <strong>Each row is scaled to its own maximum</strong>, so shapes
				compare and levels do not; read the level off the share at the right.
				<a href="{resolve('/methods')}#word-list">The registers are a proposal &rarr;</a>
			</p>
		{/snippet}
		{#if registerView === 'rows'}
			<SmallMultiples
				rows={registerRows}
				periods={years}
				events={eventTicks}
				eventsLabel="{data.overlay.events.length} reference dates"
				description="Six rows, one per register of vocabulary, each showing the share of speeches per year that use it, scaled to its own maximum."
			/>
		{:else}
			<Chart
				bind:this={registerFigure}
				option={registerLines}
				height="380px"
				description="Six lines on one shared axis showing the share of speeches per year using each register of vocabulary, with faint rules on the years carrying a reference date."
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
						>Every word and word family over time, set against {data.overlay.events.length} reference
						dates: {kinds.map(([k, n]) => `${n} ${k}`).join(', ')}.</span
					>
					<Icon icon={ArrowRight} />
				</a>
			</li>
			<li>
				<a href={resolve('/language')}>
					<strong>Language</strong>
					<span
						>The words that sit next to <em>genocide</em>, how they differ from one speaker or
						decade to the next, and which terms turn up in the same speech.</span
					>
					<Icon icon={ArrowRight} />
				</a>
			</li>
			<li>
				<a href={resolve('/concordance')}>
					<strong>Concordance</strong>
					<span
						>All {count(totals.occurrences)} occurrences with the text around them, sortable, and openable
						to the full speech.</span
					>
					<Icon icon={ArrowRight} />
				</a>
			</li>
			<li>
				<a href={resolve('/methods')}>
					<strong>Methods</strong>
					<span
						>How each figure was made, where its numbers come from, and what they cannot show.</span
					>
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
