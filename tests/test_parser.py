"""Tests for the pure Nominatim place parser."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from aioplaces.models import ParsedPlace
from aioplaces.parser import parse_place


def test_parse_place_complete_response() -> None:
    """Parse a representative response into normalized place fields."""
    payload: dict[str, object] = {
        "licence": "OSM licence",
        "type": "yes",
        "addresstype": "road",
        "category": "amenity",
        "namedetails": {
            "name": "Generic Park",
            "name:en": "English Park",
            "name:fr": "Parc Français",
        },
        "address": {
            "road": "Main Street",
            "amenity": "Community Park",
            "house_number": "42",
            "city": "City of Springfield",
            "town": "Springfield Town",
            "village": "West Village",
            "suburb": "Downtown",
            "neighbourhood": "Old Centre",
            "state": "California",
            "ISO3166-2-lvl4": "us-ca",
            "county": "Orange County",
            "country": "United States",
            "country_code": "us",
            "postcode": "90210",
        },
        "display_name": "42 Main Street, Springfield",
        "osm_id": "000123",
        "osm_type": "way",
    }
    original_payload = deepcopy(payload)

    place = parse_place(payload, language="fr,en")

    assert place == ParsedPlace(
        attribution="OSM licence",
        osm_id="123",
        osm_type="way",
        place_type="road",
        place_category="amenity",
        place_name="Parc Français",
        street_number="42",
        street="Main Street",
        city="City of Springfield",
        city_clean="Springfield City",
        postal_town="Springfield Town",
        neighbourhood="West Village",
        region="California",
        state_abbr="CA",
        county="Orange County",
        country="United States",
        country_code="US",
        postal_code="90210",
        formatted_address="42 Main Street, Springfield",
    )
    assert payload == original_payload


def test_parse_place_applies_name_precedence_and_retail_fallback() -> None:
    """Apply type, category, namedetail, language, and retail names in order."""
    payload: dict[str, object] = {
        "type": "road",
        "category": "highway",
        "namedetails": {"name": "Main Road", "name:en": "English Road"},
        "address": {"road": "Main Road", "highway": "Category Road", "retail": "Shop"},
    }

    assert parse_place(payload).place_name == "Shop"
    assert parse_place(payload, language="en").place_name == "English Road"
    assert parse_place({**payload, "namedetails": {}}).place_name == "Category Road"


def test_parse_place_respects_exact_language_preference_segments() -> None:
    """Use comma-separated languages without trimming or normalizing codes."""
    payload: dict[str, object] = {"namedetails": {"name": "Generic", "name:en": "English"}}

    assert parse_place(payload, language="de, en").place_name == "Generic"
    assert parse_place(payload, language="de,en").place_name == "English"


def test_parse_place_skips_address_types_claimed_by_higher_groups() -> None:
    """Preserve city, postal-town, and neighbourhood key precedence."""
    payload: dict[str, object] = {
        "address": {
            "city": "City value",
            "town": "Town value",
            "village": "Village value",
            "suburb": "Suburb value",
            "neighbourhood": "Neighbourhood value",
        }
    }

    place = parse_place(payload)

    assert place.city == "City value"
    assert place.postal_town == "Town value"
    assert place.neighbourhood == "Village value"


def test_parse_place_extracts_highway_reference_without_trimming_segment() -> None:
    """Choose the first numeric highway reference and preserve its whitespace."""
    place = parse_place(
        {
            "category": "HIGHWAY",
            "namedetails": {"ref": "Main; B2, C3"},
        }
    )

    assert place.route_number == " B2"
    assert parse_place({"category": "amenity", "namedetails": {"ref": "B2"}}).route_number is None


@pytest.mark.parametrize(
    ("osm_id", "expected"),
    [
        (123, "123"),
        ("000123", "123"),
        (True, None),
        (1.0, None),
        (0, None),
        ("-1", None),
        ("1.5", None),
    ],
)
def test_parse_place_normalizes_only_positive_integer_osm_ids(
    osm_id: object,
    expected: str | None,
) -> None:
    """Normalize positive integer IDs and reject booleans and fractions."""
    assert parse_place({"osm_id": osm_id}).osm_id == expected


@pytest.mark.parametrize(
    "payload",
    [
        {
            "licence": 123,
            "type": ["road"],
            "category": 5,
            "namedetails": ["name", "Park"],
            "address": ["city", "Springfield"],
            "display_name": False,
            "osm_id": True,
            "osm_type": {"way": "way"},
        },
        {"address": None, "namedetails": None},
    ],
)
def test_parse_place_ignores_malformed_shapes_and_scalars(payload: Mapping[str, object]) -> None:
    """Return a partial result instead of failing on malformed response shapes."""
    place = parse_place(payload)

    assert place.attribution is None
    assert place.osm_id is None
    assert place.osm_type is None
    assert place.place_type is None
    assert place.place_category is None
    assert place.place_name is None
    assert place.city is None
    assert place.formatted_address is None


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ({"type": "yes", "addresstype": "building"}, "building"),
        ({"type": "yes"}, None),
        ({"type": "yes", "addresstype": 3}, None),
        ({"type": "yes", "addresstype": ""}, None),
    ],
)
def test_parse_place_uses_addresstype_for_yes(
    payload: Mapping[str, object],
    expected_type: str | None,
) -> None:
    """Resolve OSM's generic yes type through the addresstype field."""
    assert parse_place(payload).place_type == expected_type


def test_parse_place_defaults_are_none_and_result_is_frozen() -> None:
    """Leave missing fields unset and prevent mutation of the result object."""
    place = parse_place({})

    assert all(getattr(place, field.name) is None for field in fields(ParsedPlace))
    attribute_name = "place_name"
    with pytest.raises(FrozenInstanceError):
        setattr(place, attribute_name, "Changed")


@pytest.mark.parametrize(("category", "expected"), [("highway", "Shop"), ("HIGHWAY", "Main Road")])
def test_retail_fallback_preserves_category_case(category: str, expected: str) -> None:
    """Preserve the original case-sensitive retail fallback.

    Args:
        category: Upstream category whose casing controls retail substitution.
        expected: Place name retained by the reference Places parser.
    """
    payload = {
        "category": category,
        "namedetails": {"name": "Main Road"},
        "address": {"road": "Main Road", "retail": "Shop"},
    }
    assert parse_place(payload).place_name == expected
