Installation
============

Use Python 3.14 or newer in a virtual environment. Before the first PyPI release,
install from a checkout of the
`repository <https://github.com/Snuffy2/aioplaces>`_:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate
   python -m pip install .

After the package is published, install it from PyPI with:

.. code-block:: bash

   python -m pip install aioplaces

The library depends on ``aiohttp``, ``cachetools``, and ``yarl``. It has no Home
Assistant dependency.
