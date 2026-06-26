# Laptop Codex Prompt

Use this prompt when opening the project on another machine:

```text
You are helping with a Tidbyt plane tracker project.

Project summary:
- This repo builds a Tidbyt app that shows the most likely audible nearby aircraft using AirLabs live flight data.
- The user wants to hear a plane, glance at the Tidbyt, and immediately identify it.
- The display is intentionally a single page, not rotating panels.

Current implementation:
- bridge/airlabs_bridge.py polls AirLabs using a bbox around the configured home location.
- It filters and scores flights based on audibility heuristics:
  - in display radius
  - below altitude cap
  - recent update age
  - optionally commercial-only
  - slant distance plus a heading penalty
- tidbyt/plane_overhead.star renders a four-line single-page Tidbyt screen.
- Tests exist in tests/test_airlabs_bridge.py.
- Sample data exists in samples/airlabs_flights.json.

Project goals:
- Validate the live AirLabs integration with a real API key.
- Render the Pixlet app locally.
- Tune the candidate-selection heuristics so the displayed plane usually matches what the user is hearing.
- Help prepare a stable workflow for running the bridge and updating the Tidbyt regularly.

Constraints:
- Do not commit config.json because it contains the AirLabs API key.
- Prefer small, practical improvements over large refactors.
- Preserve the single-page Tidbyt layout unless the user asks otherwise.

Please start by:
1. Reading README.md
2. Reading .codex/project-context.md
3. Reviewing bridge/airlabs_bridge.py and tidbyt/plane_overhead.star
4. Running the tests
5. Asking only for missing live credentials or missing local tools if needed

When reporting back, focus on:
- whether the bridge runs
- whether Pixlet rendering works
- whether the chosen aircraft seems reasonable
- what tuning changes would improve real-world audibility matching
```
