"""Speech text: line endings, the opening form of address, delivery language.

Three jobs, all of them prerequisites for honest lexical counting:

1. **Line endings.** The raw texts carry CRLF. Everything downstream — regex
   offsets, KWIC windows, the speech reader's highlight positions — assumes a
   single canonical text, so normalise once, here, and never again.

2. **The form of address.** Each speech opens with the segmentation marker the
   corpus authors cut on: ``Mr. Levitte (France) (spoke in French):``. Counting
   words without removing it over-represents country names, honorifics and the
   word "President". :func:`split_address` returns the offset where the body
   begins, so an offset into the body still maps back into the full text.

3. **The delivery language.** ``(spoke in French)`` / ``(interpretation from
   Arabic)`` records the language actually spoken — recoverable for 40% of the
   corpus, and the only handle on the translation caveat in docs/CORPUS.md §10.4.

:func:`modal_case`, at the end, is the fourth and smallest job: collapsing the
case collisions in the categorical fields so a groupby does not undercount.

Nothing here mutates text in place. Offsets stay valid.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

# --- 1. Line endings ------------------------------------------------------


def normalise_line_endings(text: str) -> str:
    """CRLF and lone CR to LF. The only whitespace edit made to speech text."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


# --- 2. The form of address ----------------------------------------------

# Personal honorifics observed at the start of a speech, in descending
# frequency. This list is derived from the corpus, not invented: 02_normalise
# reports its own match rate and a sample of misses, so a title that stops
# being covered shows up in notes/02_normalise.md rather than silently
# truncating nothing.
TITLES: tuple[str, ...] = (
    "Mr", "Mrs", "Ms", "Miss", "Sir", "Dame", "Dr", "Judge", "Archbishop",
    "Monsignor", "Bishop", "Prince", "Princess", "King", "Queen", "Lord",
    "Lady", "Baroness", "Baron", "Nana", "Sheikha", "Sheikh", "Dato",
    "Major", "Lieutenant", "President",
)

# Offices that appear as "The <office>:" — a closed set.
OFFICES: tuple[str, ...] = (
    "President", "PRESIDENT", "Deputy Secretary-General", "Secretary-General",
    "Acting President", "Vice-President", "Chairman", "Chairperson",
)


def _alternation(words: tuple[str, ...]) -> str:
    """Regex alternation, longest first so 'Sheikha' wins over 'Sheikh'."""
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


# ``Mr.Elarahy:`` and ``ArchbishopChullikatt:`` occur — the separating space is
# an OCR casualty — hence ``\.?\s*`` rather than a required space.
#
# The name segment forbids parentheses, colons and newlines, which is what
# keeps the match from running past the end of the address. The trailing
# ``(...)`` groups absorb the country and the language marker in either order.
ADDRESS_RE = re.compile(
    r"^[ \t]*"
    r"(?:"
    rf"The\s+(?:{_alternation(OFFICES)})"
    rf"|(?:{_alternation(TITLES)})\.?[ \t]*[^\s(:.][^(:\n]{{0,60}}?"
    r")"
    r"(?:[ \t]*\([^)\n]{0,90}\)){0,3}"
    r"[ \t]*:",
)


@dataclass(frozen=True)
class Address:
    """The opening form of address and where the speech body starts."""

    address: str      # "Mr. Levitte (France) (spoke in French):", or ""
    body_start: int   # index into the *normalised* text where the body begins

    @property
    def matched(self) -> bool:
        return bool(self.address)


def split_address(text: str) -> Address:
    """Locate the opening form of address.

    Returns an :class:`Address` with ``body_start == 0`` when the speech has no
    form of address. That is not a failure: about 5% of speeches are
    continuations that open straight into prose ("I thank the President for
    ..."), and truncating those would delete real words.
    """
    match = ADDRESS_RE.match(text, 0, 300)
    if match is None:
        return Address("", 0)
    end = match.end()
    # Step over the whitespace between the colon and the first real word.
    while end < len(text) and text[end] in " \t\n":
        end += 1
    return Address(match.group(0), end)


def body_of(text: str) -> str:
    """The speech with its opening form of address removed."""
    return text[split_address(text).body_start:]


def window(text: str, start: int, end: int, width: int = 150) -> tuple[str, str, str]:
    """Left context, keyword, right context around ``text[start:end]``.

    Line breaks are flattened to spaces so a concordance line reads as one
    line; the underlying offsets are untouched.
    """
    def flat(fragment: str) -> str:
        return re.sub(r"\s+", " ", fragment).strip()

    return (
        flat(text[max(0, start - width):start]),
        flat(text[start:end]),
        flat(text[end:end + width]),
    )


# --- 3. Delivery language -------------------------------------------------

# Every language actually attested in the corpus's markers. Closed by design:
# resolution can only ever return a member of this set, so OCR noise cannot
# invent a language.
LANGUAGES: tuple[str, ...] = (
    "Albanian", "Arabic", "Bengali", "Bosnian", "Chinese", "Croatian",
    "English", "French", "German", "Greek", "Hebrew", "Hindi", "Italian",
    "Japanese", "Macedonian", "Nepalese", "Persian", "Polish", "Portuguese",
    "Russian", "Serbian", "Slovak", "Spanish", "Turkish", "Ukrainian",
    "Vietnamese",
)

# Named corrections, applied before fuzzy matching. Two kinds live here:
# country names standing in for the language (a scribal slip, not OCR damage),
# and OCR spellings too mangled to clear the fuzzy threshold. Both are listed
# explicitly rather than absorbed by a looser cutoff — a named fix is
# reviewable in a diff, a slacker threshold silently changes every other match.
_SPELLING_FIXES: dict[str, str] = {
    "france": "French",
    "russia": "Russian",
    "china": "Chinese",
    "spain": "Spanish",
    "arabia": "Arabic",
    "preach": "French",    # "(interpretation from Preach)"
    "snaniah": "Spanish",  # "(interpretation from Snaniah)"
}

# Only the *opening* word of the parenthetical is required. Everything after it
# — preposition and separator alike — is OCR-damaged too often to pattern-match
# on: the corpus has "interpretation fron Arabic", "interpretation trom French",
# "interpretation fmm Spanish", "spoke [a French", "spoke inArabic",
# "interpretation from. French". Handing the whole fragment to
# :func:`resolve_language`, which searches for a known language inside it,
# recovers all of them without a spelling table for prepositions.
LANGUAGE_MARKER_RE = re.compile(
    r"\(\s*(?:spoke|spoken|interpretation|interpreted)([^)]{0,90})\)",
    re.IGNORECASE,
)

_LOOKUP = {lang.lower(): lang for lang in LANGUAGES}
_FUZZY_CUTOFF = 0.72


def _tokens(raw: str) -> list[str]:
    """Split a marker fragment into comparable words, in reading order.

    Only the semicolon is treated as a separator: it divides the delivery
    language from the Secretariat's arrangements ("Serbian; English text
    provided by the delegation"), and keeping only the head stops "English"
    from being read as the language spoken. Commas are *not* separators — they
    appear both as a stand-in for the semicolon and as OCR noise mid-phrase
    ("interpretation from, French"). Reading order settles the ambiguity
    instead: the delivery language always comes first.
    """
    head = raw.split(";", 1)[0]
    folded = unicodedata.normalize("NFKD", head).encode("ascii", "ignore").decode()
    return [t for t in re.split(r"[^a-z]+", folded.lower()) if t]


def _candidates(tokens: list[str]) -> list[str]:
    """Each token, and each token joined to the one after it, in reading order.

    OCR breaks a word in two as readily as it fuses two into one: the corpus
    has "Rus- sian" and "F rench" alongside "inArabic". Offering the joins as
    candidates turns those back into exact vocabulary hits, which is far safer
    than lowering the fuzzy threshold until the split halves match something.
    """
    out: list[str] = []
    for i, token in enumerate(tokens):
        out.append(token)
        if i + 1 < len(tokens):
            out.append(token + tokens[i + 1])
    return out


def resolve_language(raw: str) -> tuple[str | None, bool]:
    """Map a raw marker fragment to a language.

    Returns ``(language, was_fuzzy)``. ``was_fuzzy`` is True when the match
    needed approximate string comparison, so the caller can report exactly
    which OCR spellings were absorbed instead of hiding them.

    Certain matches are exhausted across every token before any approximate
    one is considered, so a clean "Portuguese" later in the fragment always
    beats a fuzzy reading of the damaged word before it.
    """
    candidates = _candidates(_tokens(raw))
    for candidate in candidates:
        if candidate in _LOOKUP:
            return _LOOKUP[candidate], False
        if candidate in _SPELLING_FIXES:
            return _SPELLING_FIXES[candidate], False
    for candidate in candidates:
        best, score = None, 0.0
        for low, lang in _LOOKUP.items():
            ratio = SequenceMatcher(None, candidate, low).ratio()
            if ratio > score:
                best, score = lang, ratio
        if score >= _FUZZY_CUTOFF:
            return best, True
    return None, False


def spoken_language(address: str) -> tuple[str | None, bool]:
    """The language a speech was delivered in, read off its form of address.

    ``(None, False)`` means the record carries no marker, which the Secretariat
    omits when the speech was delivered in English.
    """
    match = LANGUAGE_MARKER_RE.search(address)
    if match is None:
        return None, False
    return resolve_language(match.group(1))


# --- 4. Case collisions in categorical fields -----------------------------


def modal_case(values: pd.Series) -> pd.Series:
    """Collapse case variants of a label onto its most frequent spelling.

    `agenda_item2` carries "Children and armed conflict" alongside "Children
    And Armed Conflict", and `participanttype` has eight "The PRESIDENT" among
    39,483 "The President". Left alone, each pair splits into two categories
    and every groupby undercounts.

    Choosing the *modal* spelling rather than imposing a title-case rule keeps
    the corpus's own dominant form, which is what the codebook documents and
    what a reader will recognise.
    """
    counts = values.value_counts()
    winners = (
        counts.rename_axis("label")
        .reset_index(name="n")
        .assign(key=lambda f: f["label"].str.casefold())
        .sort_values(["n", "label"], ascending=[False, True])
        .drop_duplicates("key")
        .set_index("key")["label"]
    )
    return values.map(lambda v: winners.get(v.casefold(), v) if isinstance(v, str) else v)
