# Endpoint diagnostics

Run these manual tools from the repository root with Python 3.14+ and the
repository virtualenv. They make real, read-only HTTP requests when you select an
endpoint. They are separate from the mocked pytest suite and are not installed
with the library.

If the environment is not set up yet:

```sh
uv sync --python 3.14 --locked --group dev --group build
```

Use `--user-agent` to supply your own application name and contact information.
No API keys are required.

For Nominatim reverse and lookup requests, include `--email you@example.com` to
send your contact address as the `email` query parameter. Nominatim's
[API documentation](https://nominatim.org/release-docs/latest/api/Reverse/#other)
asks for this when making larger numbers of requests; the parameter is optional
for ordinary queries. An email in the User-Agent does not populate this query
parameter. `--email` is not sent to Wikidata.

The public service's
[usage policy](https://operations.osmfoundation.org/policies/nominatim/) requires
an identifying User-Agent or Referer and limits traffic to one request per second.

## Library endpoints

`aioplaces_dump.py` calls `PlacesClient.reverse`, `lookup`, or `wikidata`, and
prints an object containing `endpoint` and normalized `data`. Lookup returns a
single object; no result becomes JSON `null`. Each invocation uses a fresh client
and bypasses cache reads. Wikidata is requested only when explicitly selected.

```sh
./.venv/bin/python -m scripts.aioplaces_dump --list
./.venv/bin/python -m scripts.aioplaces_dump --endpoint reverse \
  --latitude 48.8584 --longitude 2.2945 --language en --email you@example.com
./.venv/bin/python -m scripts.aioplaces_dump --endpoint lookup \
  --osm-type way --osm-id 5013364 --email you@example.com
./.venv/bin/python -m scripts.aioplaces_dump --endpoint wikidata \
  --wikidata-id Q243 --output /tmp/wikidata.json
```

## Raw upstream endpoints

`osm_api_call.py` sends the corresponding GET directly to Nominatim or Wikidata
using the same endpoint parameters as the library. It prints the URL, HTTP status,
reason, headers, decoded JSON, and original response text. This lets you compare
upstream payloads with the library's normalization and inspect HTTP error bodies
or non-JSON responses. Wikidata is a separate upstream service, not an OSM endpoint.

```sh
./.venv/bin/python -m scripts.osm_api_call --list
./.venv/bin/python -m scripts.osm_api_call --endpoint reverse \
  --latitude 48.8584 --longitude 2.2945 --email you@example.com
./.venv/bin/python -m scripts.osm_api_call --endpoint lookup \
  --osm-type W --osm-id 5013364 --email you@example.com --output /tmp/osm-lookup.json
./.venv/bin/python -m scripts.osm_api_call --endpoint wikidata --wikidata-id Q243
```

## Configuration and exit status

Both tools support the following options.

### General options

| Option | Purpose | Default | Required |
| --- | --- | --- | --- |
| `--endpoint` | Select `reverse`, `lookup`, or `wikidata` | — | Yes, unless using `--list` or `--help` |
| `--user-agent` | Identifying application/contact string | `aioplaces-endpoint-scripts/1.0` | No |
| `--timeout` | Positive finite request timeout in seconds | `10` | No |
| `--output` | Also save JSON to a UTF-8 file; overwrites that file | — | No |
| `--list` | List endpoints without a request; mutually exclusive with `--endpoint` | `false` | No |
| `--help` | Show all options without making a request | — | No |

### Reverse geocoding (`--endpoint reverse`)

| Option | Purpose | Default | Required |
| --- | --- | --- | --- |
| `--latitude` | Latitude from -90 to 90 | — | Yes |
| `--longitude` | Longitude from -180 to 180 | — | Yes |
| `--base-url` | Nominatim service root | `https://nominatim.openstreetmap.org` | No |
| `--language` | Nominatim language preference | — | No |
| `--email` | Contact address sent as Nominatim’s `email` query parameter | — | No |

### OSM feature lookup (`--endpoint lookup`)

| Option | Purpose | Default | Required |
| --- | --- | --- | --- |
| `--osm-type` | Feature type: `node`, `way`, `relation`, `N`, `W`, or `R` | — | Yes |
| `--osm-id` | Positive integer OSM feature identifier | — | Yes |
| `--base-url` | Nominatim service root | `https://nominatim.openstreetmap.org` | No |
| `--language` | Nominatim language preference | — | No |
| `--email` | Contact address sent as Nominatim’s `email` query parameter | — | No |

### Wikidata (`--endpoint wikidata`)

| Option | Purpose | Default | Required |
| --- | --- | --- | --- |
| `--wikidata-id` | Entity identifier such as `Q243` | — | Yes |
| `--wikidata-base-url` | Wikidata entity root | `https://www.wikidata.org/wiki/Special:EntityData` | No |

### Exit status and request behavior

Each invocation makes at most one request. HTTPS requests use certificate
verification; requests do not follow redirects and are not automatically retried.
Both tools exit nonzero for invalid arguments, network failures, or output errors.
An output-file error still prints the received result to stdout before exiting.
The library tool also exits nonzero for HTTP or response validation errors; no
result is a successful `null` response. The raw tool exits `1` for any HTTP
status outside 200–299, while still printing the response. A service error
inside an HTTP 200 body remains a raw HTTP success; inspect `json`/`text` for
its meaning.

Follow the upstream usage policies documented in the project's documentation.
For public Nominatim, leave at least one second between requests, including
separate invocations and other clients. Do not run these commands concurrently
against the public service or use them for bulk queries. The library throttles
within its client instance; separate processes and the raw tool do not share a
throttle. Use `--base-url` for your own Nominatim instance when needed.

## Offline validation

Run the full suite and repository checks without contacting upstream services:

```sh
./.venv/bin/python -m pytest
./.venv/bin/python -m prek run -a
```
