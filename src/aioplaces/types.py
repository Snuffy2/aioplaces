"""JSON types used by the public client interface."""

from __future__ import annotations

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]
type JSONMapping = dict[str, JSONValue]
