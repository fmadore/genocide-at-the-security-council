<script lang="ts">
	import { count, percent } from '$lib/format';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const REPO = 'https://github.com/fmadore/un-security-council-debates';

	const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);
	const totals = $derived({
		speeches: sum(data.series.corpus.speeches),
		tokens: sum(data.series.corpus.tokens),
		meetings: sum(data.series.corpus.meetings)
	});

	const lines = $derived(data.kwic.terms.reduce((a, t) => a + t.count, 0));
	const longSentences = $derived(data.kwic.terms.reduce((a, t) => a + t.long_sentences, 0));

	const steps = [
		{
			id: '01_build_parquet.py',
			does: 'Joins the three raw files into one table and validates it.',
			checks:
				'Row count, token sum, join completeness and date parsing are asserted against the published codebook. Two undocumented defects in the distribution — a UTF-8/cp1252 encoding trap and 36 rows split by a literal newline — are repaired here.'
		},
		{
			id: '02_normalise.py',
			does: 'Canonicalises speaker names, resolves Council membership by year, locates the form of address, recovers delivery language.',
			checks:
				'Refuses to run on a speaker missing from the crosswalk, or on a Council year that does not hold exactly five permanent and ten elected seats.'
		},
		{
			id: '03_lexicon.py',
			does: 'Counts every lexicon term in every speech body.',
			checks:
				'All fourteen figures published in the corpus documentation are reproduced exactly. An OCR-tolerant pattern is measured and reported separately rather than folded in — it adds one speech in 106,302.'
		},
		{
			id: '04_series.py',
			does: 'Rates per year and quarter, breakdowns, change points, event overlay.',
			checks:
				'Change points are permutation-tested; the raw and normalised series are both reported so the difference between them is visible rather than chosen.'
		},
		{
			id: '05_lexical.py',
			does: 'Collocates, keyness against a matched control, co-occurrence network.',
			checks:
				'The unmatched comparison ships alongside the matched one, so the effect of matching can be checked instead of assumed.'
		},
		{
			id: '08_kwic.py',
			does: 'Concordance lines with a ±150-character window and the full sentence.',
			checks:
				'Fails rather than writing anything if a term’s line count disagrees with the occurrence count computed in step 03. All 22 terms reproduce exactly.'
		},
		{
			id: '09_export_speeches.py',
			does: 'One JSON per meeting with full text and per-term occurrence offsets.',
			checks:
				'Speech count and offset count are both asserted against the parquet before anything is written.'
		}
	];
</script>

<svelte:head>
	<title>Methods — Genocide at the Security Council</title>
</svelte:head>

<article class="prose">
	<h1>Methods</h1>
	<p class="standfirst">
		Every number on this site is produced by a versioned script from a single parquet file, and
		every script writes a findings note saying what it found rather than only what it did. This page
		says how, and what is still unverified.
	</p>

	<h2>The corpus</h2>
	<p>
		<a href="https://doi.org/10.7910/DVN/KGVSYH">UN Security Council Debates</a> (Schoenfeld,
		Eckhard, Patz, van Meegdenburg &amp; Pires), Harvard Dataverse v6.1, CC0 &mdash; public domain. {count(
			totals.speeches
		)} speeches from {count(totals.meetings)} meetings,
		{count(totals.tokens)} words, 6 January 1992 to 30 December 2023. A fresh clone of the
		<a href={REPO}>repository</a> plus two scripts rebuilds the canonical table from the DOI; nothing
		derived is committed.
	</p>

	<h2>The pipeline</h2>
	<p>
		Numbered, idempotent, each reading the previous step's output. A step that cannot assert its own
		output is correct exits non-zero rather than leaving a plausible-looking artefact behind.
	</p>
	<table>
		<thead>
			<tr><th>Step</th><th>What it does</th><th>What it checks</th></tr>
		</thead>
		<tbody>
			{#each steps as step (step.id)}
				<tr>
					<td><code>{step.id}</code></td>
					<td>{step.does}</td>
					<td class="quiet">{step.checks}</td>
				</tr>
			{/each}
		</tbody>
	</table>

	<h2>Choices that shape what you see</h2>

	<h3>Rates, not counts</h3>
	<p>
		The corpus grows more than sevenfold across the period. Any raw series is therefore mostly a
		picture of the Council's growing verbosity, which is why every series here ships with a rate as
		its default view and the raw count as an option rather than the reverse.
	</p>

	<h3>The lexicon is a hypothesis</h3>
	<p>
		<code>genocid*</code> matches
		{percent(sum(data.series.terms.genocide.speeches) / totals.speeches)} of speeches. What counts as
		<em>discussing genocide</em>
		is a harder question, and the lexicon's registers — legal, preventive, commemorative, contentious,
		accountability — are a proposal about how the vocabulary groups, recorded in
		<code>config/lexicon.yml</code> and open to disagreement. They are not findings.
	</p>

	<h3>Change points</h3>
	<p>
		{data.breaks.method}. Minimum segment {data.breaks.parameters.min_size} periods,
		{count(data.breaks.parameters.trials)} permutations per accepted split, α =
		{data.breaks.parameters.alpha}, seed {data.breaks.parameters.seed}.
	</p>
	<p class="caveat">{data.breaks.caveat}</p>

	<h3>Keyness and its control</h3>
	<p>
		Comparing genocide-bearing speeches to the rest of the corpus recovers the vocabulary of the
		occasion rather than of the concept. Each target is therefore paired with a speech from the same {data.keyness.matched_on.join(
			', '
		)} that does not use the term.
		{count(data.keyness.control_speeches)} of {count(data.keyness.target_speeches)} targets found a partner
		({percent(data.keyness.coverage)}); the {data.keyness.short_strata.length} strata that could not be
		filled are debates in which nearly everyone used the word, and are left short rather than back-filled.
	</p>

	<h3>Sentence segmentation</h3>
	<p>
		The sentence is the unit offered for quotation, so it is segmented by explicit rules tuned to
		this genre — <code>Mr.</code>, <code>para.</code>, <code>No.</code>, <code>U.S.</code>,
		<code>S/PV.3453</code>, <code>resolution 955 (1994).</code>, and initials in a name — rather
		than by a general-purpose model. Across {count(lines)} concordance lines,
		{count(longSentences)} ({percent(longSentences / lines)}) exceed 500 characters and are likely
		either OCR-damaged run-ons or segmentation failures. They are kept rather than truncated, and
		counted here.
	</p>

	<h2>What is not verified</h2>
	<ul class="open">
		<li>
			<strong>The reference dates on the chronology chart are drafted, not sourced.</strong> They carry
			a UN document symbol where one exists, but no line has been confirmed against a primary record.
			A chart annotation carries the authority of the chart, so this is the highest-priority open item.
		</li>
		<li>
			<strong>The precision of the lexicon has not been hand-audited.</strong> A random sample of
			100 occurrences is drawn and awaits a human verdict; until then there is no measured
			false-positive rate for <code>genocid*</code>.
		</li>
		<li>
			<strong>Roughly two speeches in five are translations.</strong> Delivery language is
			recoverable for 40.2% of the corpus from the <code>(spoke in …)</code> markers; the rest were delivered
			in English, which the Secretariat does not mark. Nothing here measures what was said in the room,
			only what the English verbatim record says was said.
		</li>
		<li>
			<strong>Speaker attribution is weaker for 4.9% of speeches</strong> that open with no form of address
			and are read as continuations.
		</li>
	</ul>

	<h2>Reproducing this</h2>
	<p>
		The <a href={REPO}>repository</a> holds the pipeline, the analysis scripts and this application.
		<code>ruff</code>
		and {188} unit tests run on every push. The tests include the hand-edited files in
		<code>config/</code>, so a bad country alias or a mistyped Council term fails in continuous
		integration rather than halfway through someone's run.
	</p>
	<p class="quiet">
		Artefacts on this page were generated by lexicon version
		{data.series.meta.lexicon_version}, {data.series.meta.generated}.
	</p>
</article>

<style>
	.prose {
		max-width: 44rem;
	}

	.standfirst {
		font-size: 1.08rem;
		color: var(--ink-soft);
		margin-bottom: 2rem;
	}

	h2 {
		margin-top: 2.4rem;
	}

	h3 {
		margin-top: 1.6rem;
	}

	table {
		margin: 1rem 0 1.5rem;
		font-size: 0.85rem;
	}

	td.quiet,
	p.quiet {
		color: var(--ink-faint);
	}

	td code {
		white-space: nowrap;
		font-size: 0.78rem;
	}

	.caveat {
		border-left: 2px solid var(--rule);
		padding-left: 0.9rem;
		font-size: 0.9rem;
		color: var(--ink-soft);
	}

	.open {
		padding-left: 1.1rem;
	}

	.open li {
		margin-bottom: 0.7rem;
	}
</style>
