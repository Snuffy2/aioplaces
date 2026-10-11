# aioplaces
[![Documentation][docs-shield]][docs]

aioplaces is a standalone asynchronous Python client for Nominatim reverse
geocoding and OSM feature lookup, Wikidata entity retrieval, and typed parsing
of Nominatim place responses. Python 3.14 or newer is required.

## Documentation

- Read the Docs: <https://aioplaces.readthedocs.io>

The documentation covers installation, quick start examples, client configuration,
API reference, upstream usage policies, and development.

## Releases

The publish workflow uses
PyPI Trusted Publishing: stable GitHub Releases go to PyPI and prereleases go
to TestPyPI.

## Origin and license

Extracted from the [Places Home Assistant integration](https://github.com/custom-components/places).
Credit belongs to the Places contributors. Licensed under GPL-3.0-only; see
[LICENSE](LICENSE).

[docs]: https://aioplaces.readthedocs.io
[docs-shield]: https://app.readthedocs.org/projects/aioplaces/badge/?version=latest&style=for-the-badge

## Endpoint diagnostics

The [scripts README](scripts/README.md) documents manual tools for testing
aioplaces client methods and inspecting raw Nominatim and Wikidata responses.
