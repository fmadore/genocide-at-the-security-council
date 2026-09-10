"""Geography must locate source spellings without changing research identities."""

import pandas as pd
import pytest
from lib import entities


def source(names, types=None):
    return pd.DataFrame(
        {
            "country_org": names,
            "entity_type": types or ["state"] * len(names),
            "iso3": pd.Series(pd.NA, index=range(len(names)), dtype="string"),
            "un_regional_group": pd.Series(pd.NA, index=range(len(names)), dtype="string"),
            "lat": float("nan"),
            "lon": float("nan"),
        }
    )


def test_reviewed_alias_targets_exist_and_are_states():
    geography = entities.load_entities()
    lookup = geography.set_index(geography.country_org.map(entities.geography_key))
    for target in entities.GEOGRAPHY_ALIASES.values():
        assert lookup.loc[entities.geography_key(target), "entity_type"] == "state"


def test_mapping_preserves_distinct_source_labels_and_types():
    names = [
        "Iran",
        "United Kingdom",
        "Russia",
        "Côte d'Ivoire",
        "Côte d'Ivoire",
        "Ivory Coast",
        "Madagascar",
    ]
    original = source(names)
    result = entities.enrich_geography(original)
    assert result.country_org.tolist() == names
    assert result.entity_type.tolist() == original.entity_type.tolist()
    assert result.iso3.tolist() == ["IRN", "GBR", "RUS", "CIV", "CIV", "CIV", "MDG"]
    assert result.lat.notna().all() and result.lon.notna().all()
    assert original.lat.isna().all()


def test_nonstates_ambiguous_and_unreviewed_historical_labels_are_not_guessed():
    result = entities.enrich_geography(
        source(
            ["Palestine", "United Nations", "India or Netherland", "Czechoslovakia"],
            ["other", "un", "state", "state"],
        )
    )
    assert result.iso3.isna().all()
    assert result.lat.isna().all()


def test_duplicate_normalized_lookup_is_rejected():
    geography = entities.load_entities()
    with pytest.raises(ValueError, match="ambiguous geography"):
        entities.enrich_geography(source(["Iran"]), pd.concat([geography, geography.iloc[:1]]))


def test_eastern_european_labels_use_the_un_regional_group():
    result = entities.enrich_geography(
        source(
            [
                "Belarus",
                "Bulgaria",
                "Czechia",
                "Hungary",
                "Moldova",
                "Poland",
                "Romania",
                "Russia",
                "Slovakia",
                "Ukraine",
            ]
        )
    )
    assert set(result.un_regional_group) == {"Eastern European Group"}
