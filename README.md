# aioplaces

Async Nominatim and Wikidata requests with typed, side-effect-free place parsing.
Python 3.14 or newer is required. No Home Assistant installation is needed.

The library provides reverse geocoding, OSM feature lookup, Wikidata entity
retrieval, a shared TTL cache, and serialized request throttling. It does not
implement forward search, Overpass, sensor state, zones, or previous-place history.

## Installation

Until the first PyPI release, install from a local checkout:

```sh
python -m pip install .
```

Once published, installation will be `python -m pip install aioplaces`.

## Usage

Choose a Nominatim endpoint whose usage policy permits your application. Set
`NOMINATIM_URL` to that endpoint's base URL, including any deployment path prefix.
The library deliberately requires the endpoint and an identifying user agent.

```python
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
```

The caller owns the HTTP session and closes it. Reuse one `PlacesClient` across
concurrent consumers to share its cache and throttle. Client instances belong to
one event loop; different instances or processes do not coordinate their limits.
Language and optional contact `email` are per-request arguments. The library does
not invent a contact email or submit one unless supplied.

`reverse(latitude, longitude, ...)` calls Nominatim's `/reverse` endpoint.
`lookup(osm_type, osm_id, ...)` calls `/lookup` for one feature: `osm_type` accepts
`node`, `way`, `relation`, or `N`, `W`, `R`. `wikidata("Q123")` retrieves the
Wikidata entity JSON. Lookup requests include namedetails, addressdetails, and
extratags. Wikidata retrieval is explicit; the library does not fetch enrichment
automatically.

Each operation returns a JSON mapping, or `None` when no result exists. The raw
mapping remains available for application-specific attributes and enrichment.
`parse_place` returns an immutable `ParsedPlace` containing attribution, OSM
identity, type/category, localized name, street, city, cleaned city, postal town,
neighbourhood, region, county, country, postal code, formatted address, and route
reference. Missing or inappropriate scalar values become `None`; parsing never
mutates the supplied payload. Language preference follows the comma-separated
order used by Places. Duplicate-name suppression and history belong to callers.

## Cache and failures

Defaults are a 500-entry cache with a four-hour TTL, a ten-second HTTP timeout,
and serialized requests spaced at least one second apart. Settings are constructor
arguments: `cache_maxsize`, `cache_ttl`, `timeout`, and `min_request_interval`.
The optional `wikidata_base_url` defaults to Wikidata's `Special:EntityData` endpoint.
Custom Nominatim servers can use a different nonnegative request interval; the
public OpenStreetMap host cannot be configured below one second.

Results are copied, including nested values, so callers cannot corrupt cached
responses. `use_cache=False` bypasses reads and replaces the cache after a successful
request. A failed forced refresh retains the previous success until it expires.
Empty results and errors are not cached. A failed normal request removes any
cached result for that request. Endpoint, language, email, and request arguments
participate in the cache key.

`PlacesError` is the common exception base. `TransportError` represents connection
or timeout failures; `HTTPError` exposes `status` and optional `retry_after`;
`InvalidResponseError` represents invalid JSON, unsupported response shapes, or
upstream service errors. Invalid caller arguments raise `ValueError`. Cancellation
propagates. Requests are not retried automatically.

## Upstream usage policies

The [public Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
requires an identifying application user agent, attribution, caching, and at most
one request per second across the application. Recurring geocoding has additional
restrictions, including four requests per minute for regular or long-running bulk
scripts. Periodic requests are discouraged. These limits are not per library
instance or per end user: a local throttle alone does not establish compliance.
Use a suitable hosted provider or your own Nominatim deployment when required.
Do not submit confidential or personal information contrary to the service policy.

Preserve and display attribution returned in `ParsedPlace.attribution`.
OpenStreetMap data licensing is separate from this library's source license.
Consult [Wikimedia's user-agent policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
for Wikidata requests as well.

## Development

```sh
uv sync --python 3.14 --locked --group dev --group build
./.venv/bin/python -m prek run -a
./.venv/bin/python -m pytest
./.venv/bin/python -m build --no-isolation
./.venv/bin/python -m twine check dist/*
```

Tests mock HTTP requests and do not contact upstream services. CI also installs
the built wheel into a fresh environment without Home Assistant and imports its
public API. At least 80% combined statement/branch coverage is required.

## Releases

Release Please manages version updates and changelogs from conventional commits.
Configure `RELEASE_PLEASE_TOKEN` with repository access so its release events can
trigger the publication workflow. Set the repository variable
`RELEASE_PLEASE_ENABLED=true` after configuring that token to enable automation.
Configure PyPI and TestPyPI Trusted Publishers
for owner `Snuffy2`, repository `aioplaces`, workflow `publish.yml`, and environments
`pypi` and `testpypi` respectively. Protect both GitHub environments with required
reviewers and restrict production publication to release tags.

Manual dispatch of `publish.yml` uploads to TestPyPI. Publishing a non-prerelease
GitHub release with a tag matching `v<pyproject version>` uploads its validated
wheel and source distribution to PyPI. No package has been published yet. A PyPI
name lookup returning 404 does not guarantee the name can be registered.

## Origin and license

Request behavior and address precedence were extracted from the
[Places Home Assistant integration](https://github.com/custom-components/places)
at commit `f2e9e3af54f67e83b680189b2e069d478f9e2ade` (3.0.2).
Credit belongs to the Places contributors; source history is retained in the
original repository. This library preserves the GPL version 3 source license; see
[LICENSE](LICENSE). Places itself has not been changed to use this package.
