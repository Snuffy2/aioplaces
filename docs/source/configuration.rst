Configuration and failures
==========================

``PlacesClient`` requires an open ``aiohttp.ClientSession``, a Nominatim
``base_url``, and an identifying ``user_agent``. Endpoint URLs must use HTTP or
HTTPS and must not contain credentials, query strings, or fragments.

.. list-table:: Optional client settings
   :header-rows: 1
   :widths: 25 20 55

   * - Setting
     - Default
     - Purpose
   * - ``timeout``
     - 10 seconds
     - Positive request timeout.
   * - ``cache_ttl``
     - 14,400 seconds
     - Positive cache lifetime (four hours).
   * - ``cache_maxsize``
     - 500
     - Maximum number of successful responses to cache.
   * - ``min_request_interval``
     - 1 second
     - Minimum spacing between requests from this client.
   * - ``wikidata_base_url``
     - ``https://www.wikidata.org/wiki/Special:EntityData``
     - Wikidata entity endpoint root.

The public ``nominatim.openstreetmap.org`` host rejects an interval below one
second. A custom endpoint may use any finite, nonnegative interval. Requests are
serialized per client; cancellation propagates and requests are not retried
automatically.

Caching
-------

Successful responses are cached and deep-copied when stored and returned. Empty
results are not cached. Endpoint, language, email, operation, and operation
arguments are part of the cache key.

A normal failed request evicts the cached response for that request.
``use_cache=False`` bypasses cache reads, replaces the cached value on success,
and retains an earlier successful value if the refresh fails.

Failures
--------

``PlacesError`` is the common exception base:

* ``InvalidInputError`` covers invalid configuration and caller arguments.
* ``TransportError`` covers network, timeout, and response-processing failures.
* ``HTTPError`` exposes the response ``status`` and optional, unmodified
  ``retry_after`` header.
* ``InvalidResponseError`` covers invalid JSON and unsupported or error response
  payloads.

Invalid caller arguments, unsupported session types, and request URL or
argument-type errors rejected by ``aiohttp`` raise ``InvalidInputError``.
Other ``ValueError`` failures while obtaining or reading a response raise
``TransportError``; JSON decoding failures raise ``InvalidResponseError``.
Translated failures retain the original exception as
their ``__cause__``. Task cancellation continues to propagate as
``asyncio.CancelledError``.
