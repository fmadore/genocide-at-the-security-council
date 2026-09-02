# Roadmap and release gates

This roadmap separates work that makes the existing claims trustworthy from optional
analyses that would create new claims. The order is deliberate: a topic model, map or LLM
layer is not a substitute for validating the corpus, lexicon and denominators it consumes.

Status: 11 August 2026.

## Research contract

The project studies how genocide vocabulary appears in the English UN verbatim record. It
does not measure private Council deliberation, what was said before translation, whether an
event caused a change in language, or whether a speech describes conduct that legally
constitutes genocide.

Every public quantitative claim must have:

- a versioned input and configuration;
- an explicit numerator, denominator and unit;
- a machine-readable artifact carrying hashes, package versions and the generating commit;
- a readable table or concordance path behind any chart;
- a stated uncertainty or limitation;
- a test that fails when its data contract changes unexpectedly.

## Where the work runs

Steps 00–05, 08, 09, 11 and 12 run on a laptop. Steps 06 (embeddings), 07 (the topic
comparison) and 10 (the lemma layer) run on the University of Bayreuth GPU cluster;
`docs/CLUSTER.md` is the walkthrough, and nothing in the repository names an account
or a host.

Two environments, deliberately: the release pipeline installs `requirements.lock`
with hashes and nothing else, while the optional steps install `requirements-cluster.txt`
resolved freely. They cannot be shared — `umap-learn` needs `numba`, which does not
support the numpy the lock pins, and pip resolves that by silently downgrading numpy.
Splitting them means an optional step can never move the environment that produces a
published figure. The consequence is intended and visible: a manifest from step 06 or
10 names a different numpy from one written by step 01. Lift the split when numba
catches up.

Reduced-precision GPU arithmetic is not bit-exact across devices. Embedding artifacts
are reproducible against the device and package versions their manifest records, not
by hash — which is a weaker guarantee than the corpus has, and is why nothing in the
release depends on them.

## Phase 0 — Correct and harden the existing pipeline

Status: complete in the current implementation; regenerated artifacts still require the
release checks below.

- Pin Harvard Dataverse v6.1 by default; make “latest” an explicit opt-in.
- Validate checksums, strict UTF-8 decoding, tab counts, repaired record counts, dates,
  joins, entity coordinates and complete Council-year coverage.
- Correct the singular/plural atrocity patterns. Require examples and safe literal
  prefilters for every regex.
- Distinguish explicit non-English delivery languages, inferred in-person English and
  unknown VTC delivery language.
- Write parquet, JSON directories, audit samples and exports atomically.
- Record input/config hashes, package versions, Git commit and generation time.
- Replace raw-value breakpoint claims with denominator-aware binomial and Poisson models;
  retain wild binary segmentation only as an exploratory diagnostic.
- Use true paired target/control samples for keyness and report sensitivity across seeds.
- Merge overlapping collocation windows and suppress lexicon edges implied by nesting.
- Validate web payloads at the fetch boundary and verify every public static route.

Exit gate: full Python, Ruff, Svelte, ESLint, Prettier and production-build checks pass from
a clean environment.

## Phase 1 — Validation freeze and first citable release

Status: in progress.

### 1.1 Human lexicon audit

`scripts/03_lexicon.py` draws a deterministic 200-row sample with two complementary
sampling frames:

- occurrence-level rows estimate the experience of opening a random concordance hit;
- speech-level rows prevent repetitive speeches from dominating the estimate;
- term × period anchors ensure rare terms and all four periods are inspectable.

A human reviewer records `verdict`, `source_checked` and `phenomenon`. Report precision
with its denominator for the core term and for the broader lexicon; do not silently turn an
AI review into a human verdict. Any pattern edit bumps the lexicon version and restarts this
gate.

### 1.2 Source and data checks

- All chronology annotations must link to the primary institutional record. They remain a
  contextual overlay, never an explanatory variable.
- Resolve the single OCR-tolerant `genecide` case against the printed S/PV record.
- Spot-check repaired TSV rows and continuation speeches against source documents as listed
  in `docs/VALIDATION.md`.
- Record the difference between 6,595 corpus documents and 6,582 distinct meeting symbols;
  never label one as the other.

### 1.3 Release metadata

- ~~Choose an explicit licence for repository code and project-authored derived
  artifacts.~~ Settled on 10 August 2026: code MIT (`LICENSE`), derived artifacts CC BY 4.0
  (`LICENSE-DATA.md`). Three layers, not two — the source corpus remains CC0 by its
  depositors, and verbatim speech text extracted from a derived table stays CC0 rather than
  acquiring an attribution requirement it was never under. CC BY covers the selection,
  arrangement and computation this project contributes, which is the part that has an
  author.
- ~~Confirm author names, ORCIDs and contributors in `CITATION.cff`.~~ Confirmed by the
  author on 10 August 2026: sole author, ORCID 0000-0003-0959-2092, University of Bayreuth.
  The corpus depositors stay in the `references` block, which is where they belong: they
  are cited, not credited as contributors here.
- Tag the release only after all generated notes and dashboard prose match the regenerated
  figures.

Exit gate: human audit complete, primary-source links present, licence selected, citation
metadata confirmed, and a clean rebuild reproduces artifact hashes apart from timestamps
and commit metadata.

## Phase 2 — Reproducible publication

Status: implemented; first live deployment still depends on repository Pages settings.

The Pages workflow rebuilds the 491 MB payload from Dataverse v6.1 rather than committing
generated data or relying on one workstation. It installs the hashed Python lock, runs steps
00–09 plus 11, 12 and `export_web.py`, builds every public route and uploads the static
artifact. Since 11 August 2026 it does that only when it has to: §2.1 records the two caches
that let a push touching nothing the payload depends on deploy without rebuilding it.

Operational checks:

- Pages source is set to GitHub Actions;
- direct visits to overview, chronology, language, actors, concordance and methods work
  under the repository base path — `web/scripts/verify-static.mjs` asserts the six of them
  plus the `404.html` the reader falls back to after every build, so a route that stopped
  being prerendered fails the build rather than a reader's visit;
- the reader fallback loads a meeting and preserves concordance highlighting;
- manifest hashes and the visible lexicon version agree;
- a failed data fetch shows a useful retry state, not a blank chart.

### 2.1 The archive is a dependency, and it is not ours

The sentence at the top of `deploy.yml` — "this costs build time, but makes a release
reproducible from the DOI and the repository alone" — is the right principle and was, as
written, also a single point of failure. **On 11 August 2026 the publish workflow failed
twice in a row inside `00_fetch_data.py`**, once on the dataset version lookup and once
part-way through the files, after `meta.tsv` had already arrived intact. Nothing about the
deposit had changed: v6.1 was `RELEASED`, the DOI resolved, and the same URLs answered
from a laptop while CI was failing.

Harvard Dataverse sheds load by returning **404 with an HTML error page** rather than 429
or 503, and the same URL succeeds seconds later. Measured at the time: within one minute
`meta.tsv` gave 303 then 404, and `speaker.tsv` gave 404 then 200 with all 33,027,398
bytes; across eight consecutive version lookups, all eight succeeded but **seven needed a
retry**. The pipeline was not unlucky twice — it was riding on one HTTP round trip per
request, and the odds had turned.

That is fixed: `with_retry` in `00_fetch_data.py` wraps whole operations rather than
`urlopen`, so a connection dropped mid-stream is retried too, and a real "no such
version" — which Dataverse answers as JSON carrying `status: ERROR` — still fails on the
first attempt rather than after two minutes of retries. What is *not* fixed is the shape
of the dependency, and three things would change it. They are listed cheapest first
because the first one is also the largest win.

**The pin is immutable, so most of this work is waste.** v6.1 cannot change, and its MD5s
are recorded in `data/raw/dataset-manifest.json`. Re-downloading 508 MB on every push buys
nothing — and because `deploy.yml` triggers on `web/**`, a CSS change re-fetches half a
gigabyte from Harvard to move a grid column. The failed deploy of 11 August was exactly
that. **Two `actions/cache` steps removed it on 11 August 2026**, with no new trust
assumption:

- `data/raw/` under a key naming the pinned version, which never has to change.
  `00_fetch_data.py` is already cache-aware: it MD5-checks every local file and prints
  `ok` rather than downloading, so a hit costs one API call instead of 508 MB;
- `data/derived/` and `web/static/data/` under the hash of the inputs that determine
  them — which is the set `lib/artifacts.provenance` already claims determines an
  artifact. On a hit, steps 00–12 are skipped and a `web/src/**`-only push deploys with
  no Dataverse contact at all. Roughly 0.9 GB together; `embeddings/` and `lemmas/` are
  cluster-only and never produced by this workflow.

The risk to design against is cache correctness: a key that misses an input ships a
payload that does not match the code. This repository is unusually well placed to catch
that, because every artifact already carries its input hashes and generating commit, so a
mismatch stays detectable after the fact. And eviction is a feature rather than a
problem — the cache must stay an optimisation, never a dependency, with Dataverse and the
retry as the backstop.

**What building it added**, in three corrections to the paragraph above, each of which
would have produced a cache that appeared to work.

*The raw manifest cannot be in the key.* The list above named it, and it is written by
`00_fetch_data.py` into a gitignored directory — so at the moment the key is evaluated it
does not exist, and after a rebuild it would be a key computed from an output. What stands
in for it is the pin itself, which lives in `scripts/lib/paths.py` and is therefore already
inside `hashFiles('scripts/**')`. The version is also read out separately and named in both
keys, so the Actions UI says which deposit a cache belongs to.

*`deploy.yml` is an input.* It names the Python version and the list of steps that run, and
a payload built by a different sequence is a different payload. It is in the derived key,
which means editing this workflow evicts the derived cache — the safe direction, and cheap.

*A `.pyc` would have made the key unrepeatable.* Importing anything under `scripts/` writes
`__pycache__`, a `.pyc` records the mtime of the source it was compiled from, and a fresh
checkout stamps a new mtime every run. `hashFiles('scripts/**')` would then differ between
the restore and the save, so every run would miss while the workflow reported doing
everything right. The job sets `PYTHONDONTWRITEBYTECODE`, which is a correctness
requirement here rather than a preference, and the pin is read with `sed` rather than by
importing `lib.paths`.

One further decision is not a correction but is worth naming, because the obvious
implementation has the opposite behaviour. The caches are **saved by explicit
`actions/cache/save` steps** rather than by letting `actions/cache` write in its post step.
A post step runs during cleanup, so a run that failed part-way through the pipeline would
publish a half-built tree under a key that claims to be the whole payload — a cache that
does not match the code, arrived at from the other direction. The save steps sit after the
pipeline and are reached only when it succeeded. Neither cache carries `restore-keys` for
the same reason: a partial key match is precisely the failure being designed against.

**A mirror would remove the single point of failure for the corpus.** The three pinned
files could be held somewhere the project controls and used only when Dataverse fails. The
source corpus is CC0 by its depositors, so redistribution is permitted, and integrity is
guaranteed by the MD5s *Harvard* published: a mirror cannot silently substitute different
bytes without failing the check `00_fetch_data.py` already makes. `speeches.tar` is 474 MB,
inside GitHub's 2 GB release-asset limit; Zenodo is the better home if the mirror should
itself be archival. The DOI stays the citable source either way — the mirror is a
checksum-verified cache, and must be described as one.

**A tagged release should not depend on either.** When §1's gate closes and a version is
tagged, the derived payload and its manifest should be attached to that release, or
deposited with their own DOI. Only then is a citable release reproducible if both Harvard's
copy and the Actions cache have gone. That belongs with §1.3 rather than in the deploy
workflow, and it is the real answer to depending on an archive nobody here controls.

## Phase 3 — Actor view

Status: the table exists and is now drawn — a ranked view and a locator map, shipped on
10 August 2026. **All four of the things a profile should show now have both their table
and their view**, the last of them on 10 August 2026: rates over time (coarse),
quotations (linked), agenda composition with matched keyness, and membership standing.
That is not the same as saying the profile is built — these are four figures about
speakers on one page rather than one view of one speaker — but nothing in the list below
is now a table with nothing drawn from it.

It landed before the first validated release it was queued behind, and the reordering is
recorded rather than smoothed over. What the release gate protects is the point at which
these figures become citable, and that is a tag: nothing is tagged, the audit's state is
on the methods page, and the view reads `countries.json` and nothing else — so closing
§1.1 can move every rate in it without touching a line of the view.

`scripts/11_countries.py` writes `data/derived/countries/countries.json`: per canonical
`country_org` and per period, the speaker's own denominator, its `genocide`-bearing
speeches and occurrences, both rates computed by the same `lib/series.py` helpers 04 uses,
its ISO3, UN group and centroid where `config/entities.csv` has them, and a `sufficient`
flag. This is what §7 requires to exist before anything is drawn, and it is deliberately
all that was built — a table is not a profile, and publishing one does not license the
other.

Three decisions in it are the gate's, not the author's. **The minimum is derived rather
than declared**: 100 speeches, because at the corpus prevalence of 3.1% a country needs
about 96 before a *zero* means "quieter than the Council" rather than "not heard from
enough". Below it the rates are written as null, so a slice under the minimum cannot be
drawn by a consumer that forgot to check. **Historical states stay separate**: Yugoslavia,
Serbia and Montenegro and Zaire carry a successor's ISO3 so they can be placed at all,
which makes the code ambiguous; merging them would build a denominator no state ever had,
so the collisions are published in `iso3_collisions` instead. **Centroids are labelled as
navigation**, in the artifact rather than only here, and every row carries a `mappable`
flag so the UN Secretariat is excluded on purpose rather than by having no coordinate.

An actor profile is the strongest next addition because the normalized corpus already has
speaker identity, Council status and denominators. It should show:

- speeches and term-bearing speech rates over time;
- membership-aware P5/E10/non-member status;
- agenda composition and matched keyness with minimum-sample disclosure;
- quotations linked to the concordance and source reader.

Of those four the shipped view has one and a half, and a second table has since been
written for a third. **Rates over time** exist at the
resolution the table was built at — `all` and the four periods `countries.json`
declares — which answers *when* coarsely and is not a series. **Quotations** are linked
as of 10 August 2026: every figure in the picked-speaker panel carries that speaker, that
term and that period into the concordance, so a reader sent from Rwanda's 26.83% arrives
at its 960 lines and not at all 79,569. A set measure becomes one link per member, because
the concordance shows one term and a single link would offer a fifth of the evidence as
all of it. The decision is in `web/src/lib/actors.ts` with tests, not in the component.

**Membership status** had its table before its view — deliberately, in that order, because
§7 refuses to let a visual precede the table it depicts — and the view was drawn on
10 August 2026. `countries.json` carries a `standing` block: per speaker and per period,
the five counts that sum to its own denominator, plus `seated` and `seated_share`. The E10
rotates, so a row is a composition rather than a label, and the numbers say why that
matters — **105 of 601 speakers spoke both from a seat and from outside one**, 5 only ever
from a seat and 491 never. Shading a speaker with one membership colour would be wrong
about the first group, which is the group worth looking at: Japan gave 1,602 of its 2,055
speeches as an elected member and 453 as a non-member.

The view follows that rather than working around it. Each row is a stacked composition
painted in the row's own background — the bar *is* the table, as in the keyness figure, so
there is no second rendering to drift — and the default cut is the 105 speakers whose
standing changed, because they are the ones a label would misdescribe. Two decisions in
`web/src/lib/standing.ts` are worth naming. **The three records are told apart on the
integer counts, never on `seated_share`**: a speaker at 9,999,999 seated speeches out of
10,000,000 has a share that prints as 1 and is not one, and a float comparison would file
it with the five that never left their seat. And **five hues rather than a seated family
and an unseated one** — "not seated" covers three different situations, and a shared
colour would assert they were one. What groups the two seated positions instead is
structure: they are listed first, so the seated share is always the left-hand part of a
row, which is the number printed beside it.

One thing the site's own stylesheet nearly broke, recorded because it would have looked
like a finding. `app.css` zebra-stripes every table, and these bands are 32% opaque, so
the stripe showed through and drew the *same* membership position in two alternating
colours down the column. Decoration and data cannot share a channel; the striping is
switched off for the two tables whose backgrounds now carry a figure.

Two decisions in that block are the gate's rather than the author's. **All five counts are
published, not just the seated total**, because "not seated" covers three different
situations — a state that was not on the Council, the UN Secretariat which never can be,
and an invited non-state speaker — and a single share erases the difference. **The counts
and the share are written at every denominator**, unlike the rates beside them, and the
reason is worth stating because it looks like an exception to §1's minimum: a share of a
speaker's own known speeches is a fact about the record, not an estimate from a sample.
"Of the twelve speeches it gave, twelve were from a seat" is exactly true at n=12; "33% of
its speeches used the word" over three speeches is not. The minimum guards the second and
has nothing to say about the first.

One check came with it. 02 freezes `speaker_group` into the corpus and every later step
reads that column, which is the right dependency and also the one that hides an edit: a
term corrected in `config/council_membership.csv` afterwards would change nothing visible
while the config and the published figures disagreed about who sat on the Council.
`council.drift()` recomputes the column and stops the run, the same stance
`actors.crosswalk_drift()` takes on `entities.csv`.

**Agenda composition and matched keyness** now have their table too, written on 10 August
2026 by `scripts/12_speaker_keyness.py` into `data/derived/countries/speaker_keyness.json`,
and drawn nowhere. 05 computes matched keyness for lexicon slices — genocide speeches
against comparable speeches that do not use the word — which is a different question and
could not be cut into this one, so it was a pipeline step before it could be a view. Each
of a speaker's speeches is paired with a speech from the same year, agenda item and speaker
group given by somebody else, and the two vocabularies are compared. **126 of the 133
speakers that clear the minimum are published**, the same 133 the rate table draws and the
same 468 it withholds.

The matching is doing real work rather than decorating the claim: across published speakers
the median top-15 effect size **falls by 1.31 on the log2 scale** — a factor of 2.5 in
rate — once the occasion is held constant. Both readings are published per speaker, because
the unmatched one is not a second result but the thing the matching improves on, and the
pair is what lets a reader see that it did.

Three decisions in it are the gate's rather than the author's. **There are two gates, not
one**, and the second exists because of a case the first does not catch: the UN Secretariat
is the only speaker in its speaker group, so the pairing found partners for 123 of its 4,709
speeches. Those 123 clear a minimum counted in pairs comfortably, and the table they would
support describes a non-random fortieth of what the Secretariat said. Coverage must reach
half a speaker's own speeches, `coverage` is published for every speaker either way, and
`withheld_because` names which gate closed — "too few speeches to compare" and "compared on
an unrepresentative part of the record" are different objections. **The minimum is inherited
rather than derived**, which is stated because every other minimum here is derived: 100 is
the denominator at which a *zero rate* becomes informative, an argument that does not
transfer to a table with no rate in it. What justifies it here is consistency — profiling a
delegation beside a blank where its rate should be is the inconsistency §7 forbids — and the
statistical guard is per row instead, at five occurrences. **Self-reference is marked, never
removed**: 148 of the 1,008 rows in the top eight of a published table are a word from the
speaker's own name, which is a fact about the register rather than noise. The rule is
mechanical and therefore partial — it catches `federation` and misses `french` — and the
artefact says so, because an unmarked row must not read as a guarantee.

One defect is recorded because it was found by looking at the drawn figure rather than at
the artefact, and because it read as an error while being none. The view prints a keyword's
log ratio beside the interval it moved across, and Russia's `believe` came out as
**`+1.33 [+1.38, +1.53]`** — a value outside its own bracket. Two causes, both fixed on
10 August 2026. The stability repetitions ran on seeds *after* the published one, so the
interval described draws that excluded the draw beside it; they now start at the published
seed. And the bracket was the 5th and 95th percentiles, which at ten draws are interpolated
*inside* the extremes, so a published draw that is its sample's own minimum sits below its
own p05 about a fifth of the time. The artefact now carries the observed range beside the
percentiles — the percentiles stay, so 05's whole-corpus table and this one remain
comparable — and the figure prints the range, which cannot exclude a member of the sample
it was computed from.

One thing the shipped view got wrong and now does not, recorded because the failure looked
exactly like a result. `atrocity_core` is a union of five overlapping terms, so
`11_countries.py` withholds its occurrence count rather than double-counting a speech that
uses two of them; the row simply has no `occurrences` and no `token_rate`. Read through the
`?? 0` every consumer uses for a nullable number, that withholding was published as
`0.00 per 100,000 words` and `NaN occurrences`, and the ranking control offered to order
133 speakers by a figure none of them had. The interface now detects the absence once
(`carries()`), and drops the column, the ordering and the tooltip line instead of filling
them — and `plan()` reports which ordering it actually used, so the control cannot name a
figure the table is not in.

Gate: no profile or ranking for a slice below the declared minimum; aliases and membership
must pass existing crosswalk tests. Country centroids may support navigation, but they must
not imply that a diplomatic speaker is geographically located at that point.

## Phase 4 — Optional topics and semantic projection

Status: **evaluated on 10 August 2026, and not adopted.** The apparatus was run in full on
20,000 speeches with five stability seeds; the numbers are below and in
`data/derived/topics/evaluation.json`. One gate remains open by design — the blinded
intrusion task needs a person — but the measured gates do not support adoption, so the
open one is not what is holding it back.

Do not make a topic model part of the release pipeline until there is a written research
question that collocates and agenda labels cannot answer. That question does not yet exist,
and nothing below creates one.

### What the run found

**Neither model is stable under a 10% resample.** Adjusted Rand index across five seeds:
the NMF baseline averages **0.532** (worst pair 0.454), the embedding model **0.697**
(worst 0.643). Both sit below the 0.7 the script treats as stable, and the embedding model
does not agree with itself about how many topics exist — 62, 61, 64, 66, 62 across the five
fits. A partition that moves that much under a change of sample is a property of a fit.

**The coherence advantage does not survive equal abstention.** Left to their own thresholds
the embedding model leads by 0.037 NPMI. Forced to HDBSCAN's own 15.0% abstention, the
baseline scores **+0.240** against **+0.281** — a gap of **0.041**, below the 0.05 this
phase declares as too small to justify preferring an opaque model over one whose topics can
be checked against a concordance. That comparison is the reason the abstention threshold had
to be calibrated; at the old constant it could not have been made at all.

**Nearly half the sample has no topic more concentrated than noise.** The calibrated
threshold is **0.490** against a floor of 1/k = 0.040, and it leaves **43.8%** of documents
unassigned. The corpus does beat the null — real documents concentrate at a median share of
0.53 against 0.22 for the same words dealt at random, so the model is finding something —
but for 44% of speeches what it finds is not more concentrated than shuffled text.

**The space groups by agenda item, not by speaker.** This is the one result that runs
*against* the caution in this section, and it is recorded as such. In the 2D diagnostic,
74.3% of a point's 25 nearest neighbours share its hand-coded agenda item — a lift of 22.9
over chance — while only 1.8% share its speaker (lift 11.8) and 19.9% its year (lift 4.8).
06's finding that a genocide-bearing speech's nearest neighbour is the same delegation 55.4%
of the time had suggested the space recovered the occasion through the speaker; over 25
neighbours in the projection it does not. An agenda item is still substantially the
occasion, so this does not license a thematic reading — but it is a better result than this
section anticipated, and the next person to weigh adoption should weigh it rather than
inherit the earlier expectation.

**The picture is faithful to the space that was clustered**, which removes one objection
rather than confirming it: trustworthiness of the 2D projection against the 5D reduction is
**0.981**, though 29.1% of each point's 5D neighbours are still absent from its 2D
neighbourhood.

**What would change the decision.** A research question first, per the paragraph above.
Then: stability at or above 0.7 for whichever model is proposed, a coherence margin at
equal abstention that clears 0.05, and a completed intrusion task showing a reader can pick
the intruder well above the 1-in-6 chance rate. Failing stability is the binding constraint
today, and the k sweep suggests it is not a matter of choosing k better: coherence rises
only from +0.210 to +0.249 across k = 15, 25, 40 while the unassigned share falls from 50.7%
to 38.8%.

What has been built is the apparatus for deciding, not the decision. `scripts/06_embed.py`
encodes the corpus on a GPU and `scripts/07_topics.py` runs the comparison this phase
requires — a count-based NMF baseline against a UMAP/HDBSCAN approach on a frozen,
period-stratified sample, both seeing the same documents. Neither writes a release
artifact: `export_web.py` does not read `data/derived/topics/`, and the dashboard does not
know it exists. Both run on the Bayreuth cluster; see `docs/CLUSTER.md`.

Required evaluation, and where it now stands:

- stability across seeds and plausible topic counts — measured, as the adjusted Rand index
  between refits that resample 90% of the frozen sample and change the solver seed, plus a
  sweep over k;
- topic coherence plus blinded human interpretability — NPMI coherence is computed against
  this corpus; the interpretability half is a word-intrusion task, and **remains open until
  a human completes it**. A score generated automatically here would repeat the error §1.1
  forbids for the lexicon audit. The task was blinded properly on 10 August 2026, and the
  correction is worth recording because the first version was not. 07 wrote one file whose
  columns were `topic, words, intruder, intruder_position, intruder_from_topic, verdict` —
  the answer three columns left of the blank a reader fills in, which is not a blinded task
  whatever this section called it. Two further leaks sat behind that one: `nmf.json` and
  `embedding.json` publish every topic's top words, so an item labelled with its model and
  topic was answerable by subtraction without reading the six words; and the two models'
  items were concatenated rather than interleaved, so the file changed register halfway
  through. It is now `intrusion_task.csv` (an opaque id, the words, a blank) beside
  `intrusion_key.csv`, with the items shuffled together and each carrying the model it came
  from. That last column is not tidiness: both models label topics from zero, so without it
  a completed task scores the pair jointly and cannot say which model a reader could read —
  which is the comparison this whole section exists to make. `scripts/score_intrusion.py`
  joins the two afterwards and reports accuracy per model, with its denominator and beside
  the 1-in-6 chance rate, counting abstentions and answers that were never offered
  separately rather than as wrong;
- sensitivity to long speeches, formulaic Council language and time period — reported per
  topic as median and p90 length, the share of words appearing in over half of all speeches,
  and the dominant period;
- nearest-neighbour inspection for the 3,273 genocide-bearing speeches — written by 06.
  Read the same-year and same-speaker shares first: if the neighbours are mostly the same
  debate, the space has recovered the occasion, and a topic model built on it will return
  agenda items dressed as themes;
- an explicit “unassigned/uncertain” outcome rather than forced labels — HDBSCAN's noise
  label is kept, and the NMF baseline is given the same abstention through a minimum
  document-topic weight, so the comparison does not reward one model for a candour the
  other was never offered.

The last of those took two attempts, and the first attempt is worth recording. A
document's NMF share is its largest topic weight over the sum of them, so it can never
fall below 1/k. The threshold was a constant, 0.05: unreachable at k=15, a rounding error
above the floor at k=25, and binding only at k=40 — one number meaning three things across
the sweep it was swept over. The run of 10 August 2026 showed the consequence, 0.0%
unassigned in every NMF fit against 15–23% for HDBSCAN, which is precisely the asymmetry
the bullet exists to prevent.

The threshold is now calibrated rather than declared. Every token of the frozen sample is
pooled, shuffled and dealt back into documents of the same lengths; the same vocabulary and
idf are applied; the model is refitted; and the threshold is the 95th percentile of the
shares that null produces. A document is assigned only when its best topic is more
concentrated than the model manages on text with no co-occurrence structure at all. The
quantile is declared in `scripts/lib/topics.py` before any run, each k in the sweep is
calibrated against its own floor, and the threshold is then held fixed across the stability
refits — recalibrating inside each refit would make the adjusted Rand index measure the
threshold moving as much as the topics moving.

Because the two models still abstain at different rates, the baseline is read a second time
at HDBSCAN's rate — same factorisation, same topics, only the line moved — so a coherence
gap cannot be an artefact of one model having declined to answer more often. Both readings,
the null and observed share distributions, and the unassigned share across a range of
thresholds are written to `evaluation.json`.

Two limits on what a passing evaluation would license. Reduced-precision GPU arithmetic is
not bit-exact across devices, so embedding artifacts are reproducible only against the
device and package versions their manifest records, not by hash. And a 2D projection remains
exploratory navigation only — distances on a UMAP plot are not evidence of historical
influence or categorical separation.

07 does now write a 2D projection, and it is worth being exact about what changed, because
the sentence that used to stand here said it never would. **The projection is a diagnostic
whose purpose is inverted from the usual one: it exists to argue against a thematic reading
of the embedding space, not to support one.** It is fitted after the clustering, from the
same vectors and the same seed; the five-dimensional reduction HDBSCAN is fitted in is
untouched; no cluster is fitted on the 2D coordinates, no label is derived from them, and
the coordinates are not written to disk, so there is no column to join onto a speech and
call a topic. What is written is `projection.json` and three PNGs, in
`data/derived/topics/`, which is not a release artefact and which `export_web.py` cannot
reach — a guarantee `tests/test_cluster.py` now asserts file by file.

What makes it evidence rather than decoration is that it is measured. For each point,
`projection.json` reports the share of its 25 nearest neighbours **in the 2D coordinates**
that share its speaker, delegation, year, period, hand-coded agenda item, NMF topic and
HDBSCAN cluster, each beside the base rate a randomly chosen other speech would give, so
the figure is a lift rather than a bare fraction. That settles the question the bullet
above only poses: if purity by speaker greatly exceeds purity by agenda item and by NMF
topic, the picture is a picture of speakers, and the note says so in words with the numbers
in them rather than referring a reader to a figure. The HDBSCAN row is reported as a
ceiling, not as a result — the clusters and the picture are two reductions of the same
vectors and are bound to agree to some degree.

The same file also measures how far the picture is from the space that was actually
clustered: trustworthiness of the 2D embedding against the 5D reduction, and the plainer
figure of what share of each point's nearest neighbours in 5D are absent from its
neighbourhood in 2D. Both run on a deterministic subsample whose size and seed are recorded
in the artefact, because the ranks the measure needs are an n-by-n matrix at 20,000 points.
That is the arithmetic reason a thematic map would mislead: points the clustering called
neighbours can sit far apart in the figure. The purity and trustworthiness maths is written
out in numpy, like the adjusted Rand index and the NPMI coherence beside it, so it is
testable in an environment with no scikit-learn; only the UMAP call and the matplotlib
figures need the cluster's packages, and both are imported inside the functions that use
them. `matplotlib` is in `requirements-cluster.txt` for that reason, and the figures select
the Agg backend explicitly because the compute node has no display.

## Phase 5 — Optional LLM structured extraction

Status: in progress as Phase L of `docs/IMPROVEMENT_ROADMAP.md`, decided 28 August 2026 —
as a marked experiment, not a result. This section was written when no human coding
protocol existed; the codebook and its two-coder protocol now do, and the owner's decision
to run the layer before the full H1 campaign is recorded, with its gates, in the Phase L
section of the roadmap. The requirements below stand unchanged; where each one now lives
is mapped after the list.

The LLM layer may classify a bounded question such as referent, speech act or legal stance;
it must not decide whether genocide occurred. Build it as a frozen evaluation before a
corpus-wide run:

1. Define a small schema with evidence spans, an abstention value and no free-form hidden
   rationale.
2. Create a stratified human-coded gold set including difficult negatives, quoted/denied
   claims, commemorative uses and OCR damage.
3. Measure per-class precision, recall, macro F1, abstention and evidence-span validity.
4. Run prompt/model sensitivity and negative controls; keep model and prompt versions in
   every output.
5. Require a second human coder on a subset and report agreement. Adjudicate disagreements
   before setting thresholds.
6. Ship only categories that meet predeclared thresholds. Mark all model-derived fields in
   the interface and always expose the supporting quotation.

No model output may overwrite corpus text, lexicon counts or human annotations.

Where each requirement lives as of 28 August 2026: (1) the schema is the codebook's own —
verdict, quotation, stance, function, referent, confidence — enforced by
`scripts/lib/llm.py`, with `unclear` as a first-class abstention and a verbatim evidence
quote in place of free-form rationale; (2) `scripts/13_gold_sample.py` draws the gold
sample in three frames — 120 by equal probability, 80 by decade × usage cue (rejection,
quotation, commemorative, dense meeting) so denied and commemorative uses are oversampled
rather than hoped for, and, since 2 September 2026, 535 from the strata the two committed
model runs read differently, so that a rare class can be measured at all; each frame
records its own inclusion probability and they are never pooled — hard negatives remain
§1.1's own negative frame; (3) `scripts/15_usage.py` computes per-class precision, recall
and F1 against the human rows above a support floor of twenty, with counts below it, a
macro and a support-weighted average, the share of double-coded occurrences each field's
score was *not* computed over, and evidence validity; the `/usage` view displays them
beside the model output, including the honest zero state while coding is under way;
(4) model id and prompt hash travel in every output row and every run manifest, and the
pilot and full runs stay committed side by side under `model_annotations/` — the
second-model sensitivity run landed as L8 on 31 August 2026, and a second-*prompt* one is
still owed before any citable claim; (5) both coders, FM and JG, code the full sample independently,
100% double-coded, with adjudication per the codebook; (6) shares are withheld below a
declared minimum, every model-derived surface is marked experimental, and the supporting
quotation is one click away everywhere — predeclared per-class thresholds for promoting a
category out of "experimental" are still owed. The closing rule above is structural, not
aspirational: model output lives in `model_annotations/`, the pipeline never writes
`annotations/`, and 15 refuses a run whose lexicon version or occurrence identities no
longer match the corpus.

## Phase 6 — Lemma-based lexicometry

Status: built and runnable; not adopted, and not part of the release.

Inflection splits every table in 05: `crimes` and `crime` occupy two of the hundred rows
a collocate list has, each carrying a fraction of the evidence they jointly support.
`scripts/10_lemmatise.py` builds a lemma layer over the corpus and
`05_lexical.py --vocabulary lemma` counts it, writing to `data/derived/lexical_lemma/`.
Measured on the full corpus: 15.3% of running text collapses (9.0M of 58.9M tokens), and
merging `crimes`/`crime` and `committed`/`commit` promotes `punishment` into the top
collocates of `genocide` — the Convention's own title, previously held below the cutoff
by inflection alone.

Three constraints are structural, not incidental:

- **The lexicon is never lemmatised.** `config/lexicon.yml` matches surface forms and
  §1.1 gates a human audit on those patterns. Folding `genocides` into `genocide` before
  step 03 would move every published count and restart that audit.
- **The surface tables are never overwritten.** Lemma mode writes to its own directory.
  The dashboard reads the surface tables, and so does the audit in progress.
- **A missed merge is preferred to a wrong one.** A lemma is accepted only when the
  tagger and `lib.lexical.tokenise` agree on the token's extent *and* the lemma is itself
  a word. Both rules were added after a run produced wrong output rather than an error:
  hyphenated compounds inheriting their first fragment's lemma (`Secretary-General` →
  `secretary`, 71,703 occurrences) and document symbols entering the vocabulary
  (`S/24232`). Hyphenated compounds consequently do not collapse. 1.7% of tokens have a
  lemma offered and refused, and that figure is reported.

Every merge is recorded in `data/derived/lemmas/mapping.csv`, most frequent first, so a
reader who distrusts a lemma table can see what was merged into what without rerunning
anything.

Open decisions before this could become the default reading:

- `further` lemmatises to `far`, which the stoplist does not cover. Adding `far` to
  `config/stopwords.txt` would also change the surface tables, so the leak is reported
  and left for a human.
- Adoption would change published collocate and keyness figures, so it cannot precede
  the §1.1 audit closing.

Gate: adopt as the default only with the audit closed, the mapping table reviewed at
least down to the frequency where a wrong merge stops mattering, and both readings
published side by side for the release they first appear in.

## Phase 7 — Visualisation

Status: items 1, 2, 3 and 5 shipped; item 4 gated behind a Phase 4 that was not adopted.
Item 3 shipped as a ranking, a map, a matched-keyness figure and a membership composition
rather than as the single profile §3 describes. Nothing here may precede the table it
depicts, and item 5 was built in that order on purpose: the pipeline step first, the
figure second, on the same day.

The project's charts are currently rates over time, the event overlay and the
concordance. Five additions are worth building, in this order:

1. ~~**Word clouds over the lemma collocate table.**~~ **Shipped**, over the *surface*
   collocate table rather than the lemma one: Phase 6 is not adopted, and adopting it
   would move published figures before §1.1 closes. The cost is carried in the figure's
   own caveat rather than here — `crimes` and `crime` are two words in that cloud, each
   holding a share of the evidence they jointly support, so the words to trust least are
   the ones with the commonest inflections, and the cloud is to that extent a picture of
   English morphology rather than of the Council.

   Everything else the item argued for holds. 05 has always said that a cloud is a
   rendering of the collocate table rather than a separate artifact, and that shipping it
   as its own file would invite it to drift from the numbers it claims to depict; it is
   generated from `collocates.json` at render time, sized by log ratio over a stated
   stoplist, with the table reachable from it.

   It is also **facetable**: `collocates_sliced.json` already carries `by_period`,
   `by_speaker_group` and `by_country` with a declared `minimum_speeches`, and a cloud
   that cannot be cut by period or speaker is a decoration where a comparison was
   available. The facet is a selection over that artifact, not a property of the renderer.
   Which is the argument against `echarts-wordcloud`: it is canvas-only, so no word can
   be a link or be read aloud, it has been unpublished since 2022, and its peer dependency
   is `echarts ^5` against this project's `^6` — a major downgrade bought for a layout
   algorithm. Positions come from `d3-cloud` instead, which computes placement and draws
   nothing, so the words are rendered as SVG anchors that reach the concordance and can be
   read aloud. Its randomness is seeded from the facet key: a cloud that reshuffles
   between renders is not a depiction of a table.
2. ~~**The co-occurrence network as a graph.**~~ **Shipped.** `network.json` carries PMI
   and nPMI edges between lexicon terms, whole-corpus and per period, and the Language
   view draws it as a force graph. Both constraints hold in the shipped version: stroke
   width and opacity derive from **nPMI**, not raw PMI, so a rare term cannot buy
   prominence with rarity alone; and the four nested edges the lexicon implies
   (`atrocity`/`mass_atrocity`, `genocide`/`genocide_convention`,
   `genocide`/`prevention_of_genocide`, `genocide`/`genocidal_ideology`) are suppressed in
   the artifact, listed there under `suppressed_nested_edges`, and named in the figure's
   caveat rather than silently dropped. `min_speeches` is 20 and declared in the artifact,
   so no sub-minimum edge is drawn, and the edge table sits beside the graph.
3. **Actor-view visuals** (Phase 3): speech and term-bearing rates per speaker with
   membership shading, and matched keyness with minimum-sample disclosure. Country
   centroids may support navigation but must never imply that a diplomat is located at
   that point. **The ranking and the map are shipped**, drawn from `countries.json`, and
   **membership is drawn** as of 10 August 2026 over that file's `standing` block — as a
   composition per row rather than as the shading this item asked for, which the table
   itself rules out.
   **Matched keyness is drawn** as of 10 August 2026, over `speaker_keyness.json`, on the
   same page and immediately after the table it depicts was written. Its decisions are in
   `web/src/lib/keyness.ts` with tests; the component renders and computes nothing. The bar
   *is* the table — length is drawn in the row's own background, so the figure and the
   numbers are one element and there is no second rendering to drift — and colour carries
   only the direction of the effect, from the register palette, because `--blue` is reserved
   for interaction. A withheld speaker stays in the picker and refuses with its own reason:
   the UN Secretariat's panel says it found 123 comparable speeches out of 4,709, which is
   more useful than its absence would have been. §3 says why membership arrived as a
   composition instead of the shading named above: 105 speakers spoke both from a seat and
   from outside one, so a single colour per speaker was never available.
   Both warnings this item raised were honoured rather than discovered late: 133 of 601
   speakers clear the minimum and the other 468 are reported as a withheld count rather
   than ranked low, and nothing is keyed on ISO3 — circles key on `country_org`,
   coincident centroids group into one marker that knows how many it stands for, and the
   two shared codes are named in the apparatus and marked in the table.

   **A choropleth was added as a second view on 11 August 2026, and the objection that
   kept it out is what it is built around.** The objection was never that filling
   territory is ugly; it was that a fill has to be keyed on ISO3, and a fill keyed on a
   shared code paints one row over another silently. So it does not paint one: a code with
   more than one drawable holder is `contested` — outlined, unfilled, and named in the
   interface — and `web/src/lib/choropleth.ts` decides that rather than the renderer. The
   branch is unreachable in the present corpus, because only one holder of each shared
   code ever clears the minimum, and it is tested anyway, on the same argument the
   chronology's unreachable `unobserved` cell state is kept on.

   Three costs come with it and are carried in the interface rather than here. A fill is
   territory, so a historical speaker is drawn inside its successor's borders — Yugoslavia
   fills modern Serbia — which is a claim the circles never made and cannot be removed by
   keying anything differently. Area is not evidence, so a large state is conspicuous for
   being large. And Natural Earth's 1:110m sheet omits 31 of the corpus's 197 coded
   speakers, which are marked at their centroid rather than dropped. The circles remain
   the default and the table remains the primary presentation; the geometry is a committed
   asset built by `tools/build_boundaries.py`, not a pipeline artefact, because it is
   derived from `config/entities.csv` and not from the Dataverse pin.
4. **A 2D semantic projection**, only if Phase 4 is approved, and only as exploratory
   navigation. Distance on a UMAP plot is not evidence of influence or of categorical
   separation, and any such map must carry that statement in the interface rather than
   in a methods note nobody opens. **The projection 07 writes is not this and must not be
   promoted into it.** It is a diagnostic against a thematic reading (§4), it lives in
   `data/derived/topics/`, its coordinates are never written, and its own numbers are the
   argument for leaving it there: the neighbourhood purities say how much of the picture
   is speaker and occasion rather than subject. Shipping it would mean re-deriving the
   coordinates for the dashboard and answering the §4 gates first — not copying a PNG.

5. ~~**A year × month heatmap.**~~ **Shipped on 10 August 2026**, the pipeline step first
   and the figure after it, as this section requires. `04_series.py` writes
   `series/monthly.json`; the Chronology page draws the grid and, beside it, the pooled
   calendar. The scoping below was written before either existed and every number in it
   held when the step ran, so it is kept as written and what the building added is
   recorded after it. The chronology is annual and quarterly; a year is a coarse unit for
   a body that meets some 250 times in one, and the question a month resolution can answer
   is whether genocide vocabulary has a calendar.

   It does, and **not the one the question implies** — which is the argument for building
   it. April, the Rwanda commemoration month, is *not* elevated: 2.90% of its speeches
   carry `genocide` against a corpus rate of 3.08%, and July, for Srebrenica, is 2.32%.
   What stands out is **June at 5.98% and December at 5.06%**, and the pattern survives
   dropping 1994 and 1995 (5.87% and 5.00%), so it is not the Rwanda spike leaking into a
   monthly view. The agenda items behind those speeches say what it is: **International
   Tribunals**, 213 genocide-bearing speeches in June and 177 in December, the largest item
   in both months. The ICTY and ICTR reported to the Council semi-annually. The most
   visible feature of this figure would be the Council's own reporting calendar.

   That is the finding and also the caveat, and it must be in the figure rather than in a
   note: a month's vocabulary is the vocabulary of the debates scheduled in it, which is
   the same confound §3's keyness step spends its entire design controlling for. A reader
   shown a bright June without the tribunal cycle beside it learns something false.

   Two constraints follow from the data. **The gap must be drawn as withheld, not as
   white.** All 384 months are observed, but only 331 of them (86.2%) clear the 100-speech
   minimum, and those hold 97.1% of all speeches; white on a heatmap reads as zero, which
   is the `?? 0` failure recorded below, in a form that covers 53 cells. **The column read
   is a second figure, not a margin of the first**: month-of-year pooled across thirty-two
   years has a different denominator from any cell, and drawing it as a strip beside the
   grid would invite the two to be read off one scale.

   It is a pipeline step before it is a view, like §3's keyness. `lib/series.py` already
   takes a frequency and 04 already writes `annual.json` and `quarterly.json`, so `month`
   is a third branch; the real work is the withholding rule, which the annual series never
   needed because a year always has thousands of speeches and a month need not.

   **What building it added.** The withholding rule was the work the scoping expected, and
   it moved code rather than adding it: the zero-ceiling arithmetic that derives the
   minimum lived in `lib/actors.py`, and a monthly cell needs the same rule for the same
   reason, so it now lives in `lib/series.py` — which owns denominators — and `actors`
   re-exports it. Two implementations of one threshold would eventually disagree and
   nothing in the output would say which was wrong. The grid is written **complete**, all
   `years × 12` cells, so a month nobody spoke in is a row of zeros rather than an absent
   key: on a heatmap a missing cell is drawn by whatever the consumer does with a missing
   value, and that is white, and white is the colour a zero has. Every month in this
   corpus is observed, so the state is unreachable today; it exists so the figure does not
   have to change the day one is not.

   Three decisions were the figure's rather than the table's, and all three are in
   `web/src/lib/heatmap.ts` with tests. **The ramp is not proportional.** These rates are
   skewed — the median drawn month is 2.2% against a maximum of 19.2% — so a colour
   proportional to the value leaves half the grid indistinguishable from the page, which
   understates what is drawn as badly as exaggeration would. The ramp is on the square
   root: monotone, nothing clipped, every cell keeping its own colour and its order. It is
   disclosed in the figure's own note rather than in this file, because the reader who
   would misread it is the one looking at the picture. **Rates only, no counts.** The
   chronology offers counts because the contrast between a count and a rate is its
   argument; here a count would be a picture of when the Council met, which is precisely
   the confound this figure exists to disclose — and a count needs no minimum, so two of
   four units would quietly have no withheld cells and no legend for them. **The column
   read is scaled inside itself**, never against the grid, which is this item's own
   requirement turned into a test.

   One limitation was recorded rather than left to be discovered, and **closed on 11 August
   2026**. The concordance filtered lines by year, so a cell could not open the evidence
   behind *itself*; the table under the grid linked each year and the interface said it was
   the year. Wider than the square, and said so. The fix was where the note predicted — the
   concordance's URL contract, its controls and its export, not this figure — and
   `web/src/lib/concordance.ts` now owns what `month` means there, with the reader and the
   link builders tested against each other so the two cannot drift.

   **A month of the year, not a `YYYY-MM` period.** The obvious parameter names the cell and
   serves one of the two figures; the pooled calendar beside the grid is thirty-two Junes,
   which a period string cannot express without a second, incompatible form. A month of the
   year is orthogonal to the year bounds the contract already carried, so one parameter
   serves both — a square is `month=6` inside `from=2014&to=2014`, a calendar row is
   `month=6` across every year. That is also the shape of `monthly.json`, which publishes
   the grid and `month_of_year` as two readings of one table.

   **A withheld square links.** The minimum governs a *rate*: 100 speeches is the
   denominator at which a zero starts to mean "quieter than the Council" rather than "not
   heard from enough". A concordance line is not an estimate from a sample, so a month
   holding 40 speeches of which 2 use the word has no publishable rate and exactly two lines
   of evidence, and refusing to open them would withhold the record to protect a figure that
   is not being shown. The same distinction §3 draws between a speaker's standing counts and
   the rates beside them.

   **An unreadable month does not filter.** `month=13` reads as no month at all rather than
   as an empty result, which is the lenient reading the year bounds already take. What keeps
   it honest is that the control is the disclosure — the select shows "All" whenever the
   parameter cannot be read, so the interface never claims a month it is not showing, and
   the URL rewrites itself from the parsed value on the first write.

   Building it surfaced a defect in the link it replaced, recorded because it had been
   shipped and because nothing would have reported it. The old link was
   `?term=<measure>&from=<year>&to=<year>` for whatever the grid was drawing, and the
   concordance holds one file per term: ten of the thirty-two measures — six registers and
   four sets — are not terms, so selecting `atrocity_core` and following its year link
   reached a file that does not exist and a retry button. A set is now expanded to its
   members exactly as `lib/actors` does for a speaker's quotations, and because 384 squares
   cannot each carry five links, a multi-term measure declines to link and the note under
   the table names the terms to draw instead. Refusing is the repair.

Requirements that apply to all five:

- every visual links to the table behind it, and the two are generated from one artifact;
- no visual introduces a number that does not exist in a JSON artifact with a manifest.
  The actor view broke this on 10 August 2026 and was fixed the same day, which is worth
  keeping because of *how* it broke: nothing invented a number, it read a field that was
  never written. `atrocity_core` has no occurrence count by design, and `?? 0` — the idiom
  every consumer here uses for a nullable figure — turned that silence into
  `0.00 per 100,000 words`. The general lesson is that a missing key and a measured zero
  are indistinguishable downstream unless something checks, so the check belongs once, in
  the tested module, and the interface drops what the artifact withholds;
- colour must not encode a quantity the underlying table does not support;
- a slice below the declared minimum sample is not drawn, in any of them;
- **the arithmetic a visual performs at render time is tested.** The research contract
  requires a test that fails when a data contract changes unexpectedly, and until the word
  cloud that requirement was met only on the Python side: the dashboard had no test runner,
  so a filter, a minimum-sample gate or a scale computed in the browser was covered by
  nothing but `svelte-check`, which checks types rather than behaviour. The rule that
  follows is architectural — a visual's decisions live in a plain module that can be
  called from a test, and the Svelte component is a renderer over it. Logic reachable only
  by mounting a component is logic nobody will test twice. `web/src/lib/data.ts` validates
  every payload at the fetch boundary and throws on a malformed one; those validators are
  covered in the same pass. The boundary states each artefact's structure once, as
  `REQUIRED` — every key it must carry and of what kind — which is also the half of the
  contract `contract.test.ts` reads, so the dashboard cannot come to require a field, or a
  type, that the pipeline does not write. What the validators keep is what is substantive
  rather than structural, and two are worth naming: an event without a primary-source URL is
  refused there, which is §1.2 enforced at the boundary rather than trusted upstream; and a
  failed request is evicted from the cache, which is the only reason the concordance's retry
  can ever succeed.

### 7.5 Export what is on screen

Status: **shipped on 10 August 2026**, ahead of the release this section placed it after —
the same reordering §3 records, for the same reason: it changes what a reader can take
away, not what any figure says. Every figure now offers its numbers as CSV and, where
there is a chart, the picture as SVG or PNG, from beside the source rather than over the
drawing. The decisions live in `web/src/lib/export.ts` with tests; the component decides
nothing and does the work on click.

Every chart and every generated table should be downloadable — the numbers as CSV, the
chart as an image — from beside the thing itself.

Three constraints, or the export becomes a second source of truth — each of them now a
test rather than an intention:

- **Export the artifact's numbers, not the chart's pixels.** A CSV is written from the same
  JSON the chart is drawn from, at full precision, including rows a zoom or a top-N cut is
  currently hiding. A file containing only what happened to be visible is a screenshot with
  commas in it.
- **The file carries its own provenance.** Leading comment rows, or a companion column,
  naming the generating script, the artifact, the lexicon version and the manifest hash —
  the same identifiers the dashboard shows — so a CSV that outlives the tab it came from
  can still be traced. A downloaded table with no version is an orphan the moment a figure
  is regenerated.
- **Chart images state their filters.** A PNG of a filtered or zoomed view must carry the
  term, window, unit and period in the rendered image, not only in the filename.

The first constraint is the one that shaped the shipped files: nothing in the export module
can read a chart's state, so a caller hands over the rows the artifact holds and the file
comes out wider than the figure. The chronology series exports all 32 measures in four
units; the actor table exports all 601 speakers with the 468 withheld ones' nulls intact
and a `sufficient` column beside them, because a reader given only the drawable rows cannot
recover what was left out or know that it was. The concordance is the one legitimate
subset — a filter there is the reader's question, not a display cut — and it now offers
both readings with each declaring its scope.

## Priority order

1. Complete the human audit and source-document spot checks.
2. ~~Select the code/derived-artifact licence and confirm citation identities.~~ Done,
   10 August 2026 — see §1.3.
3. Run the first reproducible Pages release and archive its manifest. ~~Cache the pinned
   corpus and the derived payload in the workflow first.~~ Cached on 11 August 2026 — see
   §2.1: a `web/**`-only push no longer contacts Dataverse at all, where it previously
   re-fetched 508 MB to change a stylesheet and cost a release two failed deploys in a row.
   What is left of this item needs no code. The Pages source has to be set to GitHub
   Actions, which is a repository setting; then the operational checks in §2 have to pass
   against a live deployment. Archiving the manifest is also where the payload itself should
   stop depending on an archive nobody here controls.
4. ~~Build the actor view.~~ Complete as of 10 August 2026: the ranking, the map, the
   concordance links, the per-speaker matched keyness and the membership composition are
   all shipped — see §3. Every table this phase wrote now has a figure over it.
5. Review the lemma mapping table and decide whether the lemma reading becomes the
   default, or stays a second reading published beside the surface one.
6. ~~Add the faceted word cloud, generated from the artifact it depicts.~~ Shipped over
   the surface collocate table — see §7.1. (The co-occurrence graph that stood beside it
   here is shipped too — see §7.2.)
7. ~~Add CSV and image export beside every chart and generated table.~~ Shipped —
   see §7.5.
8. ~~Decide whether topics answer a question the current methods cannot.~~ Decided on
   10 August 2026: not on this evidence — see §4. Reopen only with a research question and
   a model that clears stability, not by rerunning the same comparison.
9. ~~Add the month resolution.~~ Shipped on 10 August 2026: `monthly.json` from 04 with
   the withholding rule a monthly denominator needs, then the year × month heatmap and the
   pooled calendar over it — see §7's fifth item. The tribunal reporting cycle it makes
   visible was the reason to build it and is the caveat it carries, in the figure rather
   than in a note. The one limitation it shipped with — a square that could not open its
   own evidence — was closed on 11 August 2026 by giving the concordance a month.
10. Consider the LLM evaluation only after a human coding protocol exists.

Steps 4, 6, 7 and 9 were built before step 3 rather than after it. The gate they jumped
governs what may be *tagged* as citable, and nothing is tagged; each of them draws from an
artifact the §1.1 audit can regenerate without touching a line of the view. Step 5 is the
one that stays behind the audit, and not for sequencing reasons: adopting the lemma
reading would move published collocate and keyness figures, which is the one thing an
open audit forbids.

**What is left is what only a person can do**, and as of 11 August 2026 that is meant
literally: step 3's remaining half is a repository setting and the operational checks that
follow a live deployment, not code. Steps 1 and 3 — the human lexicon audit with its
source-document spot checks, and the first reproducible Pages release — are the whole of
the near-term list, with step 5 behind the first of them and step 10 behind a coding
protocol that does not exist. No figure in the release is waiting on a table, and no table
in the release is waiting on a figure. Two artifact directories remain
deliberately undrawn and should stay that way: `data/derived/topics/`, whose projection is
a diagnostic *against* a thematic reading (§4), and `data/derived/lexical_lemma/`, which
cannot become a default reading before the audit closes (§6).

This ordering keeps the next release modest and defensible while leaving clear gates for
more ambitious digital-humanities work.
