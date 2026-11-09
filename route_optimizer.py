"""Small TSP demo using the free HeiGIT/OpenRouteService API.

Distances are for ORS-selected routes (normally time-weighted), NOT certificates
of the absolute shortest road distance. API requests happen only on demand.
"""
from __future__ import annotations

from functools import lru_cache
import math
from typing import Sequence

import numpy as np
import requests

GEOCODE_URL = "https://api.heigit.org/pelias/v1/search"
MATRIX_URL = "https://api.heigit.org/openrouteservice/v2/matrix/driving-car"
MAX_STOPS = 10  # deliberate safety limit for the experimental app


class RoutingError(RuntimeError):
    """Actionable API or input error."""


def _error_summary(response):
    """Do not include request URLs (which may contain an API key)."""
    try:
        obj = response.json()
        msg = obj.get("error") or obj.get("message") or obj.get("geocoding")
        return str(msg)[:350] if msg else "Request rejected"
    except (ValueError, AttributeError, TypeError):
        return "Request rejected"


def _validate_point(point):
    try:
        lon, lat = float(point[0]), float(point[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("Expected a [longitude, latitude] pair") from exc
    if not all(map(math.isfinite, [lon, lat])) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Coordinates outside geographic bounds")
    return [lon, lat]


def geocode_candidates(address: str, api_key: str, size: int = 3):
    """Return up to 3 candidate locations; caller MUST verify the selected address."""
    address = address.strip()
    if not address or not api_key:
        raise ValueError("A nonempty address and ORS_API_KEY are required")
    if "*" in api_key:
        raise RoutingError("The ORS key contains asterisks. Copy the FULL Basic Key using the Copy button at account.heigit.org; do not copy masked text.")
    try:
        response = requests.get(
            GEOCODE_URL,
            params={"text": address, "size": max(1, min(3, int(size))), "api_key": api_key},
            timeout=20,
        )
    except requests.RequestException:
        raise RoutingError("Could not connect to ORS geocoding") from None
    if response.status_code == 403:
        raise RoutingError("Geocoding HTTP 403 (access disallowed): likely an incomplete/invalid ORS key. At account.heigit.org use Copy next to the Basic Key (NOT the masked asterisks). Replace ORS_API_KEY, restart Streamlit, and try again. If it persists, check the dashboard or contact HeiGIT support.")
    if response.status_code != 200:
        raise RoutingError(f"Geocoding HTTP {response.status_code}: {_error_summary(response)}")
    try:
        features = response.json().get("features", [])
    except (ValueError, AttributeError) as exc:
        raise RoutingError("ORS geocoding returned invalid JSON") from exc
    results = []
    for feature in features:
        try:
            coordinates = _validate_point(feature["geometry"]["coordinates"])
            properties = feature.get("properties") or {}
            label = properties.get("label") or properties.get("name") or address
            results.append({"label": str(label), "coordinates": coordinates})
        except (ValueError, KeyError, TypeError):
            continue
    if not results:
        raise RoutingError(f"No geocoding candidate for {address!r}. Verify spelling or use another address.")
    return results


def get_distance_matrix(coordinates: Sequence[Sequence[float]], api_key: str):
    """Return D (meters) and T (seconds) for directed driving routes."""
    n = len(coordinates)
    if not 2 <= n <= MAX_STOPS:
        raise ValueError(f"Expected 2–{MAX_STOPS} locations")
    if not api_key:
        raise ValueError("ORS_API_KEY is missing")
    locations = [_validate_point(point) for point in coordinates]
    try:
        response = requests.post(
            MATRIX_URL,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            json={"locations": locations, "metrics": ["distance", "duration"], "units": "m"},
            timeout=60,
        )
    except requests.RequestException:
        raise RoutingError("Could not connect to ORS Matrix API") from None
    if response.status_code == 403:
        raise RoutingError("Matrix HTTP 403 (access disallowed): verify that ORS_API_KEY is the FULL key copied from the HeiGIT dashboard, then restart Streamlit. Check the account dashboard if the problem continues.")
    if response.status_code != 200:
        raise RoutingError(f"Matrix HTTP {response.status_code}: {_error_summary(response)}")
    try:
        result = response.json()
        D = np.asarray(result["distances"], dtype=float)
        T = np.asarray(result["durations"], dtype=float)
    except (ValueError, KeyError, TypeError) as exc:
        raise RoutingError("ORS Matrix returned unexpected or incomplete JSON") from exc
    for name, matrix in (("distances", D), ("durations", T)):
        if matrix.shape != (n, n):
            raise RoutingError(f"Unexpected {name} matrix shape: {matrix.shape}")
        if not np.isfinite(matrix).all() or (matrix < 0).any():
            raise RoutingError(f"{name} matrix has unreachable/invalid pairs")
        np.fill_diagonal(matrix, 0)
    return D, T


def held_karp(cost_matrix: Sequence[Sequence[float]]):
    """Exact directed TSP: starts and returns at node 0, for up to 10 stops."""
    D = np.asarray(cost_matrix, dtype=float)
    if D.ndim != 2 or D.shape[0] != D.shape[1]:
        raise ValueError("A square cost matrix is required")
    n = D.shape[0]
    if not 2 <= n <= MAX_STOPS or not np.isfinite(D).all() or (D < 0).any():
        raise ValueError(f"Expected a finite nonnegative matrix of size 2–{MAX_STOPS}")

    @lru_cache(maxsize=None)
    def dp(mask: int, last: int):
        bit = 1 << (last - 1)
        if mask == bit:
            return float(D[0, last]), (last,)
        prev = mask ^ bit
        candidates = (
            (dp(prev, other)[0] + D[other, last], dp(prev, other)[1] + (last,))
            for other in range(1, n) if prev & (1 << (other - 1))
        )
        return min(candidates, key=lambda item: item[0])

    full = (1 << (n - 1)) - 1
    best_cost, best_path = min(
        ((dp(full, last)[0] + D[last, 0], dp(full, last)[1])
         for last in range(1, n)),
        key=lambda item: item[0],
    )
    route = (0,) + best_path + (0,)
    return route, float(best_cost)


def route_total(matrix, route):
    return float(sum(matrix[i, j] for i, j in zip(route, route[1:])))


def demo_matrices():
    """Purely synthetic, for testing without a key; NOT real street distances."""
    D = np.array([
        [0, 6400, 1300, 4700],
        [5600, 0, 4900, 1600],
        [1100, 4600, 0, 3900],
        [4900, 1700, 3700, 0],
    ], dtype=float)
    T = D / 7.0  # also synthetic
    return D, T
