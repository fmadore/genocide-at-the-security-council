<script lang="ts">
	/**
	 * What one delegation says that the room did not.
	 *
	 * A renderer over `keyness.ts`, which holds every decision: which speakers
	 * are drawable, which are refused and why, how long a bar is, and what the
	 * download contains. Nothing here computes a number.
	 *
	 * The bar *is* the table. `docs/PLAN.md` §7 requires every visual to link to
	 * the table behind it and for the two to be generated from one artefact; the
	 * strongest form of that is for them to be the same element, so the bar is
	 * drawn in the row's own background and the figures sit in its cells. There
	 * is no second rendering to drift.
	 *
	 * Colour carries the direction of the effect and nothing else — over- and
	 * under-representation — from the register palette rather than the accent,
	 * because `--blue` is reserved for interaction and may never stand for a
	 * datum. Length carries the log ratio, which is the column a reader should
	 * be looking at: on tens of thousands of tokens almost everything is
	 * significant, and G² would draw a picture of how much a delegation spoke.
	 */
	import { resolve } from '$app/paths';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Figure from './Figure.svelte';
	import Icon from './Icon.svelte';
	import { provenanceOf } from './export';
	import type { ExportRequest } from './export';
	import { count, decimal, percent, shortCountry, signed } from './format';
	import {
		EXPORT_COLUMNS,
		exportRows,
		neverPaired,
		pick,
		published,
		removed,
		selfReferenceShare,
		withheld
	} from './keyness';
	import type { Reading } from './keyness';
	import type { SpeakerKeyness } from './types';

	let { data }: { data: SpeakerKeyness } = $props();

	const drawable = $derived(published(data));
	const refused = $derived(withheld(data));
	const unpaired = $derived(neverPaired(data));

	/* The largest speaker by matched pairs, so the figure opens on something
	   rather than on a prompt. */
	let chosen = $state<string | null>(null);
	const name = $derived(chosen ?? drawable[0]?.country_org ?? null);

	/* Named `control` rather than `reading`: `Figure` takes a snippet called
	   `reading` and the two cannot share a name in one component. */
	let control = $state<Reading>('matched');
	let rows = $state(20);

	const plan = $derived(pick(data, name, control, rows));
	const speaker = $derived(plan.speaker);
	const fell = $derived(speaker ? removed(speaker) : null);
	const marked = $derived(selfReferenceShare(plan.rows));

	/**
	 * The download: both readings in full, not the twenty rows on screen.
	 *
	 * §7.5's first constraint — a file containing only what happened to be
	 * visible is a screenshot with commas in it. The `reading` column is what
	 * keeps the two tables from being read as one.
	 */
	function table(): ExportRequest {
		return {
			title: `Matched keyness — ${shortCountry(speaker?.country_org ?? '')}`,
			columns: EXPORT_COLUMNS,
			rows: speaker ? exportRows(speaker) : [],
			provenance: provenanceOf(data.meta, 'countries/speaker_keyness.json'),
			filters: [
				`speaker: ${speaker?.country_org ?? '—'}`,
				`matched on: ${data.matched_on.join(', ')}`,
				`pairs: ${speaker?.pairs ?? 0} of ${speaker?.held ?? 0} speeches ` +
					`(${percent(speaker?.coverage ?? 0)} coverage)`,
				`seed: ${data.seed}`
			],
			scope:
				`both readings at full length — ${data.limit} rows each as the artefact holds ` +
				`them, not the ${rows} drawn — with the stability interval where one exists`
		};
	}
</script>

<Figure
	title="What a delegation says that the room does not"
	question="With the debate held constant, which words set one speaker's language apart from everybody else's?"
	source="12_speaker_keyness.py → countries/speaker_keyness.json"
	note="Bar length shows the size of the difference, not the confidence in it. Colour shows which way the difference runs."
	download={{ name: ['unsc', 'keyness', speaker?.country_org ?? 'none', control], table }}
>
	{#snippet controls()}
		<label>
			Speaker
			<!-- Bound to the effective speaker rather than to `chosen`, which is
			     null until someone picks: a control showing blank beside a figure
			     drawing Russia is a control that is lying about its own state. -->
			<select value={name} onchange={(event) => (chosen = event.currentTarget.value)}>
				{#each drawable as row (row.country_org)}
					<option value={row.country_org}
						>{shortCountry(row.country_org)} ({count(row.pairs)})</option
					>
				{/each}
				{#if refused.length}
					<optgroup label="No table available">
						{#each refused as row (row.country_org)}
							<option value={row.country_org}>{shortCountry(row.country_org)}</option>
						{/each}
					</optgroup>
				{/if}
			</select>
		</label>
		<label>
			Compared against
			<select bind:value={control}>
				<option value="matched">Speeches from the same debates</option>
				<option value="unmatched">The whole corpus</option>
			</select>
		</label>
		<label>
			Rows
			<select bind:value={rows}>
				{#each [10, 20, 40] as size (size)}<option value={size}>{size}</option>{/each}
			</select>
		</label>
	{/snippet}

	{#snippet reading()}
		<p>
			One row per word, ordered by how confident the comparison is (G²). <strong
				>Bar length carries the log ratio</strong
			>: how many times more often this speaker used the word than the speeches it is compared
			against, doubling with every whole number. A word can reach the top of the table on a small
			difference, which is why length carries the size of the effect rather than the confidence.
		</p>
		<p>
			An asterisk marks a word taken from the speaker's own name. Those rows are marked rather than
			deleted: how often a delegation names itself says something about how it speaks, and removing
			rows would change the ranking of everything below them.
		</p>
		{#if control === 'matched'}
			<p>
				The bracket after a row is the range its log ratio covered across {data.repetitions} draws of
				the comparison set, this one among them. A wide bracket says more about the luck of the draw than
				about the speaker.
			</p>
		{/if}
	{/snippet}

	{#snippet caveat()}
		<p>{data.reading_rule}</p>
		<p>
			{#if control === 'unmatched'}
				<strong>This is the whole-corpus comparison.</strong> {data.unmatched_rule}
			{:else}
				{data.control_rule}
			{/if}
		</p>
		<p>{data.self_reference_rule}</p>
	{/snippet}

	{#if plan.missing}
		<p class="refusal">That speaker is not in this data.</p>
	{:else if plan.refusal}
		<div class="refusal">
			<p>
				<strong>{shortCountry(speaker?.country_org ?? '')} has no table here</strong>, and the
				reason is not that it said nothing distinctive.
			</p>
			{#if plan.refusal.because.includes('coverage')}
				<p>
					A comparable speech could be found for only {count(plan.refusal.pairs)} of its {count(
						plan.refusal.held
					)}
					&mdash; {percent(plan.refusal.coverage)}, against a declared minimum of
					{percent(data.minimum_coverage)}. A table built on that would describe a small and
					lopsided part of what this speaker said: the debates where somebody comparable happened to
					speak too.
				</p>
			{/if}
			{#if plan.refusal.because.includes('pairs')}
				<p>
					Only {count(plan.refusal.pairs)} of its {count(plan.refusal.held)} speeches found a partner,
					below the {count(data.minimum_pairs)} pairs this figure requires.
				</p>
			{/if}
		</div>
	{:else if speaker}
		<!-- The target is the same in both readings; what it is compared against is
		     not, so the line says which. Printing the control's word count under the
		     unmatched reading would name a denominator that reading never used. -->
		<p class="denominator">
			<strong>{count(speaker.pairs)} paired speeches</strong> out of {count(speaker.held)} ({percent(
				speaker.coverage
			)} of its record) &middot;
			{count(speaker.target_tokens ?? 0)} words against
			{#if control === 'matched'}
				{count(speaker.control_tokens ?? 0)} in the comparison set
				{#if fell !== null}
					&middot; pairing reduced the largest differences by {decimal(fell)} on the log-ratio scale
				{/if}
			{:else}
				the rest of the corpus
			{/if}
		</p>

		<table class="bars">
			<caption class="sr-only">
				Keywords for {speaker.country_org}, {control === 'matched'
					? 'against a matched control'
					: 'against the whole corpus'}
			</caption>
			<thead>
				<tr>
					<th scope="col">Word</th>
					<th scope="col" class="num">Log ratio</th>
					<th scope="col" class="num">This speaker</th>
					<th scope="col" class="num">Compared with</th>
					<th scope="col" class="num">G²</th>
					<th scope="col" class="num">Speeches / meetings</th>
					<th scope="col" class="num">DP</th>
				</tr>
			</thead>
			<tbody>
				{#each plan.rows as row (row.word)}
					<tr>
						<th scope="row">
							<span
								class="bar"
								class:under={row.logRatio < 0}
								style="--weight: {row.weight}"
								aria-hidden="true"
							></span>
							<span class="word"
								>{row.word}{#if row.selfReference}<abbr title="A word from this speaker's own name."
										>*</abbr
									>{/if}</span
							>
						</th>
						<td class="num">
							{signed(row.logRatio)}
							{#if row.interval}
								<span class="interval"
									>[{signed(row.interval.low)}, {signed(row.interval.high)}]</span
								>
							{/if}
						</td>
						<td class="num">{count(row.target)}</td>
						<td class="num">{count(row.reference)}</td>
						<td class="num">{count(Math.round(row.g2))}</td>
						<td class="num"
							>{count(row.documents)} / {row.meetings == null ? '—' : count(row.meetings)}</td
						>
						<td class="num">{decimal(row.dp)}</td>
					</tr>
				{/each}
			</tbody>
		</table>

		{#if marked.marked}
			<p class="note-self">
				{marked.marked} of the {marked.of} rows drawn are the speaker naming itself.
			</p>
		{/if}

		<section class="agenda">
			<h4>What it was heard on</h4>
			<p>
				The pairing holds the agenda item constant, so this is what was held constant.
				{shortCountry(speaker.country_org)} spoke on {count(speaker.agenda.items)} items, and
				{percent(speaker.agenda.concentration)} of its speeches fell on its three commonest.
			</p>
			<ul>
				{#each speaker.agenda.top.slice(0, 5) as item (item.item)}
					<li>
						<span>{item.item}</span>
						<span class="share">{percent(item.share)}</span>
					</li>
				{/each}
				{#if speaker.agenda.other.speeches}
					<li class="rest">
						<span>{count(speaker.agenda.items - speaker.agenda.top.length)} further items</span>
						<span class="share">{percent(speaker.agenda.other.share)}</span>
					</li>
				{/if}
			</ul>
		</section>
	{/if}
</Figure>

<section class="apparatus">
	<h3>Who is not here</h3>
	<ul>
		<li>
			<strong>{count(unpaired)} speakers were never paired at all.</strong> They delivered fewer
			than
			{count(data.minimum_pairs)} speeches, so no comparison could be built. They appear here as a number
			rather than a list, because there is nothing to show.
		</li>
		{#if refused.length}
			<li>
				<strong>{count(refused.length)} were paired and then held back.</strong> Unlike the group
				above, each of these has a figure a reader can weigh, so they stay in the picker and give
				their reason when selected:
				{#each refused as row, index (row.country_org)}{shortCountry(row.country_org)} ({percent(
						row.coverage
					)}){#if index < refused.length - 1},
					{/if}{/each}.
			</li>
		{/if}
		<li>
			<strong>A distinctive word is not a position.</strong>
			{data.reading_rule} A delegation that names a conflict often may be prosecuting it, deploring it,
			or chairing the debate about it.
			<a class="more" href={resolve('/concordance')}>
				Read the record instead <Icon icon={ChevronRight} />
			</a>
		</li>
	</ul>
</section>

<style>
	.denominator {
		margin: 0 0 var(--sp-4);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.refusal {
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.55;
		color: var(--ink-2);
		border-left: 2px solid var(--state-warn);
		padding-left: var(--sp-3);
	}

	.refusal :global(p) {
		margin: 0 0 0.6em;
	}

	table.bars {
		width: 100%;
		border-collapse: collapse;
	}

	.bars th[scope='row'] {
		position: relative;
		font-weight: 400;
		text-align: left;
		padding-left: var(--sp-2);
		min-width: 12rem;
	}

	/* The bar is the row's own background rather than a second drawing of the
	   same number. Colour is the register palette, never the accent: `--blue`
	   belongs to interaction and may not stand for a datum. */
	.bar {
		position: absolute;
		inset: 2px auto 2px 0;
		width: calc(var(--weight) * 100%);
		background: var(--reg-legal);
		opacity: 0.22;
	}

	.bar.under {
		background: var(--reg-contentious);
	}

	.word {
		position: relative;
	}

	.bars abbr {
		text-decoration: none;
		color: var(--ink-3);
		cursor: help;
	}

	.interval {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
		white-space: nowrap;
		margin-left: 0.4em;
	}

	.note-self {
		margin: var(--sp-3) 0 0;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.agenda {
		margin-top: var(--sp-5);
		padding-top: var(--sp-4);
		border-top: var(--hair) solid var(--rule);
		max-width: var(--measure);
	}

	.agenda h4 {
		margin: 0 0 var(--sp-2);
		font-size: var(--step-0);
	}

	.agenda p {
		margin: 0 0 var(--sp-3);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
		line-height: 1.5;
	}

	.agenda ul {
		list-style: none;
		margin: 0;
		padding: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.agenda li {
		display: flex;
		justify-content: space-between;
		gap: var(--sp-4);
		padding: 0.2rem 0;
		border-bottom: var(--hair) solid var(--rule);
	}

	.agenda .rest {
		color: var(--ink-3);
	}

	.share {
		font-variant-numeric: tabular-nums lining-nums;
		color: var(--ink-3);
	}

	.apparatus {
		margin: var(--sp-7) 0 var(--sp-8);
		padding-top: var(--sp-4);
		border-top: var(--hair) solid var(--rule-strong);
		max-width: var(--measure);
	}

	.apparatus h3 {
		font-size: var(--step-1);
		margin: 0 0 var(--sp-3);
	}

	.apparatus ul {
		margin: 0;
		padding-left: var(--sp-4);
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.55;
		color: var(--ink-2);
	}

	.apparatus li {
		margin-bottom: var(--sp-3);
	}

	.more {
		display: inline-flex;
		align-items: center;
		gap: 0.25em;
		white-space: nowrap;
	}
</style>
