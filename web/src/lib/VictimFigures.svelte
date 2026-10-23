<script lang="ts">
	/**
	 * The three victim figures: who is named, whether a people is named at all,
	 * and which delegations name which peoples.
	 *
	 * Renderers over `#lib/victims`, which decides the rows, the caps and when a
	 * share is withheld. Every figure is marked model-derived by its source, and
	 * every caveat carries `tableStatus`: the labels are a model's and their
	 * grouping an AI draft, and a reader is told how much of it a person has read.
	 */
	import type { BarSeriesOption, EChartsOption } from 'echarts';
	import Chart from '#lib/Chart.svelte';
	import Figure from '#lib/Figure.svelte';
	import VictimGrid from '#lib/VictimGrid.svelte';
	import { provenanceOf } from '#lib/export.js';
	import type { ExportRequest } from '#lib/export.js';
	import { count, percent } from '#lib/format.js';
	import { axisX, axisY, colours, neutral, textStyle, tooltip } from '#lib/theme.js';
	import type { Usage } from '#lib/types.js';
	import {
		ACTOR_COLUMNS,
		DECADE_COLUMNS,
		KIND_LABELS,
		KINDS,
		NAMING_COLUMNS,
		actorExportRows,
		actorPlan,
		decadeExportRows,
		decadePlan,
		namingExportRows,
		namingPlan,
		tableStatus
	} from '#lib/victims.js';

	let {
		data,
		status,
		name
	}: { data: Usage; status: string | null; name: (actor: string) => string } = $props();

	const victims = $derived(data.victims);
	const byDecade = $derived(decadePlan(victims));
	const byActor = $derived(actorPlan(victims, name));
	const naming = $derived(namingPlan(victims, data.minimum_occurrences));
	const checked = $derived(tableStatus(victims));
	const provenance = $derived(provenanceOf(data.meta, 'usage/usage.json'));
	let chart = $state<Chart | null>(null);

	const leader = $derived(victims.groups.find((g) => !g.unspecified));
	const latest = $derived(naming.findLast((d) => d.shares));
	const lowest = $derived(
		naming
			.filter((d) => d.shares)
			.reduce<(typeof naming)[number] | null>(
				(low, d) => (!low || d.shares!.people < low.shares!.people ? d : low),
				null
			)
	);

	const option: EChartsOption = $derived.by(() => {
		const p = $colours;
		// From the most specific to the least: ink for a named people, down to the
		// page's own rule colour for a passage that names no one.
		const fills = {
			people: p.ink,
			unspecified: p.inkFaint,
			ungrouped: neutral(p),
			none: p.ruleSoft
		};
		return {
			textStyle,
			aria: { enabled: true, decal: { show: false } },
			legend: {
				top: 0,
				icon: 'rect',
				itemWidth: 10,
				itemHeight: 10,
				itemGap: 14,
				textStyle: { color: p.inkSoft, fontSize: 12 },
				data: KINDS.map((k) => KIND_LABELS[k])
			},
			grid: {
				left: 2,
				right: 16,
				top: 40,
				bottom: 4,
				outerBoundsMode: 'same',
				outerBoundsContain: 'axisLabel'
			},
			tooltip: {
				...tooltip(p),
				trigger: 'axis',
				axisPointer: { type: 'shadow' },
				formatter: (params: unknown) => {
					const [first] = params as { dataIndex: number }[];
					const d = naming[first?.dataIndex ?? 0];
					if (!d) return '';
					const lines = KINDS.map(
						(k) =>
							`${KIND_LABELS[k]}: ${count(d.counts[k])}${d.shares ? ` (${percent(d.shares[k])})` : ''}`
					);
					const head = `<strong>${d.label}</strong>: ${count(d.eligible)} occurrences${d.shares ? '' : ` (shares withheld below ${count(data.minimum_occurrences)})`}`;
					return [head, ...lines].join('<br>');
				}
			},
			xAxis: { ...axisX(p), type: 'category', data: naming.map((d) => d.label) },
			yAxis: {
				...axisY(p),
				type: 'value',
				min: 0,
				max: 1,
				axisLabel: { ...axisY(p).axisLabel, formatter: (v: number) => `${(v * 100).toFixed(0)}%` }
			},
			series: KINDS.map((k): BarSeriesOption => ({
				name: KIND_LABELS[k],
				type: 'bar',
				stack: 'kinds',
				data: naming.map((d) => (d.shares ? d.shares[k] : null)),
				barMaxWidth: 44,
				itemStyle: { color: fills[k], borderColor: p.paper, borderWidth: 1 }
			}))
		};
	});

	const exportOf = (
		title: string,
		columns: string[],
		rows: ExportRequest['rows'],
		filters: string[],
		scope: string
	): ExportRequest => ({
		title,
		columns,
		rows,
		provenance,
		status,
		filters: [...filters, checked],
		scope
	});
</script>

<Figure
	title="Who is named as the victim"
	question="Which peoples do speakers name as the victims of a genocide, decade by decade?"
	source="15_usage.py → usage/usage.json"
	note="Cells count occurrences whose victim group, as the AI model wrote it, falls in that group."
	download={{
		name: ['unsc', 'usage', 'victims-by-decade'],
		table: () =>
			exportOf(
				'Who is named as the victim',
				DECADE_COLUMNS,
				decadeExportRows(data),
				['rows: the 15 peoples named most often, then the groups that name no particular people'],
				'every group and decade the artefact counts, including the peoples the grid leaves out'
			)
	}}
>
	{#snippet reading()}
		<p>
			Each row is a people the AI model named as the victim, grouped across spellings: "the Jewish
			people" and "Jews" count together. Rows are ranked over the whole period. Groups that name no
			particular people, such as civilians, sit under the rule, in italics.
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>
			An AI model wrote each victim label, and an AI-drafted table grouped them. {checked} Read the quotations
			before relying on a count.
		</p>
	{/snippet}
	{#snippet more()}
		{#if leader}<p>
				Across the whole period the people named most often is {leader.group}: {count(leader.count)}
				occurrences, from {count(leader.actors)} delegations.
			</p>{/if}
		<p>
			A label the table does not yet group is left out of every row; the figure beside this one
			counts those labels. The table, <code>annotations/lexicon/victim_groups.csv</code>, keeps the
			place a speaker named in the original label: "Palestinians in Gaza" are counted as
			Palestinians.
		</p>
	{/snippet}

	{#if byDecade.refusal}
		<p class="refusal">The published run names no victim group to count.</p>
	{:else}
		<VictimGrid
			plan={byDecade}
			rowName="Group"
			unit="occurrences"
			description="Victim groups down the side, decades across; each cell counts the occurrences naming that group."
		/>
		{#if byDecade.hidden.rows}<p class="disclosure">
				{count(byDecade.hidden.rows)} further peoples, named in {count(byDecade.hidden.occurrences)} occurrences,
				are in the download.
			</p>{/if}
	{/if}
</Figure>

<Figure
	title="Naming a people, or not"
	question="How often does a speaker name a particular people as the victim, and how often no one?"
	source="15_usage.py → usage/usage.json"
	note="Each bar divides a decade's eligible occurrences into four kinds; the shares sum to 100%."
	download={{
		name: ['unsc', 'usage', 'naming-a-people'],
		table: () =>
			exportOf(
				'Naming a people, or not',
				NAMING_COLUMNS,
				namingExportRows(data),
				[`shares withheld below ${data.minimum_occurrences} occurrences in a decade`],
				'every decade the artefact counts'
			),
		chart: () => chart?.svg() ?? null
	}}
>
	{#snippet reading()}
		<p>
			Each bar is one decade of uses of the word. Black is the share that names a particular people;
			grey shades name a generic group, carry a label not yet grouped, or name no victim at all, as
			when a speaker cites the Convention or a tribunal.
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>
			An AI model decided whether a passage names a victim, and an AI-drafted table sorted the
			labels. {checked}
		</p>
	{/snippet}
	{#snippet more()}
		{#if lowest?.shares && latest?.shares}<p>
				The share naming a people is lowest in the {lowest.label}, at {percent(
					lowest.shares.people
				)}; in the {latest.label} it is {percent(latest.shares.people)}.
			</p>{/if}
	{/snippet}

	{#if !naming.length}
		<p class="refusal">The published run carries no dated occurrences to divide.</p>
	{:else}
		<Chart
			bind:this={chart}
			{option}
			height="380px"
			description="Stacked bars, one per decade, of the share of occurrences that name a people, a generic group, an ungrouped label or no victim."
		/>
	{/if}
</Figure>

<Figure
	title="Which delegations name which people"
	question="Which delegations name which peoples as the victims of a genocide?"
	source="15_usage.py → usage/usage.json"
	note="Cells count occurrences in which that delegation names that people, as grouped from the AI model's labels."
	download={{
		name: ['unsc', 'usage', 'victims-by-delegation'],
		table: () =>
			exportOf(
				'Which delegations name which people',
				ACTOR_COLUMNS,
				actorExportRows(data),
				[
					'rows: the 20 delegations naming a people most often; columns: the 10 peoples named most often'
				],
				'every group and speaker the artefact counts, including those the grid leaves out'
			)
	}}
>
	{#snippet reading()}
		<p>
			Rows are the delegations that name a particular people most often; columns are the ten peoples
			named most often. Darker amber means more occurrences. Groups that name no particular people
			are left out here.
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>
			An AI model wrote each victim label, and an AI-drafted table grouped them. {checked} A count is
			a naming, not an endorsement of the claim.
		</p>
	{/snippet}

	{#if byActor.refusal}
		<p class="refusal">No delegation names a people the table groups.</p>
	{:else}
		<VictimGrid
			plan={byActor}
			rowName="Delegation"
			unit="occurrences"
			upright
			description="Delegations down the side, peoples across; each cell counts the occurrences in which that delegation names that people."
		/>
		{#if byActor.hidden.rows}<p class="disclosure">
				{count(byActor.hidden.rows)} further delegations, with {count(byActor.hidden.occurrences)} occurrences,
				are in the download.
			</p>{/if}
	{/if}
</Figure>

<style>
	.refusal,
	.disclosure {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}
</style>
