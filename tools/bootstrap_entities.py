"""Propose config/entities.csv — the country_org crosswalk.

`config/entities.csv` is a hand-checked artefact: it decides what appears on
the map, which speakers count as states, and how the P5/E10 comparison is
drawn. This tool exists to produce the *first draft* of it and to re-propose
rows when the corpus gains new speakers. It never edits the checked-in file.

    python tools/bootstrap_entities.py            # -> data/interim/entities_proposal.csv
    python tools/bootstrap_entities.py --missing  # only country_org values absent from config

Read the proposal, correct it, and move it into place by hand. Rows the rules
are unsure about are marked in the `needs_review` column and sorted to the top
of their block, with the most-spoken entities first — auditing effort should
land where the speeches are.

Reference data is downloaded once and cached under data/interim/reference/:

- ISO 3166 codes and regions, from lukes/ISO-3166-Countries-with-Regional-Codes
- Country centroids, from gavinr/world-countries-centroids

Neither is needed at pipeline runtime; only this tool touches the network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import console
from lib import entities as entity_lib
from lib.paths import COUNTRY_ALIASES, ENTITIES, INTERIM, SPEECHES, ensure_dirs, rel

REFERENCE = INTERIM / "reference"
ISO_URL = (
    "https://raw.githubusercontent.com/lukes/"
    "ISO-3166-Countries-with-Regional-Codes/master/all/all.csv"
)
CENTROID_URL = (
    "https://raw.githubusercontent.com/gavinr/"
    "world-countries-centroids/master/dist/countries.geojson"
)

# --- States the corpus names differently from ISO 3166 --------------------
# Corpus label -> ISO 3166 English short name. Only spellings that fail an
# exact normalised match need an entry here.
STATE_ALIASES: dict[str, str] = {
    "United Kingdom Of Great Britain And Northern Ireland": "United Kingdom of Great Britain and Northern Ireland",
    "Republic Of Korea": "Korea, Republic of",
    "Democratic People's Republic Of Korea": "Korea, Democratic People's Republic of",
    "Democratic Republic Of The Congo": "Congo, Democratic Republic of the",
    "United Republic Of Tanzania": "Tanzania, United Republic of",
    "Republic Of Moldova": "Moldova, Republic of",
    "Netherlands": "Netherlands, Kingdom of the",
    "Slovak Republic": "Slovakia",
    "Palestine": "Palestine, State of",
    "Czech Republic": "Czechia",
    "Cape Verde": "Cabo Verde",
    "Swaziland": "Eswatini",
    "Turkey": "Türkiye",
    "Former Yugoslav Republic Of Macedonia": "North Macedonia",
    "Plurinational State Of Bolivia": "Bolivia (Plurinational State of)",
    "Federated States Of Micronesia": "Micronesia (Federated States of)",
    "Hashemite Kingdom Of Jordan": "Jordan",
}

# --- States with no current ISO 3166 entry --------------------------------
# Historical states and one contested case. Each keeps its own row rather than
# being folded into a successor: "Yugoslavia" in 1999 and "Serbia" in 2015 are
# not the same speaker, even though both sit in Belgrade. The iso3 given is the
# successor's, so the map can still place them; the note records the choice.
NON_ISO_STATES: dict[str, dict[str, object]] = {
    "Zaire": {
        "iso3": "COD", "un_regional_group": "African Group",
        "lat": -4.04, "lon": 21.76,
        "note": "Renamed Democratic Republic of the Congo in 1997; kept distinct, mapped to COD.",
    },
    "Yugoslavia": {
        "iso3": "SRB", "un_regional_group": "Eastern European Group",
        "lat": 44.02, "lon": 20.92,
        "note": "Federal Republic of Yugoslavia (1992-2003); mapped to SRB (Belgrade).",
    },
    "Serbia And Montenegro": {
        "iso3": "SRB", "un_regional_group": "Eastern European Group",
        "lat": 44.02, "lon": 20.92,
        "note": "State union 2003-2006; mapped to SRB (Belgrade).",
    },
    "Kosovo": {
        "iso3": "XKX", "un_regional_group": "",
        "lat": 42.60, "lon": 20.90,
        "note": "No ISO 3166 entry; XKX is the widely used user-assigned code. Not a UN member.",
    },
}

# --- UN regional groups ---------------------------------------------------
# The groups are political, not geographic, so they cannot be read off ISO
# regions alone. The mapping below is the geographic first pass; the overrides
# after it are the cases where the two genuinely differ.
_REGION_TO_GROUP = {
    "Africa": "African Group",
    "Americas": "Latin American and Caribbean Group",
    "Asia": "Asia-Pacific Group",
    "Oceania": "Asia-Pacific Group",
}

UN_GROUP_OVERRIDES: dict[str, str] = {
    # Balkans and Baltics: ISO files them under Southern/Northern Europe.
    "ALB": "Eastern European Group", "BIH": "Eastern European Group",
    "HRV": "Eastern European Group", "MNE": "Eastern European Group",
    "MKD": "Eastern European Group", "SRB": "Eastern European Group",
    "SVN": "Eastern European Group", "EST": "Eastern European Group",
    "LVA": "Eastern European Group", "LTU": "Eastern European Group",
    # South Caucasus: ISO files these under Western Asia.
    "ARM": "Eastern European Group", "AZE": "Eastern European Group",
    "GEO": "Eastern European Group",
    # WEOG, against geography.
    "ISR": "Western European and Others Group",
    "TUR": "Western European and Others Group",
    "AUS": "Western European and Others Group",
    "NZL": "Western European and Others Group",
    "CAN": "Western European and Others Group",
    "USA": "Western European and Others Group",  # participates as observer
    # Cyprus sits in the Asia-Pacific Group.
    "CYP": "Asia-Pacific Group",
    # Non-members and observers belong to no group.
    "VAT": "", "PSE": "",
}

# --- Entity typing --------------------------------------------------------
# Applied in order; first match wins. These carry the confident cases only —
# anything they do not catch falls through to the default and is flagged for
# review.
TYPE_RULES: list[tuple[str, str]] = [
    (r"^UN$|^United Nations\b|^UN[- ]", "un"),
    (r"^UN(ICEF|HCR|RWA|FPA|ODC)$|^WHO$|^IOM$|^ICAO$|^IAEA$", "un"),
    (r"\bWorld (Food Programme|Health Organization|Meteorological)\b", "un"),
    (r"\bInternational (Labour Organization|Maritime Organization)\b", "un"),
    (r"\bInternational Court of Justice\b|^ICJ$", "un"),
    (r"\bInternational Residual Mechanism\b", "un"),
    (r"\bHigh Commissioner for (Refugees|Human Rights)\b", "un"),
    (r"\bUnited Nations University\b", "un"),
    (
        r"\b(African Union|European Union|European Council|Council of the European Union"
        r"|NATO|OSCE|ASEAN|League of Arab States|Caribbean Community|Council of Europe"
        r"|Commonwealth|Pacific Islands Forum|Pacific Community|East African Community"
        r"|Organization of American States|Shanghai Cooperation|Collective Security Treaty"
        r"|Commonwealth of Independent States|Gulf Cooperation Council|Arab Maghreb Union"
        r"|Economic Community|Intergovernmental Authority|Alliance of Small Island"
        r"|Organization of Islamic|Organisation of Islamic|International Criminal Court"
        r"|INTERPOL|Interpol|OPCW|Organization for the Prohibition)\b",
        "igo",
    ),
    (r"\b(World Bank|International Monetary Fund|^IMF$|Development Bank)\b", "igo"),
    # No trailing \b: "Universit" has to match inside "University".
    (r"\b(?:Universit|College|Academy|School of|Institut(?:e|o) (?:for|of))", "academia"),
    (
        r"\b(Goldman Sachs|Microsoft|Mastercard|Siemens|Gazprom|Anthropic|Deutsche Post"
        r"|Moby Group|Jigsaw|Gro Intelligence|Insight Strategy Partners|Grayzone"
        r"|Rossiya Segodnya)\b",
        "company",
    ),
]

# Rules cannot settle these; they are typed by hand.
TYPE_OVERRIDES: dict[str, str] = {
    "Civil Society": "civil_society",
    "Holy See": "state",
    "Sovereign Order of Malta": "other",
    "Security Council Procedure": "other",
    "Security Council Report": "ngo",
    "Ireland And Mexico": "other",
    "Dominican Republic/Germany": "other",
    "Organization Of African Unity": "igo",
    "High Representative For Bosnia And Herzegovina": "other",
    "High Representative for the Implementation of the Peace Agreement on Bosnia and Herzegovina": "other",
    # International NGOs, distinguished from the local associations that make
    # up most of the long tail.
    "International Committee Of The Red Cross": "ngo",
    "International Federation Of Red Cross And Red Crescent Societies": "ngo",
    "Medecins Sans Frontieres": "ngo", "Médecins Du Monde": "ngo",
    "Human Rights Watch": "ngo", "Oxfam": "ngo", "CARE": "ngo",
    "Save The Children": "ngo", "International Rescue Committee": "ngo",
    "Norwegian Refugee Council": "ngo", "International Crisis Group": "ngo",
    "Reporters Without Borders": "ngo", "Action Against Hunger": "ngo",
    "Search For Common Ground": "ngo", "The Elders": "ngo",
    "Malala Fund": "ngo", "Enough Project": "ngo", "Small Arms Survey": "ngo",
    "Trial International": "ngo", "Physicians For Human Rights": "ngo",
    "Global Initiative Against Transnational Organized Crime": "ngo",
    "Women's International League For Peace And Freedom": "ngo",
    "Inter-Parliamentary Union": "igo",
    "Community Of Sant'Egidio": "ngo",
}

DEFAULT_TYPE = "civil_society"

COLUMNS = [
    "country_org", "entity_type", "iso3", "un_regional_group",
    "lat", "lon", "needs_review", "note",
]


def _download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    console.info(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=60) as response:
        dest.write_bytes(response.read())
    return dest


def load_reference() -> pd.DataFrame:
    """ISO 3166 names, codes and regions, with a centroid per country."""
    # keep_default_na is essential: Namibia's alpha-2 code is "NA", which the
    # default null values would turn into a missing value and drop off the map.
    iso = pd.read_csv(
        _download(ISO_URL, REFERENCE / "iso3166.csv"),
        encoding="utf-8",
        keep_default_na=False,
        na_values=[""],
    )
    geo = json.loads(
        _download(CENTROID_URL, REFERENCE / "centroids.geojson").read_text(encoding="utf-8")
    )
    points = {
        f["properties"]["ISO"]: f["geometry"]["coordinates"]
        for f in geo["features"]
        if f.get("geometry")
    }
    iso["lon"] = iso["alpha-2"].map(lambda a: points.get(a, [None, None])[0])
    iso["lat"] = iso["alpha-2"].map(lambda a: points.get(a, [None, None])[1])
    iso["key"] = iso["name"].map(normalise_name)
    return iso


def normalise_name(name: str) -> str:
    """Casefold, strip diacritics and punctuation — for matching only."""
    folded = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", folded.lower().replace("&", " and ")).strip()


def classify(name: str) -> tuple[str, bool]:
    """Return (entity_type, needs_review) for a non-state speaker."""
    if name in TYPE_OVERRIDES:
        return TYPE_OVERRIDES[name], False
    for pattern, entity_type in TYPE_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            return entity_type, False
    return DEFAULT_TYPE, True


def propose(names: pd.Series) -> pd.DataFrame:
    """Build one proposed row per distinct canonical country_org."""
    iso = load_reference()
    by_key = iso.set_index("key")

    rows = []
    for name, n_speeches in names.items():
        record: dict[str, object] = dict.fromkeys(COLUMNS, "")
        record["country_org"] = name

        lookup = STATE_ALIASES.get(name, name)
        key = normalise_name(lookup)

        if name in NON_ISO_STATES:
            record.update(NON_ISO_STATES[name])
            record["entity_type"] = "state"
        elif key in by_key.index:
            match = by_key.loc[key]
            iso3 = match["alpha-3"]
            record["entity_type"] = "state"
            record["iso3"] = iso3
            record["lat"] = None if pd.isna(match["lat"]) else round(float(match["lat"]), 4)
            record["lon"] = None if pd.isna(match["lon"]) else round(float(match["lon"]), 4)
            record["un_regional_group"] = UN_GROUP_OVERRIDES.get(
                iso3, _REGION_TO_GROUP.get(match["region"], "Western European and Others Group")
            )
            if name in STATE_ALIASES:
                record["note"] = f"ISO 3166 name: {lookup}"
        else:
            entity_type, needs_review = classify(name)
            record["entity_type"] = entity_type
            record["needs_review"] = "yes" if needs_review else ""

        record["_n"] = int(n_speeches)
        rows.append(record)

    frame = pd.DataFrame(rows)
    # Review effort should land where the speeches are: flagged rows first,
    # then by volume.
    frame = frame.sort_values(
        ["needs_review", "_n"], ascending=[False, False]
    ).drop(columns="_n")
    return frame[COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--missing",
        action="store_true",
        help="propose only country_org values absent from config/entities.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=INTERIM / "entities_proposal.csv",
        help="where to write the proposal (never config/entities.csv)",
    )
    args = parser.parse_args()

    ensure_dirs()
    if args.out.resolve() == ENTITIES.resolve():
        console.fail("refusing to overwrite the hand-checked config/entities.csv")

    console.step("Reading distinct speakers")
    raw = pd.read_parquet(SPEECHES, columns=["country_org"])["country_org"].dropna()
    console.info(f"{raw.nunique():,} distinct country_org values")

    aliases = entity_lib.load_aliases()
    counts = entity_lib.canonicalise(raw, aliases).value_counts()
    console.info(
        f"{len(counts):,} after applying {len(aliases)} aliases from {rel(COUNTRY_ALIASES)}"
    )
    if unused := sorted(set(aliases) - set(raw.unique())):
        console.warn(f"aliases matching nothing in the data: {', '.join(unused)}")

    if args.missing and ENTITIES.exists():
        known = set(pd.read_csv(ENTITIES, encoding="utf-8")["country_org"])
        counts = counts[~counts.index.isin(known)]
        console.info(f"{len(counts):,} absent from {rel(ENTITIES)}")
        if counts.empty:
            console.info("nothing to propose")
            return

    console.step("Classifying")
    frame = propose(counts)
    breakdown = frame["entity_type"].value_counts()
    console.table([(t, f"{n:,}") for t, n in breakdown.items()])
    flagged = int((frame["needs_review"] == "yes").sum())
    console.info(f"{flagged:,} rows flagged for review")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False, encoding="utf-8")
    console.step(f"Wrote {rel(args.out)}")
    console.info("Review it, then move the corrected file to config/entities.csv")


if __name__ == "__main__":
    main()
