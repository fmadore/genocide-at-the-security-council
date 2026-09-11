<script lang="ts">
	import { resolve } from '$app/paths';
	import { count, matchedOn, measureLabel, percent } from '$lib/format';
	import PageMeta from '$lib/PageMeta.svelte';
	import { PAGE_METADATA } from '$lib/seo';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const REPO = 'https://github.com/fmadore/genocide-at-the-security-council';

	const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);
	const totals = $derived({
		speeches: sum(data.series.corpus.speeches),
		words: sum(data.series.corpus.words),
		meetings: sum(data.series.corpus.meetings)
	});

	/**
	 * The one published measure that is not a word, and the size of what it takes out.
	 *
	 * The explanation lived in `config/lexicon.yml`'s `derived` block, which is
	 * the right place for the rule and no place at all for a reader: the site
	 * showed a subtraction and never said what was subtracted. The arithmetic is
	 * read off the annual series here rather than written down, so a re-cut
	 * corpus moves the figures, and null where an artefact carries no such
	 * measure — an archived payload keys the raw term and nothing derived.
	 */
	const subtraction = $derived.by(() => {
		const [name, measure] =
			Object.entries(data.series.terms).find(([, term]) => term.derived_from) ?? [];
		const raw = measure?.derived_from ? data.series.terms[measure.derived_from] : undefined;
		if (!name || !measure || !raw || !measure.occurrences || !raw.occurrences) return null;
		return {
			name,
			from: measure.derived_from!,
			minus: measure.derived_minus ?? [],
			occurrences: sum(raw.occurrences),
			removed: sum(raw.occurrences) - sum(measure.occurrences),
			speeches: sum(raw.speeches) - sum(measure.speeches)
		};
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
			does: 'Combines the published speech and meeting tables.',
			checks: 'Checks identifiers, dates, row totals and links between the two tables.',
			artefact: 'speeches.parquet',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '02_normalise.py',
			does: 'Prepares speech text and records speaker affiliations and Council membership.',
			checks: 'Retains the source categories; unknown delivery language remains unknown.',
			artefact: 'speeches_normalised',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '03_lexicon.py',
			does: 'Finds the words and phrases on the search list in speech bodies.',
			checks:
				'Tests patterns against examples. The separate sample for checking matches by hand is still awaiting review.',
			artefact: 'speeches_flagged',
			state: 'open',
			says: 'Human review pending'
		},
		{
			id: '04_series.py',
			does: 'Calculates counts and rates over time, monthly patterns and possible changes in rates.',
			checks:
				'Checks totals and denominators; compares constant-rate and split-rate models. Historical reference dates are supplied separately.',
			artefact: 'series/*.json',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '05_lexical.py',
			does: 'Compares nearby words, vocabulary in matched speeches and terms found in the same speech.',
			checks:
				'Merges overlapping word windows. Applies frequency and G² thresholds, records spread across speeches and repeats random matching.',
			artefact: 'lexical/*.json',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '06_embed.py',
			does: 'Uses a language model to represent each speech numerically for similarity comparisons.',
			checks:
				'Records the model revision and checks that embeddings correspond to the speech texts. Step 21 uses these embeddings for the semantic map.',
			artefact: 'embeddings',
			state: 'experimental',
			says: 'Model-based'
		},
		{
			id: '07_topics.py',
			does: 'Compares methods for grouping speeches by theme.',
			checks:
				'Topic groups are not presented in this dashboard. Their interpretation requires separate assessment.',
			artefact: 'topics/*.json',
			state: 'unadopted',
			says: 'Not displayed'
		},
		{
			id: '08_kwic.py',
			does: 'Builds passages with the matched term, surrounding text and full sentence.',
			checks: 'Checks that passage totals reproduce the occurrence counts.',
			artefact: 'kwic/*.json',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '09_export_speeches.py',
			does: 'Prepares full meeting records and the three reading sets.',
			checks:
				'Checks speech totals and the positions of highlighted matches against the source tables.',
			artefact: 'speeches/*.json; scopes.json',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '10_lemmatise.py',
			does: 'Groups word forms, such as crime and crimes, under a common form.',
			checks:
				'The displayed lexical tables use separate word forms; this optional analysis is not used in those tables.',
			artefact: 'lemmas.parquet',
			state: 'unadopted',
			says: 'Not displayed'
		},
		{
			id: '11_countries.py',
			does: 'Calculates speaker counts, rates and membership breakdowns.',
			checks:
				'Rates use each affiliation’s own speech totals; rates below the declared minimum are withheld. Map positions identify affiliations.',
			artefact: 'countries/countries.json',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '12_speaker_keyness.py',
			does: 'Compares a delegation’s vocabulary with that of other speakers.',
			checks:
				'Matches on year, agenda and speaker group; reports coverage and variation across repeated draws of comparison speeches.',
			artefact: 'countries/speaker_keyness.json',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '13_gold_sample.py',
			does: 'Selects passages for independent coding by two human readers.',
			checks:
				'Stores the sample, each coder’s decisions and any later resolution of disagreements separately. The Usage page reports coding progress.',
			artefact: 'annotations/genocide/annotations.csv',
			state: 'open',
			says: 'Human review pending'
		},
		{
			id: '14_llm_annotate.py',
			does: 'Asks a language model which case a mention refers to and what position the speaker expresses.',
			checks:
				'Requires valid categories and a quotation present in the speech. Records the model and instructions. These checks cannot establish that a label is correct.',
			artefact: 'model_annotations/*.csv',
			state: 'experimental',
			says: 'Model-based'
		},
		{
			id: '15_usage.py',
			does: 'Summarises model labels by delegation, case and position.',
			checks:
				'Reports excluded occurrences, withheld shares and available comparisons with other model runs or human coding.',
			artefact: 'usage/*.json',
			state: 'experimental',
			says: 'Model-based'
		},
		{
			id: '17_frames.py',
			does: 'Identifies recurring phrase patterns around genocide using written rules.',
			checks:
				'Assigns the first matching pattern in a fixed order and retains unmatched occurrences as a separate category.',
			artefact: 'frames/frames.json',
			state: 'verified',
			says: 'Automatic checks'
		},
		{
			id: '21_semantic_map.py',
			does: 'Places speech embeddings on a two-dimensional map and lists related speeches.',
			checks:
				'Checks the data against the corpus; measures map distortion and compares approximate similarity search with exact search.',
			artefact: 'semantic/*.json',
			state: 'experimental',
			says: 'Model-based'
		}
	];
</script>

<PageMeta meta={PAGE_METADATA['/methods/']} />

<article class="prose">
	<h1>Methods</h1>
	<p class="standfirst">
		This dashboard studies how the vocabulary of genocide appears in English Security Council
		records. It combines word counts, statistical comparisons and language-model analyses. Use the
		figures to identify patterns, then read the speeches to interpret them.
	</p>

	<h2>The speech collection</h2>
	<p>
		The source is <a href="https://doi.org/10.7910/DVN/CKPTRB">The UNSC Meetings and Speeches</a> by
		Sakamoto and Matsuoka, Harvard Dataverse v5.0. The working collection contains {count(
			totals.speeches
		)} speeches from {count(totals.meetings)} meeting records and {count(totals.words)} words. The source
		covers 17 January 1946 to 30 December 2024. Here, <em>corpus</em> means this collection of texts.
	</p>
	<p>
		The transcripts are in English, including translations. The dataset does not reliably identify
		the language actually spoken. Results therefore concern the English records. Scanning errors,
		missing metadata and the source's division of records into speeches can affect the analysis.
	</p>

	<h2 id="provenance">Where the results come from</h2>
	<p>
		<strong>Computed from the record</strong> identifies counts or calculations based on text and
		metadata. <strong>Model-derived · experimental</strong> identifies results based on a language
		model, including similarity embeddings and classifications of passages.
		<strong>Computed and model-derived</strong> combines the two, for example a concordance filtered by
		a model-assigned case.
	</p>
	<p>
		These labels identify the method, not its accuracy. Each figure names its source files and
		offers available downloads. Navigation labels cover the methods a page can use; a figure's label
		reflects its own sources.
	</p>

	<h2>Reading counts and rates</h2>
	<h3 id="rates">What is being counted?</h3>
	<p>
		An <strong>occurrence</strong> is one match for a search term. A speech repeating the term ten
		times contributes ten occurrences but only one <strong>speech using the term</strong>. The
		<strong>share of speeches</strong>
		divides speeches with a match by all speeches in the relevant year, period or speaker's record.
		<strong>Occurrences per 100,000 words</strong> divides matches by the number of words, then multiplies
		by 100,000.
	</p>
	<p>
		Rates help compare periods or delegations that produced different amounts of speech. They do not
		adjust for differences in agenda, speaking opportunities or the political meaning of a passage.
		Figures state their denominators and any minimum speech or occurrence count required to display
		a rate. A withheld rate is not zero.
	</p>
	<p>
		The reading-set selector identifies speeches containing <em>genocid*</em>, speeches containing
		that term or related atrocity vocabulary, or all speeches in meetings where <em>genocid*</em> appears.
		It affects the figures labelled as reading-set summaries and the reader's membership markers. Other
		charts and concordance results use their own filters.
	</p>

	<h3 id="word-list">Search terms and word families</h3>
	<p>
		The search list is defined in <code>config/lexicon.yml</code>. Its patterns include spelling
		variants: <code>genocid*</code>, for example, captures forms such as <em>genocide</em>,
		<em>genocidal</em>
		and <em>génocidaires</em>. The raw pattern appears in {percent(
			sum(data.series.terms.genocide.speeches) / totals.speeches
		)} of speeches.
	</p>
	<p>
		Terms are grouped into families, called <em>registers</em>, such as legal, preventive or
		commemorative language. These are research choices used to organise and colour the interface.
		They do not classify a speech's purpose, and the term charts show individual terms separately. A
		match alone cannot establish that a speaker alleged, endorsed or denied genocide.
	</p>

	{#if subtraction}
		<h3 id="derived-measure">Why génocidaires is counted separately</h3>
		<p>
			<em>{measureLabel(subtraction.name)}</em> removes <em>génocidaire</em> and
			<em>génocidaires</em>, labels for perpetrators, from the broader
			<code>{subtraction.from}</code>
			pattern. This removes {count(subtraction.removed)} of {count(subtraction.occurrences)} occurrences,
			including {count(subtraction.speeches)} speeches whose only matches were those forms.
		</p>
		<p>
			This subtraction distinguishes word forms. The remaining matches can still include denials,
			quotations and abstract legal discussion; they are not all allegations about an event.
			Concordance links open the raw pattern, including the excluded forms. The original match
			identifiers remain stable for annotations and citations.
		</p>
	{/if}

	<h3 id="change-points">Testing for a change over time</h3>
	<p>
		The change-point test compares one constant rate with two rates separated at a candidate date.
		It searches the allowed dates and reports the best split. Speech shares use a binomial model;
		occurrence counts use a Poisson model with word totals to account for speech volume.
	</p>
	<p>
		The search is repeated {count(data.breaks.inference.trials)} times under a no-change model. {#if data.breaks.inference.null === 'meeting_block_permutation'}Whole
			meetings are reassigned between years, keeping speeches within a meeting together. This
			accounts for shared debate context. The independent-speech result is also shown for
			comparison.{/if} The p-value measures how often the no-change procedure produces a contrast at least
		as strong as the observed one. It is not the probability that a historical explanation is true.
	</p>
	<p>
		A split is accepted below {percent(data.breaks.inference.per_test_alpha)}. This threshold
		accounts for multiple tests ({data.breaks.inference.correction}). Each side must span at least {data
			.breaks.parameters.min_size} periods. An accepted split summarises a statistical difference; an
		unaccepted one means insufficient evidence under this test. Historical reference dates provide context,
		not causal evidence. The second change-point method is exploratory.
	</p>
	<p>
		<strong>95% Wilson intervals</strong> accompany speech shares. They indicate precision under a model
		treating speeches as independent observations; wider intervals usually accompany smaller totals. The
		observed corpus share itself is a count of available records. These intervals do not account for clustered
		meetings, classification errors or missing records, and comparing overlapping intervals is not a formal
		significance test.
	</p>

	<h2 id="lexical-measures">Understanding the vocabulary tables</h2>
	<p>
		A <strong>word window</strong> contains a specified number of words before and after a term. A
		<strong>collocate</strong>
		is a word counted in those windows. Overlapping windows are merged to avoid counting the same surrounding
		text twice. Common function words are removed; word forms such as <em>crime</em> and
		<em>crimes</em> remain separate.
	</p>
	<dl>
		<dt>Log ratio</dt>
		<dd>
			Compares a word's frequency per word of text in two sets. +1 means twice the comparison
			frequency, +2 four times and +3 eight times. Zero means equal rates; negative values mean a
			lower rate. A small adjustment permits calculation when a count is zero.
		</dd>
		<dt>G² (log-likelihood)</dt>
		<dd>
			Tests departure from equal word frequencies in the two sets. Larger values can reflect a
			larger difference, more text or both. The published tables apply a minimum G² before ranking
			words. G² is neither a confidence percentage nor a measure of historical importance.
		</dd>
		<dt>logDice</dt>
		<dd>
			Ranks the association between a term and a nearby word using their joint count relative to
			their individual counts. Higher scores mean a stronger association. It is a different measure
			from log ratio; row order and dot position can therefore differ.
		</dd>
		<dt>Spread (DP)</dt>
		<dd>
			Measures how unevenly a word is distributed across speeches, allowing for speech length.
			Values near zero mean relatively even distribution; values near one mean concentration in a
			small part of the text. Speech and meeting counts help identify results dominated by a few
			debates.
		</dd>
		<dt>nPMI</dt>
		<dd>
			Measures whether two terms occur in the same speech more often than expected from their
			individual frequencies. Zero corresponds to independence; positive values indicate
			association, up to 1. A high score does not require the terms to occur next to each other.
			Rare pairs still need careful interpretation.
		</dd>
	</dl>

	<h3 id="keyness">Choosing comparison speeches</h3>
	<p>
		For the genocide vocabulary comparison, speeches using the term are paired with speeches without
		it that share their {matchedOn(data.keyness.matched_on)}. {count(data.keyness.target_speeches)} of
		{count(data.keyness.eligible_target_speeches)} eligible speeches found a partner ({percent(
			data.keyness.coverage
		)}), giving {count(data.keyness.control_speeches)} comparison speeches. The {data.keyness
			.short_strata.length} groups with insufficient partners remain short.
	</p>
	<p>
		Matching reduces differences in the recorded context but cannot hold every aspect of a debate
		constant. The whole-corpus comparison shows how results change without matching. Random matching
		is repeated {data.keyness.stability.repetitions} times to assess sensitivity to the choice of partners.
		The Actors page applies a separate matched comparison to each delegation's vocabulary across its speeches.
	</p>

	<h3 id="sentences">Passages and sentence boundaries</h3>
	<p>
		The concordance gives each match with surrounding text and a full sentence. Rules account for
		abbreviations such as <code>Mr.</code> and document symbols such as <code>S/PV.3453</code>.
		Across {count(lines)} concordance entries, {count(longSentences)} ({percent(
			longSentences / lines
		)}) have sentences longer than 500 characters. These may be long sentences or missed boundaries
		caused by scanning or sentence-splitting errors. Check the full speech before quoting.
	</p>

	<h2 id="embeddings">Semantic embeddings and the speech map</h2>
	<p>
		A language model converts each speech into a list of numbers, its <strong>embedding</strong>.
		The numbers represent patterns of wording and meaning learned by the model. Comparing these
		lists can retrieve speeches about similar subjects even when their wording differs. Long
		speeches are divided into overlapping sections; their embeddings are combined using weights
		based on section length.
	</p>
	<p>
		<strong>Cosine similarity</strong> compares the direction of two embeddings. Scores closer to 1 indicate
		more similar representations; the score is not a percentage of agreement or shared meaning. The related-speech
		list uses approximate search over the original embeddings and can miss some of the closest speeches.
	</p>
	<p>
		<strong>UMAP</strong> places the embeddings on a flat map while trying to preserve local neighbours.
		Compressing many numerical dimensions into two changes distances. The axes have no substantive units,
		and large gaps or apparent clusters do not establish political blocs. Map filters hide speeches without
		recalculating their positions.
	</p>
	<p>
		The map reports how many neighbours are lost in a diagnostic sample and how often approximate
		search recovers the ten closest speeches found by exact search. Publication requires at least
		80% recovery in the search check. These checks evaluate computation and distortion; interpreting
		similarity still requires reading the texts. The <a href={resolve('/semantic')}>Semantic map</a> reports
		whether the data are available.
	</p>

	<h2 id="model-labels">Model classifications and human review</h2>
	<p>
		The <a href={resolve('/usage')}>Usage page</a> asks a language model to classify individual
		mentions. A <strong>referent</strong> is the event, situation or general concept a mention
		concerns. <strong>Speaker position</strong> records whether the passage asserts, rejects, conditionally
		applies or reports a genocide claim, among other categories. These labels describe the model's interpretation
		of a passage; they do not establish whether an event was genocide.
	</p>
	<p>
		A valid model response must use the permitted categories and quote text found in the speech.
		Those checks cannot show that the interpretation is correct. The human reference sample is coded
		independently by two readers; unresolved disagreements and later adjudications are kept
		explicit. The Usage page reports coverage and review progress for the published run.
	</p>
	<p>
		<strong>Observed agreement</strong> is the proportion of identical labels.
		<strong>Kappa</strong>
		adjusts for agreement expected from each reader's label frequencies; <strong>PABAK</strong> here uses
		an alternative equal-category chance baseline. They can differ sharply when one label dominates. Agreement
		between models measures consistency, not accuracy.
	</p>
	<p>
		<strong>Precision</strong> asks how many model assignments to a category match the human
		reference; <strong>recall</strong> asks how many reference examples the model finds.
		<strong>F1</strong> combines the two, with 1 indicating a perfect match. Weighted F1 gives frequent
		categories more weight; macro F1 averages the eligible categories equally. Read these scores with
		sample sizes, exclusions and abstentions.
	</p>

	<h2>Analysis steps and checks</h2>
	<p>
		The following scripts produce the displayed analyses or related optional outputs. <strong
			>Automatic checks</strong
		> cover data consistency and implementation; they do not mean a researcher has verified every passage.
		Model-based results require separate interpretation and validation.
	</p>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
	<div class="table-scroll" role="region" aria-label="Analysis steps" tabindex="0">
		<table class="ledger">
			<thead><tr><th>Step</th><th>Purpose and checks</th><th>Output</th><th>Status</th></tr></thead
			><tbody
				>{#each steps as step (step.id)}<tr
						><td class="step"><code>{step.id}</code></td><td
							>{step.does}<span class="checks">{step.checks}</span></td
						><td><code class="artefact">{step.artefact}</code></td><td
							class="state"
							data-state={step.state}>{step.says}</td
						></tr
					>{/each}</tbody
			>
		</table>
	</div>

	<h2>Reproducing and citing the analysis</h2>
	<p>
		The <a href={REPO}>repository</a> contains scripts, configuration, tests and instructions.
		Analytical files record their inputs and settings. An <code>analysis_hash</code> is a content identifier:
		it changes with the analytical data or declared settings, but not solely with the generation time.
		Retain that identifier and the filters when saving or citing a result.
	</p>
	<p>
		The source corpus is released under CC0. The code uses the <a href="{REPO}/blob/main/LICENSE"
			>MIT licence</a
		>; project-generated tables and figures use
		<a href="{REPO}/blob/main/LICENSE-DATA.md">CC BY 4.0</a>. Cite the project using
		<a href="{REPO}/blob/main/CITATION.cff">CITATION.cff</a> and cite the source corpus as well.
	</p>
	<p class="quiet">
		Word-list version {data.series.meta.lexicon_version}. Data generated {data.series.meta
			.generated}.
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

	/* The one thing on this page that is genuinely open, marked as such. */
</style>
