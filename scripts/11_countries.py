"""Per-country table: the artefact a map would depict, without the map.

Reads speeches_flagged.parquet and writes data/derived/countries/countries.json
plus a findings note.

`docs/PLAN.md` §7 says nothing may precede the table it depicts, and §3 gates the
actor view on a declared minimum sample. This step builds that table and declares
that minimum. It draws nothing: the visualisation is a separate decision, and it
is meant to be made after someone has read these numbers rather than instead of
reading them.

Everything the step is careful about is a way for a per-country table to be
wrong while looking right:

- a speaker missing from `config/entities.csv` would be dropped by the join and
  leave a total that is quietly short, so an untyped speaker stops the run, the
  same stance `02_normalise.py` takes;
- a rate over a handful of speeches outranks every real one, so rates are
  withheld below `actors.MIN_SPEECHES` rather than published small;
- three speakers share a successor's ISO 3166 code with a living state, so the
  collisions are computed and reported rather than left for the filled map to
  resolve by overdrawing — it reads them and refuses those codes;
- every aggregate is reconciled against the corpus totals before anything is
  written, per period and per measure.

Usage:
    python scripts/11_countries.py [--minimum 100]

Requires an x64 Python 3.12 — pyarrow publishes no 32-bit wheel.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import actors, artifacts, console, council, entities, frames, lexicon, series
from lib.paths import (
    COUNCIL_MEMBERSHIP,
    COUNTRIES,
    COUNTRY_ALIASES,
    ENTITIES,
    EXPECTED_SPEECHES,
    EXPECTED_TOKENS,
    EXPECTED_WORDS,
    LEXICON,
    ROOT,
    SPEECHES_FLAGGED,
    ensure_dirs,
    rel,
    write_note,
)

#: The measures this table carries, mirroring `04_series.py`'s TRACKED so the
#: actor view and the temporal series argue about the same two objects.
#: `atrocity_core` is a union and therefore has no occurrence count of its own;
#: `lib.series.measure` withholds one rather than summing overlapping members.
TRACKED: list[tuple[str, str]] = [
    ("terms", "genocide_qualification"),
    ("sets", "atrocity_core"),
]

#: Columns read from the corpus. The whole table is 100 columns wide and 419 MB
#: of it is speech text this step never looks at.
COLUMNS = [
    "row_id",
    "year",
    "country_org",
    "meeting_symbol",
    "words",
    # Kept for the codebook assertion below, never divided by.
    "tokens",
    "entity_type",
    "iso3",
    "un_regional_group",
    "speaker_group",
    "lat",
    "lon",
]


def measure_attributes(lex: lexicon.Lexicon, kind: str, name: str) -> dict[str, object]:
    """How the artefact describes a measure, matching 04's vocabulary.

    A derived measure is described like a term and carries what it is derived
    from, because a reader looking at a rate labelled `genocide_qualification`
    is owed the arithmetic behind the name in the artefact rather than only in
    the configuration.
    """
    if kind == "terms" and name in lex.derived:
        measure = lex.derived[name]
        return {
            "kind": kind,
            "tier": measure.tier,
            "register": measure.register,
            "derived_from": measure.minuend,
            "derived_minus": list(measure.subtrahends),
        }
    if kind == "terms":
        term = lex.terms[name]
        return {"kind": kind, "tier": term.tier, "register": term.register}
    return {"kind": kind, "members": lex.sets[name]}


def load_corpus(minimum: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the corpus and the crosswalk, refusing to continue on any drift."""
    columns = COLUMNS + [
        column
        for kind, name in TRACKED
        for column in series.columns_for(kind, name)
        if column is not None
    ]
    speeches = frames.read(SPEECHES_FLAGGED, columns=columns)

    # Both totals, and for different reasons. The codebook's token sum says the
    # corpus is the one the dataset documents; the word sum says the
    # denominator this table divides by is the one every other step divides by.
    if (
        len(speeches) != EXPECTED_SPEECHES
        or int(speeches["tokens"].sum()) != EXPECTED_TOKENS
        or int(speeches["words"].sum()) != EXPECTED_WORDS
    ):
        console.fail(
            "the corpus does not match the totals this table reconciles against",
            [
                f"{len(speeches):,} speeches, expected {EXPECTED_SPEECHES:,}",
                f"{int(speeches['tokens'].sum()):,} codebook tokens, expected "
                f"{EXPECTED_TOKENS:,}",
                f"{int(speeches['words'].sum()):,} words, expected {EXPECTED_WORDS:,}",
                "re-run 01_build_parquet.py through 03_lexicon.py",
            ],
        )

    crosswalk = entities.load_entities()
    if problems := entities.validate(crosswalk):
        console.fail("config/entities.csv is not internally consistent", problems)
    if problems := entities.validate_coverage(speeches["country_org"], crosswalk):
        console.fail(
            "the crosswalk does not cover every speaker, so a per-country total "
            "would be short by an unknown amount",
            problems,
        )
    if problems := actors.crosswalk_drift(speeches, crosswalk):
        console.fail(
            "config/entities.csv has changed since 02_normalise.py last ran",
            [*problems[:8], "re-run 02_normalise.py and everything after it"],
        )
    if problems := council.drift(speeches):
        console.fail(
            "config/council_membership.csv has changed since 02_normalise.py last ran",
            [*problems, "re-run 02_normalise.py and everything after it"],
        )
    if problems := actors.check_coverage(speeches["year"]):
        console.fail("the declared periods do not partition the corpus", problems)

    console.info(
        f"{speeches['country_org'].nunique():,} canonical speakers, "
        f"{int((crosswalk['entity_type'] == 'state').sum()):,} of them states in the crosswalk"
    )
    seated = int(speeches["speaker_group"].isin(actors.SEATED).sum())
    console.info(
        f"{seated:,} of {len(speeches):,} speeches ({seated / len(speeches):.1%}) were "
        "delivered from a seat on the Council"
    )
    console.info(f"minimum sample {minimum:,} speeches per speaker per period")
    return speeches, crosswalk


def build_measures(
    speeches: pd.DataFrame,
    lex: lexicon.Lexicon,
    slices: list[actors.Period],
    minimum: int,
) -> tuple[dict[str, object], dict[str, dict[str, pd.DataFrame]]]:
    """Every measure over every period, reconciled before it is kept."""
    payload: dict[str, object] = {}
    computed: dict[str, dict[str, pd.DataFrame]] = {}

    for kind, name in TRACKED:
        has_column, count_column = series.columns_for(kind, name)
        rows: list[dict[str, object]] = []
        computed[name] = {}

        for window in slices:
            subset = speeches[window.mask(speeches["year"])]
            frame = actors.by_country(subset, has_column, count_column)
            if problems := actors.reconcile(
                frame, subset, has_column, count_column, f"{name} / {window.key}"
            ):
                console.fail("the per-country aggregation does not reconcile", problems)
            frame = actors.withhold_below(frame, minimum)
            computed[name][window.key] = frame
            rows += actors.as_rows(frame, window.key)

        # The declared periods are asserted to partition the corpus before any of
        # this runs, so the four slices must add back up to the whole-corpus row.
        # Checking it here rather than trusting the assertion is cheap, and it is
        # the one place a mis-set period boundary would show as a number.
        if problems := actors.reconcile_periods(computed[name], slices):
            console.fail(f"{name}: the period slices do not add up to the whole", problems)

        payload[name] = {**measure_attributes(lex, kind, name), "rows": rows}
        cleared = int(computed[name][actors.WHOLE]["sufficient"].sum())
        console.info(
            f"{name:14s} {len(rows):,} rows over {len(slices)} periods; "
            f"{cleared} speakers clear the minimum over the whole corpus"
        )

    return payload, computed


def build_standing(
    speeches: pd.DataFrame,
    slices: list[actors.Period],
    computed: dict[str, dict[str, pd.DataFrame]],
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    """Who held a seat when they spoke, per speaker and per period.

    This is one block rather than a column on each measure: membership is a
    property of the speaker's speeches, not of the vocabulary in them, and
    repeating it inside `genocide` and `atrocity_core` would give the same fact
    two places to disagree with itself.

    The denominator is checked against the measure rows as well as against the
    corpus. Both are cut from the same subset by different code — `series` does
    the measures, `crosstab` does this — so an equal `held` is a real agreement
    between two paths rather than a comparison of a number with itself.
    """
    rows: list[dict[str, object]] = []
    frames_by_period: dict[str, pd.DataFrame] = {}

    for window in slices:
        subset = speeches[window.mask(speeches["year"])]
        frame = actors.standing(subset)
        if problems := actors.reconcile_standing(frame, subset, window.key):
            console.fail("the membership composition does not reconcile", problems)

        measured = computed["genocide"][window.key]
        disagreeing = [
            f"{name}: {int(frame.loc[name, 'held']):,} speeches here, "
            f"{int(measured.loc[name, 'held']):,} in the genocide measure"
            for name in frame.index
            if name in measured.index and int(frame.loc[name, "held"]) != int(measured.loc[name, "held"])
        ]
        if missing := sorted(set(measured.index) ^ set(frame.index)):
            disagreeing.append(
                f"{len(missing)} speakers appear in one table and not the other: "
                f"{', '.join(str(name) for name in missing[:6])}"
            )
        if disagreeing:
            console.fail(
                f"{window.key}: the composition and the measures disagree about a denominator",
                disagreeing[:8],
            )

        frames_by_period[window.key] = frame
        rows += actors.standing_as_rows(frame, window.key)

    whole = frames_by_period[actors.WHOLE]
    seated = int(whole["seated"].sum())
    console.info(
        f"standing        {len(rows):,} rows over {len(slices)} periods; "
        f"{seated:,} seated speeches, "
        f"{int((whole['seated_share'] == 1).sum()):,} speakers always seated, "
        f"{int((whole['seated'] == 0).sum()):,} never"
    )

    payload = {
        "groups": list(council.SPEAKER_GROUPS),
        "seated_groups": list(actors.SEATED),
        "seated_rule": (
            "The UN Charter provides two kinds of Council membership: five permanent "
            "members (P5) and ten elected ones (E10). A speech counts as 'seated' when "
            "its speaker held one of those places in the year it was delivered. The "
            "other three groups are not a single category: a non-member state was simply "
            "not on the Council that year, the UN Secretariat never can be, and a "
            "non-state speaker was invited to address it. All five counts are published "
            "separately so that distinction survives, and together they add up to every "
            "speech that speaker gave."
        ),
        "membership_rule": (
            "Membership belongs to a speech rather than to a country. The ten elected "
            "seats rotate, so no speaker has a single fixed status: Rwanda spoke as an "
            "elected member in 1994 and again in 2013-2014, and as a non-member in every "
            "other year of the corpus. Each row here is therefore a mixture rather than "
            "a label, and shading a speaker in one colour would erase that change. "
            "Unlike the rates elsewhere on this page, these figures are published however "
            "few speeches lie behind them: a share of a speaker's own known speeches is a "
            "fact about the record rather than an estimate drawn from it."
        ),
        "rows": rows,
    }
    return payload, frames_by_period


def build_periods(
    speeches: pd.DataFrame, slices: list[actors.Period], computed: dict, minimum: int
) -> list[dict[str, object]]:
    """Corpus totals per slice, so no consumer has to hard-code a denominator."""
    out = []
    for window in slices:
        subset = speeches[window.mask(speeches["year"])]
        frame = computed["genocide"][window.key]
        out.append(
            {
                **window.as_dict(),
                "speeches": len(subset),
                "words": int(subset["words"].sum()),
                "speakers": int(subset["country_org"].nunique()),
                "speakers_at_minimum": int(frame["sufficient"].sum()),
                "speeches_at_minimum": int(frame.loc[frame["sufficient"], "held"].sum()),
            }
        )
        window_min = out[-1]
        console.info(
            f"{window.key:10s} {window_min['speeches']:>7,} speeches  "
            f"{window_min['speakers']:>3} speakers  "
            f"{window_min['speakers_at_minimum']:>3} at or above {minimum} "
            f"({window_min['speeches_at_minimum'] / max(len(subset), 1):.1%} of speeches)"
        )
    return out


def build_note(
    speeches: pd.DataFrame,
    payload: dict,
    computed: dict[str, dict[str, pd.DataFrame]],
    standing_frames: dict[str, pd.DataFrame],
    speakers: list[dict[str, object]],
    minimum: int,
    required: int,
    prevalence: float,
) -> str:
    whole = computed["genocide"][actors.WHOLE]
    cleared = whole[whole["sufficient"]].sort_values("speech_rate", ascending=False)
    types = pd.Series({s["country_org"]: s["entity_type"] for s in speakers})
    groups = pd.Series({s["country_org"]: s["un_regional_group"] or "—" for s in speakers})

    def table(frame: pd.DataFrame, limit: int) -> list[str]:
        return [
            f"| {name} | {types.get(name, '?')} | {row.held:,.0f} | {row.speeches:,.0f} | "
            f"{row.speech_rate:.2%} | {row.token_rate:.2f} | {groups.get(name, '—')} |"
            for name, row in frame.head(limit).iterrows()
        ]

    # Whether a *rate* map has to resolve a shared code is a fact about the data,
    # not a hope. Count, per period, how many of the speakers sharing a code
    # carry a rate at all; if that is never more than one, the ambiguity binds on
    # a count map and nowhere else, and the note may say so.
    def carries_rate(key: str, name: str) -> bool:
        frame = computed["genocide"][key]
        return bool(name in frame.index and frame.loc[name, "sufficient"])

    contested = max(
        (
            sum(carries_rate(key, name) for name in names)
            for key in computed["genocide"]
            for names in payload["iso3_collisions"].values()
        ),
        default=0,
    )

    # Who changed standing, and how often. A speaker whose seated share sits
    # strictly between 0 and 1 spoke on both sides of the table at some point,
    # which is the case a single membership label would erase.
    seats = standing_frames[actors.WHOLE]
    both = seats[(seats["seated_share"] > 0) & (seats["seated_share"] < 1)]
    always = seats[seats["seated_share"] == 1]
    never = seats[seats["seated"] == 0]
    swung = both.assign(
        elected=lambda f: f[council.ELECTED],
        outside=lambda f: f[council.NON_MEMBER],
    ).sort_values("held", ascending=False)

    silent = cleared[cleared["speeches"] == 0]
    states = [s for s in speakers if s["entity_type"] == "state"]
    mappable = [s for s in speakers if s["mappable"]]
    collisions = payload["iso3_collisions"]
    below = whole[~whole["sufficient"]]
    non_state_cleared = [
        name for name in cleared.index if types.get(name) != "state"
    ]

    return "\n".join(
        [
            "# 11 — Per-country table",
            "",
            f"{len(speeches):,} speeches attributed to {len(speakers):,} canonical speakers, "
            f"cut into {len(payload['periods'])} periods and two measures. This is the table "
            "the actor view's map is drawn from, in either of its two encodings — and the "
            "`iso3_collisions` block below is what lets the filled one refuse a shared "
            "code instead of overdrawing it.",
            "",
            "## The minimum sample, and why it is this number",
            "",
            f"**{minimum} speeches.** A rate needs a denominator that can carry it, and the "
            "usual failure of a per-country map is that the loudest colour belongs to a "
            "country that spoke three times.",
            "",
            "The threshold is set by asking what a *blank* country claims. Observing no "
            f"`genocide`-bearing speech in n tries puts a 95% ceiling of roughly 3/n on that "
            f"speaker's underlying rate. The corpus-wide prevalence is **{prevalence:.2%}**, so "
            f"a zero only means \"quieter than the Council\" once n reaches **{required}**; "
            f"below that it means the sample was too short to tell. {minimum} is the round "
            f"number above {required}.",
            "",
            "**Rates below the minimum are withheld, not shrunk.** `speech_rate` and "
            "`token_rate` are written as `null` and `sufficient` is `false`; `held`, "
            "`speeches` and `occurrences` are always written, because a count is a fact and a "
            "rate is an estimate. This follows `lib.series.measure`, which returns an empty "
            "occurrence count for a set rather than a plausible-looking one.",
            "",
            "## What clears it",
            "",
            "| Period | Speeches | Speakers | At or above the minimum | Share of speeches covered |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {p['key']} | {p['speeches']:,} | {p['speakers']:,} | "
                f"{p['speakers_at_minimum']:,} | "
                f"{p['speeches_at_minimum'] / p['speeches']:.1%} |"
                for p in payload["periods"]
            ],
            "",
            f"{len(below):,} of {len(whole):,} speakers fall below the minimum over the whole "
            f"corpus and carry no rate. They account for "
            f"{int(below['held'].sum()):,} speeches "
            f"({int(below['held'].sum()) / len(speeches):.1%}) — the exclusion is wide in "
            "speakers and narrow in speeches, which is the shape a long tail of "
            "single-appearance civil-society briefers produces.",
            "",
            "**A whole-corpus row is not a sum of the period rows.** A speaker can clear the "
            "minimum over thirty-two years and clear it in none of them, and the periods have "
            "different denominators, so the two must not be mixed in one chart.",
            "",
            "## Highest rates over the whole corpus",
            "",
            "Speakers at or above the minimum, ranked by the share of their own speeches that",
            "carry `genocid*`. Read the denominator column: this is a rate table, and the",
            "countries at the top are not the ones that said the word most often.",
            "",
            "| Speaker | Type | Speeches | With `genocid*` | Rate | Per 100k words | UN group |",
            "|---|---|---:|---:|---:|---:|---|",
            *table(cleared, 15),
            "",
            f"{len(silent)} speakers clear the minimum and never use the word at all"
            + (f": {', '.join(silent.index[:6])}." if len(silent) else "."),
            "",
            "## Who held a seat when they spoke",
            "",
            "P5 and E10 are the Charter's two kinds of membership, and both are properties "
            "of a *speech*: the elected ten rotate, so a speaker has no single status. "
            f"{len(both):,} speakers spoke both from a seat and from outside one, "
            f"{len(always):,} only ever from a seat, and {len(never):,} never from one at "
            "all. A view that shades a speaker with one membership colour is wrong about "
            f"the first group, which is where the interesting cases are.",
            "",
            "| Speaker | Speeches | As E10 | As non-member | Seated share |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {name} | {int(row.held):,} | {int(row.elected):,} | "
                f"{int(row.outside):,} | {row.seated_share:.0%} |"
                for name, row in swung.head(12).iterrows()
            ],
            "",
            "The composition is written per speaker and per period in `standing`, as five "
            "counts that sum to the speaker's own denominator. All five are kept rather "
            "than only the seated total, because 'not seated' covers three different "
            "things: a state that was not on the Council, the UN Secretariat which never "
            "can be, and an invited non-state speaker.",
            "",
            "**These counts are written at every denominator**, unlike the rates above. A "
            "share of a speaker's own known speeches is a fact about the record — of the "
            "twelve speeches it gave, twelve were from a seat — not an estimate of a "
            "latent propensity from a sample of twelve. The minimum guards the second and "
            "has nothing to say about the first.",
            "",
            "## Non-state speakers",
            "",
            f"{len(speakers) - len(states):,} of {len(speakers):,} speakers are not states: "
            "IGOs, UN bodies, NGOs, local associations, universities and a handful of firms. "
            "They are in the table, with `entity_type`, and they are excluded from any map by "
            "the `mappable` flag rather than by having a null coordinate that a consumer might "
            "read as missing data. `config/entities.csv` refuses to give them a centroid at "
            "all, which is why the flag exists: there is nowhere on a globe that the UN "
            "Secretariat is.",
            "",
            f"{len(non_state_cleared)} non-state speakers clear the minimum"
            + (f" ({', '.join(non_state_cleared[:6])})." if non_state_cleared else "."),
            "",
            "## Historical states",
            "",
            "Three speakers in the corpus no longer exist. The crosswalk gives each its "
            "successor's ISO 3166 code so it can be placed at all, which makes the code "
            "ambiguous rather than absent:",
            "",
            "| Code | Speakers sharing it |",
            "|---|---|",
            *[f"| `{code}` | {', '.join(names)} |" for code, names in sorted(collisions.items())],
            "",
            "**They are kept as separate rows.** Merging Yugoslavia into Serbia would build a "
            "denominator no state ever had, and the successions are not clean: Yugoslavia "
            "speaks until 2002, Serbia and Montenegro from 2003 to 2006, Serbia from 2006, so "
            "the 2000-2009 slice contains all three. The collisions are published in "
            "`iso3_collisions` so that a consumer joining on ISO3 has to decide rather than "
            "discover.",
            "",
            f"In every period, at most **{contested}** of the speakers sharing a code carries a "
            "rate at all — the rest are below the minimum and blank. So a *rate* map never has "
            "to choose between them, and a *count* map always does. That asymmetry is worth "
            "knowing before deciding which quantity to colour.",
            "",
            "## Reconciliation",
            "",
            "Every aggregate is checked against the corpus it was cut from before anything is "
            "written — speeches, words, term-bearing speeches and occurrences, per measure "
            "and per period. A speaker lost to a failed join leaves a table that still looks "
            "complete and every rate in it still correct, so the total is the only place the "
            "loss shows.",
            "",
            "| Check | Table | Corpus |",
            "|---|---:|---:|",
            f"| Speeches | {int(whole['held'].sum()):,} | {len(speeches):,} |",
            f"| Words | {int(whole['words'].sum()):,} | {int(speeches['words'].sum()):,} |",
            f"| `genocid*` speeches | {int(whole['speeches'].sum()):,} | "
            f"{int(speeches['has_genocide'].sum()):,} |",
            f"| `genocid*` occurrences | {int(whole['occurrences'].sum()):,} | "
            f"{int(speeches['n_genocide'].sum()):,} |",
            "",
            "A `country_org` absent from `config/entities.csv` stops the run, as it does in "
            "02. So does a crosswalk edited since 02 last ran, because this table would then "
            "be built from a file the rest of the payload has never seen.",
            "",
            "## What a map may and may not do with this",
            "",
            f"- **Do not draw a slice below the minimum.** {len(below):,} speakers have no "
            "rate here on purpose; a map that fills them in has invented the number.",
            f"- **Filter on `mappable`, not on coordinates.** {len(mappable):,} speakers are "
            "states with a code and a centroid; the rest are not places.",
            "- **A centroid is navigation, not location.** `docs/PLAN.md` §3 is explicit: a "
            "centroid may help a reader find a country, and must never imply that the "
            "diplomat who spoke is at that point. The delegate speaks in New York.",
            "- **Colour what the table supports.** `speech_rate` is the share of a speaker's "
            "own speeches; `token_rate` is occurrences per 100,000 of its own words. Neither "
            "is a share of the Council, and a legend that says otherwise is wrong about the "
            "denominator rather than about the shading.",
            "- **Attribution is uneven.** `docs/CORPUS.md` §3 records that `country_org` is "
            "reliable for Council members and shakier for invited speakers, and OCR loss makes "
            "every count a floor. Both fall hardest on the small denominators this table "
            "already withholds.",
            "",
        ]
    ) + "\n"


def run(minimum: int) -> None:
    ensure_dirs()

    console.step("Reading the flagged corpus and the crosswalk")
    speeches, crosswalk = load_corpus(minimum)
    lex = lexicon.load()
    console.info(f"lexicon version {lex.version}, {len(lex.active)} active terms")

    prevalence = float(speeches["has_genocide"].mean())
    required = actors.informative_zero_minimum(prevalence)
    console.info(
        f"corpus prevalence {prevalence:.2%}; a zero is informative from {required} speeches"
    )
    if minimum < required:
        console.warn(
            f"the declared minimum {minimum} is below the {required} the corpus now requires "
            "for a zero to mean anything — re-declare actors.MIN_SPEECHES"
        )

    console.step("Aggregating by speaker")
    slices = actors.periods(int(speeches["year"].min()), int(speeches["year"].max()))
    measures, computed = build_measures(speeches, lex, slices, minimum)

    console.step("Reading who held a seat")
    standing, standing_frames = build_standing(speeches, slices, computed)

    console.step("Summarising periods")
    period_totals = build_periods(speeches, slices, computed, minimum)

    console.step("Describing speakers")
    try:
        speakers = actors.describe_speakers(speeches, crosswalk)
    except KeyError as exc:
        console.fail("a speaker would be dropped from the table", [str(exc.args[0])])
        raise  # unreachable; console.fail exits, and mypy cannot know that
    collisions = actors.iso3_collisions(speakers)
    console.info(f"{sum(1 for s in speakers if s['mappable']):,} speakers are mappable states")
    for code, names in sorted(collisions.items()):
        console.warn(f"{code} is carried by {len(names)} speakers: {', '.join(names)}")

    console.step("Writing")
    meta = artifacts.provenance(
        ROOT,
        "11_countries.py",
        inputs=[SPEECHES_FLAGGED],
        configs=[LEXICON, ENTITIES, COUNTRY_ALIASES, COUNCIL_MEMBERSHIP],
        extra={
            "lexicon_version": lex.version,
            "speeches": len(speeches),
            "words": int(speeches["words"].sum()),
            "codebook_tokens": int(speeches["tokens"].sum()),
            "speakers": int(speeches["country_org"].nunique()),
            "minimum_speeches": minimum,
            "informative_zero_minimum": required,
            "corpus_speech_prevalence": round(prevalence, 6),
            "rate_per_tokens": series.RATE_PER,
        },
    )
    payload = {
        "minimum_speeches": minimum,
        "minimum_speeches_rule": (
            f"A speaker gets no rate for any period in which it delivered fewer than "
            f"{minimum} speeches. That threshold is the point at which a zero starts to "
            f"mean something: across the corpus as a whole, {prevalence:.2%} of speeches "
            f"use this vocabulary, so seeing none of it in fewer than {required} speeches "
            f"is exactly what the Council average would predict. The counts are published "
            f"either way, because a count is a fact and a rate is an estimate."
        ),
        "rate_per_tokens": series.RATE_PER,
        "centroid_rule": (
            "A country's position on this map is a way of finding it, nothing more. It "
            "does not locate the speaker: every speech in this corpus was delivered in "
            "the Security Council chamber in New York."
        ),
        "iso3_collisions": collisions,
        "periods": period_totals,
        "countries": speakers,
        "standing": standing,
        "measures": measures,
    }

    with artifacts.atomic_directory(COUNTRIES) as staged:
        path = staged / "countries.json"
        artifacts.atomic_write_json(path, {"meta": meta, **payload})
        console.info(f"wrote countries.json  ({path.stat().st_size / 1e3:,.0f} kB)")

    note = write_note(
        "11_countries.md",
        build_note(
            speeches,
            {**payload, "periods": period_totals},
            computed,
            standing_frames,
            speakers,
            minimum,
            required,
            prevalence,
        ),
    )
    console.info(f"wrote {note.name}")
    console.info(f"payload in {rel(COUNTRIES)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--minimum",
        type=int,
        default=actors.MIN_SPEECHES,
        help="speeches a speaker needs in a period before its rates are published",
    )
    args = parser.parse_args()
    run(args.minimum)


if __name__ == "__main__":
    main()
