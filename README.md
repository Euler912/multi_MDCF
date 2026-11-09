# RouteOptimizer — free OpenRouteService + exact TSP

This repository also contains the original **MDCF** and **Google Maps** notebooks, which are left unchanged.
The new \`app.py\` uses **HeiGIT/openrouteservice (ORS)** for road-distance and travel-time matrices
and **Held–Karp** for an exact optimal visit order for 2–10 stops.

> **Important:** ORS Matrix reports distances **along ORS-selected driving routes** (typically
> optimized for travel time). They are **not necessarily globally shortest road distances**.
> Held–Karp certifies optimal visit order *relative to the returned matrix*, not the road
> distance optimality of each leg. Data comes from OpenStreetMap; verify exact building locations.

## 1. Free API key

Sign up at https://account.heigit.org/ and create a **free HeiGIT API key**.
No Google account or Google Maps billing is needed. Free usage has request/rate limits.

**As of November 2026**, ORS endpoints moved from \`api.openrouteservice.org\` to
\`api.heigit.org\`:
- Geocoding: \`https://api.heigit.org/pelias/v1/search\`
- Matrix: \`https://api.heigit.org/openrouteservice/v2/matrix/driving-car\`

Check current quotas in the HeiGIT account dashboard. Do not commit or share keys.

## 2. Run on macOS

\`\`\`bash
git clone https://github.com/Euler912/multi_MDCF.git
cd multi_MDCF
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export ORS_API_KEY="paste-your-own-key-here"
python -m streamlit run app.py
\`\`\`

The app normally opens at http://localhost:8501. You can also enter a key through
the app's masked field if no environment variable is set.

## 3. Use it

1. Enter 2–10 addresses, one per line (first = depot/start/end).
2. Select **Live ORS** and click **Find address candidates**.
3. **Verify the matched building/address and coordinates**; choose the right candidate.
4. Click **Fetch ORS matrix and solve TSP**.
5. View **D** (meters converted to km), **T** (seconds converted to minutes),
   the exact visit order, total distance/time, and download D as CSV.

Use **Synthetic demo** to test the app without an account or any API calls.
No external API calls are made automatically when the app loads. Each live calculation
uses one matrix API request and one geocoding lookup per address.

## 4. Architecture

\`\`\`
addresses -> ORS Pelias geocoding (verified candidates)
          -> ORS driving-car matrix (D meters, T seconds)
          -> Held–Karp (min D or min T, fixed depot 0)
          -> solution + matrices + CSV + map link
\`\`\`

Functions in \`route_optimizer.py\`:
- \`geocode_candidates(address, key)\`
- \`get_distance_matrix([[lon, lat], ...], key)\`
- \`held_karp(D)\`
- \`route_total(D, route)\`

\`MDCF\` is **not yet wired into this app**; the separate MDCF notebook is retained
for mathematical research and side-by-side benchmarking.

## 5. Accuracy, scope, attribution

- \`D[i,j]\` is directed travel distance in **meters**; \`T[i,j]\` is estimated time in **seconds**.
- \`D[i,j]\` may differ from \`D[j,i]\`.
- Street-network/house-number quality and road snapping affect distances.
- Routing uses ORS distance of its selected route, **not** a guaranteed distance-minimizing
  path between coordinates; it does not include live traffic.
- For traffic-sensitive routes, multiple vehicles, or time windows, a different model
  and/or solver is required.
- Google Maps link is just a convenience to view stop order; it can recalculate the route.
- OpenRouteService/HeiGIT — © OpenStreetMap contributors.
- A public deployment should use server-side secret management and abuse/rate limits.

Documentation:
https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/
https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912
