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
# 14 and 16 are never targets: they spend money and write a run by hand.
# 15 aggregates the run named in model_annotations/genocide/current_run.txt.

PY ?= python
LIB := $(wildcard scripts/lib/*.py)

RAW_FILES := data/raw/speeches.tar data/raw/speaker.tsv data/raw/meta.tsv
SPEECHES  := data/derived/speeches.parquet
NORM      := data/derived/speeches_norm.parquet
FLAGGED   := data/derived/speeches_flagged.parquet
SERIES    := data/derived/series/annual.json
LEXICAL   := data/derived/lexical/collocates.json
KWIC      := data/derived/kwic/index.json
SPEECHES_WEB := web/static/data/meetings.json
COUNTRIES := data/derived/countries/countries.json
SPEAKER_KEYNESS := data/derived/countries/speaker_keyness.json
GOLD      := data/interim/genocide_gold_candidates.csv
USAGE     := data/derived/usage/usage.json
PAYLOAD   := web/static/data/manifest.json

EMBEDDINGS := data/derived/embeddings/manifest.json
TOPICS     := data/derived/topics/manifest.json
LEMMAS     := data/derived/lemmas/lemmas.parquet
LEXICAL_LEMMA := data/derived/lexical_lemma/collocates.json

.PHONY: all payload derived raw cluster clean

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
$(SPEECHES) $(MEETINGS) &: $(RAW_FILES) scripts/01_build_parquet.py $(LIB) config/dataset-pin.json
	$(PY) scripts/01_build_parquet.py

$(NORM): $(SPEECHES) scripts/02_normalise.py $(LIB) config/entities.csv config/country_aliases.csv config/council_membership.csv
	$(PY) scripts/02_normalise.py

$(FLAGGED): $(NORM) scripts/03_lexicon.py $(LIB) config/lexicon.yml config/lexicon.lock.json annotations/lexicon/annotations.csv
	$(PY) scripts/03_lexicon.py

# --- Analysis artefacts -------------------------------------------------------
$(SERIES): $(FLAGGED) scripts/04_series.py $(LIB) config/events.csv
	$(PY) scripts/04_series.py

$(LEXICAL): $(FLAGGED) scripts/05_lexical.py $(LIB) config/stopwords.txt
	$(PY) scripts/05_lexical.py

$(KWIC): $(FLAGGED) scripts/08_kwic.py $(LIB)
	$(PY) scripts/08_kwic.py

$(SPEECHES_WEB): $(FLAGGED) $(MEETINGS) scripts/09_export_speeches.py $(LIB)
	$(PY) scripts/09_export_speeches.py

$(COUNTRIES): $(FLAGGED) scripts/11_countries.py $(LIB) config/entities.csv
	$(PY) scripts/11_countries.py

# 12 writes into derived/countries/ beside 11, which export_web copies wholesale.
$(SPEAKER_KEYNESS): $(FLAGGED) scripts/12_speaker_keyness.py $(LIB) config/stopwords.txt
	$(PY) scripts/12_speaker_keyness.py

# Deterministic — same corpus, same seed, byte-identical CSVs. 15 refuses to run
# without the candidates file it draws, because the gold block reports on a
# sample that exists; the coded rows live in annotations/, which is committed.
$(GOLD): $(NORM) scripts/13_gold_sample.py $(LIB) config/lexicon.yml $(wildcard annotations/genocide/*)
	$(PY) scripts/13_gold_sample.py

$(USAGE): $(NORM) $(GOLD) scripts/15_usage.py $(LIB) config/lexicon.yml $(wildcard model_annotations/genocide/*) $(wildcard model_annotations/genocide/runs/*/*) $(wildcard annotations/genocide/*)
	$(PY) scripts/15_usage.py

derived: $(SERIES) $(LEXICAL) $(KWIC) $(SPEECHES_WEB) $(COUNTRIES) $(SPEAKER_KEYNESS) $(GOLD) $(USAGE)

# --- The site's payload -------------------------------------------------------
$(PAYLOAD): $(SERIES) $(LEXICAL) $(KWIC) $(SPEECHES_WEB) $(COUNTRIES) $(SPEAKER_KEYNESS) $(USAGE) scripts/export_web.py $(LIB) tests/contract/payload.json
	$(PY) scripts/export_web.py

payload: $(PAYLOAD)

# --- Cluster-only steps (docs/CLUSTER.md) -------------------------------------
# Not part of the release pipeline: they need requirements-cluster.txt and a
# GPU or spaCy model. 10 feeds an optional second run of 05 over lemmas, into
# its own directory; the surface tables the site reads are never overwritten.
$(EMBEDDINGS): $(FLAGGED) scripts/06_embed.py $(LIB) config/embedding_models.yml
	$(PY) scripts/06_embed.py

$(TOPICS): $(FLAGGED) $(EMBEDDINGS) scripts/07_topics.py $(LIB)
	$(PY) scripts/07_topics.py

$(LEMMAS): $(FLAGGED) scripts/10_lemmatise.py $(LIB)
	$(PY) scripts/10_lemmatise.py

$(LEXICAL_LEMMA): $(FLAGGED) $(LEMMAS) scripts/05_lexical.py $(LIB) config/stopwords.txt
	$(PY) scripts/05_lexical.py --vocabulary lemma

cluster: $(EMBEDDINGS) $(TOPICS) $(LEXICAL_LEMMA)

clean:
	rm -rf data/derived data/interim web/static/data
