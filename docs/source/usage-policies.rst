Upstream usage policies
=======================

The `public Nominatim usage policy
<https://operations.osmfoundation.org/policies/nominatim/>`_ requires an
identifying application user agent, attribution, caching, and no more than one
request per second across the application. Recurring geocoding has additional
restrictions, including four requests per minute for regular or long-running
bulk scripts; periodic requests are discouraged.

These limits apply to the whole application, not each library instance or end
user. A client throttle alone does not establish compliance. Use a suitable
hosted provider or your own Nominatim deployment when needed, and do not submit
confidential or personal information contrary to the service policy.

Preserve and display attribution returned in ``ParsedPlace.attribution``.
OpenStreetMap data licensing is separate from this library's source license.
Consult `Wikimedia's user-agent policy
<https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy>`_
for Wikidata requests as well.
