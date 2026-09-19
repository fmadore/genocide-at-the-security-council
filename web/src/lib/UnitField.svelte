<script lang="ts">
	/**
	 * A quantity counted in units, the way a programme's statistical page did:
	 * one square per `unit`, laid in rows, the `part` of them drawn in ink and
	 * the rest outlined. A share is then something a reader can count rather
	 * than a percentage they have to trust.
	 *
	 * Squares, not pictograms. On this subject a row of little figures would be
	 * grotesque; the abstraction is the point.
	 *
	 * A CSS grid rather than an SVG: the squares keep their size and the row
	 * length follows the width, so the field is forty to a row on a desk and
	 * twenty on a phone, and stays countable at both. The whole field is one
	 * image with one accessible name, because a square per tab stop would be
	 * a hundred and seventy tab stops.
	 */
	interface Props {
		/** The whole. */
		total: number;
		/** The counted part of the whole, drawn in ink. */
		part: number;
		/** What one square stands for. */
		unit: number;
		/** Announced in place of the drawing. */
		description: string;
	}

	let { total, part, unit, description }: Props = $props();

	const squares = $derived(Math.max(1, Math.round(total / unit)));
	const filled = $derived(Math.min(squares, Math.round(part / unit)));
	const cells = $derived(Array.from({ length: squares }, (_, i) => i < filled));
</script>

<div class="field" role="img" aria-label={description}>
	{#each cells as ink, i (i)}
		<i class:ink></i>
	{/each}
</div>

<style>
	.field {
		--per-row: 40;
		display: grid;
		grid-template-columns: repeat(var(--per-row), minmax(0, 1fr));
		gap: var(--sp-1);
		color: var(--ink);
	}

	.field i {
		display: block;
		aspect-ratio: 1;
		border: var(--hair) solid currentColor;
		background: var(--paper);
	}

	.field i.ink {
		background: currentColor;
	}

	@media (max-width: 40rem) {
		.field {
			--per-row: 20;
		}
	}

	/* Forty-eight to a row on a wide desk: the field stays countable and
	   Plate 1 stays inside the first screen. */
	@media (min-width: 64rem) {
		.field {
			--per-row: 48;
		}
	}

	/* The counted part is a background, and a background is the first thing a
	   forced-colour mode replaces: the field would read as one empty grid. The
	   reader's own text colour fills the squares instead, so the share stays
	   countable in whatever two colours they chose. */
	@media (forced-colors: active) {
		.field i {
			border-color: CanvasText;
		}

		.field i.ink {
			background: CanvasText;
		}
	}

	@media print {
		.field i.ink {
			background: #000;
			-webkit-print-color-adjust: exact;
			print-color-adjust: exact;
		}
	}
</style>
