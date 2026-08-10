<script lang="ts">
	/**
	 * The one place an icon's size and weight are decided.
	 *
	 * Icons come from Lucide rather than from paths drawn here: a hand-cut glyph
	 * is a drawing that only one person can maintain, and a typographic stand-in
	 * (`›`, `↗`) is whatever the reader's fallback font happens to contain.
	 *
	 * They are set at `1em` in `currentColor`, so an icon takes the size and the
	 * colour of the text it sits in and needs no token of its own. Stroke weight
	 * matches the hairline rules the rest of the system separates things with.
	 *
	 * Every icon here is decorative — it repeats a word that is already in the
	 * markup — so it is hidden from assistive technology. An icon that is the
	 * only label for a control does not belong in this component.
	 */
	import type { LucideIcon } from '@lucide/svelte';

	interface Props {
		/** A Lucide icon component, e.g. `ChevronRight`. */
		icon: LucideIcon;
	}

	let { icon: Glyph }: Props = $props();
</script>

<span class="icon">
	<Glyph size="1em" color="currentColor" strokeWidth={1.75} aria-hidden={true} focusable="false" />
</span>

<style>
	.icon {
		display: inline-flex;
		/* Optical, not metric: a stroked square hung on the alphabetic baseline
		   sits high against lowercase text. */
		vertical-align: -0.125em;
		flex: none;
	}
</style>
