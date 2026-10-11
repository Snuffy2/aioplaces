"""Call one live aioplaces client method and dump its normalized JSON result."""

from __future__ import annotations

import asyncio

import aiohttp

from aioplaces import PlacesClient, PlacesError
from scripts._common import parse_args, write_output


async def async_main(argv: list[str] | None = None) -> int:
    """Run one library endpoint using a session owned by this command.

    Args:
        argv (list[str] | None): CLI arguments, or process arguments when omitted.

    Returns:
        int: Zero after a successful request or endpoint listing.
    """
    args = parse_args("Dump an aioplaces endpoint response.", argv)
    if args.list:
        write_output(["reverse", "lookup", "wikidata"], args.output)
        return 0
    async with aiohttp.ClientSession() as session:
        client = PlacesClient(
            session,
            base_url=args.base_url,
            wikidata_base_url=args.wikidata_base_url,
            user_agent=args.user_agent,
            timeout=args.timeout,
        )
        if args.endpoint == "reverse":
            data = await client.reverse(
                args.latitude,
                args.longitude,
                language=args.language,
                email=args.email,
                use_cache=False,
            )
        elif args.endpoint == "lookup":
            data = await client.lookup(
                args.osm_type,
                args.osm_id,
                language=args.language,
                email=args.email,
                use_cache=False,
            )
        else:
            data = await client.wikidata(args.wikidata_id, use_cache=False)
    write_output({"endpoint": args.endpoint, "data": data}, args.output)
    return 0


def main() -> int:
    """Run the command and report library or file failures.

    Returns:
        int: Process exit status.

    Raises:
        SystemExit: If an expected runtime failure prevents completion.
    """
    try:
        return asyncio.run(async_main())
    except (PlacesError, ValueError, OSError) as err:
        raise SystemExit(f"{type(err).__name__}: {err}") from None


if __name__ == "__main__":
    raise SystemExit(main())
