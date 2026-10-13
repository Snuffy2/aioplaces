"""Tests for decoded JSON value validation."""

from __future__ import annotations

import pytest

from aioplaces.client import _as_json_value
from aioplaces.exceptions import InvalidResponseError


@pytest.mark.parametrize(
    "value",
    [object(), [object()], {"nested": object()}],
    ids=("root", "list-item", "mapping-value"),
)
def test_as_json_value_rejects_unsupported_values(value: object) -> None:
    """Reject unsupported values at the root and within JSON containers.

    Args:
        value (object): A value outside JSON's supported value types.
    """
    with pytest.raises(InvalidResponseError):
        _as_json_value(value)
