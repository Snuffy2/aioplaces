# aioplaces

aioplaces is a standalone asynchronous Python client for Nominatim reverse
geocoding and OSM feature lookup, Wikidata entity retrieval, and typed parsing
of Nominatim place responses. Python 3.14 or newer is required. It has no Home
Assistant dependency.

The library does not implement forward search, Overpass, sensor state, zones, or
previous-place history. Hosted documentation is planned for a later change; this
README is the current user guide.

## Installation

The package has not had its first PyPI release. For now, install from a checkout
with Python 3.14 active:

~~~sh
python -m pip install .
~~~

After the package is published, install it from PyPI with:

~~~sh
python -m pip install aioplaces
~~~

## Quick start

Choose a Nominatim endpoint whose usage policy permits your application. Set
`NOMINATIM_URL` to its base URL, including any deployment path prefix. The client
requires both the endpoint and an identifying user agent.

~~~python
import asyncio
import os

import aiohttp

from aioplaces import PlacesClient, parse_place


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        client = PlacesClient(
            session,
            base_url=os.environ["NOMINATIM_URL"],
            user_agent="your-app/1.0 (+https://your-app.example/contact)",
        )
        payload = await client.reverse(40.7128, -74.0060, language="en,fr")
        if payload is not None:
            place = parse_place(payload, language="en,fr")
            print(place.place_name, place.city, place.country)


asyncio.run(main())
~~~

The caller owns and closes the `aiohttp.ClientSession`. Reuse a client instance
for concurrent consumers on the same event loop to share its cache and request
spacing. Separate instances and processes do not coordinate. The optional
Nominatim `email` argument is sent only when the caller supplies it.

`reverse(latitude, longitude)` calls Nominatim's `/reverse` endpoint.
`lookup(osm_type, osm_id)` calls `/lookup` for one node, way, or relation (also
accepted as `N`, `W`, or `R`). `wikidata("Q123")` retrieves Wikidata entity JSON.
Lookup requests ask for address details, name details, and extra tags; Wikidata
retrieval is explicit and is not automatic enrichment.

Each client operation returns a JSON mapping or `None` if there is no result.
The raw mapping remains available for application-specific fields.
`parse_place` returns a frozen `ParsedPlace` with attribution, OSM identity, type
and category, localized name, street, city, postal town, neighbourhood, region,
county, country, postal code, formatted address, and route reference. Malformed
or unsupported values become `None`; parsing does not mutate the input. Language
preferences are tried in their comma-separated order.

## Client defaults and failures

The defaults are a 500-entry cache, a four-hour cache lifetime, a ten-second
request timeout, and at least one second between requests made by a client.
Configure these with `cache_maxsize`, `cache_ttl`, `timeout`, and
`min_request_interval`; `wikidata_base_url` selects another Wikidata entity
endpoint. The public `nominatim.openstreetmap.org` host rejects an interval
below one second. A custom Nominatim endpoint may use any finite, nonnegative
interval.

Cached mappings are deep-copied both when stored and returned. By default, a
successful response is cached; an empty result is not. A normal failed request
evicts a cached response for that request. A forced refresh with
`use_cache=False` bypasses cache reads, replaces the cached value on success,
and retains an earlier successful value if the refresh fails. Request settings,
including endpoint, language, email, and operation arguments, are part of the
cache key.

`PlacesError` is the common exception base. `TransportError` covers network and
timeout failures. `HTTPError` exposes the response `status` and optional
`retry_after` header. `InvalidResponseError` covers invalid JSON and unsupported
or error response payloads. Invalid caller arguments raise `ValueError`.
Cancellation propagates, and requests are not retried automatically.

## Upstream usage policies

The [public Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
requires an identifying application user agent, attribution, caching, and no
more than one request per second across the application. Recurring geocoding
has additional restrictions, including four requests per minute for regular or
long-running bulk scripts; periodic requests are discouraged. These limits
apply to the whole application, not each library instance or end user. A local
client throttle alone does not establish compliance. Use a suitable hosted
provider or your own Nominatim deployment when needed, and do not submit
confidential or personal information contrary to the service policy.

Preserve and display attribution returned in `ParsedPlace.attribution`.
OpenStreetMap data licensing is separate from this library's source license.
Consult [Wikimedia's user-agent policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
for Wikidata requests as well.

## Development

Install the locked development and build dependencies with
[uv](https://docs.astral.sh/uv/) and Python 3.14 or newer:

~~~sh
uv sync --python 3.14 --locked --group dev --group build
./.venv/bin/python -m prek run -a
uv sync --locked --group dev --group build
uv sync --python 3.14 --locked --group dev --group build
./.venv/bin/python -m pytest
./.venv/bin/python -m build --no-isolation
./.venv/bin/python -m twine check dist/*
~~~

The `dev` dependency group includes the `lint` and `pytest` groups; `build` is
separate. The second sync restores the build dependencies after prek. Tests mock
HTTP requests and do not contact upstream services. CI runs these checks on
pull requests and pushes to `main`, then installs the built wheel in a clean
Python 3.14 environment without Home Assistant and imports the public API.
Coverage must reach 80 percent.

## Releases

Release automation and repository setup are described in
[.github/RELEASING.md](.github/RELEASING.md). The publish workflow uses
PyPI Trusted Publishing: stable GitHub Releases go to PyPI and prereleases go
to TestPyPI. No package has been published yet.

## Origin and license

Request behavior and address precedence were extracted from the
[Places Home Assistant integration](https://github.com/custom-components/places)
at commit `f2e9e3af54f67e83b680189b2e069d478f9e2ade` (3.0.2). Credit belongs
to the Places contributors; source history remains in the original repository.
This library preserves the GPL version 3 source license; see [LICENSE](LICENSE).
The Places integration has not been changed to use this package.
