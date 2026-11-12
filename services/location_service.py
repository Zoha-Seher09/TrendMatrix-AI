"""
TrendMatrix AI - Global Location Search Service

Provides global location search through the Photon geocoding API.
Includes a short-lived in-memory cache to reduce repeated requests.
"""

import time

import requests


# --------------------------------------------------
# Photon API configuration
# --------------------------------------------------

PHOTON_URL = "https://photon.komoot.io/api/"

GEOCODING_USER_AGENT = (
    "TrendMatrixAI/1.0 "
    "(NASA Space Apps educational project)"
)


# --------------------------------------------------
# In-memory search cache
# --------------------------------------------------

GEOCODING_CACHE = {}
GEOCODING_CACHE_TTL = 300
GEOCODING_CACHE_LIMIT = 200


# --------------------------------------------------
# Location display formatting
# --------------------------------------------------

def get_photon_display_name(properties: dict) -> tuple[str, str]:
    """
    Generate a location name and a contextual display name.
    """

    name = (
        properties.get("name")
        or properties.get("city")
        or properties.get("country")
        or "Unknown location"
    )

    locality = (
        properties.get("city")
        or properties.get("district")
        or properties.get("county")
        or properties.get("state")
        or ""
    )

    country = properties.get("country", "")

    context_parts = []

    for part in (locality, properties.get("state"), country):

        if part and part.casefold() != str(name).casefold():

            if part not in context_parts:
                context_parts.append(part)

    context = ", ".join(context_parts)

    short_name = name

    if context:
        short_name = f"{name}, {context}"

    return name, short_name


# --------------------------------------------------
# Global Photon location search
# --------------------------------------------------

def search_photon_locations(query: str) -> list:
    """
    Search globally for locations using the Photon API.
    """

    cache_key = query.casefold().strip()
    now = time.monotonic()

    cached = GEOCODING_CACHE.get(cache_key)

    if cached:
        created_at, cached_results = cached

        if now - created_at < GEOCODING_CACHE_TTL:
            return cached_results

    response = requests.get(
        PHOTON_URL,
        params={
            "q": query,
            "limit": 12,
            "lang": "en",
        },
        headers={
            "User-Agent": GEOCODING_USER_AGENT,
        },
        timeout=6,
    )

    response.raise_for_status()

    features = response.json().get("features", [])

    results = []
    seen = set()

    for feature in features:

        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        coordinates = geometry.get("coordinates", [])

        if len(coordinates) < 2:
            continue

        try:
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])

        except (TypeError, ValueError):
            continue

        if not -90 <= latitude <= 90:
            continue

        if not -180 <= longitude <= 180:
            continue

        name, short_name = get_photon_display_name(properties)

        identity = (
            short_name.casefold(),
            round(latitude, 5),
            round(longitude, 5),
        )

        if identity in seen:
            continue

        seen.add(identity)

        results.append({
            "name": name,
            "short_name": short_name,
            "latitude": latitude,
            "longitude": longitude,
            "country": properties.get("country", ""),
            "state": properties.get("state", ""),
            "city": (
                properties.get("city")
                or properties.get("district")
                or ""
            ),
            "type": properties.get("type", "location"),
        })

    if len(GEOCODING_CACHE) >= GEOCODING_CACHE_LIMIT:
        GEOCODING_CACHE.clear()

    GEOCODING_CACHE[cache_key] = (now, results)

    return results
