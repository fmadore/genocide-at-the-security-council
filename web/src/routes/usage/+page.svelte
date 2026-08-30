<script lang="ts">
	/**
	 * The experimental layer: which genocide a delegation meant, and what it was
	 * doing with the word.
	 *
	 * Every reading on this page is a model's, and the page is arranged around
	 * saying so before it says anything else — the apparatus block is the first
	 * thing under the standfirst, not a footnote at the bottom. Nothing here
	 * decides anything: `$lib/usage` settles what is drawn, what is withheld and
	 * what a key press does, and `$lib/data` refuses a payload that would let this
	 * page publish something the model did not say.
	 */
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import PageMeta from '$lib/PageMeta.svelte';
	import UsageMatrix from '$lib/UsageMatrix.svelte';
	import { kwic, usageOccurrences } from '$lib/data';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, decimal, isoDate, percent, shortCountry, termLabel } from '$lib/format';
	import { segments } from '$lib/highlight';
	import { PAGE_METADATA } from '$lib/seo';
	import {
		MATRIX_COLUMNS,
		STANCES,
		STANCE_COLUMNS,
		USAGE_TERM,
		drillDown,
		goldProgress,
		matrixExportRows,
		matrixPlan,
		readUsageState,
		selectUsage,
		stanceExportRows,
		stanceLabel,
		stanceRanking,
		usageParams
	} from '$lib/usage';
	import type { MatrixCell, StanceSegment, UsageSort, UsageState, UsageUnit } from '$lib/usage';
	import type {
		KwicLine,
		StanceCounts,
		UsageActor,
		UsageOccurrences,
		UsageReferent
	} from '$lib/types';
	import { onMount, tick } from 'svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const artefact = $derived(data.usage);

	let actor = $state('');
	let referent = $state('');
	let unit = $state<UsageUnit>('count');
	let sort = $state<UsageSort>('assigned');
	let urlReady = $state(false);
	/** How many quotations of the drill-down are on screen. Presentation only. */
	let shown = $state(20);

	const current = (): UsageState => ({ actor, referent, unit, sort });

	onMount(() => {
		const state = readUsageState(page.url.searchParams, artefact);
		actor = state.actor;
		referent = state.referent;
		unit = state.unit;
		sort = state.sort;
		// The first replaceState must wait until SvelteKit has assigned its root,
		// exactly as the actor and concordance views do.
		void tick().then(() => {
			urlReady = true;
		});
	});

	/** Keep the URL in step, so any reading of this matrix is citable. */
	$effect(() => {
		if (!urlReady) return;
		const search = usageParams(current()).toString();
		replaceState(`${page.url.pathname}${search ? `?${search}` : ''}`, page.state);
	});

	const plan = $derived(matrixPlan(artefact, current()));
	const ranking = $derived(stanceRanking(artefact));
	const gold = $derived(goldProgress(artefact));
	const selected = $derived(Boolean(actor || referent));
	const referentLabel = (id: string) =>
		artefact.referents.find((entry) => entry.id === id)?.label ?? termLabel(id);

	/* ---- the evidence, fetched at the first drill-down and not before -------
	   Two artefacts, requested together rather than in sequence: they are
	   independent files and neither alone yields a quotation. `fetched` is a
	   plain variable rather than state because it guards the effect that fills
	   the state — a guard that was itself a dependency would run the effect a
	   second time to discover that it had already run. */
	let annotations = $state<UsageOccurrences | null>(null);
	let lines = $state<KwicLine[]>([]);
	let loading = $state(false);
	let failure = $state<string | null>(null);
	let retry = $state(0);
	let fetched = false;

	$effect(() => {
		void retry;
		if (!selected || fetched) return;
		fetched = true;
		loading = true;
		failure = null;
		Promise.all([usageOccurrences(), kwic(USAGE_TERM)])
			.then(([coded, file]) => {
				annotations = coded;
				lines = file.lines;
			})
			.catch((error: Error) => {
				failure = error.message;
			})
			.finally(() => {
				loading = false;
			});
	});

	function again() {
		fetched = false;
		retry += 1;
	}

	const evidence = $derived(drillDown(annotations?.occurrences ?? [], lines, actor, referent));

	$effect(() => {
		void [actor, referent];
		shown = 20;
	});

	function pick(nextActor: string, nextReferent: string) {
		const next = selectUsage(current(), nextActor, nextReferent);
		actor = next.actor;
		referent = next.referent;
	}

	/* ---- how the two units are written -------------------------------------
	   A cell is read at a glance and is 2.6rem wide, so a share is rounded to
	   the nearest point there and stated exactly in the cell's own title. */
	const cellFigure = (value: number) =>
		unit === 'share' ? `${Math.round(value * 100)}%` : count(value);

	const SORT_LABELS: Record<UsageSort, string> = {
		assigned: 'occurrences placed on a referent',
		occurrences: 'occurrences of the word',
		name: 'name'
	};

	/** Every stance a set of counts actually holds, as a sentence. */
	const describeStances = (stances: StanceCounts, total: number) =>
		STANCES.filter((stance) => (stances[stance] ?? 0) > 0)
			.map(
				(stance) =>
					`${stanceLabel(stance).toLowerCase()} ${count(stances[stance])}` +
					(total > 0 ? ` (${percent(stances[stance] / total)})` : '')
			)
			.join(', ');

	function cellLabel(cell: MatrixCell, speaker: UsageActor, subject: UsageReferent): string {
		const who = shortCountry(speaker.country_org);
		if (cell.count === 0) {
			return `${who} × ${subject.label}: no occurrence placed here.`;
		}
		const share =
			cell.share === null
				? `share withheld — fewer than ${count(artefact.minimum_occurrences)} eligible occurrences`
				: `${percent(cell.share)} of its ${count(speaker.assigned)} placed occurrences`;
		const many = cell.count === 1 ? 'occurrence' : 'occurrences';
		return (
			`${who} × ${subject.label}: ${count(cell.count)} ${many}, ${share}. ` +
			`${describeStances(cell.stances, cell.count)}.`
		);
	}

	/* One hue per stance, tinted toward the page so the numbers can be read on
	   top of them. `--blue` appears nowhere: it belongs to what a reader can act
	   on, never to a datum. Rejection is the strongest weight because it is the
	   question the figure is ordered by. */
	const slug = (stance: string) => stance.replace(/_/g, '-');
	const bands = (parts: StanceSegment[]) =>
		parts
			.map(
				(band) =>
					`var(--stance-${slug(band.stance)}) ${band.from.toFixed(3)}% ${band.to.toFixed(3)}%`
			)
			.join(', ');

	const sha = $derived(artefact.model.prompt_sha256);
	const shortSha = $derived(`${sha.slice(0, 12)}…`);

	const GOLD_STATE: Record<string, string> = {
		not_started: 'not started',
		in_progress: 'in progress',
		complete: 'complete'
	};

	/* ---- the two downloads ------------------------------------------------- */

	const onScreen = () => [
		`unit: ${unit === 'share' ? "share of the delegation's placed occurrences" : 'occurrences'}`,
		`rows: ${plan.rows.length} of ${plan.disclosure.speakers} speakers with anything placed, ordered by ${SORT_LABELS[sort]}`,
		`minimum for a share: ${artefact.minimum_occurrences} eligible occurrences`,
		`labels: ${artefact.model.id}, run ${artefact.model.run_id}, prompt v${artefact.model.prompt_version} sha256:${sha}`
	];

	function matrixTable(): ExportRequest {
		return {
			title: 'Which genocide each delegation means',
			columns: MATRIX_COLUMNS,
			rows: matrixExportRows(artefact),
			provenance: provenanceOf(artefact.meta, 'usage/usage.json'),
			filters: onScreen(),
			scope:
				`every filled cell the artefact holds — ${count(artefact.matrix.length)} pairings over ` +
				`${count(artefact.actors.length)} speakers and ${count(artefact.referents.length)} referents, ` +
				`including the ${count(plan.disclosure.hiddenRows)} rows the figure's cap left out and the ` +
				`speakers whose shares are withheld, whose share column is null beside a sufficient flag`
		};
	}

	function stanceTable(): ExportRequest {
		return {
			title: 'Who rejects the word',
			columns: STANCE_COLUMNS,
			rows: stanceExportRows(artefact),
			provenance: provenanceOf(artefact.meta, 'usage/usage.json'),
			filters: [
				`ranked by: share of eligible occurrences that reject or deny`,
				`minimum for a share: ${artefact.minimum_occurrences} eligible occurrences`,
				`labels: ${artefact.model.id}, run ${artefact.model.run_id}`
			],
			scope:
				`every speaker the run produced a stance profile for, including the ` +
				`${count(ranking.withheld.length)} whose share is withheld and written null`
		};
	}
</script>

<PageMeta meta={PAGE_METADATA['/usage/']} />

<article>
	<header class="lede">
		<h1>What the word was doing</h1>
		<p class="standfirst">
			The corpus can say how often a delegation said <em>genocide</em>. It cannot say which genocide
			was meant, or whether the speaker was making the claim or refusing it. This page holds a
			model's answer to both questions, kept apart from everything else on this site and marked as
			what it is.
		</p>
	</header>

	<!-- The apparatus first, before any figure. A reader who stops after the
	     opening paragraph should already know whose reading this is. -->
	<section class="experiment" aria-labelledby="experiment-heading">
		<span class="label" id="experiment-heading">Experimental — model-derived</span>
		<p class="governing">
			Every label below was produced by a language model reading one occurrence at a time. It is an
			experiment, not a measurement. <strong>The human labels are the authority</strong>: where a
			coder and the model disagree, the coder is right and the disagreement is reported as a
			disagreement. Nothing here alters the corpus text, the counts on the rest of this site, or the
			human annotations.
		</p>
		<dl>
			<div>
				<dt>Model</dt>
				<dd><code>{artefact.model.id}</code></dd>
			</div>
			<div>
				<dt>Run</dt>
				<dd><code>{artefact.model.run_id}</code> &middot; {artefact.model.run_date}</dd>
			</div>
			<div>
				<dt>Prompt</dt>
				<dd>
					v{artefact.model.prompt_version} &middot;
					<code title={sha}>sha256:{shortSha}</code>
				</dd>
			</div>
			<div>
				<dt>Reasoning</dt>
				<dd>{artefact.model.reasoning_effort}</dd>
			</div>
			<div>
				<dt>Coverage</dt>
				<dd>
					{count(artefact.model.occurrences_annotated)} of {count(artefact.model.occurrences_total)} occurrences,
					over {count(artefact.model.requests)} requests
				</dd>
			</div>
			<div>
				<dt>Abstained</dt>
				<dd>
					{count(artefact.model.abstention.verdict_uncertain)} verdict &middot;
					{count(artefact.model.abstention.referent_unclear)} referent &middot;
					{count(artefact.model.abstention.stance_unclear)} stance
				</dd>
			</div>
			<div>
				<dt>Refused</dt>
				<dd>
					{count(artefact.model.parse_failures)} unparseable &middot;
					{count(artefact.model.evidence_invalid)} evidence spans not found in the speech
				</dd>
			</div>
			<div>
				<dt>Gold sample</dt>
				<dd>
					{GOLD_STATE[gold.state] ?? gold.state} &mdash; {count(gold.coded)} of {count(
						gold.sampleSize
					)} coded
				</dd>
			</div>
		</dl>
	</section>

	<Figure
		title="Which genocide each delegation means"
		question="Which genocide is each delegation talking about when it says the word?"
		source="15_usage.py → usage/usage.json"
		note="A cell is a count of occurrences, not of speeches: one speech saying the word four times fills four of them."
		download={{ name: ['unsc', 'usage', 'matrix', unit], table: matrixTable }}
	>
		{#snippet controls()}
			<div class="control">
				<span class="label" id="usage-unit">Unit</span>
				<div class="segmented" role="group" aria-labelledby="usage-unit">
					<button
						type="button"
						title="Occurrences placed on this referent. Published for every delegation, because a count is a fact about the record."
						aria-pressed={unit === 'count'}
						onclick={() => (unit = 'count')}>Occurrences</button
					>
					<button
						type="button"
						title="The same cell as a share of that delegation's own placed occurrences. Withheld below the minimum."
						aria-pressed={unit === 'share'}
						onclick={() => (unit = 'share')}>Share of its own</button
					>
				</div>
			</div>
			<label>
				Ordered by
				<select bind:value={sort}>
					<option value="assigned">Occurrences placed</option>
					<option value="occurrences">Occurrences of the word</option>
					<option value="name">Name</option>
				</select>
			</label>
			{#if selected}
				<button type="button" class="ghost" onclick={() => pick(actor, referent)}>
					Clear the selection
				</button>
			{/if}
		{/snippet}

		{#snippet reading()}
			<p>
				One row per delegation, one column per referent on the model's controlled list. A shaded
				cell is that delegation placing the word on that genocide; the deeper the amber, the more of
				them. <strong>Click a cell</strong> to read the occurrences behind it, a row heading for a delegation
				on its own, or a column heading for one referent across every delegation.
			</p>
			<p>
				The last columns, ruled off and set in italic, are not genocides. They are the ways of
				talking about the category &mdash; the Convention, the legal definition, an office's title,
				a warning about no case in particular &mdash; together with
				<em>other known referent</em>, which is a real referent the controlled list has not given a
				name to yet. Ranked among Rwanda and Srebrenica by count, each would read as one more case.
			</p>
			<p>
				A share is withheld below {count(artefact.minimum_occurrences)} eligible occurrences and the cell
				is hatched instead. A count is published at every denominator, because two occurrences out of
				two is a fact about the record and &ldquo;100% of this delegation's uses&rdquo; is not.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>These columns are a model's reading, not a coding.</strong>
				<code>{artefact.model.id}</code> assigned every referent here, and no human has yet checked any
				of them. A wrong referent looks exactly like a right one in a table of counts.
			</p>
			<p>
				The rows do not add up to the corpus, and the disclosure under the figure says by how much:
				{count(plan.disclosure.ineligible)} occurrences never became eligible &mdash; the model judged
				them not a real use of the word, or could not find its own evidence span in the speech &mdash;
				and {count(plan.disclosure.unassigned)} more were eligible and could not be placed on any referent
				at all.
			</p>
			<p>
				A referent is not an endorsement. The list carries the situations argued before the Council,
				including ones whose characterisation as genocide is contested and one — the embargo against
				Cuba — that is a claim about a sanctions regime. Placing an occurrence on a referent says
				what a speaker was talking about, never whether they were right.
			</p>
		{/snippet}

		{#if plan.refusal}
			<p class="refusal">
				The run placed no occurrence on any referent, so there is nothing here that could be drawn.
			</p>
		{:else}
			<UsageMatrix
				{plan}
				label={cellLabel}
				format={cellFigure}
				name={(speaker) => shortCountry(speaker.country_org)}
				unit={unit === 'share' ? "share of the delegation's own" : 'occurrences'}
				description="Delegations down the side, referents across the top; each cell holds the occurrences that delegation placed on that referent."
				onselect={pick}
			/>

			<p class="disclosure">
				{count(plan.rows.length)} of {count(plan.disclosure.speakers)} delegations with anything placed
				are drawn here.
				{#if plan.disclosure.hiddenRows}
					The {count(plan.disclosure.hiddenRows)} below them hold {count(
						plan.disclosure.hiddenOccurrences
					)} further occurrences and are in the CSV, not in the table.
					{#if plan.disclosure.hiddenSufficient}
						{count(plan.disclosure.hiddenSufficient)} of those
						{plan.disclosure.hiddenSufficient === 1 ? 'is a delegation' : 'are delegations'} the artefact
						does publish a share for: the cut is a fixed number of rows and the minimum is counted on
						a different denominator, so the two have come apart here.
					{/if}
				{/if}
				{#if plan.disclosure.silent}
					{count(plan.disclosure.silent)}
					{plan.disclosure.silent === 1 ? 'further delegation' : 'further delegations'} used the word
					and had nothing placed, so
					{plan.disclosure.silent === 1 ? 'it has' : 'they have'} no row at all.
				{/if}
				{#if plan.disclosure.emptyColumns}
					{count(plan.disclosure.emptyColumns)}
					{plan.disclosure.emptyColumns === 1
						? 'referent on the list is'
						: 'referents on the list are'}
					used by no delegation drawn here; the {plan.disclosure.emptyColumns === 1
						? 'column is'
						: 'columns are'} kept, because a case the vocabulary offered and nobody invoked is a finding
					rather than a gap.
				{/if}
			</p>
		{/if}
	</Figure>

	<!-- The evidence, under the figure that sent the reader to it. -->
	<section class="evidence" aria-labelledby="evidence-heading">
		<h2 id="evidence-heading">
			{#if actor && referent}
				{shortCountry(actor)} on {referentLabel(referent)}
			{:else if actor}
				{shortCountry(actor)}
			{:else if referent}
				{referentLabel(referent)}
			{:else}
				The occurrences behind a cell
			{/if}
		</h2>

		{#if !selected}
			<p class="quiet">
				Pick a cell, a delegation or a referent above and the occurrences behind it are listed here,
				each with the sentence it was read from and a way into the speech it came from.
			</p>
		{:else if loading}
			<p class="quiet">Loading the annotations and the concordance for {USAGE_TERM}…</p>
		{:else if failure}
			<p class="error">{failure}</p>
			<button type="button" class="ghost" onclick={again}>Try again</button>
		{:else if evidence.length === 0}
			<p class="quiet">
				No annotated occurrence in this build carries that pairing. The matrix counts and the
				quotations are two artefacts, and a cell can be counted in one before the other is rebuilt.
			</p>
		{:else}
			<p class="quiet">
				{count(evidence.length)}
				{evidence.length === 1 ? 'occurrence' : 'occurrences'}, oldest first. The stance is the
				model's; the sentence is the record's.
			</p>
			<ol class="quotations">
				{#each evidence.slice(0, shown) as row (row.id)}
					<li>
						<p class="line">
							<span class="symbol">{row.spv}</span>
							<span class="who">{shortCountry(row.country)}</span>
							<span class="when">{isoDate(row.date)}</span>
						</p>
						<blockquote>
							{#each segments(row.sentence, row.keyword) as part, i (i)}{#if part.hit}<mark
										>{part.text}</mark
									>{:else}{part.text}{/if}{/each}
						</blockquote>
						<p class="labels">
							<span class="stance" data-stance={row.stance}>{row.stanceLabel}</span>
							{#each row.functions as name (name)}<span class="fn">{termLabel(name)}</span>{/each}
							<span class="fn">confidence {row.confidence}</span>
							{#if !referent}<span class="fn">{referentLabel(row.referent)}</span>{/if}
						</p>
						{#if row.quoteDiffers}
							<p class="span">
								<span class="label">Model's evidence span</span>
								&ldquo;{row.evidenceQuote}&rdquo;{#if !row.evidenceValid}
									<em> — not found in the speech it names</em>{/if}
							</p>
						{/if}
						<p class="actions">
							<a
								class="button"
								href="{resolve('/reader/[meeting]', { meeting: row.reader.meeting })}?{row.reader
									.query}"
							>
								Read the whole speech<Icon icon={ArrowRight} />
							</a>
							<a href="{resolve('/concordance')}?{row.concordance.query}">See in concordance</a>
							<code class="id">{row.id}</code>
						</p>
					</li>
				{/each}
			</ol>
			{#if shown < evidence.length}
				<button type="button" class="more" onclick={() => (shown += 40)}>
					Show {count(Math.min(40, evidence.length - shown))} more
				</button>
			{/if}
		{/if}
	</section>

	<Figure
		title="Who rejects the word"
		question="When a delegation says genocide, is it making the claim or refusing it?"
		source="15_usage.py → usage/usage.json"
		note="Width is the share of that delegation's own eligible occurrences, not of the corpus."
		download={{ name: ['unsc', 'usage', 'stance'], table: stanceTable }}
	>
		{#snippet reading()}
			<p>
				Each row is one delegation's eligible occurrences divided by what it was doing with the
				word. The rows are ordered by the <strong>rejects or denies</strong> band: the delegations at
				the top are the ones that most often used the word in order to refuse it.
			</p>
			<p>
				This is the figure for the comparison the project's collaborators asked for &mdash; whether
				a delegation invokes only the consensual cases, whether another applies the word to a
				sanctions regime, whether a third spends its uses denying the term. It lets that question be
				asked. It does not answer it here, and the ordering will move when the labels are checked.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>A stance is the hardest of these labels to get right</strong>, and the one a model
				is most likely to invert: &ldquo;we reject the claim that this is genocide&rdquo; and
				&ldquo;this is genocide&rdquo; differ by three words. Until the gold sample is coded there
				is no measured error rate for this column and none can be guessed at.
			</p>
			<p>
				{count(ranking.withheld.length)} delegations have fewer than {count(ranking.minimum)} eligible
				occurrences and carry no share. They are not ranked low; they are not ranked. Their counts are
				in the table below.
			</p>
		{/snippet}

		<div class="key">
			{#each STANCES as stance (stance)}
				<span class="swatch"
					><i style:--band="var(--stance-{slug(stance)})"></i>{stanceLabel(stance)}</span
				>
			{/each}
		</div>

		{#if ranking.rows.length === 0}
			<p class="refusal">
				No delegation reached {count(ranking.minimum)} eligible occurrences, so no share here could be
				drawn honestly.
			</p>
		{:else}
			<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
			<div class="scroll" role="region" aria-label="Stance profile table" tabindex="0">
				<table class="stances">
					<caption class="sr-only">
						Delegations ranked by the share of their eligible occurrences that reject or deny the
						characterisation
					</caption>
					<thead>
						<tr>
							<th scope="col">Delegation</th>
							<th scope="col" class="num">Eligible</th>
							<th scope="col" class="num">Rejects or denies</th>
						</tr>
					</thead>
					<tbody>
						{#each ranking.rows as row (row.actor)}
							<tr class="band" style:--bands="linear-gradient(to right, {bands(row.segments)})">
								<th scope="row" title={describeStances(row.stances, row.total)}>
									{shortCountry(row.actor)}
								</th>
								<td class="num">{count(row.eligible)}</td>
								<td class="num">{percent(row.shareRejects)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

		<details class="data-table">
			<summary
				><Icon icon={ChevronRight} />Every stance count, withheld delegations included</summary
			>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
			<div class="scroll" role="region" aria-label="Every stance count" tabindex="0">
				<table>
					<thead>
						<tr>
							<th scope="col">Delegation</th>
							<th scope="col" class="num">Eligible</th>
							{#each STANCES as stance (stance)}
								<th scope="col" class="num">{stanceLabel(stance)}</th>
							{/each}
							<th scope="col" class="num">Rejects</th>
						</tr>
					</thead>
					<tbody>
						{#each ranking.rows as row (row.actor)}
							<tr>
								<th scope="row">{shortCountry(row.actor)}</th>
								<td class="num">{count(row.eligible)}</td>
								{#each STANCES as stance (stance)}
									<td class="num">{count(row.stances[stance] ?? 0)}</td>
								{/each}
								<td class="num">{percent(row.shareRejects)}</td>
							</tr>
						{/each}
						{#each ranking.withheld as row (row.actor)}
							<tr class="withheld">
								<th scope="row">{shortCountry(row.actor)}</th>
								<td class="num">{count(row.eligible)}</td>
								{#each STANCES as stance (stance)}
									<td class="num">{count(row.stances[stance] ?? 0)}</td>
								{/each}
								<td class="num">withheld</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	</Figure>

	<section class="prompt-block">
		<h2>The prompt</h2>
		<p class="quiet">
			The instruction the model was given, verbatim, at version {artefact.model.prompt_version}. A
			change to any character of it is a different run with a different
			<code>sha256</code>, and the labels are not comparable across the two.
		</p>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />Show the prompt (<code>sha256:{shortSha}</code>)</summary
			>
			<pre>{artefact.prompt}</pre>
		</details>
	</section>

	<section class="agreement">
		<h2>Agreement</h2>
		{#if !gold.hasAgreement && !gold.hasModelScores}
			<p class="quiet">
				<strong
					>No gold rows coded yet &mdash; agreement will appear here when there is something to
					compute.</strong
				>
				A sample of {count(gold.sampleSize)} occurrences ({count(gold.uniqueOccurrences)} of them distinct)
				is drawn and waiting; two coders will code every one of them independently, and the tables below
				will then carry how far the two agreed with each other and how far the model agreed with them.
				Until then, every number on this page has no measured error rate, and none can be guessed at.
			</p>
		{:else}
			<p class="quiet">
				{count(gold.coded)} of {count(gold.sampleSize)} sampled occurrences carry a human verdict,
				{count(gold.doubleCoded)} of them from both coders, with {count(gold.adjudicated)} adjudicated.
			</p>
			{#if gold.hasAgreement}
				<h3>Between the two coders</h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
				<div class="scroll" role="region" aria-label="Agreement between coders" tabindex="0">
					<table>
						<thead>
							<tr>
								<th scope="col">Field</th>
								<th scope="col" class="num">Double-coded</th>
								<th scope="col" class="num">Observed</th>
								<th scope="col" class="num">Kappa</th>
							</tr>
						</thead>
						<tbody>
							{#each artefact.gold.human_agreement as row (row.field)}
								<tr>
									<th scope="row">{termLabel(row.field)}</th>
									<td class="num">{count(row.n)}</td>
									<td class="num">{percent(row.observed)}</td>
									<td class="num">{row.kappa === null ? '—' : decimal(row.kappa)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="quiet">
					A dash in the kappa column means the statistic could not be computed: with every row in
					one category there is no chance agreement to correct for.
				</p>
			{/if}
			{#if gold.hasModelScores}
				<h3>The model against the human labels</h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
				<div
					class="scroll"
					role="region"
					aria-label="The model against the human labels"
					tabindex="0"
				>
					<table>
						<thead>
							<tr>
								<th scope="col">Field</th>
								<th scope="col" class="num">Rows</th>
								<th scope="col" class="num">Accuracy</th>
								<th scope="col" class="num">Macro F1</th>
								<th scope="col" class="num">Abstained</th>
							</tr>
						</thead>
						<tbody>
							{#each artefact.gold.model_vs_human as row (row.field)}
								<tr>
									<th scope="row">{termLabel(row.field)}</th>
									<td class="num">{count(row.n)}</td>
									<td class="num">{percent(row.accuracy)}</td>
									<td class="num">{row.macro_f1 === null ? '—' : decimal(row.macro_f1)}</td>
									<td class="num">{percent(row.abstention_rate)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<details class="data-table">
					<summary><Icon icon={ChevronRight} />Per class</summary>
					<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
					<div class="scroll" role="region" aria-label="Per class scores" tabindex="0">
						<table>
							<thead>
								<tr>
									<th scope="col">Field</th>
									<th scope="col">Class</th>
									<th scope="col" class="num">Support</th>
									<th scope="col" class="num">Precision</th>
									<th scope="col" class="num">Recall</th>
									<th scope="col" class="num">F1</th>
								</tr>
							</thead>
							<tbody>
								{#each artefact.gold.model_vs_human as field (field.field)}
									{#each field.classes as row (row.label)}
										<tr>
											<th scope="row">{termLabel(field.field)}</th>
											<td>{stanceLabel(row.label)}</td>
											<td class="num">{count(row.support)}</td>
											<td class="num">{decimal(row.precision)}</td>
											<td class="num">{decimal(row.recall)}</td>
											<td class="num">{decimal(row.f1)}</td>
										</tr>
									{/each}
								{/each}
							</tbody>
						</table>
					</div>
				</details>
			{/if}
		{/if}
	</section>
</article>

<style>
	.lede {
		max-width: var(--measure);
		margin-bottom: var(--sp-6);
	}

	h1 {
		font-family: var(--serif);
		font-size: var(--display);
		line-height: 1.05;
		margin: 0 0 var(--sp-4);
	}

	.standfirst {
		font-family: var(--serif);
		font-size: var(--step-1);
		color: var(--ink-2);
		margin: 0;
	}

	/* The standing marking. A rule on the leading edge and the warning token, not
	   a panel: nothing on this site is a box, and a banner would make the claim
	   look like a dismissible notice rather than a property of the page. */
	.experiment {
		margin: 0 0 var(--sp-7);
		padding-left: var(--sp-4);
		border-left: 2px solid var(--state-warn);
	}

	.experiment .label {
		color: var(--state-warn);
		margin-bottom: var(--sp-2);
	}

	.governing {
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.55;
		color: var(--ink-2);
		margin: 0 0 var(--sp-4);
	}

	.governing strong {
		color: var(--ink);
	}

	.experiment dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: var(--sp-3) var(--sp-5);
		margin: 0;
	}

	.experiment dt {
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
	}

	.experiment dd {
		margin: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.experiment code {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink);
		overflow-wrap: anywhere;
	}

	/* ---- the figure's own controls ---------------------------------------- */

	.control {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	.control .label {
		display: inline;
	}

	.disclosure,
	.refusal,
	.quiet {
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	.disclosure {
		margin: var(--sp-3) 0 0;
	}

	.error {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--state-bad);
		max-width: var(--measure);
	}

	/* ---- the quotations ---------------------------------------------------- */

	.evidence,
	.prompt-block,
	.agreement {
		margin: 0 0 var(--sp-8);
	}

	h2 {
		font-family: var(--serif);
		font-size: var(--step-2);
		margin: 0 0 var(--sp-3);
	}

	h3 {
		font-family: var(--sans);
		font-size: var(--step-0);
		margin: var(--sp-5) 0 var(--sp-2);
	}

	.quotations {
		list-style: none;
		margin: var(--sp-4) 0 0;
		padding: 0;
	}

	.quotations li {
		padding: var(--sp-4) 0;
		border-top: var(--hair) solid var(--rule);
	}

	.line {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-1) var(--sp-3);
		margin: 0 0 var(--sp-2);
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.line .who {
		color: var(--ink-2);
	}

	blockquote {
		margin: 0 0 var(--sp-3);
		padding-left: var(--sp-3);
		border-left: var(--hair) solid var(--rule-strong);
		font-family: var(--serif);
		font-size: var(--step-0);
		line-height: 1.55;
		max-width: var(--measure);
	}

	.labels {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--sp-2) var(--sp-3);
		margin: 0 0 var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--2);
	}

	/* The stance is a datum, so it carries a data colour and no control ever
	   does. The colour is a rule under the word rather than the word itself —
	   the same gesture `app.css` gives a marked term of a given register, and
	   the reason is the same one that produced it there: several of these
	   tokens are chosen to be told apart from each other on a chart, not to be
	   read as 12px text on paper, and set as text they fall short of the
	   contrast a label has to clear. Ink carries the reading; the hue carries
	   the category. A filled chip is not used either: it would read as
	   something to press. */
	.stance {
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--ink);
		padding-bottom: 0.15em;
		box-shadow: inset 0 -2px 0 var(--rule-strong);
	}

	.stance[data-stance='asserts'] {
		box-shadow: inset 0 -2px 0 var(--reg-contentious);
	}
	.stance[data-stance='attributes_or_reports'] {
		box-shadow: inset 0 -2px 0 var(--reg-commemorative);
	}
	.stance[data-stance='rejects_or_denies'] {
		box-shadow: inset 0 -2px 0 var(--ink);
	}
	.stance[data-stance='hypothetical_or_conditional'] {
		box-shadow: inset 0 -2px 0 var(--reg-preventive);
	}
	.stance[data-stance='neutral_legal_reference'] {
		box-shadow: inset 0 -2px 0 var(--reg-legal);
	}
	.stance[data-stance='unclear'],
	.stance[data-stance='not_applicable'] {
		box-shadow: inset 0 -2px 0 var(--ink-3);
	}

	.fn {
		color: var(--ink-3);
	}

	.span {
		max-width: var(--measure);
		margin: 0 0 var(--sp-3);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.span .label {
		display: block;
		margin-bottom: var(--sp-1);
	}

	.span em {
		color: var(--state-bad);
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-4);
		margin: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.button {
		display: inline-flex;
		align-items: center;
		gap: 0.4em;
		padding: var(--sp-2) var(--sp-3);
		border: var(--hair) solid var(--blue);
		color: var(--blue);
		text-decoration: none;
	}

	.button:hover {
		background: var(--blue);
		color: var(--paper);
	}

	.id {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.ghost,
	.more {
		display: inline-flex;
		align-items: center;
		gap: 0.4em;
		background: none;
		border: var(--hair) solid var(--rule-strong);
		padding: var(--sp-1) var(--sp-3);
		min-height: 2rem;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
		cursor: pointer;
	}

	.ghost:hover,
	.more:hover {
		border-color: var(--blue);
		color: var(--blue);
	}

	.more {
		display: flex;
		margin: var(--sp-4) auto 0;
		padding: var(--sp-2) var(--sp-5);
	}

	/* ---- the stance profile ------------------------------------------------ */

	/* One hue per stance, tinted toward the page so the numbers stay readable on
	   top of them — the ceiling `Standing.svelte` settled on, for the same
	   reason. Rejection carries ink, the strongest weight available, because it
	   is the band the figure is ordered by. `--blue` appears nowhere. */
	.key,
	.stances {
		--tint: 32%;
		--stance-asserts: color-mix(in oklab, var(--reg-contentious) var(--tint), transparent);
		--stance-attributes-or-reports: color-mix(
			in oklab,
			var(--reg-commemorative) var(--tint),
			transparent
		);
		--stance-rejects-or-denies: color-mix(in oklab, var(--ink) var(--tint), transparent);
		--stance-hypothetical-or-conditional: color-mix(
			in oklab,
			var(--reg-preventive) var(--tint),
			transparent
		);
		--stance-neutral-legal-reference: color-mix(
			in oklab,
			var(--reg-legal) var(--tint),
			transparent
		);
		--stance-unclear: color-mix(in oklab, var(--ink-3) calc(var(--tint) / 2), transparent);
		--stance-not-applicable: color-mix(in oklab, var(--rule-strong) var(--tint), transparent);
	}

	.key {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-2) var(--sp-4);
		margin-bottom: var(--sp-3);
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
	}

	.swatch {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-1);
	}

	.swatch i {
		width: 1.4rem;
		height: 0.55rem;
		background: var(--band);
		display: inline-block;
	}

	.scroll {
		overflow-x: auto;
		max-height: 32rem;
		overflow-y: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	thead th {
		position: sticky;
		top: 0;
		background: var(--paper);
		z-index: 1;
	}

	tbody th {
		font-weight: 400;
		white-space: nowrap;
		text-transform: none;
		letter-spacing: 0;
		font-size: var(--step--1);
		color: var(--ink);
	}

	/* The profile painted behind the row it describes: one gradient with hard
	   stops, because a band is a range of the row rather than a box inside it.
	   The zebra striping is switched off for these rows — the bands are 32%
	   opaque, so a stripe underneath would draw the same stance in two colours
	   down the column. */
	tbody tr.band {
		background-color: transparent;
		background-image: var(--bands);
	}

	tr.withheld td:last-child {
		color: var(--ink-3);
		font-style: italic;
	}

	pre {
		margin: var(--sp-3) 0 0;
		padding: var(--sp-3);
		max-height: 28rem;
		overflow: auto;
		border-left: var(--hair) solid var(--rule-strong);
		background: var(--paper-sunk);
		font-family: var(--mono);
		font-size: var(--step--2);
		line-height: 1.6;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
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
