# The pipeline as one graph.
#
# Every numbered step, what it reads and what it writes, in the one place the
# deploy workflow, the README and the cluster notes used to copy by hand — and
# drifted (review of 1 September 2026, §6.4). A target is the file a step is
# known to write; its prerequisites are the inputs the step reads, so `make
# payload` rebuilds exactly what an edited config or script invalidates and no
# more. Steps that write a directory are keyed on one file inside it.
#
#   make payload    everything the site ships, from a corpus on disk
#   make raw        fetch or MD5-verify the pinned corpus (always runs 00)
#   make cluster    the GPU / spaCy steps, on a machine that has them
#   make -n payload what would run, and in what order
#
# 14 is never a target: it reserves a cluster GPU and writes a reviewed run.
# 15 aggregates the run named in model_annotations/genocide/current_run.txt.

# `&:` grouped targets need GNU make 4.3 and `$(file <)` needs 4.2. An older
# make (macOS still ships 3.81) reads `&:` as an ordinary rule with an extra
# target named `&`, and `$(file <)` as an empty variable, and carries on without
# an error: grouped steps can run once per output, and 15 loses its
# --allow-partial flag. 4.3 is the release that announces `grouped-target`.
ifeq ($(filter grouped-target,$(.FEATURES)),)
$(error GNU make 4.3 or later is required, and this is $(MAKE_VERSION). On macOS, install GNU make with Homebrew and run gmake)
endif

PY ?= python
# Only the explicitly selected preview may bypass the coverage gate.
SELECTED_RUN := $(strip $(file <model_annotations/genocide/current_run.txt))
PARTIAL_RUN := $(strip $(file <model_annotations/genocide/allow_partial_run.txt))
USAGE_FLAGS :=
ifneq ($(SELECTED_RUN),)
ifeq ($(SELECTED_RUN),$(PARTIAL_RUN))
USAGE_FLAGS := --allow-partial
endif
endif
# Each step's `lib` prerequisites, generated from its imports by
# tools/lib_deps.py and held to them by tests/test_build_graph.py. A step used
# to depend on every module, so an edit to the usage aggregation rebuilt the
# corpus from 01.
include scripts/deps.mk
REFERENTS := annotations/lexicon/referents.csv
MODEL_INPUTS := $(wildcard model_annotations/genocide/*.md model_annotations/genocide/*.txt model_annotations/genocide/runs/*/* model_annotations/genocide/prompts/*.md)

RAW_FILES := data/raw/speeches.tsv data/raw/meetings.tsv
SPEECHES  := data/derived/speeches.parquet
NORM      := data/derived/speeches_norm.parquet
FLAGGED   := data/derived/speeches_flagged.parquet
SERIES    := $(addprefix data/derived/series/,annual.json quarterly.json monthly.json breakdowns.json change_points.json events.json decomposition.json)
LEXICAL   := $(addprefix data/derived/lexical/,collocates.json collocates_sliced.json keyness.json network.json)
KWIC      := data/derived/kwic/index.json
SPEECHES_WEB := web/static/data/meetings.json
SCOPES_WEB := web/static/data/scopes.json
COUNTRIES := data/derived/countries/countries.json
SPEAKER_KEYNESS := data/derived/speaker_keyness/speaker_keyness.json
GOLD      := $(addprefix data/interim/genocide_gold_,candidates.csv review.csv probability.csv coverage.csv disagreement.csv model_strata.csv packet.csv design.csv)
USAGE     := data/derived/usage/usage.json data/derived/usage/occurrences.json
NODE_FRAMES := data/derived/frames/frames.json data/derived/frames/occurrences.json
PAYLOAD   := web/static/data/manifest.json

EMBEDDINGS := data/derived/embeddings/manifest.json
TOPICS     := data/derived/topics/manifest.json
LEMMAS     := data/derived/lemmas/lemmas.parquet
LEXICAL_LEMMA := data/derived/lexical_lemma/collocates.json

.PHONY: all payload derived raw cluster clean robustness robustness-lemma robustness-extended semantic

all: payload

# --- Corpus ------------------------------------------------------------------
# Phony on purpose: 00 is cache-aware and MD5-checks every file already on
# disk against config/dataset-pin.json, printing `ok` rather than downloading.
# That check is worth running every time, and it costs no request.
raw:
	$(PY) scripts/00_fetch_data.py

$(RAW_FILES): | raw

# --- Canonical data -----------------------------------------------------------
MEETINGS  := data/derived/meetings.parquet

# One run writes both; `&:` (GNU make 4.3) says so, where two rules would run 01 twice.
$(SPEECHES) $(MEETINGS) &: $(RAW_FILES) scripts/01_build_parquet.py $(LIB_01_BUILD_PARQUET) config/dataset-pin.json
	$(PY) scripts/01_build_parquet.py

$(NORM): $(SPEECHES) scripts/02_normalise.py $(LIB_02_NORMALISE)
	$(PY) scripts/02_normalise.py

$(FLAGGED): $(NORM) scripts/03_lexicon.py $(LIB_03_LEXICON) config/lexicon.yml config/lexicon.lock.json config/lexicon.counts.json annotations/lexicon/annotations.csv $(REFERENTS)
	$(PY) scripts/03_lexicon.py

# --- Analysis artefacts -------------------------------------------------------
$(SERIES) &: $(FLAGGED) scripts/04_series.py $(LIB_04_SERIES) config/events.csv
	$(PY) scripts/04_series.py

$(LEXICAL) &: $(FLAGGED) scripts/05_lexical.py $(LIB_05_LEXICAL) config/stopwords.txt
	$(PY) scripts/05_lexical.py

$(KWIC): $(FLAGGED) scripts/08_kwic.py $(LIB_08_KWIC)
	$(PY) scripts/08_kwic.py

$(SPEECHES_WEB) $(SCOPES_WEB) &: $(FLAGGED) $(MEETINGS) scripts/09_export_speeches.py $(LIB_09_EXPORT_SPEECHES)
	$(PY) scripts/09_export_speeches.py

$(COUNTRIES): $(FLAGGED) scripts/11_countries.py $(LIB_11_COUNTRIES) config/entities.csv
	$(PY) scripts/11_countries.py

# 12 owns derived/speaker_keyness/; export merges it into countries/ for the web.
$(SPEAKER_KEYNESS): $(FLAGGED) scripts/12_speaker_keyness.py $(LIB_12_SPEAKER_KEYNESS) config/stopwords.txt
	$(PY) scripts/12_speaker_keyness.py

# Deterministic — same corpus, same seed, byte-identical CSVs. 15 refuses to run
# without the candidates file it draws, because the gold block reports on a
# sample that exists; the coded rows live in annotations/, which is committed.
$(GOLD) &: $(NORM) scripts/13_gold_sample.py $(LIB_13_GOLD_SAMPLE) config/lexicon.yml config/lexicon.counts.json $(wildcard annotations/genocide/*) $(REFERENTS) $(MODEL_INPUTS)
	$(PY) scripts/13_gold_sample.py

$(USAGE) &: $(NORM) $(GOLD) scripts/15_usage.py $(LIB_15_USAGE) config/lexicon.yml config/lexicon.counts.json $(MODEL_INPUTS) $(wildcard annotations/genocide/*) $(REFERENTS)
	$(PY) scripts/15_usage.py $(USAGE_FLAGS)

# 17 classifies the same occurrences 08 writes lines for, from the same corpus,
# and crosses them with whichever runs the two pointer files name — so the
# committed runs are prerequisites exactly as they are for 15. It does not read
# 08's output: both read the flagged parquet, which is what keeps the two
# counts equal without one depending on the other.
$(NODE_FRAMES) &: $(FLAGGED) scripts/17_frames.py $(LIB_17_FRAMES) config/lexicon.yml $(MODEL_INPUTS) $(REFERENTS)
	$(PY) scripts/17_frames.py

data/derived/actor_year/actor_year.csv: $(FLAGGED) scripts/20_actor_year.py $(LIB_20_ACTOR_YEAR)
	$(PY) scripts/20_actor_year.py

derived: $(SERIES) $(LEXICAL) $(KWIC) $(SPEECHES_WEB) $(SCOPES_WEB) $(COUNTRIES) $(SPEAKER_KEYNESS) $(GOLD) $(USAGE) $(NODE_FRAMES) data/derived/actor_year/actor_year.csv

# --- The site's payload -------------------------------------------------------
$(PAYLOAD): $(SERIES) $(LEXICAL) $(KWIC) $(SPEECHES_WEB) $(SCOPES_WEB) $(COUNTRIES) $(SPEAKER_KEYNESS) $(USAGE) $(NODE_FRAMES) scripts/export_web.py $(LIB_EXPORT_WEB) tests/contract/payload.json config/semantic-release.json data/derived/actor_year/actor_year.csv $(wildcard data/derived/semantic/manifest.json)
	$(PY) scripts/export_web.py

payload: $(PAYLOAD)

# --- Cluster-only steps (docs/CLUSTER.md) -------------------------------------
# Not part of the release pipeline: they need requirements-cluster.txt and a
# GPU or spaCy model. 10 feeds an optional second run of 05 over lemmas, into
# its own directory; the surface tables the site reads are never overwritten.
$(EMBEDDINGS): $(FLAGGED) scripts/06_embed.py $(LIB_06_EMBED) config/embedding_models.yml
	$(PY) scripts/06_embed.py

$(TOPICS): $(FLAGGED) $(EMBEDDINGS) scripts/07_topics.py $(LIB_07_TOPICS)
	$(PY) scripts/07_topics.py

$(LEMMAS): $(FLAGGED) scripts/10_lemmatise.py $(LIB_10_LEMMATISE)
	$(PY) scripts/10_lemmatise.py

$(LEXICAL_LEMMA): $(FLAGGED) $(LEMMAS) scripts/05_lexical.py $(LIB_05_LEXICAL) config/stopwords.txt
	$(PY) scripts/05_lexical.py --vocabulary lemma

cluster: $(EMBEDDINGS) $(TOPICS) $(LEXICAL_LEMMA)

# Optional local diagnostics, kept outside the published payload.
robustness: $(FLAGGED)
	$(PY) scripts/18_lexical_robustness.py

robustness-lemma: $(FLAGGED) $(LEMMAS)
	$(PY) scripts/18_lexical_robustness.py --lemma-layer data/derived/lemmas

robustness-extended: $(FLAGGED)
	$(PY) scripts/19_extended_robustness.py

semantic: $(FLAGGED) $(EMBEDDINGS)
	$(PY) scripts/21_semantic_map.py

clean:
	rm -rf data/derived data/interim web/static/data
