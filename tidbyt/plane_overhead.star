"""
Applet: Plane Overhead
Summary: Most likely audible nearby aircraft
Description: Displays the most likely audible aircraft from a local AirLabs bridge feed.
Author: OpenAI Codex
"""

load("cache.star", "cache")
load("encoding/json.star", "json")
load("http.star", "http")
load("render.star", "render")
load("schema.star", "schema")

DEFAULT_FEED_URL = "http://127.0.0.1:8787/plane.json"
DEFAULT_TITLE = "OVERHEAD"
DEVICE_WIDTH = 64
DEVICE_HEIGHT = 32
CACHE_TTL_SECONDS = 5

def main(config):
    title = config.get("title", DEFAULT_TITLE)
    feed_url = config.get("feed_url", DEFAULT_FEED_URL)
    data = fetch_feed(feed_url)
    plane = data.get("plane", None)

    if plane == None:
        return render.Root(
            child = build_screen(
                title,
                "No likely plane",
                data.get("area", {}).get("label", "Waiting for bridge"),
                data.get("message", "Listening..."),
            ),
        )

    return render.Root(
        child = build_screen(
            plane_identity(plane),
            join_parts([plane.get("carrier", ""), plane.get("aircraft_type", "")]),
            format_route(plane),
            join_parts([format_altitude(plane), format_speed(plane)]),
        ),
    )

def fetch_feed(feed_url):
    cache_key = "plane_overhead:" + feed_url
    cached = cache.get(cache_key)
    if cached != None:
        return json.decode(cached)

    response = http.get(feed_url)
    if response.status_code != 200:
        return {
            "message": "Bridge offline",
            "area": {
                "label": feed_url,
            },
        }

    data = response.json()
    cache.set(cache_key, json.encode(data), ttl_seconds = CACHE_TTL_SECONDS)
    return data

def build_screen(line1, line2, line3, line4):
    return render.Box(
        width = DEVICE_WIDTH,
        height = DEVICE_HEIGHT,
        child = render.Column(
            expanded = True,
            main_align = "space_evenly",
            children = [
                build_line(line1, "#58d68d", "tb-8"),
                build_line(line2, "#ffffff", "tb-8"),
                build_line(line3, "#f4d35e", "tom-thumb"),
                build_line(line4, "#8ea6b4", "tom-thumb"),
            ],
        ),
    )

def build_line(content, color, font):
    return render.Row(
        expanded = True,
        main_align = "center",
        cross_align = "center",
        children = [
            render.Marquee(
                width = 62,
                child = render.Text(str(content), color = color, font = font),
            ),
        ],
    )

def plane_identity(plane):
    return first_nonempty([
        plane.get("callsign", ""),
        plane.get("tail", ""),
        plane.get("icao", ""),
        "Unknown aircraft",
    ])

def format_route(plane):
    origin = plane.get("origin", "")
    destination = plane.get("destination", "")
    if origin and destination:
        return "%s -> %s" % (origin, destination)
    if origin:
        return "FROM %s" % origin
    if destination:
        return "TO %s" % destination
    return plane.get("aircraft_description", "Route unavailable")

def format_altitude(plane):
    altitude = plane.get("altitude_ft", None)
    if altitude == None:
        return "ALT ?"
    return "%sFT" % altitude

def format_speed(plane):
    speed = plane.get("speed_kts", None)
    if speed == None:
        return "SPD ?"
    return "%sKT" % speed

def join_parts(parts):
    items = [str(part) for part in parts if part]
    if len(items) == 0:
        return "-"
    return "  ".join(items)

def first_nonempty(values):
    for value in values:
        if value:
            return value
    return ""

def get_schema():
    return schema.Schema(
        version = "1",
        fields = [
            schema.Text(
                id = "title",
                name = "Header",
                desc = "Short label for the top row.",
                icon = "flag",
                default = DEFAULT_TITLE,
            ),
            schema.Text(
                id = "feed_url",
                name = "Bridge URL",
                desc = "URL for the local ADS-B bridge JSON feed.",
                icon = "locationDot",
                default = DEFAULT_FEED_URL,
            ),
        ],
    )
