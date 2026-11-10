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
	/* The column heads lean right at 60°, so the last one runs past the grid's
	   edge by half its length: 8 units of margin cut "mass killing" to "mass
	   killi". 72 holds a 13-character head at 11px. */
	const RIGHT = 72;
	/* The key under the grid: a row of ramp swatches and a row of refusals. */
	const KEY = 64;
	const STOPS = 10;
	const SWATCH = 16;

	const ordered = $derived(orderTerms(terms, REGISTER_ORDER));
	const cells = $derived(matrixCells(ordered, edges, suppressed));
	const size = $derived(ordered.length * CELL);
	const width = $derived(LABEL + size + RIGHT);
	const height = $derived(TOP + size + 8 + KEY);
	const keyTop = $derived(TOP + size + 20);
	const refusals = $derived(keyTop + 36);
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

<!-- A square grid cannot reflow, so it is never drawn smaller than its own
     cells: below that width the plate scrolls sideways instead of shrinking
     the matrix to 0.4 of itself, which set its terms at under 5px on a phone
     and left 56 links 8px tall. Every term inside is a link, so the keyboard
     scrolls it by moving through them. -->
<div class="frame">
	<svg
		bind:this={element}
		viewBox="0 0 {width} {height}"
		width="100%"
		style:min-width="{width}px"
		role="group"
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

		<!-- The key, inside the picture so a downloaded file still says what its
		     shades mean, drawn the way the calendar's is: swatches at even steps of
		     the *value*, so it stays a correct lookup table under the square-root
		     placement. It reads the same in both themes because it is the ramp. -->
		{#each Array.from({ length: STOPS }, (_, i) => i) as stop (stop)}
			<rect
				x={LABEL + stop * SWATCH}
				y={keyTop}
				width={SWATCH}
				height="10"
				fill={ramp(tone((stop + 0.5) / STOPS))}
				stroke={$colours.ruleSoft}
				stroke-width="0.5"
			/>
		{/each}
		<text x={LABEL} y={keyTop + 23} font-size="11" fill={$colours.inkFaint}>0</text>
		<text
			x={LABEL + STOPS * SWATCH}
			y={keyTop + 23}
			text-anchor="end"
			font-size="11"
			fill={$colours.inkFaint}>1</text
		>
		<text x={LABEL + STOPS * SWATCH + 14} y={keyTop + 9} font-size="12" fill={$colours.inkFaint}
			>association (nPMI)</text
		>
		<rect
			x={LABEL}
			y={refusals}
			width={SWATCH}
			height="10"
			fill="url(#{hatchId})"
			stroke={$colours.ruleSoft}
			stroke-width="0.5"
		/>
		<text x={LABEL + SWATCH + 6} y={refusals + 9} font-size="12" fill={$colours.inkFaint}
			>fewer than {count(minimum)} speeches use both</text
		>
		<text
			x={LABEL + 250 + SWATCH / 2}
			y={refusals + 10}
			text-anchor="middle"
			font-size="12"
			fill={$colours.inkFaint}>x</text
		>
		<text x={LABEL + 250 + SWATCH + 6} y={refusals + 9} font-size="12" fill={$colours.inkFaint}
			>patterns overlap, not drawn</text
		>
		<text
			x={LABEL + 450 + SWATCH / 2}
			y={refusals + 10}
			text-anchor="middle"
			font-size="12"
			fill={$colours.inkFaint}>-</text
		>
		<text x={LABEL + 450 + SWATCH + 6} y={refusals + 9} font-size="12" fill={$colours.inkFaint}
			>below chance</text
		>
	</svg>
</div>

<style>
	.frame {
		overflow-x: auto;
	}

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
