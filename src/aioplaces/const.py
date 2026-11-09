"""Address precedence inherited from the Places integration."""

VERSION = "v0.1.2"  # x-release-please-version

# Place type classification lists
# Note: These lists have intentional overlaps. The parsing order in parser.py is:
# 1. CITY_LIST (highest priority)
# 2. POSTAL_TOWN_LIST (items already matched in CITY_LIST are skipped)
# 3. NEIGHBOURHOOD_LIST (items already matched in previous lists are skipped)
CITY_LIST = [
    "city",
    "town",
    "village",
    "township",
    "hamlet",
    "city_district",
    "municipality",
]

POSTAL_TOWN_LIST = [
    "city",
    "town",
    "village",
    "township",
    "hamlet",
    "borough",
    "suburb",
]

NEIGHBOURHOOD_LIST = [
    "village",
    "township",
    "hamlet",
    "borough",
    "suburb",
    "quarter",
    "neighbourhood",
]
