"""Streamlit demo: free ORS distance matrix and exact small TSP."""
import os
from urllib.parse import quote

import pandas as pd
import streamlit as st

from route_optimizer import (
    RoutingError, demo_matrices, geocode_candidates,
    get_distance_matrix, held_karp, route_total, validate_distinct_locations,
)

st.set_page_config(page_title="RouteOptimizer | ORS TSP", page_icon="🧭", layout="wide")
st.title("🧭 RouteOptimizer — ORS + Held–Karp")
st.caption("Experimental demo: route distances from OpenStreetMap via HeiGIT / openrouteservice")
st.info(
    "ORS Matrix returns distances along ORS-selected driving routes; "
    "they are not necessarily the geometrically shortest road routes. "
    "Held–Karp finds the optimal visit order for the matrix provided."
)

DEFAULT = "\n".join([
    "האורגים 2, אשדוד, ישראל",
    "נחל לכיש 30, אשדוד, ישראל",
    "מורדי הגטאות 10, אשדוד, ישראל",
    "שלמה המלך 3, אשדוד, ישראל",
])
mode = st.radio("Data source", ["Live ORS (free key)", "Synthetic demo"], horizontal=True)
raw = st.text_area("One address per line; first = start/end", value=DEFAULT, height=130)
addresses = [a.strip() for a in raw.splitlines() if a.strip()]
objective = st.radio("Optimize", ["Distance (km)", "Travel time (minutes)"], horizontal=True)

def api_key():
    key = os.getenv("ORS_API_KEY", "").strip()
    if key:
        return key
    try:
        key = str(st.secrets.get("ORS_API_KEY", "")).strip()
        if key:
            return key
    except Exception:
        pass
    return st.text_input("ORS API key (not stored in GitHub)", type="password").strip()

def save_result(D, T, labels, coordinates, source):
    if coordinates is not None:
        validate_distinct_locations(coordinates)
    matrix = D if objective.startswith("Distance") else T
    route, cost = held_karp(matrix)
    st.session_state["result"] = dict(
        D=D, T=T, labels=labels, coordinates=coordinates,
        route=route, cost=cost, source=source, objective=objective,
    )

def show_result(info):
    D, T, route, labels = info["D"], info["T"], info["route"], info["labels"]
    st.subheader("Result")
    st.success(" → ".join(str(i) for i in route))
    st.write("Visit order:", " → ".join(labels[i] for i in route))
    c1, c2 = st.columns(2)
    c1.metric("Total distance", f"{route_total(D, route)/1000:.3f} km")
    c2.metric("Estimated travel time", f"{route_total(T, route)/60:.1f} min")
    st.caption(f"Exact TSP for supplied matrix • {info['source']} • objective: {info['objective']}")
    st.write("D — directed distances in km")
    st.dataframe(pd.DataFrame(D/1000, index=labels, columns=labels).round(3), use_container_width=True)
    st.write("T — directed durations in minutes")
    st.dataframe(pd.DataFrame(T/60, index=labels, columns=labels).round(2), use_container_width=True)
    st.download_button("Export D as CSV",
                       pd.DataFrame(D, index=labels, columns=labels).to_csv().encode("utf-8-sig"),
                       "distance_matrix_meters.csv", "text/csv")
    if info["coordinates"]:
        points = info["coordinates"]
        st.write("Geocoded points (pins only, not a computed route)")
        st.map(pd.DataFrame([{"lat": lat, "lon": lon} for lon, lat in points]))
        # Google Maps browser link does not use Google Maps Platform billing/API.
        parts = [quote(labels[i]) for i in route]
        st.link_button("Open visit order in Google Maps (may recalculate roads)",
                       "https://www.google.com/maps/dir/" + "/".join(parts))

if len(addresses) != len(set(addresses)):
    st.error("Duplicate addresses are not allowed.")
elif not 2 <= len(addresses) <= 10:
    st.error("Use between 2 and 10 different addresses.")
elif mode == "Synthetic demo":
    st.warning("Demo uses fictional distances, not road measurements.")
    if st.button("Solve synthetic example"):
        if len(addresses) != 4:
            st.error("Synthetic example is configured for exactly 4 addresses.")
        else:
            D, T = demo_matrices()
            save_result(D, T, addresses, None, "synthetic demo")
else:
    location_mode = st.radio(
        "How to locate the stops?",
        ["Search addresses with ORS", "Enter verified GPS coordinates"],
        horizontal=True,
        help="Use GPS coordinates if the ORS geocoder resolves several addresses to the same city/street center.",
    )
    key = api_key()

    if st.session_state.get("last_location_mode") != location_mode:
        st.session_state.pop("result", None)
        st.session_state["last_location_mode"] = location_mode

    if location_mode == "Enter verified GPS coordinates":
        st.info(
            "Open https://www.openstreetmap.org/ and locate each address on the map. "
            "Copy its GPS latitude and longitude. Each stop needs its own position. "
            "The ORS API key is still required to calculate driving distances."
        )
        st.caption("Enter GPS coordinates as latitude first, longitude second. "
                   "Examples in Israel are around latitude 31–33, longitude 34–36.")
        chosen = []
        fingerprint = []
        valid_locations = True
        for i, address in enumerate(addresses):
            st.write(f"**{i}. {address}**")
            left, right = st.columns(2)
            latitude_text = left.text_input(
                f"Latitude (north/south) — stop {i}",
                key=f"manual_lat_{i}",
                placeholder="Latitude",
            ).strip()
            longitude_text = right.text_input(
                f"Longitude (east/west) — stop {i}",
                key=f"manual_lon_{i}",
                placeholder="Longitude",
            ).strip()
            fingerprint.append((latitude_text, longitude_text))
            try:
                if not latitude_text or not longitude_text:
                    valid_locations = False
                    continue
                latitude = float(latitude_text)
                longitude = float(longitude_text)
                if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                    raise ValueError("Outside geographic bounds")
                chosen.append([longitude, latitude])  # ORS uses [lon, lat]
            except ValueError:
                valid_locations = False
                st.error(f"Invalid GPS coordinates at stop {i}.")

        if st.session_state.get("manual_points_fingerprint") != tuple(fingerprint):
            st.session_state.pop("result", None)
            st.session_state["manual_points_fingerprint"] = tuple(fingerprint)

        if valid_locations and len(chosen) == len(addresses):
            st.write("**Review selected GPS coordinates before paying for an ORS request:**")
            st.dataframe(pd.DataFrame(
                [{"address": address, "latitude": point[1], "longitude": point[0]}
                 for address, point in zip(addresses, chosen)]
            ), use_container_width=True)
            st.map(pd.DataFrame([{"lat": p[1], "lon": p[0]} for p in chosen]))
            try:
                validate_distinct_locations(chosen)
            except (RoutingError, ValueError) as exc:
                valid_locations = False
                st.error(str(exc))
        if st.button("Fetch ORS matrix and solve TSP (GPS)", disabled=(not key or not valid_locations)):
            try:
                D, T = get_distance_matrix(chosen, key)
                save_result(D, T, addresses, chosen, "ORS live matrix (manual GPS)")
            except (RoutingError, ValueError) as exc:
                st.error(str(exc))

    else:
        if st.session_state.get("geocoded_for") != tuple(addresses):
            st.session_state.pop("candidates", None)
            st.session_state.pop("result", None)
        if st.session_state.get("key_for_geocoding") != key:
            st.session_state.pop("candidates", None)
            st.session_state.pop("result", None)

        if st.button("1. Find address candidates", disabled=not key):
            try:
                candidate_sets = [geocode_candidates(address, key) for address in addresses]
                st.session_state["candidates"] = candidate_sets
                st.session_state["geocoded_for"] = tuple(addresses)
                st.session_state["key_for_geocoding"] = key
                st.session_state.pop("result", None)
            except (RoutingError, ValueError) as exc:
                st.error(str(exc))

        if st.session_state.get("candidates"):
            st.subheader("Verify geocoding before requesting distances")
            st.warning(
                "If several distinct street addresses map to one point, the ORS search "
                "is too coarse. Switch to 'Enter verified GPS coordinates' above."
            )
            chosen = []
            for i, (address, candidates) in enumerate(zip(addresses, st.session_state["candidates"])):
                pick = st.selectbox(
                    f"{i}: {address}",
                    list(range(len(candidates))),
                    format_func=lambda j, cs=candidates: (
                        f"{cs[j]['label']} — {cs[j].get('layer', '?')}/"
                        f"{cs[j].get('accuracy', '?')} — "
                        f"lon={cs[j]['coordinates'][0]:.6f}, "
                        f"lat={cs[j]['coordinates'][1]:.6f}"
                    ),
                    key=f"candidate_{i}_{address}",
                )
                chosen.append(candidates[pick]["coordinates"])

            if st.session_state.get("chosen_geocodes") != tuple(tuple(p) for p in chosen):
                st.session_state.pop("result", None)
                st.session_state["chosen_geocodes"] = tuple(tuple(p) for p in chosen)

            st.write("**Chosen locations — verify these points correspond to the real buildings:**")
            st.dataframe(pd.DataFrame([
                {"address": address, "lon": c[0], "lat": c[1]}
                for address, c in zip(addresses, chosen)
            ]), use_container_width=True)
            st.map(pd.DataFrame([{"lat": c[1], "lon": c[0]} for c in chosen]))
            try:
                validate_distinct_locations(chosen)
                valid_locations = True
            except (RoutingError, ValueError) as exc:
                valid_locations = False
                st.error(str(exc))
            if st.button("2. Fetch ORS matrix and solve TSP", disabled=(not key or not valid_locations)):
                try:
                    D, T = get_distance_matrix(chosen, key)
                    save_result(D, T, addresses, chosen, "ORS live matrix (geocoded)")
                except (RoutingError, ValueError) as exc:
                    st.error(str(exc))

if "result" in st.session_state:
    result = st.session_state["result"]
    if (result["labels"] == addresses and result["objective"] == objective
            and (mode == "Synthetic demo") == (result["source"] == "synthetic demo")):
        show_result(result)
    else:
        st.info("Inputs have changed. Run the calculation again to see the matching result.")

st.caption("Attribution: openrouteservice / HeiGIT; © OpenStreetMap contributors. No API key is committed.")
