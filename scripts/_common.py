"""Shared command-line configuration and JSON output for endpoint diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re

from yarl import URL

DEFAULT_USER_AGENT = "aioplaces-endpoint-scripts/1.0"


def base_url(value: str) -> str:
    """Validate a service root URL.

    Args:
        value (str): User-provided service URL.

    Returns:
        str: URL without trailing slashes.

    Raises:
        argparse.ArgumentTypeError: If the URL is not a plain HTTP(S) service root.
    """
    try:
        url = URL(value)
        valid = (
            url.scheme in {"http", "https"}
            and url.host is not None
            and url.user is None
            and url.password is None
            and "?" not in value
            and "#" not in value
            and not any(character.isspace() for character in value)
            and (url.port is None or 1 <= url.port <= 65535)
        )
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("Use an HTTP(S) base URL without credentials or query")
    return value.rstrip("/")


def positive_timeout(value: str) -> float:
    """Validate a finite positive request timeout.

    Args:
        value (str): Timeout supplied on the command line.

    Returns:
        float: Timeout in seconds.

    Raises:
        argparse.ArgumentTypeError: If the timeout is invalid.
    """
    try:
        timeout = float(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number") from err
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number")
    return timeout


def parse_args(description: str, argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate inputs before making any requests.

    Args:
        description (str): Help description for the calling script.
        argv (list[str] | None): Arguments, or process arguments when omitted.

    Returns:
        argparse.Namespace: Validated command-line settings.
    """
    parser = argparse.ArgumentParser(description=description)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--endpoint", choices=("reverse", "lookup", "wikidata"))
    selection.add_argument(
        "--list", action="store_true", help="List endpoints without HTTP requests"
    )
    parser.add_argument("--base-url", type=base_url, default="https://nominatim.openstreetmap.org")
    parser.add_argument(
        "--wikidata-base-url",
        type=base_url,
        default="https://www.wikidata.org/wiki/Special:EntityData",
    )
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("AIOPLACES_USER_AGENT", DEFAULT_USER_AGENT),
        help=f"Identifying User-Agent (default: {DEFAULT_USER_AGENT})",
    )
    parser.add_argument("--timeout", type=positive_timeout, default=10.0)
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--osm-type", choices=("node", "way", "relation", "N", "W", "R"))
    parser.add_argument("--osm-id", type=int)
    parser.add_argument("--wikidata-id")
    parser.add_argument("--language")
    parser.add_argument("--email")
    parser.add_argument("--output", type=Path, help="Also save JSON to this file")
    args = parser.parse_args(argv)
    if args.list:
        return args
    if (
        not args.user_agent
        or not args.user_agent.strip()
        or any(char in args.user_agent for char in "\r\n")
    ):
        parser.error(
            "--user-agent (or AIOPLACES_USER_AGENT) must identify your application/contact"
        )
    if args.endpoint == "reverse":
        for name, bound in (("latitude", 90), ("longitude", 180)):
            coordinate = getattr(args, name)
            if (
                coordinate is None
                or not math.isfinite(coordinate)
                or not -bound <= coordinate <= bound
            ):
                parser.error(f"--{name} must be finite and between {-bound} and {bound}")
    elif args.endpoint == "lookup":
        if args.osm_type is None or args.osm_id is None or args.osm_id <= 0:
            parser.error("lookup requires --osm-type and a positive --osm-id")
    elif args.wikidata_id is None or re.fullmatch(r"Q[1-9][0-9]*", args.wikidata_id) is None:
        parser.error("wikidata requires --wikidata-id such as Q42")
    return args


def write_output(result: object, output: Path | None) -> None:
    """Print JSON and optionally save the same document.

    Args:
        result (object): JSON-serializable result.
        output (Path | None): Optional destination file.
    """
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output is not None:
        output.write_text(text, encoding="utf-8")
    print(text, end="")
