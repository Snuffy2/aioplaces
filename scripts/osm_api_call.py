"""Inspect raw Nominatim and Wikidata responses without library normalization."""

from __future__ import annotations

import argparse
import asyncio
import json

import aiohttp

from scripts._common import parse_args, write_output


def reject_json_constant(value: str) -> None:
    """Reject a non-finite numeric constant from a JSON response.

    Args:
        value (str): Non-finite constant found in the response body.

    Raises:
        ValueError: Always, because the constant is not valid JSON.
    """
    raise ValueError(f"Invalid JSON constant: {value}")


def request_target(args: argparse.Namespace) -> tuple[str, dict[str, str]]:
    """Build the upstream request corresponding to the selected library method.

    Args:
        args (argparse.Namespace): Validated CLI configuration.

    Returns:
        tuple[str, dict[str, str]]: Endpoint URL and query parameters.
    """
    if args.endpoint == "wikidata":
        return f"{args.wikidata_base_url}/{args.wikidata_id}.json", {}
    params = {
        "format": "json",
        "addressdetails": "1",
        "namedetails": "1",
        "accept-language": args.language or "",
        "email": args.email or "",
    }
    if args.endpoint == "reverse":
        params.update(lat=str(args.latitude), lon=str(args.longitude), zoom="18", limit="1")
    else:
        params.update(osm_ids=f"{args.osm_type[0].upper()}{args.osm_id}", extratags="1")
    return f"{args.base_url}/{args.endpoint}", params


async def async_main(argv: list[str] | None = None) -> int:
    """Make a single raw GET request and preserve response metadata.

    Args:
        argv (list[str] | None): CLI arguments, or process arguments when omitted.

    Returns:
        int: Zero for HTTP success or listing; one for an HTTP failure.
    """
    args = parse_args("Inspect a raw OSM/Nominatim or Wikidata endpoint response.", argv)
    if args.list:
        write_output(["reverse", "lookup", "wikidata"], args.output)
        return 0
    url, params = request_target(args)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            params=params,
            headers={"User-Agent": args.user_agent},
            timeout=aiohttp.ClientTimeout(total=args.timeout),
            allow_redirects=False,
            raise_for_status=False,
        ) as response:
            body = await response.text(errors="replace")
            try:
                payload = json.loads(body, parse_constant=reject_json_constant)
            except ValueError:
                payload = None
            result = {
                "endpoint": args.endpoint,
                "url": str(response.url),
                "status": response.status,
                "reason": response.reason,
                "headers": dict(response.headers),
                "json": payload,
                "text": body,
            }
            status = 0 if 200 <= response.status < 300 else 1
    write_output(result, args.output)
    return status


def main() -> int:
    """Run the command and report transport or output failures.

    Returns:
        int: Process exit status.

    Raises:
        SystemExit: If a transport or file failure prevents completion.
    """
    try:
        return asyncio.run(async_main())
    except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as err:
        raise SystemExit(f"{type(err).__name__}: {err}") from None


if __name__ == "__main__":
    raise SystemExit(main())
