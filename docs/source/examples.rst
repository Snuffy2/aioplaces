Examples
========

OSM feature lookup
------------------

Use an existing client configured as shown in :doc:`quickstart`:

.. code-block:: python

   payload = await client.lookup("way", 12345, language="en")
   if payload is not None:
       place = parse_place(payload, language="en")
       print(place.formatted_address)

The type can be ``node``, ``way``, or ``relation``, or its ``N``, ``W``, or ``R``
abbreviation. Identifiers must be positive integers or digit strings.

Explicit Wikidata retrieval
---------------------------

.. code-block:: python

   entity = await client.wikidata("Q42")
   if entity is not None:
       print(entity.get("entities"))

Refresh a cached response
-------------------------

.. code-block:: python

   payload = await client.reverse(40.7128, -74.0060, use_cache=False)

Parsing without network access
-------------------------------

.. doctest::

   >>> from aioplaces import parse_place
   >>> payload = {"namedetails": {"name": "Central Park"}, "address": {"city": "New York"}}
   >>> place = parse_place(payload)
   >>> place.place_name
   'Central Park'
   >>> place.city
   'New York'

Parsing does not perform requests or mutate ``payload``. The library does not
implement forward search, Overpass, sensor state, zones, or previous-place history.
