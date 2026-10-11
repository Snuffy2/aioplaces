# aioplaces

## Project scope

- This is a standalone Python library for asynchronous Nominatim and Wikidata requests and pure place parsing.
- Require Python 3.14 or newer. Do not add Home Assistant dependencies or runtime behavior.
- Preserve GPL-3.0-only attribution to the Places contributors.

## Client behavior

- The caller owns the supplied `aiohttp.ClientSession`; the client must not close it.
- Keep concurrent requests serialized per client and preserve cancellation.
- Public Nominatim requests must be spaced by at least one second. Each client instance has its own cache and throttle; instances and processes do not coordinate.
- Do not add automatic retries or make Wikidata enrichment implicit.
- Keep parsing side-effect-free and preserve `ParsedPlace` immutability.

## Development commands

Use uv 0.11.0 or newer with the checked-in lock file and Python 3.14:

~~~sh
uv sync --python 3.14 --locked --group dev --group build
./.venv/bin/python -m prek run -a
uv sync --locked --group dev --group build
uv sync --python 3.14 --locked --group dev --group build
./.venv/bin/python -m pytest
./.venv/bin/python -m build --no-isolation
./.venv/bin/python -m twine check dist/*
~~~

The `dev` group includes `lint` and `pytest`; `build` is separate. `prek` runs
Ruff lint with fixes, Ruff formatting, and mypy. The second sync restores build
dependencies after prek. Pytest tests must mock HTTP and must not contact live
services. Keep coverage at or above the configured 80 percent threshold. Test
observable behavior, including relevant failure and cancellation paths, rather
than private call order.

The test workflow runs these checks on pull requests and pushes to `main`. It
also smoke-tests the built wheel in a fresh Python 3.14 environment without
Home Assistant. Do not use global Python tooling in place of the repository's
`.venv`.

## Code and documentation style

- Keep the `src/aioplaces` package layout.
- Add types, including return types, to new or changed public interfaces.
- Document public methods with Google-style docstrings.
- Catch specific exceptions and preserve useful comments.
- Update this README when install, configuration, or user-visible behavior changes.
- Keep release notes in the root `CHANGELOG.md`.

## Release and external changes

- Never push directly to `main`. Do not push any branch, publish to PyPI, or open pull requests unless the user explicitly requests it.
- Keep release versions aligned between `src/aioplaces/const.py`, release tags, and the release manifest.
- Repository automation needs externally configured GitHub secrets, variables, environments, and PyPI Trusted Publishers; see [`.github/RELEASING.md`](.github/RELEASING.md).
