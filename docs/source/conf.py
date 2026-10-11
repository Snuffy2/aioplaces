"""Sphinx configuration for the aioplaces documentation site."""

from datetime import UTC, datetime
from importlib.metadata import version as package_version

project: str = "aioplaces"
author: str = "@Snuffy2"
copyright: str = f"{datetime.now(UTC):%Y}, {author}"
release: str = package_version("aioplaces")
version: str = release

extensions: list[str] = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinx.ext.viewcode",
    "myst_parser",
]

exclude_patterns: list[str] = ["_build", "_generated"]
autosummary_generate = True
autodoc_typehints = "description"
autodoc_member_order = "bysource"
autoclass_content = "both"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_param = True
napoleon_use_rtype = True

html_theme: str = "sphinx_rtd_theme"
html_title: str = "aioplaces documentation"
html_theme_options = {
    "collapse_navigation": True,
    "navigation_depth": 2,
    "version_selector": True,
}
