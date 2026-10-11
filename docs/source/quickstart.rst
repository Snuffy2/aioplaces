Quick start
===========

Choose a Nominatim endpoint whose usage policy permits your application. Set
``NOMINATIM_URL`` to its base URL, including any deployment path prefix, and
provide an identifying application user agent.

.. code-block:: python

   import asyncio
   import os

   import aiohttp

   from aioplaces import PlacesClient, parse_place


   async def main() -> None:
       async with aiohttp.ClientSession() as session:
           client = PlacesClient(
               session,
               base_url=os.environ["NOMINATIM_URL"],
               user_agent="your-app/1.0 (+https://your-app.example/contact)",
           )
           payload = await client.reverse(40.7128, -74.0060, language="en,fr")
           if payload is not None:
               place = parse_place(payload, language="en,fr")
               print(place.place_name, place.city, place.country)


   asyncio.run(main())

The caller owns and closes the session. Reuse a client on the same event loop to
share its cache and request spacing. Separate instances and processes do not
coordinate. See :doc:`usage-policies` before using public services.

Client operations return a JSON mapping or ``None`` when there is no result.
``parse_place`` produces an immutable ``ParsedPlace`` without changing the input.
Unsupported or malformed field values become ``None``. Language preferences are
tried in their comma-separated order.
