"""The grammatical frames the node appears in, as a codebook over the concordance.

The review of 1 September 2026 (§3.6, item 2) asks for a regex pass over the
6,092 occurrences of *genocide*: *acts of genocide*, *crime of genocide*, *risk
of genocide*, *amounts to genocide*, *so-called genocide*, *genocide against X*,
*genocidal intent*, and the noun / adjective / perpetrator-noun split. The
question behind it is not lexical but pragmatic: the same word does nomination,
legal qualification, hedging, distancing, denial and prevention, and the counts
already published cannot tell those apart.

This module holds the inventory and the classifier. It is a **codebook**, not a
list of regexes: every frame carries a name, a gloss saying which discursive act
it evidences, the pattern that finds it, and an example taken verbatim from the
concordance with the line it was taken from, so that a reader can go and check
it. `tests/test_node_frames.py` asserts that every example still lands in the
frame it is filed under, which is what stops the codebook and the code drifting
apart the way a comment does.

Three decisions are made here rather than in the step, because they are what the
published numbers mean.

**A window, not a parse.** Each occurrence is classified from a ±90-character
window with the node marked, and nothing else. There is no parser in this
repository, spaCy is not a dependency, and a dependency parse of 6,092 windows
would be a second instrument to validate for a distinction most of these frames
do not need: *acts of*, *crime of*, *so-called* and *against* are adjacency, and
adjacency is what a window measures. What the window cannot do is resolve a
subject across a clause boundary — "five individuals accused of war crimes and,
in one case, genocide continue to evade the Court" reads as if the genocide
continued — so the gap inside a pattern refuses to cross a sentence end
(:data:`GAP`), and the residue is reported rather than hidden.

**First match wins, and the order is the argument.** An occurrence can satisfy
several patterns: *the crime of genocide, war crimes and crimes against
humanity* is both a legal qualification and a catalogue entry. The codebook is
therefore ordered, and :func:`classify` returns the first frame that matches,
while :func:`matches` returns all of them so the overlap is measurable rather
than lost. The order runs in five tiers, and each tier exists to keep the tier
below it honest:

1. **Citation** — the word is part of a proper name (the Convention, the Special
   Adviser). These are not claims about any event, and if they were left in they
   would be counted as prevention or as legal qualification, which is what the
   title of the Convention would otherwise look like.
2. **Footing** — what the speaker does with the label: contests it, applies it,
   hedges it to constituent acts, or names it as itself an offence.
3. **Catalogue** — the word as one item of the standing atrocity-crimes list.
   This is the single largest construction in the corpus and, as §4.2 of the
   review notes, the model runs code it exactly like a substantive accusation.
   Separating it is most of the value of this artefact.
4. **Modality and role** — what the mention does about an event: anticipates it,
   demands its prevention, commemorates it, holds someone to account, or
   attributes agency.
5. **Bare nominal** — the remaining head-noun constructions: *genocide against
   X*, and the definite reference to a case already named.

**The residue is a category.** `unframed` is written for every occurrence no
pattern reached, it is published beside the rest, and its share by year is part
of the artefact. A codebook that classified everything would be a codebook whose
patterns had been widened until they meant nothing.

The morphological split is a *second axis*, not a frame. A frame that fired only
on one wordform would duplicate it. :func:`morphology` folds the surface form
into noun, adjective, perpetrator noun or other, and the step publishes every
distinct form with its count so that a spelling nobody expected is visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from . import text as text_lib

#: Context characters kept either side of the node. Wider than any pattern
#: needs, so that the treaty title — sixty characters from *Convention* to
#: *Genocide* — fits with room for the OCR's spacing, and narrower than the
#: concordance's own ±150, because a cue five clauses away is not a frame.
WIDTH: Final = 90

#: The node's boundaries inside a window. Single guillemets: they let a pattern
#: say "immediately left of the node" without a lookaround, and no occurrence in
#: this corpus carries one in its context — the record uses straight and curly
#: quotes only, and :func:`window` strips them anyway rather than trusting that
#: to stay true. Named by code point, as `lib.kwic` names the curly quotes and
#: for the same reason: on screen they are a hair from `<` and `>`, and a
#: pattern in this file turns on which of the two it is.
NODE_OPEN: Final = chr(0x2039)   # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
NODE_CLOSE: Final = chr(0x203A)  # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK

#: The four quotation marks that can scare-quote the node, as two character
#: classes. The OCR carries both the straight and the curly pair and they are
#: indistinguishable in most editors, so the curly ones are named by code point.
_OPEN_QUOTES: Final = "\"'" + chr(0x2018) + chr(0x201C)
_CLOSE_QUOTES: Final = "\"'" + chr(0x2019) + chr(0x201D)

#: One character of filler inside a pattern: anything that is neither a node
#: marker nor the start of a sentence break. Without the lookahead a cue would
#: reach across a full stop into the previous sentence, which is how a window
#: classifier invents a reading — "brought to justice. Genocide and other grave
#: breaches" was counted as accountability until this was added. `Mr.` and
#: `S/PV.7155` also stop a gap, which is conservative in the right direction:
#: it withholds a frame rather than asserting one.
GAP: Final = rf"(?:(?!\.\s)[^{NODE_OPEN}{NODE_CLOSE}])"


@dataclass(frozen=True)
class Frame:
    """One construction, with everything needed to argue about it."""

    name: str
    #: The discursive act it evidences, in one sentence.
    gloss: str
    #: Matched case-insensitively against the window.
    pattern: str
    #: Attested in the corpus, quoted from the line named by `example_id`.
    example: str
    #: The KWIC line the example came from, so a reader can go and read it.
    example_id: str
    #: Matched case-sensitively. Only `named_case` uses one: the difference
    #: between *the Rwandan genocide* and *the genocide* is capitalisation, and
    #: an ignore-case pass would erase exactly the evidence that frame needs.
    cased: str | None = None


#: The frames, in the order :func:`classify` tries them. See the module
#: docstring for the five tiers and why each precedes the next.
CODEBOOK: Final[tuple[Frame, ...]] = (
    # --- 1. Citation: the mention is part of a name --------------------------
    Frame(
        name="legal_instrument",
        gloss=(
            "The word inside the name of an instrument — the 1948 Convention, a "
            "statute, an article. Citation of the law, not a claim that anything "
            "happened."
        ),
        pattern=(
            rf"\b(convention|covenant|statute|protocol|treaty|article\s+[ivx0-9]+)\b"
            rf"{GAP}{{0,70}}{NODE_OPEN}"
            rf"|{NODE_CLOSE}\s*conventions?\b"
        ),
        example="the Convention on the Prevention and Punishment of the Crime of Genocide",
        example_id="UNSC_1998_SPV.3953_spch0001#1",
    ),
    Frame(
        name="mandate_or_office",
        gloss=(
            "The word inside the name of a United Nations office or mandate. A "
            "delegation thanking the Special Adviser is not qualifying an event, "
            "and the prevention frame would otherwise absorb every such thanks."
        ),
        pattern=(
            rf"\b(special\s+(adviser|advisor|representative|rapporteur)|joint\s+office|office"
            rf"|framework\s+of\s+analysis|focal\s+point|under-secretary-general)\b"
            rf"{GAP}{{0,45}}\bprevention\s+(and\s+punishment\s+)?of\s+(the\s+crime\s+of\s+)?{NODE_OPEN}"
            rf"|\b(special\s+(adviser|advisor|representative)|office)\s+on\s+{NODE_OPEN}"
            rf"|{NODE_CLOSE}\s*prevention\s+(office|and\s+the\s+responsibility)"
        ),
        example="his Special Adviser on the Prevention of Genocide",
        example_id="UNSC_2007_SPV.5703_spch0028#1",
    ),
    # --- 2. Footing: what the speaker does with the label --------------------
    Frame(
        name="distancing",
        gloss=(
            "The label marked as somebody else's: scare quotes around the node, "
            "*so-called*, *alleged*, or *allegations of*. The contested use this "
            "study most wants to see, and the one a keyness table cannot show."
        ),
        pattern=(
            rf"\b(so[- ]called|alleged|allegedly|purported|purportedly|supposed|supposedly"
            rf"|self[- ]styled|false|falsely|fabricated|invented|baseless|unfounded|groundless"
            rf"|fictitious|pretext|pretence)\b{GAP}{{0,25}}{NODE_OPEN}"
            rf"|\b(allegations?|accusations?|claims?|assertions?|rhetoric|narrative|myth|slander"
            rf"|libel|propaganda)\s+(of|about)\s+{GAP}{{0,15}}{NODE_OPEN}"
            # A matched pair only. A closing quote alone would take every
            # possessive: `the genocide's 1 million victims` is not scare-quoted.
            rf"|[{_OPEN_QUOTES}]\s*{NODE_OPEN}{GAP}*{NODE_CLOSE}{GAP}{{0,25}}[{_CLOSE_QUOTES}]"
        ),
        example='he asked himself whether the term "genocide" might be applicable',
        example_id="UNSC_2000_SPV.4127_spch0004#2",
    ),
    Frame(
        name="qualification",
        gloss=(
            "The speech act of applying the label: *constitutes*, *amounts to*, "
            "*described as*, *recognized as*, or the bare copula. This is "
            "nomination in its most explicit form."
        ),
        pattern=(
            rf"\b(amounts?|amounted|amounting|constitut\w+|tantamount|equivalent|qualif\w+"
            rf"|characteriz\w+|characteris\w+|describ\w+|labell?\w*|termed|deem\w+|recogniz\w+"
            rf"|recognis\w+|declar\w+|classif\w+|akin\s+to|equat\w+|synonym\w*"
            rf"|nothing\s+less\s+than|nothing\s+short\s+of)\b{GAP}{{0,25}}{NODE_OPEN}"
            rf"|\b(is|was|are|were|be|been)\s+(a\s+|an\s+|the\s+|not\s+|clearly\s+|indeed\s+"
            rf"|simply\s+|plain\s+){{0,2}}{NODE_OPEN}"
            rf"|\bcall(s|ed|ing)?\s+(it|this|that|them|these)\s+(a\s+|an\s+|the\s+)?{NODE_OPEN}"
        ),
        example="ISIS crimes against Yazidis constitute genocide",
        example_id="UNSC_2021_S_2021_460_spch0003#1",
    ),
    Frame(
        name="crime_of",
        gloss=(
            "*the crime of genocide*: the offence named as a legal category. The "
            "Convention's own head noun, and the register in which a court, "
            "rather than a speaker, has decided."
        ),
        pattern=rf"\bcrimes?\s+of\s+(the\s+)?{NODE_OPEN}|{NODE_CLOSE}\s+is\s+a\s+crime",
        example="the indictment now includes the crime of genocide",
        example_id="UNSC_2001_SPV.4429_spch0023#1",
    ),
    Frame(
        name="acts_of",
        gloss=(
            "*acts of genocide*, *cases of genocide*: the countable-instance "
            "hedge. Saying that acts of genocide occurred is weaker than saying "
            "genocide occurred, and 1994 turned on the difference."
        ),
        pattern=(
            rf"\b(acts?|cases?|instances?|episodes?|forms?)\s+of\s+(the\s+)?{NODE_OPEN}"
        ),
        example="is an act of genocide",
        example_id="UNSC_1992_SPV.3135_spch0010#3",
    ),
    Frame(
        name="intent_or_definition",
        gloss=(
            "*genocidal intent*, *intent to destroy*, *the definition of "
            "genocide*: the Convention's mental element and its wording, argued "
            "over as law rather than asserted as fact."
        ),
        pattern=(
            rf"\b(intent\w*|dolus|mens\s+rea|in\s+whole\s+or\s+in\s+part"
            rf"|elements?\s+of\s+the\s+crime|definition|defined)\b{GAP}{{0,30}}{NODE_OPEN}"
            rf"|{NODE_OPEN}genocidal{NODE_CLOSE}\s+(intent\w*|design|purpose|plan)"
            rf"|{NODE_CLOSE}\s+(means|is\s+defined|as\s+defined)\b"
        ),
        example="the factors allowing the inference of genocidal intent",
        example_id="UNSC_2018_SPV.8381_spch0012#1",
    ),
    Frame(
        name="denial_or_ideology",
        gloss=(
            "*genocide denial*, *genocide ideology*, *glorification*: denial "
            "named as an offence. Meta-discourse about the word, not a use of "
            "it — and the speaker here is almost always condemning, not denying."
        ),
        pattern=(
            rf"{NODE_CLOSE}\s+(denial|deniers?|ideolog\w+|revisionism|negation|denialism)\b"
            rf"|\b(denial|denying|deny|denies|denied|denier\w*|revisionis\w+|glorif\w+|negation"
            rf"|minimiz\w+|minimis\w+|trivializ\w+)\b{GAP}{{0,25}}{NODE_OPEN}"
        ),
        example="the denial of genocide in the situations under the jurisdiction of the Mechanism",
        example_id="UNSC_2020_S_2020_1236_spch0009#1",
    ),
    Frame(
        name="occurrence",
        gloss=(
            "*genocide occurred*, *genocide continues*, *there is genocide*: the "
            "event predicated directly, with no legal or evidential hedge in the "
            "clause."
        ),
        pattern=(
            rf"{NODE_CLOSE}\s+(occurr\w+|occurs|took\s+place|takes\s+place|happen\w+|continu\w+"
            rf"|unfold\w+|began|begins|started|ended|is\s+under\s+way|was\s+committed"
            rf"|has\s+been\s+committed|is\s+being\s+committed|raged|swept)\b"
            rf"|\bthere\s+(is|was|has\s+been|have\s+been|are|were)\s+"
            rf"(a\s+|an\s+|the\s+|no\s+)?{NODE_OPEN}"
        ),
        example="unfortunately that genocide occurred in Rwanda",
        example_id="UNSC_2002_SPV.4538Resumption1_spch0043#3",
    ),
    # --- 3. Catalogue --------------------------------------------------------
    Frame(
        name="atrocity_triad",
        gloss=(
            "The word as one item of the standing list — *war crimes, crimes "
            "against humanity, ethnic cleansing*. Formulaic, and the largest "
            "single construction in this corpus; the model runs code it exactly "
            "as they code a substantive accusation."
        ),
        pattern=(
            rf"\b(war\s+crimes?|crimes?\s+against\s+humanity|ethnic\s+cleansing"
            rf"|crimes?\s+of\s+aggression|mass\s+atrocit\w+)\b{GAP}{{0,25}}{NODE_OPEN}"
            rf"|{NODE_CLOSE}{GAP}{{0,25}}\b(war\s+crimes?|crimes?\s+against\s+humanity"
            rf"|ethnic\s+cleansing|crimes?\s+of\s+aggression|mass\s+atrocit\w+)\b"
        ),
        example="war crimes, crimes against humanity and genocide",
        example_id="UNSC_2016_SPV.7829_spch0006#1",
    ),
    # --- 4. Modality and role ------------------------------------------------
    Frame(
        name="risk_or_threat",
        gloss=(
            "*risk of genocide*, *another genocide*, *the signs of genocide*: "
            "the event as something that has not happened yet. Irrealis, and the "
            "vocabulary the prevention agenda is argued in."
        ),
        pattern=(
            rf"\b(risks?|threats?|threaten\w*|danger\w*|spectre|specter|imminent|potential"
            rf"|possibility|warning\s+signs?|another|new|next|repeat|verge|brink|escalat\w+"
            rf"|lead\s+to|slide|precursors?)\b{GAP}{{0,25}}{NODE_OPEN}"
        ),
        example="the danger of renewed genocide in the region",
        example_id="UNSC_1999_SPV.3987_spch0015#1",
    ),
    Frame(
        name="prevention",
        gloss=(
            "*prevention of genocide*, *prevent genocide*, *protect populations "
            "from genocide*: the duty, stated as a norm. What the Council says "
            "it is for."
        ),
        pattern=(
            rf"\b(prevent\w*|protect\w*|avert\w*|early\s+warning|halt\w*|stop\w*|end|ending"
            rf"|prohibit\w*|combat\w*|deter\w*|responsibility\s+to\s+protect|save|spare"
            rf"|put\s+an\s+end)\b{GAP}{{0,25}}{NODE_OPEN}"
            rf"|{NODE_CLOSE}\s+prevention\b"
        ),
        example="our obligation to prevent genocide",
        example_id="UNSC_2004_SPV.5100Resumption1_spch0021#3",
    ),
    Frame(
        name="commemoration",
        gloss=(
            "*the anniversary of the genocide*, *the victims of the genocide*, "
            "*never again*: the event as memory. The register the Council speaks "
            "in every April, and the one the review found the models code as "
            "assertion without being told to."
        ),
        pattern=(
            rf"\b(anniversar\w+|commemorat\w+|remembrance|memorial|memory|honour\w*|honor\w*"
            rf"|mourn\w*|tribute|never\s+again|years?\s+(since|after|ago))\b"
            rf"{GAP}{{0,25}}{NODE_OPEN}"
            # Bare `victims of genocide` is an argument about a population, not a
            # commemoration; the determiner is what makes it a named remembering.
            rf"|\b(victims?|survivors?)\s+of\s+(the|this|that)\s+{NODE_OPEN}"
        ),
        example="the twentieth anniversary of the Rwandan genocide",
        example_id="UNSC_2014_SPV.7196_spch0014#1",
    ),
    Frame(
        name="accountability",
        gloss=(
            "*convicted of genocide*, *genocide fugitives*, *impunity for "
            "genocide*: the event inside a legal process that has already "
            "started. A court, not a speaker, is the one asserting."
        ),
        pattern=(
            rf"\b(convicted|convictions?|indicted|indictments?|charged|prosecut\w+|trials?"
            rf"|sentenc\w+|acquitt\w+|guilty|impunity|accountab\w+|fugitives?|extradit\w*"
            rf"|apprehend\w*|at\s+large)\b{GAP}{{0,25}}{NODE_OPEN}"
            rf"|{NODE_CLOSE}\s+(convicts?|fugitives?|suspects?|indictees?|trials?|convictions?"
            rf"|indictments?|prosecutions?|charges?)\b"
        ),
        example="Sending genocide convicts to serve out the remainder of their sentences",
        example_id="UNSC_2018_SPV.8416_spch0027#18",
    ),
    Frame(
        name="perpetration",
        gloss=(
            "*committed genocide*, *those responsible for genocide*, *a policy "
            "of genocide*: agency attributed to somebody. Accusation, before any "
            "court has been involved."
        ),
        pattern=(
            rf"\b(committ\w+|commit|commits|perpetrat\w+|carr\w+\s+out|responsib\w+|accus\w+"
            rf"|suspect\w+|architects?|authors?|masterminds?|orchestrat\w+|wag\w+|conduct\w+"
            rf"|engag\w+|planned|planning|inflict\w+|unleash\w+|behind|participat\w+)\b"
            rf"{GAP}{{0,25}}{NODE_OPEN}"
            rf"|\b(polic(y|ies)|campaigns?|plans?|programmes?|practices?|projects?|strateg\w+)"
            rf"\s+of\s+(the\s+)?{NODE_OPEN}"
        ),
        example="bring those responsible for the genocide to justice",
        example_id="UNSC_1998_SPV.3875Resumption1_spch0018#2",
    ),
    # --- 5. Bare nominal -----------------------------------------------------
    Frame(
        name="directed_against",
        gloss=(
            "*genocide against X*: the victim group named in the complement. The "
            "fullest form of nomination, and the construction *genocide against "
            "the Tutsi* made canonical."
        ),
        pattern=(
            rf"{NODE_CLOSE}\s+(against|targeting|aimed\s+at|directed\s+against"
            rf"|perpetrated\s+against|committed\s+against|inflicted\s+on|visited\s+upon)\b"
        ),
        example="Given the nature of the genocide against the Tutsi in Rwanda",
        example_id="UNSC_2019_SPV.8668Resumption1_spch0002#2",
    ),
    Frame(
        name="named_case",
        gloss=(
            "*the Rwandan genocide*, *the genocide in Srebrenica*, *the 1994 "
            "genocide*: the word used as the settled name of a case everyone "
            "present agrees on. Nomination that is no longer being argued."
        ),
        pattern=(
            rf"\b(during|after|before|since|following|throughout|amid)\s+the\s+{NODE_OPEN}"
            rf"|\b\d{{4}}\s+{NODE_OPEN}|{NODE_CLOSE}\s+of\s+\d{{4}}"
        ),
        cased=(
            rf"{NODE_CLOSE}\s+(in|of|at)\s+(the\s+)?[A-Z]"
            rf"|\b([Tt]he|[Tt]his|[Tt]hat)\s+([A-Z][\w'{chr(0x2019)}-]+\s+){{1,3}}{NODE_OPEN}"
        ),
        example="the actions of the United Nations during the 1994 genocide in Rwanda",
        example_id="UNSC_2000_SPV.4127_spch0001#1",
    ),
)

#: What an occurrence no pattern reached is called. A category, published beside
#: the others, not a gap in the table.
UNFRAMED: Final = "unframed"

#: Every frame name plus the residue, in codebook order, for a consumer that
#: must write all of them and zero-fill the rest.
FRAME_NAMES: Final[tuple[str, ...]] = (*(frame.name for frame in CODEBOOK), UNFRAMED)

_COMPILED: Final[tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]] = tuple(
    (
        frame.name,
        (re.compile(frame.pattern, re.IGNORECASE),)
        + ((re.compile(frame.cased),) if frame.cased else ()),
    )
    for frame in CODEBOOK
)


def window(left: str, keyword: str, right: str) -> str:
    """One occurrence's context with the node marked, ready to match against.

    A space is inserted either side of the markers so that a pattern anchored on
    the node can use `\\s+` and word boundaries uniformly; the concordance's own
    left and right fields arrive stripped, so without the padding a closing
    marker would sit hard against the next word and defeat every right-hand
    pattern.

    Any guillemet in the context is dropped. None occurs in this corpus, and the
    check costs one pass over 180 characters; what it buys is that a future
    source cannot smuggle a node boundary into the text being classified.
    """
    strip = str.maketrans("", "", NODE_OPEN + NODE_CLOSE)
    return (
        f"{left.translate(strip)} {NODE_OPEN}{keyword.translate(strip)}{NODE_CLOSE} "
        f"{right.translate(strip)}"
    )


def window_at(source: str, start: int, end: int, width: int = WIDTH) -> str:
    """The window around ``source[start:end]``, from a body and a span.

    Through :func:`lib.text.window`, so the context a frame is read off is the
    context the concordance shows, flattened by the same function.
    """
    return window(*text_lib.window(source, start, end, width))


def matches(text: str) -> tuple[str, ...]:
    """Every frame whose pattern the window satisfies, in codebook order.

    Published beside the primary assignment. Precedence is a decision, and a
    decision a reader cannot see the cost of is a decision they cannot argue
    with: the artefact reports both "how many occurrences this frame won" and
    "how many it matched at all".
    """
    return tuple(
        name for name, patterns in _COMPILED if any(p.search(text) for p in patterns)
    )


def classify(text: str) -> str:
    """The frame a window is filed under: the first one that matches.

    :data:`UNFRAMED` when none does. See the module docstring for the tiers the
    order is built from.
    """
    for name, patterns in _COMPILED:
        if any(p.search(text) for p in patterns):
            return name
    return UNFRAMED


# --- The second axis: the wordform itself ---------------------------------
#
# `\bgenocid\w*` folds four things into one count. §3.4 of the review makes the
# point about `genocidaire(s)`, which is an actor label for the ex-FAR and
# Interahamwe in the DRC debates and not the word as event qualification at all;
# the two model runs disagree on exactly those rows. The categories below were
# fixed after counting what the corpus actually holds — 5,685 `genocide`, 313
# `genocidal`, 62 `genocides`, 29 `genocidaires`, 2 `genocidaire`, 1 `genocida`
# — and `other` exists because the last of those is a real OCR spelling that a
# closed vocabulary would have had to either swallow or crash on.

#: The morphological categories, in the order a table lists them.
FORMS: Final[tuple[str, ...]] = ("noun", "adjective", "perpetrator_noun", "other")

_MORPHOLOGY: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    # Before the adjective: `genocidaire` would otherwise be read as one.
    (re.compile(r"^genocidaires?$", re.IGNORECASE), "perpetrator_noun"),
    (re.compile(r"^genocidal(ly)?$", re.IGNORECASE), "adjective"),
    (re.compile(r"^genocides?$", re.IGNORECASE), "noun"),
)


def morphology(keyword: str) -> str:
    """The wordform's category: noun, adjective, perpetrator noun, or other.

    `other` is not a failure. It is where a form the categories were not built
    for arrives, and the step publishes every surface form with its count beside
    this, so that a spelling nobody expected is a line in a table rather than a
    silent reassignment.
    """
    folded = keyword.strip().lower()
    for pattern, name in _MORPHOLOGY:
        if pattern.match(folded):
            return name
    return "other"


def codebook_rows() -> list[dict[str, object]]:
    """The codebook as JSON, with each frame's position in the precedence order.

    Written into the artefact rather than only into this file: a reader holding
    the JSON should be able to see which pattern produced which count, and in
    what order the patterns were tried, without the repository beside them.
    """
    return [
        {
            "frame": frame.name,
            "precedence": position,
            "gloss": frame.gloss,
            "pattern": frame.pattern,
            "cased_pattern": frame.cased,
            "example": frame.example,
            "example_line": frame.example_id,
        }
        for position, frame in enumerate(CODEBOOK, start=1)
    ]
