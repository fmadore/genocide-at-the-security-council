<script lang="ts">
	/**
	 * Agenda or usage? The genocide rate's change, decade to decade, taken apart.
	 *
	 * A renderer over `#lib/decomposition`, which settles what is drawn, what is
	 * muted and why. Each pair of decades is a row: a solid bar for the part of
	 * the change that came from the Council's speeches moving between groups
	 * (composition), an outlined bar for the part that came from use inside the
	 * same groups (within), and a tick at the net change the two add to. Ink and
	 * weight of ink only: the register hues are an analytical classification
	 * and these two parts are not registers.
	 *
	 * Drawn in markup with the palette's literal colours rather than the CSS
	 * custom properties, so the SVG that leaves through the download is the one
	 * on screen, in either theme, without a stylesheet to resolve it.
	 */
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Figure from '#lib/Figure.svelte';
	import Icon from '#lib/Icon.svelte';
	import { provenanceOf } from '#lib/export.js';
	import type { ExportRequest } from '#lib/export.js';
	import { count, points } from '#lib/format.js';
	import { colours, FONT } from '#lib/theme.js';
	import {
		EXPORT_COLUMNS,
		THIN_USING,
		decadeBases,
		decadeLabel,
		defaultPair,
		equation,
		exportRows,
		incompleteEnd,
		plan,
		pp,
		shareText,
		splitLabel,
		sum,
		tickText,
		ticks
	} from '#lib/decomposition.js';
	import type { PartsPair, PartsSplit } from '#lib/decomposition.js';
	import type { AnnualSeries, Decomposition } from '#lib/types.js';

	let {
		data,
		annual,
		split = $bindable()
	}: { data: Decomposition; annual: AnnualSeries | null; split: PartsSplit } = $props();

	const result = $derived(plan({ data, split, annual }));
	const bases = $derived(decadeBases(annual, data.term));
	const end = $derived(incompleteEnd(annual, bases));
	const endText = $derived(end ? (end.lastDate ?? String(end.lastYear)) : null);
	const thinPairs = $derived(result.pairs.filter((pair) => pair.thin).length);

	let chosen = $state<number | null>(null);
	let focused = $state<number | null>(null);
	const active = $derived(chosen ?? defaultPair(result.pairs));
	const current = $derived(result.pairs[active] ?? null);

	let width = $state(0);
	let svgElement = $state<SVGSVGElement | null>(null);
	const W = $derived(Math.max(280, width || 960));
	const wide = $derived(W >= 720);

	/* Geometry. Wide: decades on the left, the sum on the right, the bars
	   between. Narrow: the words on two lines over full-width bars. */
	const LABEL = 214;
	const RIGHT = 176;
	const TOP = 52;
	const BAR = 13;
	const GAP = 4;
	const NOTE = 14;

	const scaleTicks = $derived(ticks(result.domain, wide ? 8 : 5));
	const lo = $derived(scaleTicks[0] ?? 0);
	const hi = $derived(scaleTicks.at(-1) ?? 0);
	const plotLeft = $derived(wide ? LABEL : 0);
	const plotRight = $derived(wide ? W - RIGHT : W - 1);
	const x = (value: number) => plotLeft + ((value - lo) / (hi - lo || 1)) * (plotRight - plotLeft);

	function note(pair: PartsPair): string | null {
		const parts: string[] = [];
		if (pair.thin && pair.baseFrom && pair.baseTo)
			parts.push(`thin: ${count(pair.baseFrom.using)} → ${count(pair.baseTo.using)} use the word`);
		if (end && pair.to === end.decade) parts.push(`${end.decade}s to ${endText}`);
		if (!pair.adds) parts.push(`parts miss the change by ${points(pair.residual)}`);
		return parts.length ? parts.join(' · ') : null;
	}

	interface RowBox {
		pair: PartsPair;
		top: number;
		height: number;
		bars: number;
		note: string | null;
	}

	const rows = $derived.by(() => {
		let y = TOP;
		return result.pairs.map((pair): RowBox => {
			const text = note(pair);
			const height = wide ? 62 : text ? 90 : 76;
			const bars = wide ? y + 16 : y + (text ? 56 : 42);
			const box = { pair, top: y, height, bars, note: text };
			y += height;
			return box;
		});
	});
	const H = $derived((rows.at(-1)?.top ?? TOP) + (rows.at(-1)?.height ?? 0) + 6);

	function bar(value: number) {
		const zero = x(0);
		const at = x(value);
		const size = Math.abs(at - zero);
		return { x: Math.min(zero, at), width: value === 0 ? 0 : Math.max(1, size) };
	}

	const speeches = (pair: PartsPair) =>
		pair.baseFrom && pair.baseTo
			? `${count(pair.baseFrom.speeches)} → ${count(pair.baseTo.speeches)} speeches`
			: 'speeches not in the annual series';

	const names = (pair: PartsPair) =>
		`${decadeLabel(pair.from, pair.baseFrom)} → ${decadeLabel(pair.to, pair.baseTo)}`;

	function describe(pair: PartsPair): string {
		return (
			`${names(pair)}: share ${shareText(pair.rateFrom)} to ${shareText(pair.rateTo)}, ` +
			`change ${points(pair.change)}, composition ${points(pair.composition)}, ` +
			`within ${points(pair.within)}${pair.thin ? ', thin decade' : ''}`
		);
	}

	function choose(index: number) {
		chosen = index;
	}

	function key(event: KeyboardEvent, index: number) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			choose(index);
		} else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			const next = Math.min(
				result.pairs.length - 1,
				Math.max(0, index + (event.key === 'ArrowDown' ? 1 : -1))
			);
			choose(next);
			svgElement?.querySelectorAll<SVGGElement>('g.pair')[next]?.focus();
		}
	}

	function table(): ExportRequest {
		return {
			title: 'Agenda or usage?',
			columns: EXPORT_COLUMNS,
			rows: exportRows(data, annual),
			provenance: provenanceOf(data.meta, 'series/decomposition.json'),
			filters: [
				`term: ${data.term}`,
				`unit: ${data.unit} (rates and parts as proportions)`,
				`periods: ${data.periods}`,
				`showing: ${splitLabel(result.split).toLowerCase()}`,
				`thin: either decade under ${THIN_USING} speeches using the word (speeches from series/annual.json)`
			],
			scope:
				'every decade pair of every split the artefact holds; largest_groups lists the groups ' +
				'the artefact names, each with its composition and within parts together'
		};
	}

	const p = $derived($colours);
	const legendItems = $derived(
		wide
			? [
					{ kind: 'composition', text: 'Composition: speeches moved between groups' },
					{ kind: 'within', text: 'Within: use changed inside the same groups' },
					{ kind: 'change', text: 'Net change, the sum of the two' }
				]
			: [
					{ kind: 'composition', text: 'Composition' },
					{ kind: 'within', text: 'Within' },
					{ kind: 'change', text: 'Net change' }
				]
	);
	/* Legend positions from an estimate of each label's width: the face is
	   about 0.55em wide on average at this size. */
	const legend = $derived.by(() => {
		let at = 0;
		return legendItems.map((item) => {
			const place = { ...item, x: at };
			at += 18 + item.text.length * 6.4 + (wide ? 28 : 16);
			return place;
		});
	});
</script>

<Figure
	title="Agenda or usage?"
	question="Did the word's share of speeches change because the Council's agenda changed, or because speakers used it more?"
	source="04_series.py → series/decomposition.json"
	note="Percentage points of the share of speeches using the word. Both groupings share one axis."
	download={{
		name: ['unsc', 'agenda-or-usage', result.split],
		table,
		chart: () => svgElement
	}}
>
	{#snippet controls()}
		<div class="segmented" role="group" aria-label="Split the change">
			{#each result.splits as option (option.id)}
				<button
					type="button"
					aria-pressed={result.split === option.id}
					onclick={() => (split = option.id)}>{option.label}</button
				>
			{/each}
		</div>
	{/snippet}

	{#snippet reading()}
		<p>
			One row per pair of decades. The solid bar is composition, the change from speeches moving
			between groups; the outlined bar is within, the change inside the same groups. The tick is the
			net change, which the two bars add to. Right of the line raises the share. Select a row to
			list the groups that moved it most.
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>
			The split depends on the grouping: agenda items are the corpus's hand-coded categories, and
			another grouping divides the same change differently. A group present in one decade only
			counts entirely as composition. Muted rows rest on fewer than {THIN_USING} speeches using the word
			in a decade; the record ends {endText}.
		</p>
	{/snippet}
	{#snippet more()}
		<p>{data.method}</p>
		<p>
			The decade's speeches come from the annual series, whose decade shares agree with these. The
			1940s hold only 1946 to 1949{#if end}, and the {end.decade}s only to {endText}{/if}, so the
			last row compares a part-decade with a whole one. A group's contribution is its composition
			and within parts together; the artefact names the largest few, so a list need not add to the
			change.
		</p>
	{/snippet}

	{#if result.refusal}
		<p class="refusal">
			{result.refusal === 'no-splits'
				? 'The artefact holds no decomposition to draw.'
				: 'This grouping holds no decade pairs.'}
		</p>
	{:else}
		<div class="plot" bind:clientWidth={width}>
			<svg
				bind:this={svgElement}
				xmlns="http://www.w3.org/2000/svg"
				width={W}
				height={H}
				viewBox="0 0 {W} {H}"
				font-family={FONT}
				role="group"
				aria-label="Change in the share of speeches using the word, decade to decade, {splitLabel(
					result.split
				).toLowerCase()}: composition and within parts"
			>
				<!-- Key -->
				<g aria-hidden="true" font-size="12" fill={p.inkSoft}>
					{#each legend as item (item.kind)}
						<g transform="translate({item.x},6)">
							{#if item.kind === 'composition'}
								<rect x="0" y="2" width="14" height="10" fill={p.ink} />
							{:else if item.kind === 'within'}
								<rect
									x="0.75"
									y="2.75"
									width="12.5"
									height="8.5"
									fill={p.paper}
									stroke={p.ink}
									stroke-width="1.5"
								/>
							{:else}
								<line x1="7" y1="-1" x2="7" y2="15" stroke={p.ink} stroke-width="2.5" />
							{/if}
							<text x="20" y="11">{item.text}</text>
						</g>
					{/each}
				</g>

				<!-- Axis: ticks in points, the zero line in ink -->
				<g aria-hidden="true" font-size="11" fill={p.inkSoft}>
					{#each scaleTicks as value, index (value)}
						<line
							x1={x(value)}
							x2={x(value)}
							y1={TOP - 6}
							y2={wide ? H - 4 : TOP}
							stroke={value === 0 ? p.ink : p.ruleSoft}
							stroke-width="1"
						/>
						<text
							x={x(value)}
							y={TOP - 11}
							text-anchor={!wide && index === 0
								? 'start'
								: !wide && index === scaleTicks.length - 1
									? 'end'
									: 'middle'}
							font-weight={value === 0 ? 600 : 400}
							fill={value === 0 ? p.ink : p.inkSoft}
							>{tickText(value)}{index === scaleTicks.length - 1 ? ' pts' : ''}</text
						>
					{/each}
				</g>

				{#each rows as row, index (row.pair.from)}
					{@const pair = row.pair}
					{@const muted = pair.thin === true}
					{@const ink = muted ? p.inkFaint : p.ink}
					{@const comp = bar(pair.composition)}
					{@const within = bar(pair.within)}
					{@const tickX = x(pair.change)}
					<g
						class="pair"
						role="button"
						tabindex="0"
						aria-pressed={index === active}
						aria-label={describe(pair)}
						onclick={() => choose(index)}
						onmouseenter={() => choose(index)}
						onfocus={() => {
							focused = index;
							choose(index);
						}}
						onblur={() => (focused = null)}
						onkeydown={(event) => key(event, index)}
					>
						<rect
							x="0"
							y={row.top}
							width={W}
							height={row.height}
							fill={p.ink}
							fill-opacity={index === active ? 0.07 : 0}
						/>
						{#if focused === index}
							<rect
								class="focus"
								x="1"
								y={row.top + 1}
								width={W - 2}
								height={row.height - 2}
								fill="none"
							/>
						{/if}
						<line
							x1="0"
							x2={W}
							y1={row.top + row.height}
							y2={row.top + row.height}
							stroke={p.ruleSoft}
						/>

						{#if wide}
							<text x="8" y={row.top + 20} font-size="13" font-weight="600" fill={ink}
								>{names(pair)}</text
							>
							<text x="8" y={row.top + 36} font-size="12" fill={p.inkSoft}
								>{shareText(pair.rateFrom)} → {shareText(pair.rateTo)}</text
							>
							<text x="8" y={row.top + 51} font-size="11" fill={p.inkFaint}>{speeches(pair)}</text>
							<text x={W - RIGHT + 14} y={row.top + 22} font-size="13" font-weight="600" fill={ink}
								>{pp(pair.change)} pts</text
							>
							<text x={W - RIGHT + 14} y={row.top + 37} font-size="12" fill={p.inkSoft}
								>= {sum(pair)}</text
							>
							{#if row.note}
								<text x={W - RIGHT + 14} y={row.top + 52} font-size="11" fill={p.inkFaint}
									>{row.note}</text
								>
							{/if}
						{:else}
							<text x="0" y={row.top + 17} font-size="13" font-weight="600" fill={ink}
								>{names(pair)}</text
							>
							<text
								x={W - 1}
								y={row.top + 17}
								font-size="12"
								font-weight="600"
								fill={ink}
								text-anchor="end">{equation(pair)}</text
							>
							<text x="0" y={row.top + 32} font-size="11" fill={p.inkFaint}
								>{shareText(pair.rateFrom)} → {shareText(pair.rateTo)} · {speeches(pair)}</text
							>
							{#if row.note}
								<text x="0" y={row.top + 32 + NOTE} font-size="11" fill={p.inkFaint}
									>{row.note}</text
								>
							{/if}
							<!-- Narrow: the axis runs through the bars only, never the words. -->
							{#each scaleTicks as value (value)}
								<line
									x1={x(value)}
									x2={x(value)}
									y1={row.bars - 5}
									y2={row.bars + 2 * BAR + GAP + 5}
									stroke={value === 0 ? p.ink : p.ruleSoft}
								/>
							{/each}
						{/if}

						<g opacity={muted ? 0.45 : 1}>
							<rect x={comp.x} y={row.bars} width={comp.width} height={BAR} fill={p.ink} />
							{#if within.width > 0}
								<rect
									x={within.x + 0.75}
									y={row.bars + BAR + GAP + 0.75}
									width={Math.max(0.5, within.width - 1.5)}
									height={BAR - 1.5}
									fill={p.paper}
									stroke={p.ink}
									stroke-width="1.5"
								/>
							{/if}
							<line
								x1={tickX}
								x2={tickX}
								y1={row.bars - 5}
								y2={row.bars + 2 * BAR + GAP + 5}
								stroke={p.paper}
								stroke-width="6"
							/>
							<line
								x1={tickX}
								x2={tickX}
								y1={row.bars - 5}
								y2={row.bars + 2 * BAR + GAP + 5}
								stroke={p.ink}
								stroke-width="2.5"
							/>
						</g>
					</g>
				{/each}
			</svg>
		</div>

		<!-- The selected pair in words, where a keyboard and a screen reader can
		     reach it: a tooltip would hold the one thing this figure adds. -->
		<div class="detail" aria-live="polite">
			{#if current}
				<p class="detail-head">
					<strong>{names(current)}</strong>, {splitLabel(result.split).toLowerCase()}
				</p>
				<p>
					The share of speeches using the word went from {shareText(current.rateFrom)} to {shareText(
						current.rateTo
					)}, {points(current.change)}: {points(current.composition)} from composition and {points(
						current.within
					)} within.
					{#if current.baseFrom && current.baseTo}
						{count(current.baseFrom.using)} of {count(current.baseFrom.speeches)} speeches used it in
						the first decade, {count(current.baseTo.using)} of {count(current.baseTo.speeches)} in the
						second.
					{/if}
					{#if current.thin}<strong>Thin:</strong> a decade under {THIN_USING} such speeches, so one debate
						can move its share.{/if}
				</p>
				{#if current.largest.length}
					<p class="label">Largest contributions, composition and within together</p>
					<ol class="largest">
						{#each current.largest as item (item.group)}
							<li>
								<span class="group">{item.group}</span>
								<span class="num">{points(item.contribution)}</span>
							</li>
						{/each}
					</ol>
				{/if}
			{/if}
		</div>
	{/if}

	<details class="data-table">
		<summary><Icon icon={ChevronRight} />View the decomposition as a table</summary>
		<div class="scroll">
			<table>
				<caption class="sr-only">
					Decade-to-decade change in the share of speeches using the word, {splitLabel(
						result.split
					).toLowerCase()}
				</caption>
				<thead>
					<tr>
						<th scope="col">Decades</th>
						<th scope="col" class="num">Share</th>
						<th scope="col" class="num">Speeches</th>
						<th scope="col" class="num">Using the word</th>
						<th scope="col" class="num">Change</th>
						<th scope="col" class="num">Composition</th>
						<th scope="col" class="num">Within</th>
						<th scope="col">Largest contribution</th>
					</tr>
				</thead>
				<tbody>
					{#each result.pairs as pair (pair.from)}
						<tr>
							<th scope="row">{names(pair)}{pair.thin ? ' (thin)' : ''}</th>
							<td class="num">{shareText(pair.rateFrom)} → {shareText(pair.rateTo)}</td>
							<td class="num"
								>{pair.baseFrom && pair.baseTo
									? `${count(pair.baseFrom.speeches)} → ${count(pair.baseTo.speeches)}`
									: '—'}</td
							>
							<td class="num"
								>{pair.baseFrom && pair.baseTo
									? `${count(pair.baseFrom.using)} → ${count(pair.baseTo.using)}`
									: '—'}</td
							>
							<td class="num">{points(pair.change)}</td>
							<td class="num">{points(pair.composition)}</td>
							<td class="num">{points(pair.within)}</td>
							<td
								>{pair.largest[0]
									? `${pair.largest[0].group} (${points(pair.largest[0].contribution)})`
									: '—'}</td
							>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</details>
	{#if thinPairs}<p class="sr-only">
			{thinPairs} rows are muted as thin.
		</p>{/if}
</Figure>

<style>
	.plot {
		width: 100%;
		min-width: 0;
	}

	svg {
		display: block;
		overflow: visible;
	}

	.pair {
		cursor: pointer;
		outline: none;
	}

	.focus {
		stroke: var(--blue-flag);
		stroke-width: 2;
	}

	.detail {
		margin-top: var(--sp-4);
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.detail p {
		margin: 0 0 var(--sp-2);
	}

	.detail-head {
		color: var(--ink);
	}

	.detail .label {
		margin: var(--sp-3) 0 var(--sp-1);
		font-weight: 600;
		color: var(--ink);
	}

	.largest {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.largest li {
		display: flex;
		justify-content: space-between;
		gap: var(--sp-4);
		padding: var(--sp-1) 0;
		border-bottom: var(--hair) solid var(--rule);
	}

	.num {
		text-align: end;
		font-variant-numeric: tabular-nums lining-nums;
		white-space: nowrap;
	}

	.scroll {
		overflow-x: auto;
	}

	td,
	th {
		white-space: nowrap;
	}

	tbody th {
		font-weight: 400;
	}

	.refusal {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
</style>
