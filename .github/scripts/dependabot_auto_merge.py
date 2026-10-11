"""Validate that a dependency pull request remains safe to auto-merge."""

import json
import os
from pathlib import Path
import re
import sys
from typing import NoReturn

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

DEPENDABOT = "dependabot[bot]"
WEB_FLOW = "web-flow"


def refuse(message: str) -> NoReturn:
    """Reject an update with a diagnostic message.

    Args:
        message (str): Reason authorization failed.

    Raises:
        ValueError: Always, to prevent auto-merge.
    """
    raise ValueError(f"Refusing auto-merge; {message}")


def field(value: JSON, *keys: str | int) -> JSON:
    """Read nested API fields, returning None for missing or invalid containers.

    Args:
        value (JSON): API data to inspect.
        keys (str | int): Object keys or array indexes to traverse.

    Returns:
        JSON: Field value, or None when the path is absent.
    """
    for key in keys:
        if isinstance(value, dict) and isinstance(key, str):
            value = value.get(key)
        elif isinstance(value, list) and isinstance(key, int) and 0 <= key < len(value):
            value = value[key]
        else:
            return None
    return value


def dependency_ecosystem(head_ref: JSON) -> str:
    """Identify an allowed Dependabot branch ecosystem.

    Args:
        head_ref (JSON): Pull-request branch name.

    Returns:
        str: Supported dependency ecosystem.
    """
    if isinstance(head_ref, str):
        for prefix, ecosystem in (
            ("dependabot/uv/", "uv"),
            ("dependabot/npm_and_yarn/", "npm"),
            ("dependabot/github_actions/", "github-actions"),
        ):
            if head_ref.startswith(prefix):
                return ecosystem
    refuse(f"unsupported Dependabot branch: {head_ref}")


def is_trusted_base_file(trusted_base_directory: Path, path: str) -> bool:
    """Check that a dependency target is an existing file within the trusted base.

    Args:
        trusted_base_directory (Path): Trusted checkout directory.
        path (str): Dependency target path.

    Returns:
        bool: Whether the target is a trusted file.
    """
    base = trusted_base_directory.absolute()
    # Match lexical path containment in the original authorizer.
    candidate = Path(os.path.abspath(base / path))
    return candidate != base and candidate.is_relative_to(base) and candidate.is_file()


def assert_allowed_files(
    ecosystem: str, changed_files: list[str], trusted_base_directory: Path
) -> None:
    """Enforce the original ecosystem-specific dependency file scope.

    Args:
        ecosystem (str): Supported dependency ecosystem.
        changed_files (list[str]): Files reported by the pull-request API.
        trusted_base_directory (Path): Trusted checkout directory.
    """
    if not changed_files:
        refuse("the pull request has no changed files.")
    if ecosystem == "uv":
        if not is_trusted_base_file(trusted_base_directory, "uv.lock"):
            refuse("the trusted base does not use uv.")
        if changed_files != ["uv.lock"]:
            refuse("uv updates must change only uv.lock.")
        return
    if ecosystem == "npm":
        if not all(
            is_trusted_base_file(trusted_base_directory, path)
            for path in ("package.json", "package-lock.json")
        ):
            refuse("the trusted base does not use npm.")
        if changed_files != ["package-lock.json"] and not (
            len(changed_files) == 2 and set(changed_files) == {"package.json", "package-lock.json"}
        ):
            refuse("npm updates must change only package.json and package-lock.json.")
        return
    if not all(
        (
            re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", path)
            or re.search(r"(^|/)action\.ya?ml$", path)
        )
        and is_trusted_base_file(trusted_base_directory, path)
        for path in changed_files
    ):
        refuse("the update changes a file outside the trusted dependency scope.")


def is_verified_dependabot_commit(commit: JSON) -> bool:
    """Check the author, web-flow committer, and verified signature.

    Args:
        commit (JSON): Commit data returned by GitHub.

    Returns:
        bool: Whether the commit has verified Dependabot provenance.
    """
    return (
        field(commit, "author", "login") == DEPENDABOT
        and field(commit, "committer", "login") == WEB_FLOW
        and field(commit, "commit", "verification", "verified") is True
    )


def assert_merge_parent_ancestry(event: JSON, commits: list[JSON], ancestry_proofs: JSON) -> None:
    """Require compare API evidence that every merge parent belongs to the base.

    Args:
        event (JSON): Pull-request webhook event.
        commits (list[JSON]): Ordered pull-request history.
        ancestry_proofs (JSON): Compare API evidence for second parents.
    """
    merge_commits = commits[1:]
    current_base = field(event, "pull_request", "base", "sha")
    if not isinstance(ancestry_proofs, list) or len(ancestry_proofs) != len(merge_commits):
        refuse("the merge-parent ancestry evidence is incomplete.")
    for commit, proof in zip(merge_commits, ancestry_proofs, strict=True):
        second_parent = field(commit, "parents", 1, "sha")
        ahead_by = field(proof, "ahead_by")
        behind_by = field(proof, "behind_by")
        if (
            not isinstance(second_parent, str)
            or field(proof, "parent_sha") != second_parent
            or field(proof, "base_sha") != current_base
            or field(proof, "base_commit") != second_parent
            or field(proof, "head_commit") != current_base
            or field(proof, "merge_base_commit") != second_parent
            or field(proof, "status") not in ("ahead", "identical")
            or not isinstance(ahead_by, (int, float))
            or isinstance(ahead_by, bool)
            or ahead_by < 0
            or int(ahead_by) != ahead_by
            or not isinstance(behind_by, (int, float))
            or isinstance(behind_by, bool)
            or behind_by != 0
        ):
            refuse("a merge second parent is not proven to be on the current base.")


def assert_update_branch_history(event: JSON, commits: list[JSON], ancestry_proofs: JSON) -> None:
    """Authorize only a Dependabot root followed by GitHub Update branch merges.

    Args:
        event (JSON): Pull-request webhook event.
        commits (list[JSON]): Ordered pull-request history.
        ancestry_proofs (JSON): Compare API evidence for second parents.
    """
    if len(commits) < 2:
        refuse("the pull request is not a GitHub Update branch merge.")
    if not is_verified_dependabot_commit(commits[0]):
        refuse("the pull request history does not begin with Dependabot.")
    for previous, commit in zip(commits[:-1], commits[1:], strict=True):
        parents = field(commit, "parents")
        if (
            field(commit, "committer", "login") != WEB_FLOW
            or field(commit, "commit", "verification", "verified") is not True
            or not isinstance(parents, list)
            or len(parents) != 2
            or field(commit, "parents", 0, "sha") != field(previous, "sha")
        ):
            refuse("the pull request contains a non-Dependabot edit.")
    assert_merge_parent_ancestry(event, commits, ancestry_proofs)
    latest = commits[-1]
    if field(latest, "sha") != field(event, "pull_request", "head", "sha") or field(
        latest, "parents", 1, "sha"
    ) != field(event, "pull_request", "base", "sha"):
        refuse("the latest commit is not an update from the current base branch.")


def authorize_dependabot_update(
    *,
    changed_files: list[str],
    commits: list[JSON],
    event: JSON,
    ancestry_proofs: JSON = None,
    trusted_base_directory: Path | None = None,
) -> str:
    """Authorize a dependency update using trusted files and commit provenance.

    Args:
        changed_files (list[str]): Changed-file API results.
        commits (list[JSON]): Ordered pull-request history.
        event (JSON): Pull-request webhook event.
        ancestry_proofs (JSON): Compare API evidence, defaulting to an empty list.
        trusted_base_directory (Path | None): Trusted checkout, defaulting to cwd.

    Returns:
        str: Authorized dependency ecosystem.
    """
    if (
        field(event, "repository", "fork") is not False
        or field(event, "pull_request", "user", "login") != DEPENDABOT
        or field(event, "pull_request", "head", "repo", "full_name")
        != field(event, "repository", "full_name")
        or field(event, "pull_request", "base", "ref")
        != field(event, "repository", "default_branch")
    ):
        refuse("the pull request does not have the required Dependabot provenance.")
    ecosystem = dependency_ecosystem(field(event, "pull_request", "head", "ref"))
    if len(commits) == 1:
        if not is_verified_dependabot_commit(commits[0]) or field(commits[0], "sha") != field(
            event, "pull_request", "head", "sha"
        ):
            refuse("the pull request does not have a verified Dependabot head commit.")
    else:
        assert_update_branch_history(
            event, commits, [] if ancestry_proofs is None else ancestry_proofs
        )
    assert_allowed_files(ecosystem, changed_files, trusted_base_directory or Path.cwd())
    return ecosystem


def main() -> None:
    """Read workflow fixture files and authorize the dependency update.

    Raises:
        ValueError: Required arguments or commit pages are invalid.
    """
    if len(sys.argv) != 5:
        raise ValueError(
            "Usage: dependabot_auto_merge.py EVENT CHANGED_FILES COMMITS ANCESTRY_PROOFS"
        )
    event_path, changed_files_path, commits_path, ancestry_proofs_path = map(Path, sys.argv[1:])
    event = json.loads(event_path.read_text(encoding="utf-8"))
    changed_files = [
        path for path in changed_files_path.read_text(encoding="utf-8").split("\n") if path
    ]
    commit_pages = json.loads(commits_path.read_text(encoding="utf-8"))
    if not isinstance(commit_pages, list) or not all(
        isinstance(page, list) for page in commit_pages
    ):
        raise ValueError("Expected paginated commit arrays.")
    commits = [commit for page in commit_pages for commit in page]
    ancestry_proofs = json.loads(ancestry_proofs_path.read_text(encoding="utf-8"))
    authorize_dependabot_update(
        ancestry_proofs=ancestry_proofs, changed_files=changed_files, commits=commits, event=event
    )
    print("Authorized dependency update files and commit history.")


if __name__ == "__main__":
    main()
