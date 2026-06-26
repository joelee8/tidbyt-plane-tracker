# Tidbyt Plane Overhead

This workspace scaffolds a private Tidbyt app that shows the most likely audible aircraft around your home using AirLabs live flight data.

It is split into two pieces:

- `tidbyt/plane_overhead.star`: the Pixlet app that renders the Tidbyt screen
- `bridge/airlabs_bridge.py`: a local bridge that reads AirLabs flight data and exposes a small JSON feed for the app

## Why a bridge exists

Tidbyt apps are written in Pixlet/Starlark and can fetch HTTP data, but a local bridge is still the cleanest way to handle:

- your AirLabs API key
- rate limiting and polling cadence
- audible-plane selection logic
- a tiny normalized JSON contract for Pixlet

## Files

- [tidbyt/plane_overhead.star](tidbyt/plane_overhead.star)
- [bridge/airlabs_bridge.py](bridge/airlabs_bridge.py)
- [config.example.json](config.example.json)
- [config.sample.json](config.sample.json)
- [scripts/start-bridge.ps1](scripts/start-bridge.ps1)
- [scripts/render-and-push.ps1](scripts/render-and-push.ps1)

## Quick start

1. Copy `config.example.json` to `config.json`.
2. Put your AirLabs API key into `config.json`.
3. Verify your home coordinates and radius settings.
4. Start the bridge:

```powershell
.\scripts\start-bridge.ps1 -ConfigPath .\config.json
```

5. Install Pixlet if you have not already.
6. Render the app locally:

```powershell
pixlet render .\tidbyt\plane_overhead.star feed_url=http://127.0.0.1:8787/plane.json
```

7. Push it to your Tidbyt:

```powershell
pixlet push --installation-id plane-overhead <DEVICE_ID> .\tidbyt\plane_overhead.webp
```

If you want it to stay current, rerender and push every 15-20 seconds with Task Scheduler or the included loop script.

For a no-network smoke test, use `config.sample.json` instead. It points at the included fixture in `samples/airlabs_flights.json`.

## Bridge output contract

The bridge exposes:

```text
http://127.0.0.1:8787/plane.json
```

Example payload:

```json
{
  "generated_at": "2026-06-03T18:40:00Z",
  "area": {
    "label": "South San Francisco",
    "home_lat": 37.6547,
    "home_lon": -122.4077,
    "bbox_radius_km": 8.0,
    "display_radius_km": 5.0,
    "bbox": [37.5828, -122.4985, 37.7266, -122.3169]
  },
  "plane": {
    "icao": "a1b2c3",
    "callsign": "UAL123",
    "carrier": "United",
    "tail": "N12345",
    "aircraft_type": "B738",
    "origin": "SFO",
    "destination": "LAX",
    "altitude_ft": 7200,
    "speed_kts": 218,
    "track_deg": 146,
    "distance_km": 0.8,
    "slant_distance_km": 2.3,
    "age_seconds": 3,
    "status": "en-route"
  },
  "message": "Tracking most audible nearby aircraft"
}
```

When nothing is in range, `plane` is `null` and `message` explains why.

## Selection logic

The bridge does not just pick the nearest flight on a map. It tries to pick the plane you are most likely hearing by:

- querying AirLabs with a bounding box around your home
- filtering to airborne, recent flights inside your display radius
- excluding flights above your max altitude cap
- optionally preferring commercial flights only
- ranking candidates by slant distance plus a small heading penalty

## What You Need To Do

Before this can run against live data, you need:

1. An AirLabs API key: [Get one here](https://airlabs.co/)
2. Your home latitude/longitude in `config.json`
3. Pixlet installed locally
4. Your Tidbyt device ID for `pixlet push`

That is the full user-side setup. Everything else now lives in this workspace.

## Verification

Run the included tests with:

```powershell
& "C:\Users\joelee\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -p "test_*.py"
```
