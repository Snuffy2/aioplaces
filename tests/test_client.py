"""Tests for the public asynchronous Places client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import NoReturn
from urllib.parse import urlencode

import aiohttp
from aioresponses import aioresponses
import pytest

import aioplaces.client as client_module
from aioplaces.client import PlacesClient
from aioplaces.exceptions import HTTPError, InvalidInputError, InvalidResponseError, TransportError
from aioplaces.types import JSONMapping

NOMINATIM = "http://127.0.0.1:8080"
WIKIDATA = "http://127.0.0.1:8081/entities"
USER_AGENT = "aioplaces-tests/1.0"
REVERSE_PARAMS = (
    ("format", "json"),
    ("lat", "40.0"),
    ("lon", "-70.0"),
    ("accept-language", ""),
    ("addressdetails", "1"),
    ("namedetails", "1"),
    ("zoom", "18"),
    ("limit", "1"),
    ("email", ""),
)


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    """Provide an open session whose lifecycle belongs to the fixture.

    Yields:
        aiohttp.ClientSession: Open session owned and closed by this fixture.
    """
    async with aiohttp.ClientSession() as client_session:
        yield client_session


def make_client(session: aiohttp.ClientSession, **kwargs: object) -> PlacesClient:
    """Create a client pointed at local mock endpoints.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client.
        **kwargs (object): Client settings to override.

    Returns:
        PlacesClient: A client configured for network-free tests.
    """
    min_request_interval = kwargs.pop("min_request_interval", 0)
    return PlacesClient(
        session,
        base_url=NOMINATIM,
        user_agent=USER_AGENT,
        wikidata_base_url=WIKIDATA,
        min_request_interval=min_request_interval,  # type: ignore[arg-type]
        **kwargs,
    )


def reverse_url(*, language: str | None = None, email: str | None = None) -> str:
    """Build the expected reverse URL for the test coordinate.

    Args:
        language (str | None): Optional language parameter.
        email (str | None): Optional contact email parameter.

    Returns:
        str: The complete reverse request URL.
    """
    params = list(REVERSE_PARAMS)
    params[3] = ("accept-language", language or "")
    params[8] = ("email", email or "")
    return f"{NOMINATIM}/reverse?{urlencode(params)}"


def request_count(mocked: aioresponses) -> int:
    """Return the number of captured mocked HTTP requests.

    Args:
        mocked (aioresponses): Active aioresponses recorder.

    Returns:
        int: Total captured request count across all URLs.
    """
    return sum(len(calls) for calls in mocked.requests.values())


@pytest.mark.asyncio
async def test_reverse_preserves_nominatim_parameters_and_session_ownership(
    session: aiohttp.ClientSession,
) -> None:
    """Send configured headers and the reference query without owning the session.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url(language="en", email="geo@example.org")
    result: JSONMapping = {"name": "Test Place"}
    with aioresponses() as mocked:
        mocked.get(url, payload=result)
        client = make_client(session)

        assert await client.reverse(40, -70, language="en", email="geo@example.org") == result

    request = next(iter(mocked.requests.values()))[0]
    assert request.kwargs["headers"]["User-Agent"] == USER_AGENT
    assert request.kwargs["allow_redirects"] is False
    assert request.kwargs["raise_for_status"] is False
    request_url = next(iter(mocked.requests))[1]
    assert dict(request_url.query) == {
        "format": "json",
        "lat": "40.0",
        "lon": "-70.0",
        "accept-language": "en",
        "addressdetails": "1",
        "namedetails": "1",
        "zoom": "18",
        "limit": "1",
        "email": "geo@example.org",
    }
    assert session.closed is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("osm_type", "osm_id", "osm_prefix"),
    [("node", 12, "N12"), ("W", "42", "W42"), ("relation", 73, "R73")],
)
async def test_lookup_uses_lookup_endpoint_and_one_osm_id(
    session: aiohttp.ClientSession, osm_type: str, osm_id: int | str, osm_prefix: str
) -> None:
    """Use the singular lookup endpoint with the requested OSM type prefix.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        osm_type (str): OSM type supplied to the lookup method.
        osm_id (int | str): Feature identifier supplied to the lookup method.
        osm_prefix (str): Expected one-letter type prefix and identifier.
    """
    params = urlencode(
        (
            ("osm_ids", osm_prefix),
            ("format", "json"),
            ("addressdetails", "1"),
            ("extratags", "1"),
            ("namedetails", "1"),
            ("email", ""),
            ("accept-language", ""),
        )
    )
    url = f"{NOMINATIM}/lookup?{params}"
    with aioresponses() as mocked:
        mocked.get(url, payload=[{"osm_id": int(osm_id)}])
        client = make_client(session)

        assert await client.lookup(osm_type, osm_id) == {"osm_id": int(osm_id)}

    assert request_count(mocked) == 1


@pytest.mark.asyncio
async def test_wikidata_uses_configured_entity_endpoint(
    session: aiohttp.ClientSession,
) -> None:
    """Build a Wikidata URL from the configured endpoint and return its mapping.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = f"{WIKIDATA}/Q42.json"
    payload: JSONMapping = {"entities": {"Q42": {"id": "Q42"}}}
    with aioresponses() as mocked:
        mocked.get(url, payload=payload)
        client = make_client(session)

        assert await client.wikidata("Q42") == payload

    assert request_count(mocked) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"entities": {}}, {"entities": {}}),
        ({}, None),
        ([], None),
        (None, None),
        ([1], InvalidResponseError),
    ],
)
async def test_wikidata_response_contract(
    session: aiohttp.ClientSession,
    payload: object,
    expected: JSONMapping | None | type[InvalidResponseError],
) -> None:
    """Return empty Wikidata results as no-result and reject non-object payloads.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        payload (object): Response shape returned by the service.
        expected (JSONMapping | None | type[InvalidResponseError]):
            Normalized result or expected exception.
    """
    url = f"{WIKIDATA}/Q42.json"
    with aioresponses() as mocked:
        if payload is None:
            mocked.get(url, body="null")
        else:
            mocked.get(url, payload=payload)
        client = make_client(session)

        if expected is InvalidResponseError:
            with pytest.raises(InvalidResponseError):
                await client.wikidata("Q42")
        else:
            assert await client.wikidata("Q42") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (float("nan"), 0.0),
        (0.0, float("inf")),
        (90.01, 0.0),
        (0.0, -180.01),
        (True, 0.0),
        (10**400, 0.0),
    ],
)
async def test_reverse_rejects_invalid_coordinates(
    session: aiohttp.ClientSession, latitude: float, longitude: float
) -> None:
    """Reject invalid coordinates before making a request.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        latitude (float): Invalid latitude supplied to the request.
        longitude (float): Invalid longitude supplied to the request.
    """
    client = make_client(session)
    with pytest.raises(InvalidInputError):
        await client.reverse(latitude, longitude)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("osm_type", "osm_id"),
    [
        ("area", 1),
        ("node", 0),
        ("node", -1),
        ("node", True),
        ("node", 1.5),
        ("node", "1.2"),
        ("node", "9" * 5000),
        pytest.param("node", 10**5000, id="oversized-integer"),
    ],
)
async def test_lookup_rejects_invalid_type_or_identifier(
    session: aiohttp.ClientSession, osm_type: str, osm_id: int | str
) -> None:
    """Reject invalid OSM identifiers before sending a request.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        osm_type (str): Invalid OSM type supplied to the request.
        osm_id (int | str): Invalid identifier supplied to the request.
    """
    client = make_client(session)
    with pytest.raises(InvalidInputError):
        await client.lookup(osm_type, osm_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("wikidata_id", ["", "q42", "Q0", "Q42x", "42"])
async def test_wikidata_rejects_invalid_identifier(
    session: aiohttp.ClientSession, wikidata_id: str
) -> None:
    """Reject identifiers outside the Wikidata Q-number form.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        wikidata_id (str): Invalid identifier supplied to the request.
    """
    client = make_client(session)
    with pytest.raises(InvalidInputError):
        await client.wikidata(wikidata_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"name": "A"}, {"name": "A"}),
        ({}, None),
        ([], None),
        (None, None),
        ({"error": "Unable to geocode"}, None),
        ([{"name": "A"}], InvalidResponseError),
        ({"error": "permission denied"}, InvalidResponseError),
        ({"error_message": "service failure"}, InvalidResponseError),
    ],
)
async def test_reverse_response_contract(
    session: aiohttp.ClientSession,
    payload: object,
    expected: JSONMapping | None | type[InvalidResponseError],
) -> None:
    """Normalize valid no-result cases and reject unsupported service responses.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        payload (object): Response shape returned by Nominatim.
        expected (JSONMapping | None | type[InvalidResponseError]):
            Normalized result or expected exception.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        if payload is None:
            mocked.get(url, body="null")
        else:
            mocked.get(url, payload=payload)
        client = make_client(session)

        if expected is InvalidResponseError:
            with pytest.raises(InvalidResponseError):
                await client.reverse(40, -70)
        else:
            assert await client.reverse(40, -70) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ([{"name": "A"}], {"name": "A"}),
        ({"name": "A"}, {"name": "A"}),
        ([], None),
        ({}, None),
        ([{"name": "A"}, {"name": "B"}], InvalidResponseError),
        ([1], InvalidResponseError),
    ],
)
async def test_lookup_response_contract(
    session: aiohttp.ClientSession,
    payload: object,
    expected: JSONMapping | None | type[InvalidResponseError],
) -> None:
    """Accept no more than one mapping in the Nominatim lookup response.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        payload (object): Response shape returned by Nominatim.
        expected (JSONMapping | None | type[InvalidResponseError]):
            Normalized result or expected exception.
    """
    params = urlencode(
        (
            ("osm_ids", "N1"),
            ("format", "json"),
            ("addressdetails", "1"),
            ("extratags", "1"),
            ("namedetails", "1"),
            ("email", ""),
            ("accept-language", ""),
        )
    )
    with aioresponses() as mocked:
        mocked.get(f"{NOMINATIM}/lookup?{params}", payload=payload)
        client = make_client(session)

        if expected is InvalidResponseError:
            with pytest.raises(InvalidResponseError):
                await client.lookup("node", 1)
        else:
            assert await client.lookup("node", 1) == expected


@pytest.mark.asyncio
async def test_http_error_exposes_retry_after_and_does_not_retry(
    session: aiohttp.ClientSession,
) -> None:
    """Raise the typed HTTP error with response metadata after one request.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, status=429, headers={"Retry-After": "30"})
        client = make_client(session)

        with pytest.raises(HTTPError) as caught:
            await client.reverse(40, -70)

    assert caught.value.status == 429
    assert caught.value.retry_after == "30"
    assert request_count(mocked) == 1


@pytest.mark.asyncio
async def test_invalid_json_and_transport_failure_use_typed_errors(
    session: aiohttp.ClientSession,
) -> None:
    """Translate malformed JSON and network timeout into public exceptions.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, body="{broken", content_type="application/json")
        client = make_client(session)

        with pytest.raises(InvalidResponseError):
            await client.reverse(40, -70)

    with aioresponses() as mocked:
        mocked.get(url, exception=TimeoutError("timed out"))
        client = make_client(session)

        with pytest.raises(TransportError):
            await client.reverse(40, -70)


@pytest.mark.asyncio
async def test_cache_returns_deep_copies_and_coalesces_concurrent_calls(
    session: aiohttp.ClientSession,
) -> None:
    """Cache one concurrent response and keep caller mutations isolated.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, payload={"nested": {"values": [1]}})
        client = make_client(session)
        first, second = await asyncio.gather(client.reverse(40, -70), client.reverse(40, -70))
        assert first is not None
        nested = first["nested"]
        assert isinstance(nested, dict)
        values = nested["values"]
        assert isinstance(values, list)
        values.append(2)
        third = await client.reverse(40, -70)

    assert second == {"nested": {"values": [1]}}
    assert third == {"nested": {"values": [1]}}
    assert request_count(mocked) == 1


@pytest.mark.asyncio
async def test_cache_key_includes_language_and_contact_options(
    session: aiohttp.ClientSession,
) -> None:
    """Keep responses for different request options under distinct cache keys.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    english_url = reverse_url(language="en", email="one@example.org")
    french_url = reverse_url(language="fr", email="one@example.org")
    with aioresponses() as mocked:
        mocked.get(english_url, payload={"name": "English"})
        mocked.get(french_url, payload={"name": "Français"})
        client = make_client(session)

        assert await client.reverse(40, -70, language="en", email="one@example.org") == {
            "name": "English"
        }
        assert await client.reverse(40, -70, language="fr", email="one@example.org") == {
            "name": "Français"
        }
        assert await client.reverse(40, -70, language="en", email="one@example.org") == {
            "name": "English"
        }

    assert request_count(mocked) == 2


@pytest.mark.asyncio
async def test_cache_expiry_uses_the_monotonic_clock(
    session: aiohttp.ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expire a cached response when the controlled monotonic clock advances.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        monkeypatch (pytest.MonkeyPatch): Fixture used to replace the module clock.
    """
    now = 100.0

    def clock() -> float:
        """Return the current simulated cache time.

        Returns:
            float: Current time used by the cache.
        """
        return now

    monkeypatch.setattr(client_module, "monotonic", clock)
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, payload={"name": "old"})
        mocked.get(url, payload={"name": "new"})
        client = make_client(session, cache_ttl=5)

        assert await client.reverse(40, -70) == {"name": "old"}
        now += 6
        assert await client.reverse(40, -70) == {"name": "new"}

    assert request_count(mocked) == 2


@pytest.mark.asyncio
async def test_forced_failed_refresh_preserves_cached_success(
    session: aiohttp.ClientSession,
) -> None:
    """Keep a prior success available when a cache-bypassing refresh fails.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, payload={"name": "cached"})
        mocked.get(url, status=503)
        client = make_client(session)

        assert await client.reverse(40, -70) == {"name": "cached"}
        with pytest.raises(HTTPError):
            await client.reverse(40, -70, use_cache=False)
        assert await client.reverse(40, -70) == {"name": "cached"}

    assert request_count(mocked) == 2


@pytest.mark.asyncio
async def test_forced_no_result_evicts_cached_success(
    session: aiohttp.ClientSession,
) -> None:
    """Remove an older cache entry when a forced refresh finds no result.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, payload={"name": "old"})
        mocked.get(url, body="null")
        mocked.get(url, payload={"name": "new"})
        client = make_client(session)

        assert await client.reverse(40, -70) == {"name": "old"}
        assert await client.reverse(40, -70, use_cache=False) is None
        assert await client.reverse(40, -70) == {"name": "new"}

    assert request_count(mocked) == 3


@pytest.mark.asyncio
async def test_serialized_requests_wait_for_the_configured_interval(
    session: aiohttp.ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apply deterministic spacing between network calls from one client.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        monkeypatch (pytest.MonkeyPatch): Fixture used to replace clock and sleep.
    """
    now = 0.0
    waits: list[float] = []

    def clock() -> float:
        """Return the current simulated request time.

        Returns:
            float: Current time used by request spacing.
        """
        return now

    async def advance(seconds: float) -> None:
        """Record a throttle wait and advance the controlled clock.

        Args:
            seconds (float): Wait duration requested by the client.
        """
        nonlocal now
        waits.append(seconds)
        now += seconds

    monkeypatch.setattr(client_module, "monotonic", clock)
    monkeypatch.setattr(client_module, "sleep", advance)
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, payload={"name": "first"})
        mocked.get(url, payload={"name": "second"})
        client = make_client(session, min_request_interval=1.5)

        await client.reverse(40, -70, use_cache=False)
        await client.reverse(40, -70, use_cache=False)

    assert waits == [1.5]
    assert request_count(mocked) == 2


@pytest.mark.asyncio
async def test_cancelling_a_queued_call_releases_the_lock(
    session: aiohttp.ClientSession,
) -> None:
    """Propagate queued task cancellation without leaving the lock held.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, payload={"name": "ok"})
        client = make_client(session)
        await client._lock.acquire()
        queued = asyncio.create_task(client.reverse(40, -70))
        await asyncio.sleep(0)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        client._lock.release()

        assert await client.reverse(40, -70) == {"name": "ok"}

    assert request_count(mocked) == 1


@pytest.mark.asyncio
async def test_inflight_cancellation_propagates_and_releases_the_lock(
    session: aiohttp.ClientSession,
) -> None:
    """Propagate cancellation from the transport and permit a subsequent call.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    url = reverse_url()
    with aioresponses() as mocked:
        mocked.get(url, exception=asyncio.CancelledError())
        mocked.get(url, payload={"name": "ok"})
        client = make_client(session)

        with pytest.raises(asyncio.CancelledError):
            await client.reverse(40, -70)
        assert await client.reverse(40, -70) == {"name": "ok"}

    assert request_count(mocked) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("timeout", 0),
        ("timeout", float("inf")),
        ("cache_ttl", -1),
        ("cache_maxsize", 0),
        ("min_request_interval", -0.1),
        ("min_request_interval", 10**400),
        ("base_url", "https://user:pass@example.org"),
        ("base_url", "https://example.org/?token=x"),
        ("base_url", "https://example.org/#fragment"),
        ("base_url", "bad url"),
    ],
)
async def test_invalid_client_settings_raise_invalid_input_error(
    session: aiohttp.ClientSession, setting: str, value: object
) -> None:
    """Reject invalid numeric settings and unsafe service base URLs.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        setting (str): Client setting overridden with invalid input.
        value (object): Invalid value passed for that setting.
    """
    kwargs: dict[str, object] = {
        "base_url": NOMINATIM,
        "user_agent": USER_AGENT,
        "wikidata_base_url": WIKIDATA,
        "min_request_interval": 0,
    }
    kwargs[setting] = value
    with pytest.raises(InvalidInputError):
        PlacesClient(session, **kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url", ["https://nominatim.openstreetmap.org", "https://NOMINATIM.openstreetmap.org."]
)
async def test_public_host_rejects_subsecond_spacing(
    session: aiohttp.ClientSession,
    base_url: str,
) -> None:
    """Require the public service minimum while allowing private local hosts.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        base_url (str): Public service hostname under test.
    """
    with pytest.raises(InvalidInputError):
        PlacesClient(
            session,
            base_url=base_url,
            user_agent=USER_AGENT,
            wikidata_base_url=WIKIDATA,
            min_request_interval=0.5,
        )


@pytest.mark.asyncio
async def test_custom_and_private_hosts_allow_configured_intervals(
    session: aiohttp.ClientSession,
) -> None:
    """Allow private and custom provider URLs to use a zero or short interval.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    PlacesClient(
        session,
        base_url=NOMINATIM,
        user_agent=USER_AGENT,
        min_request_interval=0,
    )
    PlacesClient(
        session,
        base_url="https://nominatim.example.org",
        user_agent=USER_AGENT,
        wikidata_base_url=WIKIDATA,
        min_request_interval=0.25,
    )


@pytest.mark.asyncio
async def test_user_agent_rejects_header_line_breaks(
    session: aiohttp.ClientSession,
) -> None:
    """Reject CR/LF header injection while client configuration is constructed.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
    """
    with pytest.raises(InvalidInputError):
        PlacesClient(
            session,
            base_url=NOMINATIM,
            user_agent="aioplaces\r\nInjected: value",
            wikidata_base_url=WIKIDATA,
            min_request_interval=0,
        )


@pytest.mark.parametrize("operation", ["reverse", "lookup"])
@pytest.mark.parametrize("option", ["language", "email"])
@pytest.mark.parametrize("value", [0, [], "\ud800"])
async def test_invalid_query_options_raise_places_error(
    session: aiohttp.ClientSession, operation: str, option: str, value: object
) -> None:
    """Reject unsupported types and invalid Unicode before making a request.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        operation (str): Public method to exercise.
        option (str): Optional query argument to override.
        value (object): Invalid query value.
    """
    client = make_client(session)
    kwargs = {option: value}
    with aioresponses() as mocked:
        with pytest.raises(InvalidInputError):
            if operation == "reverse":
                await client.reverse(40, -70, **kwargs)  # type: ignore[arg-type]
            else:
                await client.lookup("node", 1, **kwargs)  # type: ignore[arg-type]
    assert request_count(mocked) == 0


def test_invalid_session_raises_places_error() -> None:
    """Reject a session of an unsupported type with the public input error."""
    with pytest.raises(InvalidInputError):
        PlacesClient(None, base_url=NOMINATIM, user_agent=USER_AGENT)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "error",
    [
        ValueError("invalid request"),
        TypeError("invalid header"),
        aiohttp.InvalidURL("invalid request URL"),
    ],
)
async def test_request_errors_preserve_their_cause_and_allow_recovery(
    session: aiohttp.ClientSession, error: ValueError | TypeError | aiohttp.InvalidURL
) -> None:
    """Translate local request errors and release serialization for the next call.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        error (ValueError | TypeError | aiohttp.InvalidURL): Failure raised at the HTTP boundary.
    """
    client = make_client(session)
    with aioresponses() as mocked:
        mocked.get(reverse_url(), exception=error)
        mocked.get(reverse_url(), payload={"name": "ok"})
        with pytest.raises(InvalidInputError) as caught:
            await client.reverse(40, -70)
        assert caught.value.__cause__ is error
        assert await client.reverse(40, -70) == {"name": "ok"}


@pytest.mark.parametrize(
    "body", ["[" * 2000 + "]" * 2000, "9" * 5000, '{"x":' * 600 + "0" + "}" * 600]
)
async def test_unprocessable_json_raises_places_error(
    session: aiohttp.ClientSession, body: str
) -> None:
    """Translate JSON nesting and integer conversion limits at the response boundary.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        body (str): JSON response that exceeds Python decoder limits.
    """
    with aioresponses() as mocked:
        mocked.get(reverse_url(), body=body)
        mocked.get(reverse_url(), payload={"name": "ok"})
        client = make_client(session)
        with pytest.raises(InvalidResponseError) as caught:
            await client.reverse(40, -70)
        assert await client.reverse(40, -70) == {"name": "ok"}
    assert isinstance(caught.value.__cause__, (ValueError, RecursionError))


@pytest.mark.parametrize("error", [LookupError("unknown codec"), UnicodeError("invalid text")])
async def test_response_text_errors_raise_places_error(
    session: aiohttp.ClientSession,
    monkeypatch: pytest.MonkeyPatch,
    error: LookupError | UnicodeError,
) -> None:
    """Translate response text decoding failures and retain their original cause.

    Args:
        session (aiohttp.ClientSession): Session borrowed by the client under test.
        monkeypatch (pytest.MonkeyPatch): Scoped response decoding override.
        error (LookupError | UnicodeError): Failure raised when reading response text.
    """

    async def failing_text(self: aiohttp.ClientResponse) -> NoReturn:
        """Simulate a response that cannot be decoded as text.

        Args:
            self (aiohttp.ClientResponse): Response whose text is requested.

        Raises:
            LookupError: If the configured failure concerns a codec lookup.
            UnicodeError: If the configured failure concerns text decoding.
        """  # noqa: DOC503  # The exception is supplied by the parameterized test.
        raise error

    monkeypatch.setattr(aiohttp.ClientResponse, "text", failing_text)
    with aioresponses() as mocked:
        mocked.get(reverse_url(), body="{}")
        with pytest.raises(InvalidResponseError) as caught:
            await make_client(session).reverse(40, -70)
    assert caught.value.__cause__ is error
