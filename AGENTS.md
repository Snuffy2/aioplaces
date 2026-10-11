# aioplaces

Standalone Python 3.14+ library; do not introduce Home Assistant dependencies.
Keep public methods typed and document them with Google-style docstrings.
The caller owns its aiohttp session. Preserve cancellation and serialize upstream requests.
Use `./.venv/bin/python -m pytest` and `./.venv/bin/python -m prek run -a`.
Build with `./.venv/bin/python -m build --no-isolation` and validate with `./.venv/bin/python -m twine check dist/*`.
Run all tests without live network calls. Test behavioral contracts rather than private call order.
Do not publish to PyPI, push, or open PRs without an explicit request.
