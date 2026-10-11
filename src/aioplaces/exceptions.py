"""Exceptions raised by the aioplaces client."""

from __future__ import annotations


class PlacesError(Exception):
    """Base class for client errors."""


class TransportError(PlacesError):
    """A request could not be completed because of a transport failure."""


class HTTPError(PlacesError):
    """An HTTP response had a non-success status.

    Attributes:
        status: The HTTP response status code.
        retry_after: The unmodified ``Retry-After`` response header, if present.
    """

    def __init__(self, status: int, retry_after: str | None = None) -> None:
        """Create an HTTP error with its response metadata.

        Args:
            status: The HTTP response status code.
            retry_after: The unmodified ``Retry-After`` response header.
        """
        self.status: int = status
        self.retry_after: str | None = retry_after
        super().__init__(f"HTTP request failed with status {status}")


class InvalidResponseError(PlacesError):
    """A service returned invalid JSON or a payload outside its contract."""
