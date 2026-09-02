<script lang="ts">
	import { resolve } from '$app/paths';
	import { count, matchedOn, percent } from '$lib/format';
	import PageMeta from '$lib/PageMeta.svelte';
	import { PAGE_METADATA } from '$lib/seo';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const REPO = 'https://github.com/fmadore/genocide-at-the-security-council';

	const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);
	const totals = $derived({
		speeches: sum(data.series.corpus.speeches),
		tokens: sum(data.series.corpus.tokens),
		meetings: sum(data.series.corpus.meetings)
	});

	const lines = $derived(data.kwic.terms.reduce((a, t) => a + t.count, 0));
	const longSentences = $derived(data.kwic.terms.reduce((a, t) => a + t.long_sentences, 0));

	/**
	 * The ledger. Each row names a step, what it establishes, the artefact it
	 * leaves behind, and the state of that artefact — including the three steps
	 * that are built and deliberately not adopted, because a pipeline that omits
	 * its unused halves from its own accounting is not an accounting.
	 *
	 * `state` is the claim a reader should hold this site to. `Verified` means
	 * the step asserts its own output and the assertions pass in CI; it does not
	 * mean a person has read the result. `Experimental` is weaker than any of
	 * the other three and is its own state for that reason: the step ran and its
	 * output is on the site, but what it produced is a model's reading rather
	 * than a measurement, and no human has yet checked any of it.
	 */
	type State = 'verified' | 'open' | 'unadopted' | 'experimental';

	const steps: {
		id: string;
		does: string;
		checks: string;
		artefact: string;
		state: State;
		says: string;
	}[] = [
		{
			id: '01_build_parquet.py',
			does: 'Joins the three published files into one table and checks it.',
			checks:
				'Row counts, word totals, join completeness and date parsing are all checked against the corpus codebook. Two faults in the published files that the codebook does not mention — a character-encoding trap and 36 rows split in two by a stray line break — are repaired here.',
			artefact: 'speeches.parquet',
			state: 'verified',
			says: 'Verified'
		},
		{
			id: '02_normalise.py',
			does: 'Settles on one spelling per speaker, works out who held a Council seat in each year, finds the form of address that opens each speech, and recovers the language it was delivered in.',
			checks:
				'Refuses to run if a speaker is missing from the name table, or if a Council year does not hold exactly five permanent and ten elected seats.',
			artefact: 'speeches_normalised',
			state: 'verified',
			says: 'Verified'
		},
		{
			id: '03_lexicon.py',
			does: 'Counts every word on the list in the body of every speech.',
			checks:
				'Each search pattern has to match the examples declared alongside it, and a fast plain-text filter runs before the exact count. A sample of 200 rows is drawn for hand-checking, spread across occurrences, speeches, individual words and periods. A looser pattern that tolerates scanning errors is reported separately; it adds one speech in 106,302.',
			artefact: 'speeches_flagged',
			state: 'open',
			says: '0 / 200 audited'
		},
		{
			id: '04_series.py',
			does: 'Works out rates by year and by quarter, breaks them down by speaker and by debate, tests for changes in the rate, and attaches the reference dates.',
			checks:
				'The share of speeches is modelled as a series of coin flips; the count of occurrences is modelled against the number of words spoken. The test for a change in rate is repeated in full on data where no change exists, made by moving whole meetings between years so that one debate is one draw, and the threshold is tightened to account for three tests being run. Every share of speeches is published with its Wilson 95% interval. A second, exploratory change-point method is kept visible but is never a result.',
			artefact: 'series/*.json',
			state: 'verified',
			says: 'Verified'
		},
		{
			id: '05_lexical.py',
			does: 'Finds the words that sit near each term, the words that mark out a speech using the term against a comparable speech that does not, and a map of which terms share a speech.',
			checks:
				'Each speech using the term is paired with one from the same year, debate and speaker group. Twenty consecutive random draws show how much the pairing itself moves the answer, and the unpaired comparison is kept only for contrast. Overlapping context windows are merged, and a phrase is never counted as evidence of association with a word already inside it. Significance is a floor: a row must clear G² 10.83 and is then ranked by effect — logDice for collocates, log ratio for keywords — and every row carries the speeches and meetings it appears in and its dispersion (DP).',
			artefact: 'lexical/*.json',
			state: 'verified',
			says: 'Verified'
		},
		{
			id: '06_embed.py',
			does: 'Turns every speech into a list of numbers a machine can compare.',
			checks:
				'Runs on a university cluster rather than in the fixed environment the rest of the pipeline uses, and nothing on this site reads its output.',
			artefact: 'embeddings',
			state: 'unadopted',
			says: 'Built, not adopted'
		},
		{
			id: '07_topics.py',
			does: 'Compares two ways of grouping speeches by theme — evidence towards a decision rather than a result.',
			checks:
				'Waits on a research question that the neighbouring-word and agenda evidence cannot already answer, and on a person judging whether the groups mean anything.',
			artefact: 'topics/*.json',
			state: 'unadopted',
			says: 'Built, not adopted'
		},
		{
			id: '08_kwic.py',
			does: 'Builds the concordance: each occurrence with 150 characters either side, plus the sentence around it.',
			checks:
				"Writes nothing at all if a word's line count disagrees with the count of occurrences from step 03. All 22 words reproduce exactly.",
			artefact: 'kwic/*.json',
			state: 'verified',
			says: 'Verified'
		},
		{
			id: '09_export_speeches.py',
			does: 'One file per meeting record, holding the speech text and the position of every match in it.',
			checks:
				'Both the number of speeches and the number of match positions are checked against the source table before anything is written.',
			artefact: 'speeches/*.json',
			state: 'verified',
			says: 'Verified'
		},
		{
			id: '10_lemmatise.py',
			does: 'Groups inflected forms together, so that crime and crimes stop occupying two rows of one table.',
			checks:
				'Would move figures already published on this site, so it waits on the hand-check of the word list described below.',
			artefact: 'lemmas.parquet',
			state: 'unadopted',
			says: 'Built, not adopted'
		},
		{
			id: '13_gold_sample.py',
			does: 'Draws a fixed sample of occurrences of the core word for two people to code by hand, independently of each other.',
			checks:
				'The draw is reproducible from a seed and spread across speakers, periods and agenda items. Both coders code every sampled occurrence, so a difference between them can be told from an error; neither may edit the other’s row, and a resolved disagreement is a third row rather than a correction. Nothing else on this site reads the sample until it carries verdicts.',
			artefact: 'annotations/genocide/annotations.csv',
			state: 'open',
			says: '0 / 200 coded'
		},
		{
			id: '14_llm_annotate.py',
			does: 'Asks a language model, one occurrence at a time, which genocide is being referred to and what the speaker is doing with the word.',
			checks:
				'Every answer has to name a referent on a controlled list and quote a span the script can then find in the speech itself; an answer that cannot be parsed, or whose quotation is not in the text, is counted and discarded rather than repaired. The run records its model, prompt and prompt hash. It is run by hand, needs a paid API, and its output is kept apart from the human annotations and never merged into them.',
			artefact: 'model_annotations/*.csv',
			state: 'experimental',
			says: 'Model-derived; manual step'
		},
		{
			id: '15_usage.py',
			does: 'Turns those model labels into the actor-by-referent table and the stance profiles behind the Usage view.',
			checks:
				'Its inputs are step 14’s output, so everything it publishes is a model’s reading rather than a measurement, and the view says so above every figure. Shares are withheld below a minimum of eligible occurrences, as elsewhere on this site, and the gold sample’s state travels in the artefact so the page can report honestly that nothing has been checked yet.',
			artefact: 'usage/*.json',
			state: 'experimental',
			says: 'Model-derived; unchecked'
		}
	];
</script>

<PageMeta meta={PAGE_METADATA['/methods/']} />

<article class="prose">
	<h1>Methods</h1>
	<p class="standfirst">
		Every number on this site comes out of a numbered script run against one data file, and each
		script leaves behind a note recording what it found rather than only what it did. This page sets
		out how, where the source material comes from, and what still needs a person to check it.
	</p>

	<h2>The corpus</h2>
	<p>
		<a href="https://doi.org/10.7910/DVN/KGVSYH">UN Security Council Debates</a> (Schoenfeld,
		Eckhard, Patz, van Meegdenburg &amp; Pires), Harvard Dataverse v6.1, released CC0 into the
		public domain. {count(totals.speeches)} speeches from {count(totals.meetings)} meeting records,
		{count(totals.tokens)} words, 6 January 1992 to 30 December 2023. A fresh copy of the
		<a href={REPO}>repository</a> and two scripts rebuild the working table from that DOI; none of the
		files derived from it are stored in the repository.
	</p>

	<h2>How every number was made</h2>
	<p>
		The scripts are numbered, each reads the output of the one before it, and each can be re-run
		from scratch without changing the result. A step that cannot prove its own output is correct
		stops with an error rather than leaving a plausible-looking file behind.
		<strong>Verified</strong> below means the step's own checks pass automatically every time the
		code changes. It does not mean a person has read the result.
		<strong>Experimental</strong> is a weaker claim than any of the others and marks the two steps
		whose output is a language model's reading rather than a measurement: they are published,
		separately and under that marking, on the
		<a href={resolve('/usage')}>Usage</a> page alone, where the human labels are the authority and none
		of them has been coded yet.
	</p>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
	<div class="table-scroll" role="region" aria-label="Pipeline ledger" tabindex="0">
		<table class="ledger">
			<thead>
				<tr>
					<th>Step</th>
					<th>What it establishes</th>
					<th>File it leaves</th>
					<th>State</th>
				</tr>
			</thead>
			<tbody>
				{#each steps as step (step.id)}
					<tr>
						<td class="step"><code>{step.id}</code></td>
						<td>
							{step.does}
							<span class="checks">{step.checks}</span>
						</td>
						<td><code class="artefact">{step.artefact}</code></td>
						<td class="state" data-state={step.state}>{step.says}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<h2>Choices that shape what you see</h2>

	<h3>Rates, not counts</h3>
	<p>
		The Council held more than seven times as many speeches in 2023 as in 1992. A raw count plotted
		over those years is therefore mostly a picture of that growth, which is why every series on this
		site opens on a rate and offers the raw count as an alternative rather than the other way round.
	</p>

	<h3>The word list is a proposal, not a result</h3>
	<p>
		<code>genocid*</code> matches
		{percent(sum(data.series.terms.genocide.speeches) / totals.speeches)} of speeches. What counts as
		<em>discussing genocide</em>
		is a harder question. The six registers the word list is sorted into — the core word, legal, preventive,
		commemorative, contentious and accountability language — are one way of grouping this vocabulary,
		written down in <code>config/lexicon.yml</code> and open to disagreement. They are a starting point
		for the analysis, not something it discovered.
	</p>

	<h3>Change points</h3>
	<p>
		One test is run per series, and it asks a single question: is this line better described by one
		steady rate or by two? The share of speeches is modelled as a series of coin flips; the count of
		occurrences is modelled against the number of words spoken, so a year in which the Council said
		more is expected to contain more of everything. The whole search is then repeated on
		{count(data.breaks.inference.trials)} series in which the rate never changes, which is what turns
		a split into a p-value.
		{#if data.breaks.inference.null === 'meeting_block_permutation'}
			Those series are made by moving whole <strong>meetings</strong> between years rather than flipping
			each speech on its own: speeches are not independent of one another, because whether the word can
			be said at all is fixed by the agenda of the debate they belong to, and one debate can hold two
			hundred occurrences. The p-value under the older independent-speech assumption is published beside
			the block one, so the size of that clustering is on the page.
		{/if}
		A result counts only below
		{percent(data.breaks.inference.per_test_alpha)}, a threshold already tightened to allow for
		several tests being run at once ({data.breaks.inference.correction}).
	</p>
	<p>
		Every <strong>share of speeches</strong> on the site &mdash; a year's, a month's, a speaker's, a category's
		&mdash; is a proportion with a known denominator, and is published with its 95% Wilson interval: the
		band on a line, the whisker beside a row. The interval says how much the share could move with the
		number of speeches it rests on; it does not correct for meetings clustering, which only the change-point
		null does.
	</p>
	<p class="caveat">
		{data.breaks.inference.caveat}
	</p>
	<p class="caveat">
		A second change-point method is also run and kept visible as a diagnostic.
		{data.breaks.caveat}
	</p>

	<h3>What distinguishes a speech, and what it is compared against</h3>
	<p>
		Set a speech that uses <em>genocide</em> against the rest of the corpus and the words that come
		back describe the occasion — the debate, the year, the region — rather than the concept. Each
		such speech is therefore paired with one that does not use the word but shares its
		{matchedOn(data.keyness.matched_on)}.
		{count(data.keyness.target_speeches)} of {count(data.keyness.eligible_target_speeches)} speeches found
		a partner ({percent(data.keyness.coverage)}). Where no partner existed, the
		{data.keyness.short_strata.length} groups concerned are left short rather than filled from elsewhere,
		which would have pulled the comparison towards whichever debates happened to have spare speeches.
		Both sides of the comparison therefore rest on the same {count(data.keyness.control_speeches)} pairs.
		Because the partner is drawn at random, the whole pairing is repeated across {data.keyness
			.stability.repetitions} consecutive draws, and the range those draws produced is reported beside
		each word.
	</p>

	<h3>Where one sentence ends and the next begins</h3>
	<p>
		The sentence is the unit this site offers for quotation, so sentence boundaries are found by
		explicit rules written for this kind of document — <code>Mr.</code>, <code>para.</code>,
		<code>No.</code>, <code>U.S.</code>, <code>S/PV.3453</code>,
		<code>resolution 955 (1994).</code> and the initials in a name &mdash; rather than by a
		general-purpose tool. Across {count(lines)} concordance lines,
		{count(longSentences)} ({percent(longSentences / lines)}) run past 500 characters, which usually
		means either that the scan of the original page ran two sentences together or that the rules
		missed a boundary. They are kept whole rather than trimmed, and counted here.
	</p>

	<h2>Limits and open validation</h2>
	<ul class="open">
		<li>
			<strong>The reference dates are context, not causes.</strong> Each one links to the official record
			used to verify it. A date falling near a change in the chart is not evidence that it produced the
			change.
		</li>
		<li>
			<strong>Nobody has yet checked the word list by hand.</strong> A fixed sample of 200 matches
			&mdash; drawn so that it covers individual occurrences and whole speeches, and spread across
			words and periods &mdash; has been generated and is waiting, and
			<strong>0 of the 200 currently carry a human verdict</strong>. Until they do, no count on this
			site has a measured error rate, and none can be guessed at: recording an automatic review as a
			human one is exactly the mistake the check exists to prevent. Changing any search pattern
			cancels the verdicts for that word and restarts its sample.
		</li>
		<li>
			<strong>At least two speeches in five are translations.</strong> The record states a non-English
			delivery language for 40.2% of speeches. Where an in-person speech carries no such marker, it is
			read as English by the convention of the document series; 5,072 speeches delivered by video link
			stay unknown, because that format carries no marker either way. What is measured throughout is the
			English verbatim record rather than the room it was written from.
		</li>
		<li>
			<strong>Speaker attribution is weaker for 4.9% of speeches.</strong> These are the speeches
			that begin without the usual opening formula &mdash; <code>The President:</code> or
			<code>Mr. Smith (United Kingdom):</code> &mdash; and are read as a continuation of the speech before
			them.
		</li>
	</ul>

	<h2>What is not on this site</h2>
	<p>
		Three further steps exist in the repository and feed nothing here. Step 06 turns every speech
		into a list of numbers a machine can compare, step 07 tries two ways of grouping speeches by
		theme, and step 10 groups inflected forms together so that <code>crime</code> and
		<code>crimes</code> stop occupying two rows of one table. Each needs either a graphics card or software
		the fixed environment cannot carry, so they run separately on a university cluster, and the data this
		site loads is built without them.
	</p>
	<p>
		They are held back on purpose rather than left unfinished. Grouping speeches by theme waits on a
		research question that the neighbouring-word evidence and the agenda labels cannot already
		answer, and on a person judging whether the groups mean anything. Grouping inflected forms would
		move figures already published here, so it waits on the hand-check described above. Both are
		documented in <a href="{REPO}/blob/main/docs/PLAN.md">the roadmap</a>, along with the conditions
		they have to meet first. Nothing on this page or in any chart comes from them.
	</p>

	<h2>Reproducing this</h2>
	<p>
		The <a href={REPO}>repository</a> holds the data pipeline, the analysis scripts and this
		website. A code linter, a fixed set of Python dependencies and focused pipeline and website test
		suites run on every change. Those tests cover the hand-edited files in
		<code>config/</code> too, so a wrong country name or a mistyped Council term fails automatically rather
		than halfway through somebody's run. The site is rebuilt from the Dataverse DOI by an automated workflow
		rather than uploaded from a desktop, so what you are reading was produced by the pipeline in this
		repository and not by a copy of it that once existed on somebody's laptop.
	</p>
	<p>
		Every newly generated analytical file has an <code>analysis_hash</code> computed from its canonical
		content and declared inputs and configuration. The hash stays the same when only the generation time
		or Git working-tree state changes; those readable provenance fields remain alongside it.
	</p>
	<p>
		<strong>Licences.</strong> The corpus is CC0, released by its depositors. The code is
		<a href="{REPO}/blob/main/LICENSE">MIT</a>. The tables, figures and generated notes this project
		produces &mdash; including everything drawn on this site &mdash; are
		<a href="{REPO}/blob/main/LICENSE-DATA.md">CC BY 4.0</a>, because the selection, arrangement and
		calculation are this project's contribution rather than the United Nations'. Speech text quoted
		from the record stays CC0 in whatever form it reaches you. Cite this site using
		<a href="{REPO}/blob/main/CITATION.cff">CITATION.cff</a>, and cite the corpus as well.
	</p>
	<p class="quiet">
		The files behind this page were generated by word-list version
		{data.series.meta.lexicon_version}, {data.series.meta.generated}.
	</p>
</article>

<style>
	/* One prose measure for the whole site, so the text here sets to the same
	   width as the text beside every figure. The ledger is the one thing allowed
	   out of it, because a table is not prose. */
	.prose > * {
		max-width: var(--measure);
	}

	.prose > .table-scroll {
		max-width: 100%;
	}

	.standfirst {
		font-size: var(--step-1);
		line-height: 1.5;
		color: var(--ink-2);
		margin-bottom: var(--sp-6);
	}

	h2 {
		margin-top: var(--sp-7);
	}

	h3 {
		margin-top: var(--sp-5);
	}

	.table-scroll {
		margin: var(--sp-4) 0 var(--sp-6);
		overflow-x: auto;
	}

	/* A ledger, not prose: what each step establishes, the artefact it leaves,
	   and the state a reader should hold that artefact to. */
	.ledger {
		min-width: 46rem;
	}

	.ledger td {
		vertical-align: baseline;
		padding-right: var(--sp-4);
	}

	.step code,
	.artefact {
		white-space: nowrap;
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.checks {
		display: block;
		margin-top: var(--sp-1);
		font-family: var(--sans);
		font-size: var(--step--2);
		line-height: 1.5;
		color: var(--ink-3);
	}

	/* Register colours are data, and the state of an artefact is a datum. */
	.state {
		font-family: var(--sans);
		font-weight: 600;
		font-size: var(--step--1);
		white-space: nowrap;
	}

	.state[data-state='verified'] {
		color: var(--reg-preventive);
	}

	.state[data-state='open'] {
		color: var(--reg-contentious);
	}

	.state[data-state='unadopted'] {
		color: var(--ink-3);
	}

	/* The one state that is not a register colour, because it is not a claim
	   about the analysis: it is a warning about who made the labels. */
	.state[data-state='experimental'] {
		color: var(--state-warn);
	}

	p.quiet {
		color: var(--ink-3);
	}

	.caveat {
		border-left: var(--hair) solid var(--rule-strong);
		padding-left: var(--sp-3);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	/* The one thing on this page that is genuinely open, marked as such. */
	.open {
		list-style: none;
		margin: 0;
		padding: 0 0 0 var(--sp-4);
		border-left: 2px solid var(--reg-contentious);
	}

	.open li {
		margin-bottom: var(--sp-3);
	}

	.open li:last-child {
		margin-bottom: 0;
	}
</style>
