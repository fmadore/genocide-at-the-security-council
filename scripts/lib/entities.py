"""The country_org crosswalk: aliases in, entity attributes out.

`country_org` holds 629 distinct values, of which only about 195 are states.
The rest are IGOs, UN bodies, NGOs, local associations, universities and a
handful of firms. Two hand-checked files under `config/` turn that into
something aggregatable:

- **`country_aliases.csv`** merges labels denoting the same speaker
  (`Türkiye` → `Turkey`, `Interpol` → `INTERPOL`).
- **`entities.csv`** gives each canonical label its type, ISO3 code, UN
  regional group and centroid.

Both are curated artefacts, not computed ones, so :func:`validate_coverage`
refuses to proceed on a `country_org` value that has never been typed. Without
that check a newly added speaker would silently vanish from the map and from
every state/non-state comparison — the failure would be invisible in the
output, which is the worst kind.

`tools/bootstrap_entities.py` proposes rows for new values.
"""

from __future__ import annotations

import pandas as pd

from .paths import COUNTRY_ALIASES, ENTITIES, rel

#: Values of the ``entity_type`` column.
#:
#: ``ngo`` and ``civil_society`` are both non-governmental; the split is by
#: reach, because the corpus's long tail is dominated by local associations
#: briefing the Council under the Women, Peace and Security agenda, and folding
#: those into the same bucket as Human Rights Watch would flatten the most
#: interesting thing about them. ``ngo`` is an international or transnational
#: organisation; ``civil_society`` is a national or local one.
ENTITY_TYPES: frozenset[str] = frozenset(
    {"state", "igo", "un", "ngo", "civil_society", "academia", "company", "other"}
)

#: The five UN regional groups, plus "" for entities that belong to none
#: (observers, non-members, and every non-state speaker).
UN_REGIONAL_GROUPS: frozenset[str] = frozenset(
    {
        "African Group",
        "Asia-Pacific Group",
        "Eastern European Group",
        "Latin American and Caribbean Group",
        "Western European and Others Group",
        "",
    }
)

ENTITY_COLUMNS = ["entity_type", "iso3", "un_regional_group", "lat", "lon"]


def load_aliases() -> dict[str, str]:
    """Map raw ``country_org`` labels to their canonical form."""
    if not COUNTRY_ALIASES.exists():
        return {}
    frame = pd.read_csv(COUNTRY_ALIASES, encoding="utf-8", comment="#")
    return dict(zip(frame["alias"], frame["canonical"], strict=True))


def canonicalise(names: pd.Series, aliases: dict[str, str] | None = None) -> pd.Series:
    """Apply the alias map. Labels with no alias pass through unchanged."""
    table = load_aliases() if aliases is None else aliases
    return names.map(lambda n: table.get(n, n))


def load_entities() -> pd.DataFrame:
    """The crosswalk, indexed by canonical ``country_org``."""
    if not ENTITIES.exists():
        raise FileNotFoundError(
            f"{rel(ENTITIES)} is missing. Generate a draft with:\n"
            f"    python tools/bootstrap_entities.py"
        )
    frame = pd.read_csv(ENTITIES, encoding="utf-8", comment="#", dtype={"iso3": "string"})
    frame["un_regional_group"] = frame["un_regional_group"].fillna("")
    return frame


def validate(entities: pd.DataFrame) -> list[str]:
    """Check the crosswalk's own integrity. Empty list means it is sound."""
    problems: list[str] = []
    duplicated = entities["country_org"][entities["country_org"].duplicated()]
    if len(duplicated):
        problems.append(f"duplicate rows for: {', '.join(sorted(set(duplicated))[:5])}")

    if int(entities["entity_type"].isna().sum()):
        missing = entities.loc[entities["entity_type"].isna(), "country_org"].tolist()
        problems.append(f"entities with no entity_type: {', '.join(missing[:5])}")

    unknown_types = set(entities["entity_type"].dropna()) - ENTITY_TYPES
    if unknown_types:
        problems.append(f"unknown entity_type: {', '.join(sorted(unknown_types))}")

    unknown_groups = set(entities["un_regional_group"].dropna()) - UN_REGIONAL_GROUPS
    if unknown_groups:
        problems.append(f"unknown un_regional_group: {', '.join(sorted(unknown_groups))}")

    states = entities[entities["entity_type"] == "state"]
    if int(states["iso3"].isna().sum()):
        missing = states.loc[states["iso3"].isna(), "country_org"].tolist()
        problems.append(f"states with no iso3: {', '.join(missing[:5])}")
    missing_centroid = states["lat"].isna() | states["lon"].isna()
    if int(missing_centroid.sum()):
        missing = states.loc[missing_centroid, "country_org"].tolist()
        problems.append(f"states with no centroid: {', '.join(missing[:5])}")
    invalid_centroid = (~states["lat"].between(-90, 90)) | (~states["lon"].between(-180, 180))
    if int(invalid_centroid.fillna(False).sum()):
        invalid = states.loc[invalid_centroid.fillna(False), "country_org"].tolist()
        problems.append(f"states with invalid centroid: {', '.join(invalid[:5])}")

    non_states = entities[entities["entity_type"] != "state"]
    non_state_centroid = non_states["lat"].notna() | non_states["lon"].notna()
    if int(non_state_centroid.sum()):
        named = non_states.loc[non_state_centroid, "country_org"].tolist()
        problems.append(
            "non-state entities carry a centroid, which would put a fake point "
            f"on the map: {', '.join(named[:5])}"
        )
    return problems


def validate_coverage(canonical_names: pd.Series, entities: pd.DataFrame) -> list[str]:
    """Check every speaker in the data has been typed."""
    known = set(entities["country_org"])
    unseen = sorted(set(canonical_names.dropna()) - known)
    if not unseen:
        return []
    shown = ", ".join(unseen[:8])
    more = f" (+{len(unseen) - 8} more)" if len(unseen) > 8 else ""
    return [
        f"{len(unseen)} country_org values are absent from {rel(ENTITIES)}: {shown}{more}\n"
        f"    Propose rows for them with: python tools/bootstrap_entities.py --missing"
    ]


def attach(speeches: pd.DataFrame, entities: pd.DataFrame) -> pd.DataFrame:
    """Join the crosswalk onto a speech table keyed on ``country_org``."""
    return speeches.merge(
        entities[["country_org", *ENTITY_COLUMNS]],
        on="country_org",
        how="left",
        validate="many_to_one",
    )
