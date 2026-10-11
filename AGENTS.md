# AGENTS

## Purpose

- Provide clear, repo-specific instructions for autonomous agents working in this repository.

## General Guidelines

- Be concise and explain coding steps briefly when making code changes; include code snippets and tests where relevant.
- For non-trivial edits, provide a short plan. For small, low-risk edits, implement and include a one-line summary.
- Focus on a single conceptual change at a time when public APIs or multiple modules are affected.
- Maintain project style and Python 3.14+ compatibility.
- If deviating from these guidelines, explicitly state which guideline is deviated from and why.
- Keep this library standalone; do not introduce Home Assistant dependencies.
- Preserve GPL-3.0-only attribution to the Places contributors.
- Do not modify Places unless explicitly requested. Changes explicitly requested across both Places and aioplaces require coordinated branches in both repositories.

## Agent permissions and venv policy

- Agents may create and use a repository-local venv at `./.venv`. Use `./.venv/bin/python`, `./.venv/bin/pytest`, and `./.venv/bin/prek` for local commands unless using the main checkout venv for a git worktree with no dependency changes.
- The project uses `pyproject.toml` dependency groups (`lint`, `pytest`, `dev`, `build`). Installing packages from repo manifests into `./.venv` is allowed for running tests or local tooling after approval; avoid unrelated network operations without explicit consent.

## Folder structure (repo-specific)

- `src/aioplaces`: library code.
- `tests`: pytest test suite and fixtures.
- `README.md`: primary documentation.
- `CHANGELOG.md`: release notes.
- `.github/workflows`: GitHub Workflows
- `.github/scripts`: scripts for GitHub Workflows

## Coding standards

- Add typing annotations to all functions and classes (including return types).
- Add or update docstrings for all files, classes and methods, including private methods and nested methods. Method docstrings must follow the Google Style.
- For protocol-only typing contract files, keep protocol members as typed signatures with `...`; do not add per-method docstrings or `abstractmethod` boilerplate.
- Preserve existing comments and keep imports at the top of files.
- Do not use `assert` or `cast` in main code.
- Follow existing repository style; run `prek`.
- Python 3.14 syntax is allowed, including PEP 695 type parameters and PEP 758 grouped exception handlers.

## Client behavior

- The caller owns the supplied `aiohttp.ClientSession`; the client must not close it.
- Keep concurrent requests serialized per client and preserve cancellation.
- Public Nominatim requests must be spaced by at least one second. Each client instance has its own cache and throttle; instances and processes do not coordinate.
- Do not add automatic retries or make Wikidata enrichment implicit.
- Keep parsing side-effect-free and preserve `ParsedPlace` immutability.

## Local tooling note

- Use the repo's `prek` and `pytest` commands through the applicable repo venv path (`./.venv` here, or the main checkout venv for a worktree with no dependency changes). Do not use system Python.
- By default, run the full pytest suite. If running targeted tests, explain why.
- Sync dependencies with `uv sync --python 3.14 --locked --group dev --group build`.
- Run `./.venv/bin/python -m prek run -a` and `./.venv/bin/python -m pytest`.
- The mypy hook syncs only the dev group. Restore build dependencies with `uv sync --locked --group dev --group build` before building distributions.
- Build with `./.venv/bin/python -m build --no-isolation` and check distributions with `./.venv/bin/python -m twine check dist/*`.

## Error handling & logging

- Catch specific exceptions (do not catch Exception directly).
- Add robust error handling and clear debug/info logs.
- If tests fail due to missing dev dependencies, either install them into `./.venv` (if allowed) or report exact `pip install` commands.

## Testing

- Use `pytest`.
- Add typed, well-documented tests in `tests/` and use fixtures in `conftest.py`.
- Use `importlib` only in workflow script or other script/module-loading tests; minimize `cast` and `Any` unless the test boundary requires them.
- Parameterize tests when appropriate; avoid duplicate test functions.
- Mock upstream HTTP requests; the test suite must not contact live services.
- Keep coverage at or above the configured 80 percent threshold. Test observable behavior, including relevant failure and cancellation paths, rather than private call order.

## PR & branch behavior

- Never push directly to `main`. Use feature branches and pull requests for authorized pushes.
- Create branches or PRs only when explicitly requested. Do not open PRs autonomously.
- Do not push branches or publish to PyPI unless explicitly requested.
- Every pull request title must begin with a Conventional Commit prefix, such as `fix:`,
  `feat:`, or `chore(deps):`.

## Network / install consent

- Obtain explicit consent before any network operations outside the repository not strictly needed to run local tests.
- Package installs required for running tests are allowed when user approves.

## CI/CD

- Use GitHub Actions for CI/CD where applicable.
- Keep versions aligned between `src/aioplaces/const.py`, release tags, and `.release-please-manifest.json`.
- Repository automation requires GitHub secrets, publishing environments, and PyPI Trusted Publishers; see [.github/RELEASING.md](.github/RELEASING.md).

## Conventions for changes and documentation

- When editing code, prefer fixing root causes over surface patches.
- Keep changes minimal and consistent with the codebase style.
- Add meaningful tests for changed behavior and update documentation if needed. Use relevant validators for documentation-only changes.
- Update `README.md` when install, configuration, or user-visible behavior changes.
