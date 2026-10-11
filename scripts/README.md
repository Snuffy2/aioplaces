# Endpoint diagnostics

Run these manual tools from the repository root with Python 3.14+ and the
repository virtualenv. They make real, read-only HTTP requests when you select an
endpoint. They are separate from the mocked pytest suite and are not installed
with the library.

If the environment is not set up yet:

```sh
uv sync --python 3.14 --locked --group dev --group build
```

Set an identifying User-Agent with your application name and contact information:

```sh
export AIOPLACES_USER_AGENT='my-places-check/1.0 (contact: you@example.com)'
```

You can also supply `--user-agent` on each command. No API keys are required.

## Library endpoints

`aioplaces_dump.py` calls `PlacesClient.reverse`, `lookup`, or `wikidata`, and
prints an object containing `endpoint` and normalized `data`. Lookup returns a
single object; no result becomes JSON `null`. Each invocation uses a fresh client
and bypasses cache reads. Wikidata is requested only when explicitly selected.

```sh
./.venv/bin/python -m scripts.aioplaces_dump --list
./.venv/bin/python -m scripts.aioplaces_dump --endpoint reverse \
  --latitude 48.8584 --longitude 2.2945 --language en
./.venv/bin/python -m scripts.aioplaces_dump --endpoint lookup \
  --osm-type way --osm-id 5013364
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
  --latitude 48.8584 --longitude 2.2945
./.venv/bin/python -m scripts.osm_api_call --endpoint lookup \
  --osm-type W --osm-id 5013364 --output /tmp/osm-lookup.json
./.venv/bin/python -m scripts.osm_api_call --endpoint wikidata --wikidata-id Q243
```

## Configuration and exit status

Both tools support:

| Option | Purpose / default |
| --- | --- |
| `--base-url` | Nominatim service root; `https://nominatim.openstreetmap.org` |
| `--wikidata-base-url` | Entity root; `https://www.wikidata.org/wiki/Special:EntityData` |
| `--user-agent` | Overrides `AIOPLACES_USER_AGENT` |
| `--timeout` | Positive finite request timeout in seconds; `10` |
| `--language`, `--email` | Optional Nominatim language and contact parameters |
| `--output` | Also write the printed JSON to a UTF-8 file; overwrites that file |
| `--list` | List available endpoints without making a request |
| `--help` | Show all options without making a request |

Each invocation makes at most one request. Requests use TLS verification, do not
follow redirects, and are not automatically retried. Both tools exit nonzero for
invalid arguments, network failures, or output errors. The library tool also
exits nonzero for HTTP or response validation errors; no result is a successful
`null` response. The raw tool exits `1` for any HTTP status outside 200–299, while
still printing the response. A service error inside an HTTP 200 body remains a
raw HTTP success; inspect `json`/`text` for its meaning.

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
