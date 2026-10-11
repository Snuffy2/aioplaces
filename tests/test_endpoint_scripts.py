"""Exercise manual diagnostic commands at their mocked HTTP boundary."""

from __future__ import annotations

import json
from pathlib import Path
import re

from aioresponses import aioresponses
import pytest
from yarl import URL

from aioplaces import HTTPError
from scripts import aioplaces_dump, osm_api_call
from scripts._common import parse_args

BASE = "https://nominatim.example.test"
ENTITY_BASE = "https://wikidata.example.test/entities"
COMMON = [
    "--base-url",
    BASE,
    "--wikidata-base-url",
    ENTITY_BASE,
    "--user-agent",
    "places-tests/1.0 (test@example.com)",
]


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("user_agent", [None, "places-tests/1.0 (test@example.com)"])
@pytest.mark.parametrize(
    ("endpoint", "arguments", "payload", "expected", "query"),
    [
        (
            "reverse",
            ["--latitude", "48.8584", "--longitude", "2.2945"],
            {"display_name": "Paris"},
            {"display_name": "Paris"},
            {"lat": "48.8584", "lon": "2.2945", "zoom": "18", "limit": "1"},
        ),
        (
            "lookup",
            ["--osm-type", "way", "--osm-id", "5013364"],
            [{"display_name": "Tower"}],
            {"display_name": "Tower"},
            {"osm_ids": "W5013364", "extratags": "1"},
        ),
        (
            "wikidata",
            ["--wikidata-id", "Q243"],
            {"entities": {"Q243": {}}},
            {"entities": {"Q243": {}}},
            {},
        ),
    ],
)
async def test_endpoint_requests(
    raw: bool,
    user_agent: str | None,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    arguments: list[str],
    payload: object,
    expected: object,
    query: dict[str, str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify selected endpoints, headers, query parameters, and saved JSON.

    Args:
        raw (bool): Whether to run the direct HTTP tool.
        user_agent (str | None): Explicit override, or use the built-in default.
        monkeypatch (pytest.MonkeyPatch): Isolate the default from environment overrides.
        endpoint (str): Selected operation.
        arguments (list[str]): Endpoint-specific arguments.
        payload (object): Mock upstream JSON.
        expected (object): Expected library-normalized response.
        query (dict[str, str]): Endpoint-specific query expectations.
        tmp_path (Path): Temporary output directory.
        capsys (pytest.CaptureFixture[str]): Captured command output.
    """
    monkeypatch.delenv("AIOPLACES_USER_AGENT", raising=False)
    configuration = COMMON[:-2]
    if user_agent is not None:
        configuration = configuration + ["--user-agent", user_agent]
    target = f"{ENTITY_BASE}/Q243.json" if endpoint == "wikidata" else f"{BASE}/{endpoint}"
    output = tmp_path / "result.json"
    with aioresponses() as mocked:
        mocked.get(re.compile(re.escape(target) + r"(?:\?.*)?$"), payload=payload)
        command = osm_api_call.async_main if raw else aioplaces_dump.async_main
        status = await command(
            configuration + ["--endpoint", endpoint, "--output", str(output)] + arguments
        )
        request_url = next(iter(mocked.requests))[1]
        request = next(iter(mocked.requests.values()))[0]
        assert request.kwargs["headers"]["User-Agent"] == (
            user_agent or "aioplaces-endpoint-scripts/1.0"
        )
        assert request.kwargs["allow_redirects"] is False
        assert request.kwargs["timeout"].total == 10
        for key, value in query.items():
            assert URL(request_url).query[key] == value
        if endpoint != "wikidata":
            assert URL(request_url).query["format"] == "json"
            assert URL(request_url).query["addressdetails"] == "1"
            assert URL(request_url).query["namedetails"] == "1"
    assert status == 0
    printed = capsys.readouterr().out
    assert output.read_text() == printed
    result = json.loads(printed)
    assert result["endpoint"] == endpoint
    assert result["json" if raw else "data"] == (payload if raw else expected)


@pytest.mark.parametrize("raw", [False, True])
async def test_list_without_network(raw: bool, capsys: pytest.CaptureFixture[str]) -> None:
    """List operations without a User-Agent or HTTP access.

    Args:
        raw (bool): Whether to run the raw tool.
        capsys (pytest.CaptureFixture[str]): Captured output.
    """
    with aioresponses() as mocked:
        command = osm_api_call.async_main if raw else aioplaces_dump.async_main
        assert await command(["--list"]) == 0
        assert not mocked.requests
    assert json.loads(capsys.readouterr().out) == ["reverse", "lookup", "wikidata"]


async def test_raw_http_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Preserve a non-JSON error body and return failure without retrying.

    Args:
        capsys (pytest.CaptureFixture[str]): Captured output.
    """
    with aioresponses() as mocked:
        mocked.get(
            f"{ENTITY_BASE}/Q243.json", status=429, body="Slow down", headers={"Retry-After": "5"}
        )
        assert (
            await osm_api_call.async_main(
                COMMON + ["--endpoint", "wikidata", "--wikidata-id", "Q243"]
            )
            == 1
        )
        assert sum(len(calls) for calls in mocked.requests.values()) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == 429
    assert result["json"] is None
    assert result["text"] == "Slow down"
    assert result["headers"]["Retry-After"] == "5"


async def test_library_no_result(capsys: pytest.CaptureFixture[str]) -> None:
    """Report a missing feature as a successful null result.

    Args:
        capsys (pytest.CaptureFixture[str]): Captured output.
    """
    with aioresponses() as mocked:
        mocked.get(re.compile(re.escape(f"{BASE}/lookup") + r"\?.*"), payload=[])
        assert (
            await aioplaces_dump.async_main(
                COMMON + ["--endpoint", "lookup", "--osm-type", "node", "--osm-id", "1"]
            )
            == 0
        )
    assert json.loads(capsys.readouterr().out)["data"] is None


async def test_library_http_error() -> None:
    """Surface a library HTTP failure rather than reporting success."""
    with aioresponses() as mocked:
        mocked.get(f"{ENTITY_BASE}/Q243.json", status=503)
        with pytest.raises(HTTPError):
            await aioplaces_dump.async_main(
                COMMON + ["--endpoint", "wikidata", "--wikidata-id", "Q243"]
            )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--endpoint", "reverse", "--latitude", "nan", "--longitude", "0"],
        ["--endpoint", "reverse", "--latitude", "91", "--longitude", "0"],
        ["--endpoint", "lookup", "--osm-type", "node", "--osm-id", "0"],
        ["--endpoint", "wikidata", "--wikidata-id", "Q0"],
        ["--endpoint", "wikidata", "--wikidata-id", "Q42", "--timeout", "inf"],
        [
            "--endpoint",
            "wikidata",
            "--wikidata-id",
            "Q42",
            "--base-url",
            "https://user:pass@example.com",
        ],
        ["--endpoint", "wikidata", "--wikidata-id", "Q42", "--user-agent", "bad\nagent"],
    ],
)
def test_invalid_arguments(arguments: list[str]) -> None:
    """Reject invalid endpoint inputs before network access.

    Args:
        arguments (list[str]): Invalid arguments appended to shared configuration.
    """
    with pytest.raises(SystemExit) as raised:
        parse_args("Test", COMMON + arguments)
    assert raised.value.code == 2
