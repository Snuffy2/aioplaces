Development
===========

From the repository root, install the locked development and build dependencies:

.. code-block:: bash

   uv sync --python 3.14 --locked --group dev --group build
   ./.venv/bin/python -m prek run -a
   uv sync --python 3.14 --locked --group dev --group build
   ./.venv/bin/python -m pytest
   ./.venv/bin/python -m build --no-isolation
   ./.venv/bin/python -m twine check dist/*

The ``dev`` group includes lint and test dependencies. Restore build dependencies
after prek because the mypy hook syncs only the ``dev`` group. Tests mock HTTP
requests and must not contact upstream services. Coverage must reach 80 percent.

Documentation
-------------

Install the ``docs`` extra and build HTML with warnings treated as errors:

.. code-block:: bash

   uv sync --python 3.14 --locked --group dev --extra docs
   ./.venv/bin/python -m sphinx -b html -W --keep-going docs/source docs/_build/html
   ./.venv/bin/python -m sphinx -b doctest -W docs/source docs/_build/doctest

Open ``docs/_build/html/index.html`` to read the local site. The API reference is
generated from the installed package's docstrings, and the changelog includes
the root ``CHANGELOG.md`` rather than maintaining a second copy.

Read the Docs uses ``.readthedocs.yaml`` to install the package with its ``docs``
extra and build with Python 3.14. Hosting requires importing the GitHub repository
into a Read the Docs project.
