from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen


AIRLABS_FLIGHTS_URL = "https://airlabs.co/api/v9/flights"
METERS_TO_FEET = 3.28084
KMH_TO_KNOTS = 0.539957

AIRLINE_NAMES = {
    "AA": "American",
    "AAL": "American",
    "AC": "Air Canada",
    "ACA": "Air Canada",
    "AS": "Alaska",
    "ASA": "Alaska",
    "BA": "British",
    "BAW": "British",
    "DL": "Delta",
    "DAL": "Delta",
    "F9": "Frontier",
    "FFT": "Frontier",
    "B6": "JetBlue",
    "JBU": "JetBlue",
    "KL": "KLM",
    "KLM": "KLM",
    "NK": "Spirit",
    "NKS": "Spirit",
    "QF": "Qantas",
    "QFA": "Qantas",
    "SW": "Southwest",
    "WN": "Southwest",
    "SWA": "Southwest",
    "UA": "United",
    "UAL": "United",
    "UPS": "UPS",
}


@dataclass(frozen=True)
class BridgeConfig:
    api_key: str
    home_lat: float
    home_lon: float
    bbox_radius_km: float = 8.0
    display_radius_km: float = 5.0
    max_altitude_ft: int = 12000
    max_age_seconds: int = 90
    poll_interval_seconds: int = 15
    listen_host: str = "127.0.0.1"
    listen_port: int = 8787
    label: str = "Home Airspace"
    commercial_only: bool = True
    sample_source: str = ""

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "BridgeConfig":
        return cls(
            api_key=str(mapping.get("api_key", "")),
            home_lat=float(mapping["home_lat"]),
            home_lon=float(mapping["home_lon"]),
            bbox_radius_km=float(mapping.get("bbox_radius_km", 8.0)),
            display_radius_km=float(mapping.get("display_radius_km", 5.0)),
            max_altitude_ft=int(mapping.get("max_altitude_ft", 12000)),
            max_age_seconds=int(mapping.get("max_age_seconds", 90)),
            poll_interval_seconds=int(mapping.get("poll_interval_seconds", 15)),
            listen_host=str(mapping.get("listen_host", "127.0.0.1")),
            listen_port=int(mapping.get("listen_port", 8787)),
            label=str(mapping.get("label", "Home Airspace")),
            commercial_only=bool(mapping.get("commercial_only", True)),
            sample_source=str(mapping.get("sample_source", "")),
        )

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "BridgeConfig":
        config_path = pathlib.Path(path)
        with config_path.open("r", encoding="utf-8") as handle:
            return cls.from_mapping(json.load(handle))


@dataclass
class BridgeState:
    cached_payload: dict[str, Any] | None = None
    cached_at_monotonic: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expose the best nearby AirLabs flight as Tidbyt-friendly JSON.")
    parser.add_argument("--config", default="config.json", help="Path to bridge config JSON.")
    parser.add_argument("--once", action="store_true", help="Print one JSON payload and exit.")
    parser.add_argument("--host", help="Override listen host.")
    parser.add_argument("--port", type=int, help="Override listen port.")
    parser.add_argument("--display-radius-km", type=float, help="Override display radius in kilometers.")
    args = parser.parse_args(argv)

    config = BridgeConfig.load(args.config)
    if args.host:
        config = BridgeConfig.from_mapping({**config.__dict__, "listen_host": args.host})
    if args.port:
        config = BridgeConfig.from_mapping({**config.__dict__, "listen_port": args.port})
    if args.display_radius_km:
        config = BridgeConfig.from_mapping({**config.__dict__, "display_radius_km": args.display_radius_km})

    if args.once:
        json.dump(build_payload(config), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    serve(config)
    return 0


def serve(config: BridgeConfig) -> None:
    state = BridgeState()
    handler = build_handler(config, state)
    server = ThreadingHTTPServer((config.listen_host, config.listen_port), handler)
    source = config.sample_source or "AirLabs"
    print(
        f"AirLabs bridge listening on http://{config.listen_host}:{config.listen_port}/plane.json "
        f"using source {source}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping bridge.")
    finally:
        server.server_close()


def build_handler(config: BridgeConfig, state: BridgeState):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self.respond({"ok": True})
                return
            if parsed.path == "/" or parsed.path == "/plane.json":
                try:
                    payload = get_cached_payload(config, state)
                except Exception as exc:  # pragma: no cover
                    self.respond(
                        {
                            "generated_at": now_iso(),
                            "plane": None,
                            "message": f"Bridge error: {exc}",
                        },
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return
                self.respond(payload)
                return
            self.respond(
                {
                    "generated_at": now_iso(),
                    "plane": None,
                    "message": "Not found",
                },
                status=HTTPStatus.NOT_FOUND,
            )

        def log_message(self, format: str, *args: Any) -> None:
            return

        def respond(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def get_cached_payload(config: BridgeConfig, state: BridgeState) -> dict[str, Any]:
    with state.lock:
        age = time.monotonic() - state.cached_at_monotonic
        if state.cached_payload is not None and age < config.poll_interval_seconds:
            return state.cached_payload

        payload = build_payload(config)
        state.cached_payload = payload
        state.cached_at_monotonic = time.monotonic()
        return payload


def build_payload(config: BridgeConfig) -> dict[str, Any]:
    flights = load_flights(config)
    plane = select_best_plane(flights, config)
    south, west, north, east = build_bbox(
        config.home_lat,
        config.home_lon,
        config.bbox_radius_km,
    )
    return {
        "generated_at": now_iso(),
        "area": {
            "label": config.label,
            "home_lat": round(config.home_lat, 4),
            "home_lon": round(config.home_lon, 4),
            "bbox_radius_km": round(config.bbox_radius_km, 2),
            "display_radius_km": round(config.display_radius_km, 2),
            "bbox": [round(south, 4), round(west, 4), round(north, 4), round(east, 4)],
        },
        "plane": plane,
        "message": "Tracking most audible nearby aircraft" if plane else "No likely audible aircraft nearby",
    }


def load_flights(config: BridgeConfig) -> list[dict[str, Any]]:
    if config.sample_source:
        source_path = pathlib.Path(config.sample_source)
        with source_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return extract_flights(raw)

    if not config.api_key:
        raise RuntimeError("Missing AirLabs api_key in config.json")

    south, west, north, east = build_bbox(config.home_lat, config.home_lon, config.bbox_radius_km)
    params = {
        "api_key": config.api_key,
        "bbox": ",".join(
            [
                format_coord(south),
                format_coord(west),
                format_coord(north),
                format_coord(east),
            ]
        ),
        "_fields": ",".join(
            [
                "hex",
                "reg_number",
                "lat",
                "lng",
                "alt",
                "dir",
                "speed",
                "flight_icao",
                "flight_iata",
                "flight_number",
                "dep_iata",
                "dep_icao",
                "arr_iata",
                "arr_icao",
                "airline_iata",
                "airline_icao",
                "aircraft_icao",
                "updated",
                "status",
            ]
        ),
    }
    request_url = f"{AIRLABS_FLIGHTS_URL}?{urlencode(params)}"

    try:
        with urlopen(request_url, timeout=8) as response:
            raw = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from AirLabs") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach AirLabs: {exc.reason}") from exc

    if isinstance(raw, dict) and raw.get("error"):
        message = raw["error"].get("message", "Unknown AirLabs error")
        raise RuntimeError(message)

    return extract_flights(raw)


def extract_flights(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        response = raw.get("response")
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        data = raw.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def build_bbox(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    delta_lat = radius_km / 111.32
    delta_lon = radius_km / (111.32 * math.cos(math.radians(lat)))
    return (lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


def select_best_plane(flights: list[dict[str, Any]], config: BridgeConfig) -> dict[str, Any] | None:
    candidates: list[tuple[tuple[float, float, float, float], dict[str, Any]]] = []
    for flight in flights:
        lat = to_float(flight.get("lat"))
        lon = to_float(flight.get("lng"))
        if lat is None or lon is None:
            continue

        altitude_ft = meters_to_feet(flight.get("alt"))
        if altitude_ft is None or altitude_ft <= 0 or altitude_ft > config.max_altitude_ft:
            continue

        status = safe_string(flight.get("status")).lower()
        if status in {"landed", "scheduled", "cancelled"}:
            continue

        updated_ts = to_int(flight.get("updated"))
        age_seconds = 0
        if updated_ts is not None:
            age_seconds = max(0, int(time.time()) - updated_ts)
            if age_seconds > config.max_age_seconds:
                continue

        if config.commercial_only and not is_commercial_candidate(flight):
            continue

        distance_km = haversine_km(config.home_lat, config.home_lon, lat, lon)
        if distance_km > config.display_radius_km:
            continue

        slant_distance_km = compute_slant_distance_km(distance_km, altitude_ft)
        heading_penalty = compute_heading_penalty(config.home_lat, config.home_lon, lat, lon, flight.get("dir"))
        score = (
            slant_distance_km + (altitude_ft / 20000.0) + (age_seconds / 60.0) + heading_penalty,
            slant_distance_km,
            distance_km,
            age_seconds,
        )
        normalized = normalize_plane(flight, distance_km, slant_distance_km, altitude_ft, age_seconds)
        candidates.append((score, normalized))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def normalize_plane(
    flight: dict[str, Any],
    distance_km: float,
    slant_distance_km: float,
    altitude_ft: int,
    age_seconds: int,
) -> dict[str, Any]:
    speed_kts = kmh_to_knots(flight.get("speed"))
    callsign = first_string(flight, "flight_icao", "flight_iata", "flight_number", "hex")
    return {
        "icao": first_string(flight, "hex").lower(),
        "callsign": callsign,
        "carrier": guess_carrier_name(flight, callsign),
        "tail": first_string(flight, "reg_number"),
        "aircraft_type": first_string(flight, "aircraft_icao"),
        "aircraft_description": first_string(flight, "aircraft_icao"),
        "origin": first_string(flight, "dep_iata", "dep_icao"),
        "destination": first_string(flight, "arr_iata", "arr_icao"),
        "altitude_ft": altitude_ft,
        "speed_kts": speed_kts,
        "track_deg": to_int(flight.get("dir")),
        "distance_km": round(distance_km, 1),
        "distance_mi": round(distance_km * 0.621371, 1),
        "slant_distance_km": round(slant_distance_km, 1),
        "age_seconds": age_seconds,
        "status": safe_string(flight.get("status")).lower(),
    }


def is_commercial_candidate(flight: dict[str, Any]) -> bool:
    airline_code = first_string(flight, "airline_iata", "airline_icao")
    route_origin = first_string(flight, "dep_iata", "dep_icao")
    route_destination = first_string(flight, "arr_iata", "arr_icao")
    return bool(airline_code and route_origin and route_destination)


def compute_slant_distance_km(horizontal_distance_km: float, altitude_ft: int) -> float:
    altitude_km = altitude_ft * 0.0003048
    return math.sqrt(horizontal_distance_km**2 + altitude_km**2)


def compute_heading_penalty(
    home_lat: float,
    home_lon: float,
    plane_lat: float,
    plane_lon: float,
    track_value: Any,
) -> float:
    track = to_float(track_value)
    if track is None:
        return 0.25
    bearing = bearing_degrees(plane_lat, plane_lon, home_lat, home_lon)
    diff = angular_difference(track, bearing)
    if diff <= 45:
        return 0.0
    if diff <= 90:
        return 0.25
    if diff <= 135:
        return 0.6
    return 1.0


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    y = math.sin(delta_lon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def angular_difference(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def guess_carrier_name(flight: dict[str, Any], callsign: str) -> str:
    airline_iata = first_string(flight, "airline_iata").upper()
    airline_icao = first_string(flight, "airline_icao").upper()
    if airline_iata in AIRLINE_NAMES:
        return AIRLINE_NAMES[airline_iata]
    if airline_icao in AIRLINE_NAMES:
        return AIRLINE_NAMES[airline_icao]
    prefix = "".join(char for char in callsign[:3].upper() if char.isalpha())
    return AIRLINE_NAMES.get(prefix, airline_iata or airline_icao)


def meters_to_feet(value: Any) -> int | None:
    meters = to_float(value)
    if meters is None:
        return None
    return int(round(meters * METERS_TO_FEET))


def kmh_to_knots(value: Any) -> int | None:
    kmh = to_float(value)
    if kmh is None:
        return None
    return int(round(kmh * KMH_TO_KNOTS))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def first_string(entry: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = safe_string(entry.get(key))
        if value:
            return value
    return ""


def safe_string(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text if text.lower() != "none" else ""


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    number = to_float(value)
    if number is None:
        return None
    return int(round(number))


def format_coord(value: float) -> str:
    return f"{value:.4f}"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
