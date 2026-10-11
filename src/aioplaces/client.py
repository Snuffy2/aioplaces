"""Asynchronous, cached client for Nominatim and Wikidata JSON APIs."""

from __future__ import annotations

import copy
import json
import logging
import math
import re
from asyncio import Lock, sleep
from collections.abc import Callable
from time import monotonic
from typing import NoReturn
from urllib.parse import urlencode

import aiohttp
from cachetools import TTLCache
from yarl import URL

from .exceptions import HTTPError, InvalidResponseError, PlacesError, TransportError
from .types import JSONMapping, JSONValue

_LOGGER = logging.getLogger("aioplaces.client")
_OSM_TYPES: dict[str, str] = {
    "node": "N",
    "n": "N",
    "way": "W",
    "w": "W",
    "relation": "R",
    "r": "R",
}
_WIKIDATA_ID = re.compile(r"Q[1-9][0-9]*\Z")


def _validated_base_url(value: str, setting: str) -> URL:
    """Parse and validate an absolute service base URL.

    Args:
        value: URL supplied by the caller.
        setting: Configuration name used in validation errors.

    Returns:
        A normalized URL without a trailing path separator.

    Raises:
        ValueError: If the URL is malformed or contains request-specific data.
    """
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise ValueError(f"{setting} must be an absolute HTTP(S) URL")
    try:
        parsed = URL(value)
        port = parsed.port
    except (TypeError, ValueError) as err:
        raise ValueError(f"{setting} must be a valid absolute HTTP(S) URL") from err
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.host is None
        or parsed.user is not None
        or parsed.password is not None
        or "?" in value
        or "#" in value
    ):
        raise ValueError(f"{setting} must not contain credentials, a query, or a fragment")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"{setting} contains an invalid port")
    return parsed.with_path(parsed.path.rstrip("/"))


def _finite_positive(value: float, setting: str) -> float:
    """Validate and return a positive finite numeric setting.

    Args:
        value: Setting value to validate.
        setting: Configuration name used in validation errors.

    Returns:
        The validated value.

    Raises:
        ValueError: If the value is not a positive finite number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{setting} must be a positive finite number")
    try:
        numeric_value = float(value)
    except OverflowError as err:
        raise ValueError(f"{setting} must be a positive finite number") from err
    if not math.isfinite(numeric_value) or numeric_value <= 0:
        raise ValueError(f"{setting} must be a positive finite number")
    return numeric_value


def _reject_nonstandard_constant(value: str) -> NoReturn:
    """Reject JavaScript constants that Python's JSON decoder otherwise accepts.

    Args:
        value: Non-standard JSON constant reported by ``json.loads``.

    Raises:
        ValueError: Always, because the token is not valid JSON.
    """
    raise ValueError(f"Invalid JSON constant: {value}")


def _as_json_value(value: object) -> JSONValue:
    """Validate a decoded object and convert it to the recursive JSON type.

    Args:
        value: Object returned by the JSON decoder.

    Returns:
        The same JSON-compatible value with a precise recursive type.

    Raises:
        InvalidResponseError: If the decoded payload contains a non-JSON value.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidResponseError("The service returned a non-finite JSON number")
        return value
    if isinstance(value, list):
        return [_as_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise InvalidResponseError("The service returned a non-string JSON key")
        return {key: _as_json_value(item) for key, item in value.items()}
    raise InvalidResponseError("The service returned a value outside the JSON format")


def _service_error(payload: JSONMapping) -> None:
    """Raise for an error payload returned by a remote JSON service.

    Args:
        payload: JSON mapping returned by the service.

    Raises:
        InvalidResponseError: If the payload reports a service-side error.
    """
    if "error_message" in payload or "error" in payload:
        raise InvalidResponseError("The service returned an error payload")


def _normalize_nominatim_reverse(payload: JSONValue) -> JSONMapping | None:
    """Validate and normalize a Nominatim reverse-geocoding payload.

    Args:
        payload: Decoded JSON payload.

    Returns:
        A result mapping, or ``None`` when Nominatim reports no result.

    Raises:
        InvalidResponseError: If Nominatim returns an unsupported payload.
    """
    if payload is None or payload == []:
        return None
    if not isinstance(payload, dict):
        raise InvalidResponseError("Nominatim reverse response must be an object")
    if not payload:
        return None
    if payload.get("error") == "Unable to geocode":
        return None
    _service_error(payload)
    return payload


def _normalize_nominatim_lookup(payload: JSONValue) -> JSONMapping | None:
    """Validate and normalize a Nominatim lookup payload.

    Args:
        payload: Decoded JSON payload.

    Returns:
        The single result mapping, or ``None`` when Nominatim found no result.

    Raises:
        InvalidResponseError: If the payload has an unsupported shape.
    """
    if payload is None or payload == []:
        return None
    if isinstance(payload, list):
        if len(payload) != 1 or not isinstance(payload[0], dict):
            raise InvalidResponseError("Nominatim lookup must return at most one object")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise InvalidResponseError("Nominatim lookup response must be an object")
    if not payload:
        return None
    if payload.get("error") == "Unable to geocode":
        return None
    _service_error(payload)
    return payload


def _normalize_wikidata(payload: JSONValue) -> JSONMapping | None:
    """Validate a Wikidata response object.

    Args:
        payload: Decoded JSON payload.

    Returns:
        The response mapping, or ``None`` when the response is empty.

    Raises:
        InvalidResponseError: If the payload is not a valid service object.
    """
    if payload is None or payload == [] or payload == {}:
        return None
    if not isinstance(payload, dict):
        raise InvalidResponseError("Wikidata response must be an object")
    _service_error(payload)
    return payload


class PlacesClient:
    """Async client for Nominatim and Wikidata lookup APIs.

    The caller owns the supplied aiohttp session. The client keeps only
    per-instance cache and request-spacing state and never closes the session.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        base_url: str,
        user_agent: str,
        timeout: float = 10,
        cache_ttl: float = 14400,
        cache_maxsize: int = 500,
        min_request_interval: float = 1,
        wikidata_base_url: str = "https://www.wikidata.org/wiki/Special:EntityData",
    ) -> None:
        """Create a client that borrows an existing aiohttp session.

        Args:
            session: Open aiohttp session owned by the caller.
            base_url: Nominatim service root URL.
            user_agent: User-Agent value sent with each request.
            timeout: Positive request timeout in seconds.
            cache_ttl: Positive cache lifetime in seconds.
            cache_maxsize: Maximum number of successful responses to cache.
            min_request_interval: Minimum seconds between requests from this client.
            wikidata_base_url: Wikidata entity data endpoint root.

        Raises:
            ValueError: If a URL or client setting is invalid.
        """
        if not isinstance(session, aiohttp.ClientSession):
            raise TypeError("session must be an aiohttp.ClientSession")
        if (
            not isinstance(user_agent, str)
            or not user_agent.strip()
            or "\r" in user_agent
            or "\n" in user_agent
        ):
            raise ValueError("user_agent must be non-empty and must not contain CR or LF")
        self._base_url: URL = _validated_base_url(base_url, "base_url")
        self._wikidata_base_url: URL = _validated_base_url(wikidata_base_url, "wikidata_base_url")
        self._timeout: float = _finite_positive(timeout, "timeout")
        cache_lifetime = _finite_positive(cache_ttl, "cache_ttl")
        if isinstance(cache_maxsize, bool) or not isinstance(cache_maxsize, int):
            raise ValueError("cache_maxsize must be a positive integer")
        if cache_maxsize <= 0:
            raise ValueError("cache_maxsize must be a positive integer")
        if isinstance(min_request_interval, bool) or not isinstance(
            min_request_interval, (int, float)
        ):
            raise ValueError("min_request_interval must be a finite non-negative number")
        try:
            request_interval = float(min_request_interval)
        except OverflowError as err:
            raise ValueError("min_request_interval must be a finite non-negative number") from err
        if not math.isfinite(request_interval) or request_interval < 0:
            raise ValueError("min_request_interval must be a finite non-negative number")
        if (
            request_interval < 1
            and (self._base_url.host or "").rstrip(".").lower() == "nominatim.openstreetmap.org"
        ):
            raise ValueError("Public service hosts require an interval of at least 1 second")

        self._session: aiohttp.ClientSession = session
        self._user_agent: str = user_agent
        self._cache: TTLCache[str, JSONMapping] = TTLCache(
            maxsize=cache_maxsize, ttl=cache_lifetime, timer=monotonic
        )
        self._min_request_interval: float = request_interval
        self._lock: Lock = Lock()
        self._last_request_at: float | None = None

    async def reverse(
        self,
        latitude: float,
        longitude: float,
        *,
        language: str | None = None,
        email: str | None = None,
        use_cache: bool = True,
    ) -> JSONMapping | None:
        """Find the OSM address nearest a geographic coordinate.

        Args:
            latitude: Latitude from -90 through 90 degrees.
            longitude: Longitude from -180 through 180 degrees.
            language: Optional ``Accept-Language`` preference.
            email: Optional Nominatim contact email.
            use_cache: Whether a previously cached result may be returned.

        Returns:
            The Nominatim result mapping, or ``None`` when there is no result.

        Raises:
            ValueError: If either coordinate is invalid.
            PlacesError: If the request or response fails.
        """
        lat = self._coordinate(latitude, "latitude", -90, 90)
        lon = self._coordinate(longitude, "longitude", -180, 180)
        query = urlencode(
            (
                ("format", "json"),
                ("lat", str(lat)),
                ("lon", str(lon)),
                ("accept-language", language or ""),
                ("addressdetails", "1"),
                ("namedetails", "1"),
                ("zoom", "18"),
                ("limit", "1"),
                ("email", email or ""),
            )
        )
        url = self._request_url(self._base_url, "reverse", query)
        return await self._request_json(
            url, "reverse", _normalize_nominatim_reverse, use_cache=use_cache
        )

    async def lookup(
        self,
        osm_type: str,
        osm_id: int | str,
        *,
        language: str | None = None,
        email: str | None = None,
        use_cache: bool = True,
    ) -> JSONMapping | None:
        """Look up one OSM feature by its type and identifier.

        Args:
            osm_type: One of ``node``, ``way``, ``relation``, ``N``, ``W``, or ``R``.
            osm_id: Positive integer identifier, either as an integer or digit string.
            language: Optional ``Accept-Language`` preference.
            email: Optional Nominatim contact email.
            use_cache: Whether a previously cached result may be returned.

        Returns:
            The single Nominatim result mapping, or ``None`` if no result exists.

        Raises:
            ValueError: If the type or identifier is invalid.
            PlacesError: If the request or response fails.
        """
        if not isinstance(osm_type, str) or osm_type.lower() not in _OSM_TYPES:
            raise ValueError("osm_type must be node, way, relation, N, W, or R")
        type_prefix = _OSM_TYPES[osm_type.lower()]
        id_text = self._osm_id(osm_id)
        query = urlencode(
            (
                ("osm_ids", f"{type_prefix}{id_text}"),
                ("format", "json"),
                ("addressdetails", "1"),
                ("extratags", "1"),
                ("namedetails", "1"),
                ("email", email or ""),
                ("accept-language", language or ""),
            )
        )
        url = self._request_url(self._base_url, "lookup", query)
        return await self._request_json(
            url, "lookup", _normalize_nominatim_lookup, use_cache=use_cache
        )

    async def wikidata(self, wikidata_id: str, *, use_cache: bool = True) -> JSONMapping | None:
        """Fetch one Wikidata entity's JSON data.

        Args:
            wikidata_id: Wikidata entity identifier such as ``Q42``.
            use_cache: Whether a previously cached result may be returned.

        Returns:
            The Wikidata response mapping.

        Raises:
            ValueError: If the entity identifier is invalid.
            PlacesError: If the request or response fails.
        """
        if not isinstance(wikidata_id, str) or _WIKIDATA_ID.fullmatch(wikidata_id) is None:
            raise ValueError("wikidata_id must be a Q identifier followed by digits")
        url = str(URL(f"{self._wikidata_base_url}/{wikidata_id}.json"))
        return await self._request_json(url, "wikidata", _normalize_wikidata, use_cache=use_cache)

    @staticmethod
    def _coordinate(value: float, name: str, minimum: float, maximum: float) -> float:
        """Validate one finite coordinate within its geographic bounds.

        Args:
            value: Coordinate value to validate.
            name: Coordinate name used in validation errors.
            minimum: Inclusive lower bound.
            maximum: Inclusive upper bound.

        Returns:
            The validated coordinate as a float.

        Raises:
            ValueError: If the coordinate is not a finite number in range.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite number in range")
        try:
            coordinate = float(value)
        except OverflowError as err:
            raise ValueError(f"{name} must be a finite number in range") from err
        if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
            raise ValueError(f"{name} must be a finite number in range")
        return coordinate

    @staticmethod
    def _osm_id(value: int | str) -> str:
        """Validate and return a positive OSM integer identifier as text.

        Args:
            value: Integer identifier or a string containing decimal digits.

        Returns:
            The identifier in canonical decimal form.

        Raises:
            ValueError: If the identifier is not a positive integer.
        """
        if isinstance(value, bool):
            raise ValueError("osm_id must be a positive integer")
        if isinstance(value, int):
            identifier = str(value)
        elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            identifier = value
        else:
            raise ValueError("osm_id must be a positive integer")
        if int(identifier) <= 0:
            raise ValueError("osm_id must be a positive integer")
        return str(int(identifier))

    @staticmethod
    def _request_url(base_url: URL, path: str, query: str) -> str:
        """Build a canonical request URL from a base, path, and encoded query.

        Args:
            base_url: Validated service root URL.
            path: Endpoint path to append.
            query: Already encoded query string.

        Returns:
            The canonical absolute request URL.
        """
        return str(URL(f"{base_url}/{path}?{query}"))

    async def _respect_request_interval(self) -> None:
        """Wait until this client may make its next serialized request."""
        if self._last_request_at is not None:
            elapsed = monotonic() - self._last_request_at
            remaining = self._min_request_interval - elapsed
            if remaining > 0:
                await sleep(remaining)
        self._last_request_at = monotonic()

    async def _fetch_json(self, url: str, operation: str) -> JSONValue:
        """Fetch, decode, and validate one JSON response.

        Args:
            url: Canonical request URL.
            operation: Safe operation label for internal debug logs.

        Returns:
            Parsed recursive JSON value.

        Raises:
            HTTPError: If the response has a non-success status.
            InvalidResponseError: If the response body is not valid JSON.
            TransportError: If the request fails at the network boundary.
        """
        _LOGGER.debug("Requesting %s data", operation)
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": self._user_agent},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                allow_redirects=False,
                raise_for_status=False,
            ) as response:
                if not 200 <= response.status < 300:
                    raise HTTPError(response.status, response.headers.get("Retry-After"))
                try:
                    response_text = await response.text()
                except UnicodeDecodeError as err:
                    raise InvalidResponseError("The service response is not valid text") from err
        except (aiohttp.ClientError, TimeoutError, OSError, RuntimeError) as err:
            raise TransportError("The request could not be completed") from err

        try:
            decoded: object = json.loads(response_text, parse_constant=_reject_nonstandard_constant)
        except (ValueError, UnicodeDecodeError) as err:
            raise InvalidResponseError("The service response is not valid JSON") from err
        return _as_json_value(decoded)

    async def _request_json(
        self,
        url: str,
        operation: str,
        normalize: Callable[[JSONValue], JSONMapping | None],
        *,
        use_cache: bool,
    ) -> JSONMapping | None:
        """Return a normalized response while serializing client network access.

        Args:
            url: Canonical request URL and complete cache key.
            operation: Safe operation label for internal debug logs.
            normalize: Service-specific response contract validator.
            use_cache: Whether to read and evict an existing cached response.

        Returns:
            A deep copy of the response mapping, or ``None`` for no result.

        Raises:
            PlacesError: If transport, HTTP, or response validation fails.
        """
        if use_cache and url in self._cache:
            _LOGGER.debug("Returning cached %s data", operation)
            return copy.deepcopy(self._cache[url])

        async with self._lock:
            if use_cache and url in self._cache:
                _LOGGER.debug("Returning cached %s data", operation)
                return copy.deepcopy(self._cache[url])
            await self._respect_request_interval()
            try:
                payload = await self._fetch_json(url, operation)
                result = normalize(payload)
            except PlacesError:
                if use_cache:
                    self._cache.pop(url, None)
                raise
            if result is None:
                self._cache.pop(url, None)
                return None
            self._cache[url] = copy.deepcopy(result)
            return copy.deepcopy(result)
