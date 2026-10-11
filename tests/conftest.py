"""Shared HTTP mock compatibility for the offline test suite."""

from __future__ import annotations

import inspect

import aiohttp
import aioresponses.core as aioresponses_core
import pytest
from yarl import URL


class _MockStreamWriter:
    """Provide the response writer attribute required by current aiohttp."""

    output_size: int = 0


class _CompatibleClientResponse(aiohttp.ClientResponse):
    """Adapt aioresponses' response constructor to aiohttp 3.14."""

    def __init__(self, method: str, url: URL, **kwargs: object) -> None:
        """Supply the stream-writer argument added by aiohttp 3.14.

        Args:
            method (str): HTTP method for the mocked response.
            url (URL): Request URL for the mocked response.
            **kwargs (object): Remaining constructor arguments from aioresponses.
        """
        kwargs["stream_writer"] = _MockStreamWriter()
        super().__init__(method, url, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def patch_aioresponses_response_constructor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bridge only older aioresponses response builders to aiohttp 3.14.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest patch fixture.
    """
    parameters = inspect.signature(aiohttp.ClientResponse).parameters
    builder_source = inspect.getsource(aioresponses_core.RequestMatch._build_response)
    if "stream_writer" in parameters and "stream_writer" not in builder_source:
        monkeypatch.setattr(aioresponses_core, "ClientResponse", _CompatibleClientResponse)
