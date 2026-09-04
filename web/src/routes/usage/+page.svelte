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
	import DiffusionChart from '$lib/DiffusionChart.svelte';
	import Figure from '$lib/Figure.svelte';
	import Contents from '$lib/Contents.svelte';
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
		CONTESTED_COLUMNS,
		DIFFUSION_COLUMNS,
		MATRIX_COLUMNS,
		POSITIONS,
		POSITION_COLUMNS,
		USAGE_TERM,
		comparisonApparatus,
		contestedExportRows,
		contestedList,
		diffusionChronology,
		diffusionExportRows,
		diffusionPlan,
		drillDown,
		goldProgress,
		isInstrumentDependent,
		matrixExportRows,
		matrixPlan,
		readUsageState,
		selectUsage,
		positionExportRows,
		retestRows,
		positionLabel,
		positionRanking,
		usageParams
	} from '$lib/usage';
	import type {
		DiffusionPoint,
		DiffusionSeries,
		MatrixCell,
		PositionSegment,
		UsageSort,
		UsageState,
		UsageUnit
	} from '$lib/usage';
	import type {
		KwicLine,
		PositionCounts,
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
	let contested = $state(false);
	let urlReady = $state(false);
	/** How many quotations of the drill-down are on screen. Presentation only. */
	let shown = $state(20);

	const current = (): UsageState => ({ actor, referent, unit, sort, contested });

	onMount(() => {
		const state = readUsageState(page.url.searchParams, artefact);
		actor = state.actor;
		referent = state.referent;
		unit = state.unit;
		sort = state.sort;
		contested = state.contested;
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
	const ranking = $derived(positionRanking(artefact));
	const gold = $derived(goldProgress(artefact));
	const selected = $derived(Boolean(actor || referent));
	/* The second opinion, or the empty block that says none was run. Everything
	   about it on this page is drawn on `computed` and on nothing else: under
	   `none` there is no section, no figure and no filter, which is the state the
	   published payload is in. */
	const comparison = $derived(comparisonApparatus(artefact));
	/* Each model against another run of itself, over the pilot occurrences both
	   reached. The floor the cross-model column has to be read against: two
	   models differing on a fifth of the speaker_position labels says nothing until a
	   reader knows how far one model differs from itself. */
	const retest = $derived(retestRows(artefact));
	/** One field's observed agreement in one retest, or a dash. */
	const retestField = (run: (typeof retest)[number], field: string) =>
		run.fields.find((row) => row.field === field)?.observedText ?? '—';
	const referentLabel = (id: string) =>
		artefact.referents.find((entry) => entry.id === id)?.label ?? termLabel(id);

	/* ---- the evidence, fetched at the first drill-down and not before -------
	   Two artefacts, requested together rather than in sequence: they are
	   independent files and neither alone yields a quotation. `fetched` is a
	   plain variable rather than state because it guards the effect that fills
	   the state — a guard that was itself a dependency would run the effect a
	   second time to discover that it had already run.

	   A build carrying a second opinion asks for the same two files on load
	   rather than on a click, because the reading list of contested passages is a
	   figure on this page and it needs both: the annotations carry which
	   occurrences the two runs read differently, and the concordance carries the
	   date, the delegation and the sentence they are read back to. It stays a
	   browser fetch after render, so nothing about the page's first paint changes
	   — and on a build with no comparison run, which is the published state,
	   nothing is fetched until a reader opens a cell. */
	let annotations = $state<UsageOccurrences | null>(null);
	let lines = $state<KwicLine[]>([]);
	let loading = $state(false);
	let failure = $state<string | null>(null);
	let retry = $state(0);
	let fetched = false;

	const wanted = $derived(selected || comparison.computed);

	$effect(() => {
		void retry;
		if (!wanted || fetched) return;
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

	/* One enumeration of a selection's occurrences, asked twice: the filter is a
	   flag on `drillDown` rather than a predicate written here, so the list the
	   control narrows and the list it narrows to are the same code. */
	const allEvidence = $derived(
		drillDown(annotations?.occurrences ?? [], lines, actor, referent, {
			compared: comparison.computed,
			referents: artefact.referents
		})
	);
	const contestedEvidence = $derived(
		comparison.computed
			? drillDown(annotations?.occurrences ?? [], lines, actor, referent, {
					compared: true,
					contestedOnly: true,
					referents: artefact.referents
				})
			: []
	);
	const evidence = $derived(contested ? contestedEvidence : allEvidence);

	$effect(() => {
		void [actor, referent, contested];
		shown = 20;
	});

	function pick(nextActor: string, nextReferent: string) {
		const next = selectUsage(current(), nextActor, nextReferent);
		actor = next.actor;
		referent = next.referent;
	}

	/* ---- the diffusion of one referent --------------------------------------
	   The same `referent` the matrix sets, read a second way: one state, two
	   figures, and a column heading and this figure's picker are the same
	   control. The chronology takes whatever concordance lines are in hand — it
	   needs none of them for its own rows, only for the link back into the
	   concordance, which cannot be addressed without a record symbol. */
	const diffusion = $derived(diffusionPlan(artefact, current()));
	const chronology = $derived(diffusionChronology(diffusion, lines));

	/* ---- the passages the two runs read differently -------------------------
	   Built from the same two artefacts the drill-down uses, and empty until both
	   are in hand. It is a reading list rather than an error report: the labels
	   the rest of this page counts are the published run's, here and everywhere. */
	const listing = $derived(contestedList(artefact, annotations?.occurrences ?? [], lines));

	const stepLabel = (point: DiffusionPoint, series: DiffusionSeries) =>
		`${shortCountry(point.actor)}, ${isoDate(point.date)}: ${series.label.toLowerCase()}. ` +
		`${count(point.value)} of ${count(series.total)} delegations by then. ` +
		`Position: ${point.positionLabel.toLowerCase()}.`;

	const diffusionDescription = $derived(
		`Cumulative delegations for ${diffusion.label}, ${isoDate(diffusion.span.from)} to ` +
			`${isoDate(diffusion.span.to)}: ` +
			diffusion.drawn
				.map((series) => `${series.label.toLowerCase()}, ${count(series.total)}`)
				.join('; ') +
			'. Every step is listed in the chronology below the figure.'
	);

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

	/** Every speaker_position a set of counts actually holds, as a sentence. */
	const describePositions = (positions: PositionCounts, total: number) =>
		POSITIONS.filter((speaker_position) => (positions[speaker_position] ?? 0) > 0)
			.map(
				(speaker_position) =>
					`${positionLabel(speaker_position).toLowerCase()} ${count(positions[speaker_position])}` +
					(total > 0 ? ` (${percent(positions[speaker_position] / total)})` : '')
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
		// The contested share belongs on the cell rather than only in the
		// apparatus: a reader who drills into one cell is reading that cell, and
		// how much of it the two instruments read differently is the caveat that
		// applies to the number under the cursor.
		const disputed =
			comparison.computed && cell.contestedShare !== null
				? ` ${count(cell.contested)} of them read differently by ${comparison.model} (${percent(cell.contestedShare)}).`
				: '';
		return (
			`${who} × ${subject.label}: ${count(cell.count)} ${many}, ${share}. ` +
			`${describePositions(cell.positions, cell.count)}.${disputed}`
		);
	}

	/* One hue per speaker_position, tinted toward the page so the numbers can be read on
	   top of them. `--blue` appears nowhere: it belongs to what a reader can act
	   on, never to a datum. Rejection is the strongest weight because it is the
	   question the figure is ordered by. */
	const slug = (speaker_position: string) => speaker_position.replace(/_/g, '-');
	const bands = (parts: PositionSegment[]) =>
		parts
			.map(
				(band) =>
					`var(--speaker_position-${slug(band.speaker_position)}) ${band.from.toFixed(3)}% ${band.to.toFixed(3)}%`
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

	function diffusionTable(): ExportRequest {
		const events = artefact.diffusion.referents.reduce(
			(total, entry) => total + entry.events.length,
			0
		);
		return {
			title: 'When each delegation first said it',
			columns: DIFFUSION_COLUMNS,
			rows: diffusionExportRows(artefact),
			provenance: provenanceOf(artefact.meta, 'usage/usage.json'),
			filters: [
				`on screen: ${diffusion.label}`,
				`milestones: first placed use, first assertion, first refusal of the word`,
				`labels: ${artefact.model.id}, run ${artefact.model.run_id}`
			],
			scope:
				`every first the run recorded — ${count(events)} events over ` +
				`${count(artefact.diffusion.referents.length)} referents, not the one referent the ` +
				`figure is showing and not only the curves it drew`
		};
	}

	function contestedTable(): ExportRequest {
		return {
			title: 'The contested passages',
			columns: CONTESTED_COLUMNS,
			rows: contestedExportRows(artefact, annotations?.occurrences ?? [], lines),
			provenance: provenanceOf(artefact.meta, 'usage/occurrences.json'),
			filters: [
				`published run: ${artefact.model.id}, run ${artefact.model.run_id}`,
				`second opinion: ${comparison.model}, run ${comparison.runId}`,
				`compared over: ${comparison.overlap} occurrences carrying a label from both runs`,
				`agreement between two models is stability across instruments, never accuracy`
			],
			scope:
				`every occurrence the two runs read differently — ${count(listing.contested)} of ` +
				`${count(comparison.overlap)} compared — not the ${count(listing.rows.length)} the figure ` +
				`draws, and including the ${count(listing.unquotable)} the concordance file has no line ` +
				`for, whose date and delegation are written null`
		};
	}

	function positionTable(): ExportRequest {
		return {
			title: 'Who rejects the word',
			columns: POSITION_COLUMNS,
			rows: positionExportRows(artefact),
			provenance: provenanceOf(artefact.meta, 'usage/usage.json'),
			filters: [
				`ranked by: share of eligible occurrences that reject or deny`,
				`minimum for a share: ${artefact.minimum_occurrences} eligible occurrences`,
				`labels: ${artefact.model.id}, run ${artefact.model.run_id}`
			],
			scope:
				`every speaker the run produced a speaker_position profile for, including the ` +
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
					{count(artefact.model.abstention.position_unclear)} speaker_position
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

		<!-- Nothing at all where no comparison run was made, which is the ordinary
		     state and the published one. An empty table under a heading promising a
		     second opinion would read as two models agreeing on nothing. -->
		{#if comparison.computed}
			<div class="second-opinion">
				<h2>Second opinion</h2>
				<p class="governing">
					A second model was given the same occurrences and the
					{comparison.samePrompt ? 'byte-identical prompt' : 'prompt below'}. It is a
					counter-instrument, not a check:
					<strong
						>agreement between two models measures stability across instruments, never accuracy</strong
					> &mdash; both can be wrong about a passage in the same way &mdash; and the human gold sample
					remains the only calibration. None of its labels replaces one of the published run's, and no
					figure on this page is redrawn by it.
				</p>
				<dl>
					<div>
						<dt>Second model</dt>
						<dd><code>{comparison.model}</code></dd>
					</div>
					<div>
						<dt>Run</dt>
						<dd>
							<code>{comparison.runId || '—'}</code>
							{#if comparison.runDate}&middot; {comparison.runDate}{/if}
						</dd>
					</div>
					<div>
						<dt>Reasoning</dt>
						<dd>{comparison.reasoningEffort || '—'}</dd>
					</div>
					<div>
						<dt>Annotated</dt>
						<dd>
							{count(comparison.annotated)} of {count(comparison.total)} occurrences
							{#if comparison.coverage !== null}&middot; {percent(comparison.coverage)}{/if}
						</dd>
					</div>
					<div>
						<dt>Compared</dt>
						<dd>{count(comparison.overlap)} carry a label from both runs</dd>
					</div>
					<div>
						<dt>Refused</dt>
						<dd>
							{count(comparison.abstained)}
							{comparison.abstained === 1 ? 'abstention' : 'abstentions'} &middot;
							{count(comparison.evidenceInvalid)} evidence spans not found in the speech
						</dd>
					</div>
				</dl>

				{#if comparison.fields.length}
					<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
					<div
						class="scroll"
						role="region"
						aria-label="Agreement between the two runs"
						tabindex="0"
					>
						<table>
							<caption class="sr-only">
								How far the published run and the second opinion agree, field by field, over the
								occurrences both of them reached
							</caption>
							<thead>
								<tr>
									<th scope="col">Field</th>
									<th scope="col" class="num">Compared</th>
									<th scope="col" class="num">Observed</th>
									<th scope="col" class="num">Kappa</th>
									<th scope="col" class="num">PABAK</th>
									<th scope="col" class="num">Contested</th>
									{#each retest as run (run.which)}
										<th scope="col" class="num">Same model, twice</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each comparison.fields as row (row.field)}
									<tr>
										<th scope="row">{row.label}</th>
										<td class="num">{count(row.n)}</td>
										<td class="num">{row.observedText}</td>
										<td class="num" class:withheld={row.kappaWithheld}>{row.kappaText}</td>
										<td class="num">{row.pabakText}</td>
										<td class="num">{count(row.contested)}</td>
										{#each retest as run (run.which)}
											<td class="num">{retestField(run, row.field)}</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
					<p class="quiet">
						<code>function</code> carries several labels at once and no kappa is defined on it. The
						mean overlap between the two runs is <strong>{comparison.functionJaccardText}</strong>;
						Krippendorff's &alpha; under the MASI distance, which corrects for the chance the
						overlap does not,
						<strong>{comparison.functionAlphaText}</strong>. {count(comparison.functionContested)}
						{comparison.functionContested === 1 ? 'occurrence' : 'occurrences'} carry a different set
						of functions, and almost all of it is in one label — the table below says which.
					</p>
					<p class="quiet">
						A dash in the kappa column means the statistic was not computed, or was
						<strong>withheld</strong>: below one per cent outside a run's commonest label — which is
						<code>verdict</code> in both of these — chance agreement is almost total and kappa divides
						what little is left, returning a figure near zero about the most stable field in the run.
						PABAK is that correction against a uniform chance over the codebook's categories, and is what
						to read in its place.
					</p>
					{#if retest.length}
						<p class="quiet">
							<strong>Same model, twice</strong> is each instrument against another run of itself
							with the byte-identical prompt, over the {count(retest[0].overlap)} pilot occurrences both
							reached. It is the floor the column beside it has to be read against:
							{#each retest as run, index (run.which)}<code>{run.model}</code> writes all five
								fields identically on {count(run.identical)} of {count(run.overlap)}{index <
								retest.length - 1
									? ', and '
									: '. '}{/each}A quarter of one model's own labels moving between two calls is not
							a smaller finding than two models differing on a fifth.
						</p>
					{/if}
					{#if comparison.functionLabels.length}
						<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
						<div
							class="scroll"
							role="region"
							aria-label="Agreement per function label"
							tabindex="0"
						>
							<table>
								<caption class="sr-only">
									How far the two runs agree that each function label applies
								</caption>
								<thead>
									<tr>
										<th scope="col">Function</th>
										<th scope="col" class="num">{artefact.model.id}</th>
										<th scope="col" class="num">{comparison.model}</th>
										<th scope="col" class="num">Observed</th>
										<th scope="col" class="num">Kappa</th>
									</tr>
								</thead>
								<tbody>
									{#each comparison.functionLabels as row (row.label)}
										<tr>
											<th scope="row">{row.label}</th>
											<td class="num">{count(row.left)}</td>
											<td class="num">{count(row.right)}</td>
											<td class="num">{row.observedText}</td>
											<td class="num">{row.kappaText}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
					<p class="quiet">
						<strong>Two labels are instrument-dependent</strong> and are marked wherever they
						appear: <em>attributes or reports</em> and <em>attributed or reported</em>. The two
						models place the first on 789 occurrences between them and share 215 of those; 445 are
						<em>attributes</em>
						to one and <em>asserts</em> to the other. A count of either is a count of how one model read
						a boundary the prompt does not draw.
					</p>
				{:else}
					<p class="quiet">
						The two runs reached no occurrence in common, so there is nothing to compute agreement
						over.
					</p>
				{/if}

				<p class="quiet">
					<strong
						>{count(comparison.contestedAny)} of {count(comparison.overlap)} compared occurrences</strong
					>
					{#if comparison.contestedShare !== null}({percent(comparison.contestedShare)}){/if}
					are read differently on at least one of the five fields. They are listed under
					<em>The contested passages</em> below, and marked wherever they appear in the quotations.
				</p>
			</div>
		{/if}
	</section>

	<Contents
		figures={[
			{ title: 'Which genocide each delegation means' },
			{ title: 'When each delegation first said it' },
			{ title: 'Who rejects the word' }
		]}
	/>

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
			<span class="unit-note"
				>{unit === 'count'
					? 'occurrences placed on a referent, published for every delegation'
					: "a share of the delegation's own placed occurrences, withheld below the minimum"}</span
			>
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
				Rows are delegations, columns referents; a shaded cell is the word placed on that genocide,
				deeper amber for more. <strong>Click a cell</strong> for the occurrences behind it, a row or
				column heading for the whole line. The last columns, ruled off in italic, are ways of
				talking about the category, not genocides. A share is withheld below
				{count(artefact.minimum_occurrences)} occurrences.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>These columns are a model's reading, not a coding:</strong>
				<code>{artefact.model.id}</code> assigned every referent and no human has checked one; a wrong
				referent looks like a right one. A referent is not an endorsement: it says what a speaker was
				talking about, never whether they were right.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				The rows do not add up to the corpus, and the disclosure under the figure says by how much:
				{count(plan.disclosure.ineligible)} occurrences never became eligible &mdash; the model judged
				them not a real use of the word, or could not find its own evidence span &mdash; and
				{count(plan.disclosure.unassigned)} more were eligible and could not be placed on any referent.
				<em>Other known referent</em> is a real referent the controlled list has not named yet. The list
				carries the situations argued before the Council, including ones whose characterisation is contested
				and one, the embargo against Cuba, that is a claim about a sanctions regime. A count is published
				at every denominator, because two of two is a fact about the record and &ldquo;100%&rdquo; is
				not.
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

		<!-- Offered only where a second opinion exists to filter on, and only once a
		     selection has been made: a control over an empty list is a control that
		     cannot be seen to do anything. -->
		{#if comparison.computed && selected && !loading && !failure}
			<p class="filter">
				<label>
					<input type="checkbox" bind:checked={contested} />
					Contested only ({count(contestedEvidence.length)} of {count(allEvidence.length)})
				</label>
				<span class="quiet">
					The occurrences <code>{comparison.model}</code> read differently from
					<code>{artefact.model.id}</code>. A disagreement is a passage worth reading, not an error
					found: neither run has been checked against anything.
				</span>
			</p>
		{/if}

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
		{:else if evidence.length === 0 && contested}
			<p class="quiet">
				The two runs agreed on every occurrence behind this pairing. Clear the filter above to read
				all {count(allEvidence.length)} of them.
			</p>
		{:else if evidence.length === 0}
			<p class="quiet">
				No annotated occurrence in this build carries that pairing. The matrix counts and the
				quotations are two artefacts, and a cell can be counted in one before the other is rebuilt.
			</p>
		{:else}
			<p class="quiet">
				{count(evidence.length)}
				{evidence.length === 1 ? 'occurrence' : 'occurrences'}{#if contested}, of {count(
						allEvidence.length
					)} behind this pairing{/if}, oldest first. The speaker_position is the model's; the
				sentence is the record's.
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
							<span class="speaker_position" data-speaker_position={row.speaker_position}
								>{row.positionLabel}</span
							>
							{#if row.caseLabel}<span class="fn">{row.caseLabel}</span>{/if}
							{#each row.functions as name (name)}<span class="fn">{termLabel(name)}</span>{/each}
							<span class="fn">confidence {row.confidence}</span>
							{#if !referent}<span class="fn">{referentLabel(row.referent)}</span>{/if}
							{#if row.contested.length}
								<span class="contested"
									>Contested: {row.contested.map((entry) => entry.label).join(', ')}</span
								>
							{/if}
						</p>
						{#if row.contested.length}
							<p class="second-reading">
								<span class="label">The second model read</span>
								{#each row.contested as entry (entry.field)}
									<span class="pair">
										<span class="field">{entry.label}</span>
										<strong>{entry.second}</strong>
										<span class="mine">&mdash; this run read {entry.published}</span>
									</span>
								{/each}
							</p>
						{/if}
						{#if row.schemaFields.length}
							<dl class="schema-fields">
								{#each row.schemaFields as field (field.label)}
									<dt>{field.label}</dt>
									<dd>{field.value}</dd>
								{/each}
							</dl>
						{/if}
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

	<!-- The picker is declared here rather than inline so that a build with no
	     chronology at all can be handed no controls, instead of an empty control
	     bar with two rules and nothing between them. -->
	{#snippet referentPicker()}
		<label>
			Referent
			<select
				value={diffusion.referent}
				onchange={(event) => (referent = event.currentTarget.value)}
			>
				{#each diffusion.options as option (option.id)}
					<option value={option.id}>
						{option.label} &mdash; {option.events
							? `${count(option.delegations)} ${option.delegations === 1 ? 'delegation' : 'delegations'}`
							: 'nothing recorded'}
					</option>
				{/each}
			</select>
		</label>
	{/snippet}

	<Figure
		title="When each delegation first said it"
		question="When did each delegation first place the word on this genocide, first assert it, and first refuse it?"
		source="15_usage.py → usage/usage.json"
		note="Height is a count of delegations, not of occurrences: each is counted once, on the day it first crossed that line."
		controls={diffusion.options.length ? referentPicker : undefined}
		download={{ name: ['unsc', 'usage', 'diffusion'], table: diffusionTable }}
	>
		{#snippet reading()}
			<p>
				The <strong>solid amber curve</strong> counts delegations that have asserted this genocide;
				the <strong>dashed ink curve</strong> those that used the word to refuse it. Both only rise.
				A faint hairline above them, drawn only where it differs, counts every delegation that
				placed the word here at all.
				<strong>The chronology below is the same events as text.</strong>
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>A curve of delegations speaking in this corpus</strong>, not of states holding a
				view: an absence is silence, not refusal. The milestones are
				<code>{artefact.model.id}</code>'s readings; a mislabelled speaker_position moves a
				delegation between the curves, and a referent the second model reads differently is
				withheld.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				The vertical scale is this referent's own and the time axis is every referent's, so
				switching referents moves the curve along a fixed span rather than redrawing it. An absence
				can be a seat not held or a debate never opened, and Council membership turns over yearly:
				the open debates that let a non-member speak are called unevenly, so a rise can be a change
				in who was in the room rather than in what was being said. A referent is withheld here when
				the two models place it on the same occurrences at a cross-instrument F1 below 0.8, because
				a first assertion is then a property of which model was asked.
			</p>
		{/snippet}

		{#if diffusion.refusal === 'no-diffusion'}
			<p class="refusal">
				The run recorded no first for any referent, so there is nothing here that could be drawn.
				The chronology is built from the same annotations as the matrix above, and it is empty
				exactly when nothing was placed on any referent at all.
			</p>
		{:else if diffusion.refusal === 'no-events'}
			<p class="refusal">
				The chronology carries no first this figure can draw for
				<strong>{diffusion.label}</strong>. Pick another referent above.
			</p>
		{:else if diffusion.refusal === 'unstable-referent'}
			<p class="refusal">
				<strong>Withheld for {diffusion.label}.</strong>
				A curve of firsts is a claim about dates, and a date here is the first occurrence a label fell
				on. The two models place this referent on the same occurrences
				{diffusion.reliability === null || diffusion.reliability === undefined
					? 'too rarely to measure'
					: `at F1 ${decimal(diffusion.reliability)}`}, under the 0.8 this figure requires, so its
				first assertion and its first refusal would be properties of which model was asked. The
				matrix above still counts it, because a count is not a date. Pick another referent.
			</p>
		{:else}
			<DiffusionChart plan={diffusion} label={stepLabel} description={diffusionDescription} />

			<p class="disclosure">
				{count(diffusion.totals.mention)}
				{diffusion.totals.mention === 1 ? 'delegation has' : 'delegations have'} placed the word on
				{diffusion.label}
				at all; {count(diffusion.totals.asserts)} of them asserted it, and
				{count(diffusion.totals.rejects)} used the word in order to refuse it for this case. A delegation
				can be on two of those curves and often is — the first use that refuses the word is also that
				delegation's first use of it.
			</p>

			<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
			<div class="scroll" role="region" aria-label="Chronology of firsts" tabindex="0">
				<table class="chronology">
					<caption class="sr-only">
						Every first the curves are made of, for {diffusion.label}, oldest first
					</caption>
					<thead>
						<tr>
							<th scope="col">Date</th>
							<th scope="col">Delegation</th>
							<th scope="col">Milestone</th>
							<th scope="col">Position</th>
							<th scope="col" class="num">Nth</th>
							<th scope="col">Occurrence</th>
						</tr>
					</thead>
					<tbody>
						{#each chronology as row (`${row.milestone}:${row.id}`)}
							<tr>
								<td class="when">{isoDate(row.date)}</td>
								<th scope="row">{shortCountry(row.actor)}</th>
								<td>
									<span class="milestone" data-milestone={row.milestone}>{row.milestoneLabel}</span>
								</td>
								<td
									><span class="speaker_position" data-speaker_position={row.speaker_position}
										>{row.positionLabel}</span
									></td
								>
								<td class="num">{count(row.ordinal)}</td>
								<td class="where">
									<a
										href="{resolve('/reader/[meeting]', { meeting: row.reader.meeting })}?{row
											.reader.query}"
									>
										<code>{row.id}</code>
									</a>
									{#if row.concordance}
										<a href="{resolve('/concordance')}?{row.concordance.query}">concordance</a>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</Figure>

	<!-- The reading list, and only where there is a second run to disagree with.
	     On a build with no comparison the figure is absent rather than empty: an
	     empty table here would read as two models that agreed about everything. -->
	{#if comparison.computed}
		<Figure
			title="The contested passages"
			question="Which passages did the two models read differently, and how?"
			source="15_usage.py → usage/occurrences.json"
			note="One row per occurrence, not per disagreement: an occurrence the two runs split on three fields is one row, ranked above one they split on a single field."
			download={{ name: ['unsc', 'usage', 'contested'], table: contestedTable }}
		>
			{#snippet reading()}
				<p>
					Every occurrence <code>{comparison.model}</code> labelled differently from
					<code>{artefact.model.id}</code>, hardest first: the top rows disagree on the most fields.
					The two reading columns are one occurrence read twice;
					<strong>neither corrects the other</strong>, and no human has checked either. Follow the
					identifier to read the passage whole.
				</p>
			{/snippet}
			{#snippet caveat()}
				<p>
					<strong
						>Agreement between two models measures stability across instruments, never accuracy.</strong
					> Two models can be wrong in the same way; the human gold sample is the only calibration here.
					A disagreement is not an error found. Nothing here is merged into the matrix, speaker_position
					profile or diffusion curve.
				</p>
			{/snippet}

			{#if failure}
				<p class="error">{failure}</p>
				<button type="button" class="ghost" onclick={again}>Try again</button>
			{:else if !annotations}
				<p class="quiet">Loading the annotations and the concordance for {USAGE_TERM}…</p>
			{:else if listing.refusal === 'no-contest'}
				<p class="refusal">
					The two runs labelled every one of the {count(comparison.overlap)} occurrences they both reached
					the same way. That is a finding about the labels' stability and not about their accuracy.
				</p>
			{:else if listing.rows.length === 0}
				<p class="refusal">
					{count(listing.contested)} occurrences are contested and none of them could be read back to
					a sentence in the concordance for {USAGE_TERM}. They are in the CSV below.
				</p>
			{:else}
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
				<div class="scroll" role="region" aria-label="Contested passages" tabindex="0">
					<table class="contested-table">
						<caption class="sr-only">
							Occurrences the published run and the second opinion labelled differently, most
							contested first, with both readings of each field they differ on
						</caption>
						<thead>
							<tr>
								<th scope="col">Date</th>
								<th scope="col">Delegation</th>
								<th scope="col">Field</th>
								<th scope="col">This run read</th>
								<th scope="col">The second model read</th>
								<th scope="col">Occurrence</th>
							</tr>
						</thead>
						<tbody>
							{#each listing.rows as row (row.id)}
								<tr>
									<td class="when">{isoDate(row.date)}</td>
									<th scope="row">{shortCountry(row.actor)}</th>
									<td class="fields">
										{#each row.contested as entry (entry.field)}
											<span class="field">{entry.label}</span>
										{/each}
									</td>
									<td class="fields">
										{#each row.contested as entry (entry.field)}
											<span class="reading">{entry.published}</span>
										{/each}
									</td>
									<td class="fields">
										{#each row.contested as entry (entry.field)}
											<span class="reading other">{entry.second}</span>
										{/each}
									</td>
									<td class="where">
										<a
											href="{resolve('/reader/[meeting]', { meeting: row.reader.meeting })}?{row
												.reader.query}"
										>
											<code>{row.id}</code>
										</a>
										<a href="{resolve('/concordance')}?{row.concordance.query}">concordance</a>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<p class="disclosure">
					{count(listing.rows.length)} of {count(listing.contested)} contested occurrences are drawn here,
					out of {count(listing.overlap)} the two runs both reached.
					{#if listing.hidden}
						The {count(listing.hidden)} below them are in the CSV, not in the table: fifty passages is
						already an afternoon's reading.
					{/if}
					{#if listing.unquotable}
						{count(listing.unquotable)}
						{listing.unquotable === 1 ? 'further occurrence is' : 'further occurrences are'} contested
						and {listing.unquotable === 1 ? 'has' : 'have'} no line in the concordance for {USAGE_TERM},
						so {listing.unquotable === 1 ? 'it' : 'they'} cannot be read back to a sentence and
						{listing.unquotable === 1 ? 'is' : 'are'} in the CSV alone.
					{/if}
				</p>
			{/if}
		</Figure>
	{/if}

	<Figure
		title="Who rejects the word"
		question="When a delegation says genocide, is it making the claim or refusing it?"
		source="15_usage.py → usage/usage.json"
		note="Width is the share of that delegation's own eligible occurrences, not of the corpus."
		download={{ name: ['unsc', 'usage', 'speaker_position'], table: positionTable }}
	>
		{#snippet reading()}
			<p>
				Each row divides one delegation's eligible occurrences by what it was doing with the word.
				<strong>Only the marked rows are ordered</strong>: those whose interval clears the corpus's
				own 1.7%. The rest follow by count and are not a ranking, because at these denominators one
				rejection and two cannot be told apart.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>A speaker_position is the label a model most easily inverts:</strong> &ldquo;we
				reject the claim that this is genocide&rdquo; and &ldquo;this is genocide&rdquo; differ by
				three words, and nothing here is checked until the gold sample is coded. {count(
					ranking.withheld.length
				)}
				delegations with fewer than {count(ranking.minimum)} occurrences carry no share at all.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				This ranking is unavailable until a model run has annotated the migrated corpus. Once a run
				exists, counts and shares will be shown with their intervals, and only rows whose interval
				separates from the corpus baseline will be ordered.
			</p>
		{/snippet}

		<div class="key">
			{#each POSITIONS as speaker_position (speaker_position)}
				<span class="swatch"
					><i style:--band="var(--speaker_position-{slug(speaker_position)})"></i>{positionLabel(
						speaker_position
					)}{#if isInstrumentDependent(speaker_position)}<abbr
							title="Instrument-dependent: the two models split this label from `asserts` differently, and a count of it is partly a count of which model was asked."
							>&nbsp;&dagger;</abbr
						>{/if}</span
				>
			{/each}
		</div>
		<p class="quiet">
			&dagger; <strong>Instrument-dependent.</strong> The two models place
			<em>attributes or reports</em> on 789 occurrences between them and agree on 215 of those; 445
			are <em>attributes</em> to one and <em>asserts</em> to the other. The prompt does not draw the boundary,
			so this band's width is partly a property of which model was asked.
		</p>

		{#if ranking.rows.length === 0}
			<p class="refusal">
				No delegation reached {count(ranking.minimum)} eligible occurrences, so no share here could be
				drawn honestly.
			</p>
		{:else}
			<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
			<div class="scroll" role="region" aria-label="Position profile table" tabindex="0">
				<table class="positions">
					<caption class="sr-only">
						Delegations by the share of their eligible occurrences that reject or deny the
						characterisation, those separated from the corpus rate first
					</caption>
					<thead>
						<tr>
							<th scope="col">Delegation</th>
							<th scope="col" class="num">Eligible</th>
							<th scope="col" class="num">Rejects</th>
							<th scope="col" class="num">Share</th>
							<th scope="col" class="num">95% interval</th>
						</tr>
					</thead>
					<tbody>
						{#each ranking.rows as row (row.actor)}
							<tr
								class="band"
								class:withheld={!row.separated}
								style:--bands="linear-gradient(to right, {bands(row.segments)})"
							>
								<th scope="row" title={describePositions(row.positions, row.total)}>
									{shortCountry(row.actor)}{#if row.separated}<abbr
											title="The lower bound of this share clears the corpus rate of 1.7%."
											>&nbsp;&#9679;</abbr
										>{/if}
								</th>
								<td class="num">{count(row.eligible)}</td>
								<td class="num">{count(row.rejects)}</td>
								<td class="num">{percent(row.shareRejects)}</td>
								<td class="num">{row.intervalText}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

		<details class="data-table">
			<summary
				><Icon icon={ChevronRight} />Every speaker_position count, withheld delegations included</summary
			>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
			<div class="scroll" role="region" aria-label="Every speaker_position count" tabindex="0">
				<table>
					<thead>
						<tr>
							<th scope="col">Delegation</th>
							<th scope="col" class="num">Eligible</th>
							{#each POSITIONS as speaker_position (speaker_position)}
								<th scope="col" class="num">{positionLabel(speaker_position)}</th>
							{/each}
							<th scope="col" class="num">Rejects</th>
						</tr>
					</thead>
					<tbody>
						{#each ranking.rows as row (row.actor)}
							<tr>
								<th scope="row">{shortCountry(row.actor)}</th>
								<td class="num">{count(row.eligible)}</td>
								{#each POSITIONS as speaker_position (speaker_position)}
									<td class="num">{count(row.positions[speaker_position] ?? 0)}</td>
								{/each}
								<td class="num">{percent(row.shareRejects)}</td>
							</tr>
						{/each}
						{#each ranking.withheld as row (row.actor)}
							<tr class="withheld">
								<th scope="row">{shortCountry(row.actor)}</th>
								<td class="num">{count(row.eligible)}</td>
								{#each POSITIONS as speaker_position (speaker_position)}
									<td class="num">{count(row.positions[speaker_position] ?? 0)}</td>
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
		{#if !gold.hasAgreement && !gold.hasModelScores && !gold.hasComparisonScores}
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
								<th scope="col" class="num">PABAK</th>
							</tr>
						</thead>
						<tbody>
							{#each artefact.gold.human_agreement as row (row.field)}
								<tr>
									<th scope="row">{termLabel(row.field)}</th>
									<td class="num">{count(row.n)}</td>
									<td class="num">{row.observed === null ? '—' : percent(row.observed)}</td>
									<td class="num">{row.kappa === null ? '—' : decimal(row.kappa)}</td>
									<td class="num">{row.pabak === null ? '—' : decimal(row.pabak)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="quiet">
					A dash in the kappa column means the statistic was not computed or was withheld. It is
					withheld where one coder's labels fall outside their commonest by under one per cent:
					chance agreement is then almost total, and dividing what is left produces a number near
					zero about a field the two agreed on throughout. <strong>PABAK</strong> is the same correction
					against a uniform chance over the codebook's own categories, and is what to read there.
				</p>
			{/if}
			{#if gold.hasModelScores}
				<h3>The published run against the human labels</h3>
				<p class="quiet">
					<code>{artefact.model.id}</code>, whose labels every count on this page is made of.
					<strong>Left out</strong> is the share of double-coded occurrences this field's score was
					not computed over, because the two coders differed and nobody has adjudicated: the
					reference is what they agreed on, which is right and is also the easy subset, and it is a
					different subset for each field. Read <strong>weighted F1</strong> for the referent, whose distribution
					is long-tailed; macro F1 is over the classes with twenty reference occurrences or more, and
					is a dash where none has.
				</p>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
				<div
					class="scroll"
					role="region"
					aria-label="The published run against the human labels"
					tabindex="0"
				>
					<table>
						<thead>
							<tr>
								<th scope="col">Field</th>
								<th scope="col" class="num">Rows</th>
								<th scope="col" class="num">Agreed</th>
								<th scope="col" class="num">Macro F1</th>
								<th scope="col" class="num">Weighted F1</th>
								<th scope="col" class="num">Left out</th>
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
									<td class="num">{row.weighted_f1 === null ? '—' : decimal(row.weighted_f1)}</td>
									<td class="num"
										>{row.excluded_share === null ? '—' : percent(row.excluded_share)}</td
									>
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
									<th scope="col" class="num">Placed</th>
									<th scope="col" class="num">Both</th>
									<th scope="col" class="num">Precision</th>
									<th scope="col" class="num">Recall</th>
									<th scope="col" class="num">F1</th>
								</tr>
							</thead>
							<tbody>
								{#each artefact.gold.model_vs_human as field (field.field)}
									{#each field.classes as row (row.label)}
										<tr class:withheld={!row.measurable}>
											<th scope="row">{termLabel(field.field)}</th>
											<td>{positionLabel(row.label)}</td>
											<td class="num">{count(row.support)}</td>
											<td class="num">{count(row.predicted)}</td>
											<td class="num">{count(row.correct)}</td>
											<td class="num">{row.precision === null ? '—' : decimal(row.precision)}</td>
											<td class="num">{row.recall === null ? '—' : decimal(row.recall)}</td>
											<td class="num">{row.f1 === null ? '—' : decimal(row.f1)}</td>
										</tr>
									{/each}
								{/each}
							</tbody>
						</table>
					</div>
				</details>
			{/if}
			{#if gold.hasComparisonScores}
				<h3>The second model against the same human labels</h3>
				<p class="quiet">
					<code>{comparison.model}</code>, scored against the same coded sample so the two runs can
					be read against one reference. Its labels are not merged into anything on this page; this
					table is the only place they are measured rather than merely compared.
				</p>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
				<div
					class="scroll"
					role="region"
					aria-label="The second model against the same human labels"
					tabindex="0"
				>
					<table>
						<thead>
							<tr>
								<th scope="col">Field</th>
								<th scope="col" class="num">Rows</th>
								<th scope="col" class="num">Agreed</th>
								<th scope="col" class="num">Macro F1</th>
								<th scope="col" class="num">Weighted F1</th>
								<th scope="col" class="num">Left out</th>
								<th scope="col" class="num">Abstained</th>
							</tr>
						</thead>
						<tbody>
							{#each artefact.gold.model_vs_human_comparison as row (row.field)}
								<tr>
									<th scope="row">{termLabel(row.field)}</th>
									<td class="num">{count(row.n)}</td>
									<td class="num">{percent(row.accuracy)}</td>
									<td class="num">{row.macro_f1 === null ? '—' : decimal(row.macro_f1)}</td>
									<td class="num">{row.weighted_f1 === null ? '—' : decimal(row.weighted_f1)}</td>
									<td class="num"
										>{row.excluded_share === null ? '—' : percent(row.excluded_share)}</td
									>
									<td class="num">{percent(row.abstention_rate)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
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

	/* ---- the second opinion ------------------------------------------------ */

	/* Inside the standing marking rather than beside it. A second model is one
	   more instrument of the same experiment, and a block of its own — under its
	   own rule, outside the warning — would read as a firmer layer sitting on top
	   of the model's readings rather than as more of them. */
	.second-opinion {
		margin-top: var(--sp-5);
		padding-top: var(--sp-4);
		border-top: var(--hair) solid var(--rule);
	}

	/* A heading in the document's own outline, set at the weight of the block it
	   belongs to: a serif display line here would announce a section the reader
	   has not left the apparatus for. */
	.second-opinion h2 {
		font-family: var(--sans);
		font-size: var(--step-0);
		color: var(--ink);
		margin: 0 0 var(--sp-2);
	}

	.second-opinion .scroll {
		margin-top: var(--sp-3);
	}

	.second-opinion .quiet {
		margin: var(--sp-3) 0 0;
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

	/* The speaker_position is a datum, so it carries a data colour and no control ever
	   does. The colour is a rule under the word rather than the word itself —
	   the same gesture `app.css` gives a marked term of a given register, and
	   the reason is the same one that produced it there: several of these
	   tokens are chosen to be told apart from each other on a chart, not to be
	   read as 12px text on paper, and set as text they fall short of the
	   contrast a label has to clear. Ink carries the reading; the hue carries
	   the category. A filled chip is not used either: it would read as
	   something to press. */
	.speaker_position {
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--ink);
		padding-bottom: 0.15em;
		box-shadow: inset 0 -2px 0 var(--rule-strong);
	}

	.speaker_position[data-speaker_position='asserts'] {
		box-shadow: inset 0 -2px 0 var(--ink);
	}
	.speaker_position[data-speaker_position='reports_without_position'] {
		box-shadow: inset 0 -2px 0 var(--ink-2);
	}
	.speaker_position[data-speaker_position='rejects'] {
		box-shadow: inset 0 -2px 0 var(--ink);
	}
	.speaker_position[data-speaker_position='conditional'] {
		box-shadow: inset 0 -2px 0 var(--ink-3);
	}
	.speaker_position[data-speaker_position='no_position'] {
		box-shadow: inset 0 -2px 0 var(--rule-strong);
	}
	.speaker_position[data-speaker_position='unclear'],
	.speaker_position[data-speaker_position='not_applicable'] {
		box-shadow: inset 0 -2px 0 var(--ink-3);
	}

	.fn {
		color: var(--ink-3);
	}

	/* The experimental marking at the scale of one row: the warning token the
	   whole apparatus block carries, as a rule under the word rather than a
	   filled chip — a chip would read as something to press, and the line already
	   holds three labels that are not. */
	.contested {
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--state-warn);
		padding-bottom: 0.15em;
		box-shadow: inset 0 -2px 0 var(--state-warn);
	}

	/* Set like the model's evidence span below it, which is the other place a row
	   says something about its own labels rather than about the record. */
	.second-reading {
		max-width: var(--measure);
		margin: 0 0 var(--sp-3);
		padding-left: var(--sp-3);
		border-left: 2px solid var(--state-warn);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.second-reading .label {
		display: block;
		margin-bottom: var(--sp-1);
		color: var(--state-warn);
	}

	.second-reading .pair {
		display: block;
	}

	.second-reading .field {
		display: inline-block;
		min-width: 6rem;
		color: var(--ink-3);
	}

	.second-reading strong {
		color: var(--ink);
		font-weight: 600;
	}

	.second-reading .mine {
		color: var(--ink-3);
	}

	/* ---- the contested filter ---------------------------------------------- */

	.filter {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--sp-1) var(--sp-3);
		margin: 0 0 var(--sp-4);
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.filter label {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
		color: var(--ink);
		cursor: pointer;
	}

	.filter .quiet {
		flex-basis: 100%;
		margin: 0;
	}

	/* Present only on a run coded against annotation schema 3; a schema-2 run
	   answers none of these six and the list is empty rather than blank. */
	.schema-fields {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: var(--sp-1) var(--sp-2);
		max-width: var(--measure);
		margin: 0 0 var(--sp-3);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.schema-fields dt {
		color: var(--ink-3);
	}

	.schema-fields dd {
		margin: 0;
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

	/* ---- the chronology of firsts ------------------------------------------ */

	/* Wide enough for its own content and no wider: the identifiers are long, and
	   a table squeezed into the column would set every label three words to a
	   line. The scroll region around it is where that width goes. */
	.chronology {
		width: auto;
		min-width: 100%;
	}

	.chronology th,
	.chronology td {
		padding: var(--sp-1) var(--sp-3) var(--sp-1) 0;
		vertical-align: baseline;
		border-bottom: var(--hair) solid var(--rule);
	}

	/* The same mark as in the quotations, set quietly: a speaker_position shouted once
	   under a blockquote is emphasis, and shouted on every row of a hundred is
	   noise. The rule under the word still carries the category. */
	.chronology .speaker_position {
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 400;
		letter-spacing: 0;
		text-transform: none;
		color: var(--ink-2);
		white-space: nowrap;
	}

	.when {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-2);
		white-space: nowrap;
	}

	/* The same gesture the speaker_position carries: a rule under the word in the colour
	   its curve is drawn in, so the table and the figure name the same thing the
	   same way. Ink carries the reading; the hue carries the category. */
	.milestone {
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
		white-space: nowrap;
		padding-bottom: 0.15em;
		box-shadow: inset 0 -2px 0 var(--rule-strong);
	}

	.milestone[data-milestone='asserts'] {
		box-shadow: inset 0 -2px 0 var(--ink);
	}

	.milestone[data-milestone='rejects'] {
		box-shadow: inset 0 -2px 0 var(--ink);
	}

	.milestone[data-milestone='mention'] {
		box-shadow: inset 0 -2px 0 var(--ink-3);
	}

	/* Inline rather than a flex row: a table cell that becomes a flex container
	   leaves the table's own layout, and the column stops lining up with its
	   heading. */
	.where {
		font-family: var(--sans);
		font-size: var(--step--2);
	}

	.where a + a {
		margin-left: var(--sp-3);
	}

	/* The identifier is a citation and is never broken across lines: a table that
	   wrapped it would set every row four lines tall to save a column the scroll
	   region is there to give it. */
	.where code {
		font-family: var(--mono);
		font-size: var(--step--2);
		white-space: nowrap;
	}

	/* ---- the contested passages -------------------------------------------- */

	/* Wide enough for its own content and no wider, as the chronology is: the
	   identifiers are long and three of the columns hold a stack of labels. */
	.contested-table {
		width: auto;
		min-width: 100%;
	}

	.contested-table th,
	.contested-table td {
		padding: var(--sp-2) var(--sp-3) var(--sp-2) 0;
		vertical-align: baseline;
		border-bottom: var(--hair) solid var(--rule);
	}

	/* One line per contested field, in the same order in all three columns, so
	   the row reads across: the field, what this run read, what the other did.
	   `max-content` rather than a full-width block, so the rule under a second
	   reading is as wide as the words it marks. */
	.contested-table .fields span {
		display: block;
		width: max-content;
		white-space: nowrap;
		font-size: var(--step--2);
		line-height: 1.7;
	}

	.contested-table .field {
		color: var(--ink-3);
	}

	.contested-table .reading {
		color: var(--ink-2);
	}

	/* The same warning token the marking on a quotation carries, so the column a
	   reader has to weigh against the published one is visibly the other one. */
	.contested-table .reading.other {
		color: var(--ink);
		padding-bottom: 0.15em;
		box-shadow: inset 0 -2px 0 var(--state-warn);
	}

	/* ---- the speaker_position profile ------------------------------------------------ */

	/* One hue per speaker_position, tinted toward the page so the numbers stay readable on
	   top of them — the ceiling `Standing.svelte` settled on, for the same
	   reason. Rejection carries ink, the strongest weight available, because it
	   is the band the figure is ordered by. `--blue` appears nowhere. */
	.key,
	.positions {
		--tint: 32%;
		--speaker_position-asserts: color-mix(in oklab, var(--ink) var(--tint), transparent);
		--speaker_position-attributes-or-reports: color-mix(
			in oklab,
			var(--ink-2) var(--tint),
			transparent
		);
		--speaker_position-rejects-or-denies: color-mix(in oklab, var(--ink) var(--tint), transparent);
		--speaker_position-hypothetical-or-conditional: color-mix(
			in oklab,
			var(--ink-3) var(--tint),
			transparent
		);
		--speaker_position-neutral-legal-reference: color-mix(
			in oklab,
			var(--rule-strong) var(--tint),
			transparent
		);
		--speaker_position-unclear: color-mix(
			in oklab,
			var(--ink-3) calc(var(--tint) / 2),
			transparent
		);
		--speaker_position-not-applicable: color-mix(
			in oklab,
			var(--rule-strong) var(--tint),
			transparent
		);
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
	   opaque, so a stripe underneath would draw the same speaker_position in two colours
	   down the column. */
	tbody tr.band {
		background-color: transparent;
		background-image: var(--bands);
	}

	tr.withheld td:last-child {
		color: var(--ink-3);
		font-style: italic;
	}

	/* A row or a cell whose figure is present but must not be ordered or quoted:
	   a share whose interval covers the corpus rate, a per-class rate under its
	   support floor, a kappa withheld for a flat margin. Set back rather than
	   hidden — the counts behind them are facts, and only the rate is not. */
	tbody tr.withheld th[scope='row'],
	tbody tr.withheld td,
	td.num.withheld {
		color: var(--ink-3);
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
