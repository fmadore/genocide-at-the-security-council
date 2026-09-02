<script lang="ts">
	/**
	 * The lexicon's co-occurrence as a register-ordered matrix. One cell per
	 * pair, the same position on every load; shaded by normalised PMI, hatched
	 * where too few speeches share the pair to say anything, crossed where the
	 * pair is written into the lexicon and so is not a finding.
	 */
	import { REGISTER_ORDER, colours, registerColour, sequential, tone } from './theme';
	import { matrixCells, orderTerms } from './matrix';
	import type { MatrixCell, MatrixTerm } from './matrix';
	import { count, decimal, termLabel } from './format';
	import type { Edge, Network } from './types';

	interface Props {
		terms: MatrixTerm[];
		edges: Edge[];
		suppressed: Network['suppressed_nested_edges'];
		minimum: number;
		href: (term: string) => string;
		description: string;
	}

	let { terms, edges, suppressed, minimum, href, description }: Props = $props();

	let element = $state<SVGSVGElement | null>(null);
	export function svg(): SVGSVGElement | null {
		return element;
	}

	const CELL = 24;
	const LABEL = 150;
	const TOP = 120;

	const ordered = $derived(orderTerms(terms, REGISTER_ORDER));
	const cells = $derived(matrixCells(ordered, edges, suppressed));
	const size = $derived(ordered.length * CELL);
	const width = $derived(LABEL + size + 8);
	const height = $derived(TOP + size + 8);
	const index = $derived(new Map(ordered.map((term, i) => [term.name, i])));
	const ramp = $derived(sequential($colours));
	const registerOf = $derived(new Map(ordered.map((term) => [term.name, term.register])));

	/* One pattern per instance, so two matrices on one page do not share an id. */
	const hatchId = `hatch-${Math.random().toString(36).slice(2, 8)}`;

	const explain = (cell: MatrixCell) => {
		const pair = `${termLabel(cell.row)} & ${termLabel(cell.col)}`;
		switch (cell.state) {
			case 'self':
				return `${termLabel(cell.row)}: ${count(cell.speeches ?? 0)} speeches`;
			case 'drawn':
			case 'negative':
				return `${pair}: nPMI ${decimal(cell.npmi ?? 0)}, ${count(cell.speeches ?? 0)} speeches use both`;
			case 'below':
				return `${pair}: fewer than ${count(minimum)} speeches use both`;
			case 'definitional':
				return `${pair}: not drawn (${cell.reason})`;
		}
	};

	const fill = (cell: MatrixCell) => {
		switch (cell.state) {
			case 'drawn':
				return ramp(tone(cell.npmi ?? 0));
			case 'below':
				return `url(#${hatchId})`;
			case 'self':
				return registerColour(registerOf.get(cell.row) ?? '', $colours);
			default:
				return $colours.paper;
		}
	};
</script>

<svg
	bind:this={element}
	viewBox="0 0 {width} {height}"
	width="100%"
	role="img"
	aria-label={description}
	style:font-family="var(--sans)"
	class="matrix"
>
	<defs>
		<pattern
			id={hatchId}
			width="5"
			height="5"
			patternUnits="userSpaceOnUse"
			patternTransform="rotate(45)"
		>
			<line x1="0" y1="0" x2="0" y2="5" stroke={$colours.rule} stroke-width="0.8" />
		</pattern>
	</defs>
	{#each ordered as term, i (term.name)}
		<a href={href(term.name)}>
			<text
				x={LABEL - 8}
				y={TOP + i * CELL + CELL / 2 + 4}
				text-anchor="end"
				font-size="11"
				fill={registerColour(term.register, $colours)}>{termLabel(term.name)}</text
			>
		</a>
		<a href={href(term.name)}>
			<text
				transform="rotate(-60 {LABEL + i * CELL + CELL / 2} {TOP - 8})"
				x={LABEL + i * CELL + CELL / 2}
				y={TOP - 8}
				font-size="11"
				fill={registerColour(term.register, $colours)}>{termLabel(term.name)}</text
			>
		</a>
	{/each}
	{#each cells as cell (cell.row + ' ' + cell.col)}
		{@const cx = LABEL + (index.get(cell.col) ?? 0) * CELL}
		{@const cy = TOP + (index.get(cell.row) ?? 0) * CELL}
		<g>
			<title>{explain(cell)}</title>
			<rect
				x={cx + 0.5}
				y={cy + 0.5}
				width={CELL - 1}
				height={CELL - 1}
				fill={fill(cell)}
				fill-opacity={cell.state === 'self' ? 0.35 : 1}
				stroke={$colours.ruleSoft}
				stroke-width="0.5"
			/>
			{#if cell.state === 'definitional' || cell.state === 'negative'}
				<text
					x={cx + CELL / 2}
					y={cy + CELL / 2 + 4}
					text-anchor="middle"
					font-size="12"
					fill={$colours.inkFaint}>{cell.state === 'definitional' ? 'x' : '-'}</text
				>
			{/if}
		</g>
	{/each}
</svg>

<style>
	.matrix {
		display: block;
		max-width: 100%;
		height: auto;
	}

	.matrix a:hover text,
	.matrix a:focus-visible text {
		text-decoration: underline;
	}
</style>
