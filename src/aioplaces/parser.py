"""Pure parsing helpers for OpenStreetMap place responses."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .const import CITY_LIST, NEIGHBOURHOOD_LIST, POSTAL_TOWN_LIST
from .models import ParsedPlace

__all__ = ["parse_place"]


def parse_place(payload: Mapping[str, object], language: str | None = None) -> ParsedPlace:
    """Extract normalized place fields from a Nominatim response.

    Name selection follows the Places integration order: type-derived address
    name, category-derived address name, generic namedetail, configured
    language-specific namedetail, then the retail fallback. Address groups are
    selected in their configured precedence order, with overlaps skipped after
    a higher-priority group claims them.

    Args:
        payload: Nominatim response mapping.
        language: Comma-separated preferred language codes, checked in order.

    Returns:
        An immutable record containing normalized string fields. Malformed
        nested structures and unsupported scalar values produce ``None``.
    """
    address = _mapping(payload.get("address"))
    namedetails = _mapping(payload.get("namedetails"))

    place_type = _string(payload.get("type"))
    if place_type == "yes":
        place_type = _string(payload.get("addresstype"))
        if not place_type:
            place_type = None

    place_name: str | None = None
    if place_type is not None and address is not None and place_type in address:
        place_name = _string(address[place_type])

    place_category = _string(payload.get("category"))
    if (
        "category" in payload
        and place_category is not None
        and address is not None
        and place_category in address
    ):
        place_name = _string(address[place_category])

    if namedetails is not None:
        if "name" in namedetails:
            place_name = _string(namedetails["name"])
        if language:
            for preferred_language in language.split(","):
                localized_name_key = f"name:{preferred_language}"
                if localized_name_key in namedetails:
                    place_name = _string(namedetails[localized_name_key])
                    break

    street_number = _string(address.get("house_number")) if address is not None else None
    street = _string(address.get("road")) if address is not None else None
    if (
        address is not None
        and "retail" in address
        and (
            _is_blank(place_name)
            or (
                not _is_blank(place_category)
                and not _is_blank(street)
                and place_category is not None
                and place_category == "highway"
                and street == place_name
            )
        )
    ):
        place_name = _string(address["retail"])

    city_key = _first_present(address, CITY_LIST)
    city = _string(address[city_key]) if address is not None and city_key is not None else None
    city_clean: str | None = None
    if city:
        city_clean = city.replace(" Township", "").strip()
        if city_clean.startswith("City of"):
            city_clean = f"{city_clean[8:]} City"

    city_types_to_skip = _through_match(CITY_LIST, city_key)
    postal_town_types = _without_types(POSTAL_TOWN_LIST, city_types_to_skip)
    postal_town_key = _first_present(address, postal_town_types)
    postal_town = (
        _string(address[postal_town_key])
        if address is not None and postal_town_key is not None
        else None
    )

    postal_town_types_to_skip = _through_match(postal_town_types, postal_town_key)
    neighbourhood_types = _without_types(
        NEIGHBOURHOOD_LIST,
        [*city_types_to_skip, *postal_town_types_to_skip],
    )
    neighbourhood_key = _first_present(address, neighbourhood_types)
    neighbourhood = (
        _string(address[neighbourhood_key])
        if address is not None and neighbourhood_key is not None
        else None
    )

    iso_code = _string(address.get("ISO3166-2-lvl4")) if address is not None else None
    state_abbr: str | None = None
    if iso_code is not None:
        iso_parts = iso_code.split("-")
        if len(iso_parts) >= 2:
            state_abbr = iso_parts[1].upper()

    country_code = _string(address.get("country_code")) if address is not None else None
    if country_code is not None:
        country_code = country_code.upper()

    return ParsedPlace(
        attribution=_nonempty_string(payload.get("licence")),
        osm_id=_normalized_osm_id(payload.get("osm_id")),
        osm_type=_string(payload.get("osm_type")),
        place_type=place_type,
        place_category=place_category,
        place_name=place_name,
        street_number=street_number,
        street=street,
        city=city,
        city_clean=city_clean,
        postal_town=postal_town,
        neighbourhood=neighbourhood,
        region=_string(address.get("state")) if address is not None else None,
        state_abbr=state_abbr,
        county=_string(address.get("county")) if address is not None else None,
        country=_string(address.get("country")) if address is not None else None,
        country_code=country_code,
        postal_code=_string(address.get("postcode")) if address is not None else None,
        formatted_address=_string(payload.get("display_name")),
        route_number=_route_number(place_category, namedetails),
    )


def _mapping(value: object) -> Mapping[str, object] | None:
    """Return a nested mapping value when it has the expected shape."""
    if isinstance(value, Mapping):
        return value
    return None


def _string(value: object) -> str | None:
    """Return a scalar string value, rejecting other JSON shapes."""
    if isinstance(value, str):
        return value
    return None


def _nonempty_string(value: object) -> str | None:
    """Return a nonempty string value, matching optional attribution behavior."""
    result = _string(value)
    return result if result else None


def _normalized_osm_id(value: object) -> str | None:
    """Normalize positive integer OSM identifiers to decimal strings."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if not isinstance(value, str):
        return None

    value = value.strip()
    if re.fullmatch(r"[+-]?[0-9]+", value) is None:
        return None
    try:
        identifier = int(value)
    except ValueError:
        return None
    return str(identifier) if identifier > 0 else None


def _first_present(address: Mapping[str, object] | None, types: list[str]) -> str | None:
    """Return the first configured address key present in a mapping."""
    if address is None:
        return None
    for address_type in types:
        if address_type in address:
            return address_type
    return None


def _through_match(types: list[str], matched_type: str | None) -> list[str]:
    """Return address types through the selected type in precedence order."""
    if matched_type is None:
        return []
    return types[: types.index(matched_type) + 1]


def _without_types(types: list[str], excluded_types: list[str]) -> list[str]:
    """Return candidate address types that earlier groups have not claimed."""
    excluded = set(excluded_types)
    return [address_type for address_type in types if address_type not in excluded]


def _is_blank(value: str | None) -> bool:
    """Return whether a normalized optional string is blank."""
    return value is None or value == ""


def _route_number(
    place_category: str | None,
    namedetails: Mapping[str, object] | None,
) -> str | None:
    """Extract the first highway reference segment containing a digit."""
    if (
        place_category is None
        or place_category.lower() != "highway"
        or namedetails is None
        or "ref" not in namedetails
    ):
        return None

    raw_reference = namedetails["ref"]
    if not isinstance(raw_reference, str) or not raw_reference.strip():
        return None
    for reference in re.split(r"[;\\/,.:]", raw_reference):
        if reference.strip() and re.search(r"\d", reference):
            return reference
    return None
