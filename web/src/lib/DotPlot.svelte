<script lang="ts">
	/**
	 * The collocate profile as a dot plot: one row per word, ranked as the
	 * artefact ranks them, position by log ratio, area by frequency beside the
	 * term, and a spread mark for dispersion. Inline SVG rather than ECharts so
	 * every word is a link a keyboard can reach, and so the export is the
	 * drawing itself.
	 */
	import { colours } from './theme';
	import { dotPosition, dotRadius, dotScale, spreadFill } from './dotplot';
	import { count, decimal, signed } from './format';
	import type { Word } from './types';

	interface Props {
		rows: Word[];
		term: string;
		href: (word: Word) => string;
		description: string;
	}

	let { rows, term, href, description }: Props = $props();

	let element = $state<SVGSVGElement | null>(null);
	export function svg(): SVGSVGElement | null {
		return element;
	}

	const ROW = 22;
	const LABEL = 150;
	const SPREAD = 28;
	const WIDTH = 720;
	const TOP = 28;
	const track = WIDTH - LABEL - SPREAD - 24;

	const scale = $derived(dotScale(rows));
	const largest = $derived(Math.max(1, ...rows.map((row) => row.target)));
	const height = $derived(TOP + rows.length * ROW + 8);
	const x = (ratio: number) => LABEL + dotPosition(ratio, scale) * track;

	const title = (word: Word) =>
		`${word.word}: ${count(word.target)} near ${term}, log ratio ${signed(word.log_ratio)}` +
		(word.log_dice == null ? '' : `, logDice ${decimal(word.log_dice)}`) +
		`, ${count(word.documents)} speeches` +
		(word.meetings == null ? '' : ` / ${count(word.meetings)} meetings`) +
		`, DP ${decimal(word.dp)}`;
</script>

<svg
	bind:this={element}
	viewBox="0 0 {WIDTH} {height}"
	width="100%"
	role="img"
	aria-label={description}
	style:font-family="var(--sans)"
	class="dotplot"
>
	<g class="axis">
		{#each scale.ticks as tick (tick)}
			<line
				x1={x(tick)}
				x2={x(tick)}
				y1={TOP - 6}
				y2={height - 8}
				stroke={tick === 0 ? $colours.rule : $colours.ruleSoft}
				stroke-width={tick === 0 ? 1.2 : 0.8}
			/>
			<text x={x(tick)} y={TOP - 10} text-anchor="middle" font-size="10" fill={$colours.inkFaint}
				>{tick === 0 ? '0' : signed(tick)}</text
			>
		{/each}
		<text x={LABEL} y={10} font-size="10" fill={$colours.inkFaint}>log ratio</text>
		<text x={WIDTH - 24} y={10} font-size="10" fill={$colours.inkFaint} text-anchor="end"
			>spread</text
		>
	</g>
	{#each rows as word, index (word.word)}
		{@const cy = TOP + index * ROW + ROW / 2}
		<g class="row">
			<title>{title(word)}</title>
			<a href={href(word)}>
				<text x={LABEL - 10} y={cy + 4} text-anchor="end" font-size="12" fill={$colours.ink}
					>{word.word}</text
				>
			</a>
			<line
				x1={x(0)}
				x2={x(word.log_ratio)}
				y1={cy}
				y2={cy}
				stroke={$colours.ruleSoft}
				stroke-width="1"
			/>
			<circle
				cx={x(word.log_ratio)}
				{cy}
				r={dotRadius(word.target, largest)}
				fill={$colours.ink}
				fill-opacity="0.82"
			/>
			<rect
				x={WIDTH - 24 - SPREAD}
				y={cy - 5}
				width={SPREAD}
				height="10"
				fill="none"
				stroke={$colours.rule}
				stroke-width="0.8"
			/>
			<rect
				x={WIDTH - 24 - SPREAD}
				y={cy - 5}
				width={SPREAD * spreadFill(word.dp)}
				height="10"
				fill={$colours.inkFaint}
			/>
		</g>
	{/each}
</svg>

<style>
	.dotplot {
		display: block;
		max-width: 100%;
		height: auto;
	}

	.dotplot a:focus-visible text,
	.dotplot a:hover text {
		fill: var(--blue);
		text-decoration: underline;
	}
</style>
