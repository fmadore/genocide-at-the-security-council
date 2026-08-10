<script lang="ts">
	import { count, percent } from '$lib/format';
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
				'Every pattern must match declared examples and pass a literal prefilter before exact regex counting. A stratified 200-row audit sample covers occurrences, speeches, terms and periods. An OCR-tolerant pattern is reported separately; it adds one speech in 106,302.'
		},
		{
			id: '04_series.py',
			does: 'Rates per year and quarter, breakdowns, rate-change inference, event overlay.',
			checks:
				'Speech prevalence uses a binomial model; occurrences use a Poisson model with token exposure. A parametric maximum-search bootstrap preserves the breakpoint search and a Bonferroni correction covers three planned tests. WBS remains visible only as an exploratory diagnostic.'
		},
		{
			id: '05_lexical.py',
			does: 'Collocates, keyness against a matched control, co-occurrence network.',
			checks:
				'Target and control speeches are true pairs within year × agenda × speaker group. Twenty consecutive random seeds quantify matching sensitivity; the unmatched comparison remains a diagnostic. Overlapping context windows are merged and lexical parent–child edges are suppressed.'
		},
		{
			id: '08_kwic.py',
			does: 'Concordance lines with a ±150-character window and the full sentence.',
			checks:
				'Fails rather than writing anything if a term’s line count disagrees with the occurrence count computed in step 03. All 22 terms reproduce exactly.'
		},
		{
			id: '09_export_speeches.py',
			does: 'One JSON per corpus document with speech text and per-term occurrence offsets.',
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
		says how, what is sourced, and what still requires human validation.
	</p>

	<h2>The corpus</h2>
	<p>
		<a href="https://doi.org/10.7910/DVN/KGVSYH">UN Security Council Debates</a> (Schoenfeld,
		Eckhard, Patz, van Meegdenburg &amp; Pires), Harvard Dataverse v6.1, CC0 &mdash; public domain. {count(
			totals.speeches
		)} speeches from {count(totals.meetings)} distinct meeting symbols,
		{count(totals.tokens)} words, 6 January 1992 to 30 December 2023. A fresh clone of the
		<a href={REPO}>repository</a> plus two scripts rebuilds the canonical table from the DOI; nothing
		derived is committed.
	</p>

	<h2>The pipeline</h2>
	<p>
		Numbered, idempotent, each reading the previous step's output. A step that cannot assert its own
		output is correct exits non-zero rather than leaving a plausible-looking artefact behind.
	</p>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
	<div class="table-scroll" role="region" aria-label="Pipeline steps table" tabindex="0">
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
	</div>

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
		The inferential layer is a single two-rate maximum-likelihood partition. Speech prevalence is
		binomial; occurrences are Poisson with token count as exposure. Its
		{count(data.breaks.inference.trials)} parametric simulations repeat the complete breakpoint search
		under a constant-rate model. The per-test threshold is
		{percent(data.breaks.inference.per_test_alpha)} after
		{data.breaks.inference.correction.toLowerCase()}.
	</p>
	<p class="caveat">
		{data.breaks.inference.caveat} The separate wild-binary-segmentation output is exploratory:
		{data.breaks.caveat}
	</p>

	<h3>Keyness and its control</h3>
	<p>
		Comparing genocide-bearing speeches to the rest of the corpus recovers the vocabulary of the
		occasion rather than of the concept. Each target is therefore paired with a speech from the same {data.keyness.matched_on.join(
			', '
		)} that does not use the term.
		{count(data.keyness.target_speeches)} of {count(data.keyness.eligible_target_speeches)} targets found
		a partner ({percent(data.keyness.coverage)}); the {data.keyness.short_strata.length} strata that could
		not be filled are left short rather than back-filled. Target and control corpora therefore contain
		the same {count(data.keyness.control_speeches)} paired speeches. The displayed sensitivity interval
		repeats sampling across {data.keyness.stability.repetitions} consecutive seeds.
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

	<h2>Limits and open validation</h2>
	<ul class="open">
		<li>
			<strong>The reference dates are contextual, not causal variables.</strong> Every date now links
			to the primary institutional record used to verify it, but temporal proximity does not show that
			an event caused a change in Council language.
		</li>
		<li>
			<strong>The precision of the lexicon has not been hand-audited.</strong> A deterministic
			sample of 200 rows &mdash; stratified across occurrence-level and speech-level sampling and
			term &times; period anchors &mdash; is generated and waiting, and
			<strong>0 of the 200 currently carry a human verdict</strong>. Until they do there is no
			measured false-positive rate for any count on this site, and none may be inferred: an
			automatic review recorded as a human one would be the error the audit exists to avoid. Any
			change to a lexicon pattern voids the verdicts for that term and restarts the sample.
		</li>
		<li>
			<strong>At least two speeches in five are translations.</strong> A non-English delivery language
			is explicitly recoverable for 40.2% of speeches. Missing in-person markers are classified as inferred
			English under the document convention; 5,072 VTC speeches remain unknown because that format does
			not carry the marker. Nothing here measures what was said in the room, only what the English verbatim
			record says was said.
		</li>
		<li>
			<strong>Speaker attribution is weaker for 4.9% of speeches</strong> that open with no form of address
			and are read as continuations.
		</li>
	</ul>

	<h2>What is not on this site</h2>
	<p>
		Three further steps exist in the repository and feed nothing here. Step 06 encodes every speech
		as a vector, step 07 compares a count-based topic model against an embedding-based one, and step
		10 builds a lemma layer so that <code>crime</code> and <code>crimes</code> stop occupying two rows
		of one table. They need a GPU or dependencies the locked environment cannot carry, so they run on
		a university cluster in a separate environment, and the payload this site loads is built without them.
	</p>
	<p>
		They are deliberately not adopted rather than merely unfinished. A topic model waits on a
		research question that collocates and agenda labels cannot answer, and on an interpretability
		check a person has to perform; the lemma layer would move published collocate and keyness
		figures, so it waits on the audit above. Both are documented in
		<a href="{REPO}/blob/main/docs/PLAN.md">the roadmap</a> with the gates they must pass. Nothing on
		this page or in the charts is derived from them.
	</p>

	<h2>Reproducing this</h2>
	<p>
		The <a href={REPO}>repository</a> holds the pipeline, the analysis scripts and this application.
		<code>ruff</code>, locked Python dependencies, and more than 400 unit tests run on every push.
		The tests include the hand-edited files in
		<code>config/</code>, so a bad country alias or a mistyped Council term fails in continuous
		integration rather than halfway through someone's run. The site itself is rebuilt from the
		Dataverse DOI by a workflow rather than uploaded from a workstation, so what you are reading was
		produced by the pipeline in this repository and not by a copy of it that once existed on
		somebody's laptop.
	</p>
	<p>
		<strong>Licences.</strong> The corpus is CC0, released by its depositors. The code is
		<a href="{REPO}/blob/main/LICENSE">MIT</a>. The tables, figures and generated notes this project
		produces &mdash; including everything drawn on this site &mdash; are
		<a href="{REPO}/blob/main/LICENSE-DATA.md">CC BY 4.0</a>, because the selection, arrangement and
		computation are this project's contribution rather than the United Nations'. Speech text quoted
		from the record stays CC0 in whatever form it reaches you. Cite with
		<a href="{REPO}/blob/main/CITATION.cff">CITATION.cff</a>, and cite the corpus as well.
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

	.table-scroll {
		max-width: 100%;
		overflow-x: auto;
	}

	.table-scroll:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
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
		border-left: 1px solid var(--rule);
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
