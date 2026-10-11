"""Immutable models returned by the Places client."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedPlace:
    """Normalized place information extracted from a Nominatim response."""

    attribution: str | None = None
    osm_id: str | None = None
    osm_type: str | None = None
    place_type: str | None = None
    place_category: str | None = None
    place_name: str | None = None
    street_number: str | None = None
    street: str | None = None
    city: str | None = None
    city_clean: str | None = None
    postal_town: str | None = None
    neighbourhood: str | None = None
    region: str | None = None
    state_abbr: str | None = None
    county: str | None = None
    country: str | None = None
    country_code: str | None = None
    postal_code: str | None = None
    formatted_address: str | None = None
    route_number: str | None = None


__all__ = ["ParsedPlace"]
