# Releasing aioplaces

Release Please manages stable version selection, changelog updates, release
tags, and GitHub Releases. A published GitHub Release starts the Python
distribution workflow, which builds and validates the distributions and
publishes them through PyPI Trusted Publishing.

## One-time repository setup

Create a repository-scoped Actions secret named `RELEASE_PLEASE_TOKEN` with
contents and pull request write access for this repository. The workflow runs
automatically on pushes to `main` and skips forks.

Register the PyPI Trusted Publisher for owner `Snuffy2`, repository
`aioplaces`, workflow filename `publish-pypi.yml`, and GitHub environment
`pypi`. Register the same workflow for TestPyPI with environment `testpypi`.
Create both environments in the repository with those exact names. Configure
environment protection and required reviewers in GitHub if releases need manual
approval.

The repository's hook automation also uses two Actions secrets:

- `PREK_AUTOUPDATE_TOKEN` lets the scheduled and main-branch prek update
  workflow create or update its hook update pull request and enable its
  configured auto-merge.
- `PREK_AUTOFIX_TOKEN` lets the follow-up prek autofix workflow apply fixes to
  a pull request.

Create repository-scoped tokens with the write access required by their
respective workflows and actions. If a token expires or lacks permission,
check the workflow run log, update the matching secret, then rerun the failed
workflow. These tokens are separate from `RELEASE_PLEASE_TOKEN`.

## Stable releases

1. Merge release-ready changes into `main`. Use Conventional Commit subjects:
   `fix:` indicates a patch, `feat:` indicates a minor release, and a
   `BREAKING CHANGE:` footer or `!` after the type indicates a major release.
2. After a push to `main`, Release Please creates or updates a release pull
   request. Review the version and root `CHANGELOG.md`, then let the normal
   checks pass.
3. Merge the release pull request. Release Please creates the matching
   `v`-prefixed tag and GitHub Release.
4. The published release event starts the `Publish Python Distribution`
   workflow. It checks the tag, release target, default-branch ancestry, and
   the `VERSION` marker in `src/aioplaces/const.py`. The marker must read
   `VERSION = "<tag>"  # x-release-please-version`.
5. The workflow builds a wheel and source distribution with `uv build`, checks
   them with Twine, uploads them to the GitHub Release, then uses OIDC trusted
   publishing. Stable releases go to PyPI.

Release Please derives version bumps and changelog entries from conventional
commits. To force a particular version, include a `Release-As: X.Y.Z` footer
in the release commit message.

## Prereleases

The publishing workflow sends a published prerelease to TestPyPI. Before
publishing it, ensure the release tag matches the prerelease version in
`src/aioplaces/const.py` and identifies a commit on the default branch. For a
hyphenated suffix, the first character must be a letter or digit; following
characters may also include dots or hyphens. The workflow also accepts tags
ending in `aN`, `bN`, or `rcN`. Stable tags must match `vX.Y.Z`.

The publishing workflow runs only for a published GitHub Release; it has no
manual dispatch trigger.

## Failure handling

If Release Please does not create or update its pull request, first check
whether the merged commits require a release. Then confirm the push was to
`main` and `RELEASE_PLEASE_TOKEN` is present, valid, and authorized to write
contents and pull requests. Read the failed run log, correct the repository setting or
secret, then rerun the workflow.

If distribution validation fails, inspect the published release and the commit
it targets. The tag must have a supported version shape, point to the checked
out commit, identify a commit on the default branch, and match the version
marker in that commit. Correct the release metadata or source version before
rerunning the failed workflow.

If PyPI publication fails, check that the matching environment exists, any
required environment approval has completed, and the Trusted Publisher is
registered for the exact repository, workflow filename, and environment.
After correcting the external setup, rerun the failed workflow. The workflow
does not provide a manual-dispatch path to publish a distribution.
