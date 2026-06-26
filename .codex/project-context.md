# Project Context

## Project

Tidbyt plane tracker that shows the most likely audible nearby aircraft on a single Tidbyt page using AirLabs live flight data.

## Goal

When the user hears a plane near their home, they should be able to glance at the Tidbyt and quickly see:

- callsign
- carrier
- aircraft type
- origin and destination
- altitude
- speed

## Current Architecture

- `bridge/airlabs_bridge.py`
  - polls AirLabs flights API with a bounding box around the configured home location
  - filters and scores candidate flights
  - exposes normalized JSON at `http://127.0.0.1:8787/plane.json`
- `tidbyt/plane_overhead.star`
  - Pixlet app that renders a single-page 4-line Tidbyt screen from the local JSON feed
- `scripts/start-bridge.ps1`
  - launches the Python bridge on Windows
- `scripts/render-and-push.ps1`
  - renders and pushes the Tidbyt image in a loop

## Selection Logic

The bridge is intentionally not choosing the nearest dot on a map. It tries to pick the plane the user is most likely hearing.

Current approach:

- query AirLabs with a bbox around the home lat/lon
- filter to flights with valid lat/lng
- filter to airborne flights below `max_altitude_ft`
- filter to recent flights younger than `max_age_seconds`
- optionally filter to commercial flights only
- compute horizontal distance and slant distance
- add a small heading penalty based on whether the aircraft is moving toward/near the home location
- choose the lowest overall score

## Current Status

Implemented:

- AirLabs bridge
- sample payload fixture
- unit tests for bbox and selection flow
- one-page Tidbyt display
- Windows helper scripts
- README setup instructions

Not yet done:

- live AirLabs validation with a real API key
- local Pixlet render validation on a machine with Pixlet installed
- final tuning of audible-plane heuristics using real data near the user's home
- GitHub remote creation and first push

## Important Files

- `README.md`
- `bridge/airlabs_bridge.py`
- `tidbyt/plane_overhead.star`
- `tests/test_airlabs_bridge.py`
- `config.example.json`
- `config.sample.json`

## Known Constraints

- This workspace should not commit `config.json` because it will contain the AirLabs API key.
- The current environment did not have `pixlet` installed, so rendering was not verified here.
- The current environment also did not have `gh` installed and the folder was not initially a git repo, so GitHub publishing was only prepared locally.

## Suggested Next Work

1. Create a GitHub repo and push this workspace.
2. On a real machine, create `config.json` from `config.example.json`.
3. Add the AirLabs key and real home coordinates.
4. Run the bridge locally and inspect `/plane.json`.
5. Install Pixlet and validate the Tidbyt render.
6. Tune `bbox_radius_km`, `display_radius_km`, `max_altitude_ft`, and `commercial_only` against real flights.
