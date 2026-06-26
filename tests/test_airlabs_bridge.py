import json
import pathlib
import tempfile
import unittest

from bridge import airlabs_bridge


class AirlabsBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_path = pathlib.Path(__file__).resolve().parents[1] / "samples" / "airlabs_flights.json"
        self.config = airlabs_bridge.BridgeConfig.from_mapping(
            {
                "api_key": "",
                "home_lat": 37.6547,
                "home_lon": -122.4077,
                "bbox_radius_km": 8.0,
                "display_radius_km": 5.0,
                "max_altitude_ft": 12000,
                "max_age_seconds": 120,
                "label": "South San Francisco",
                "commercial_only": True,
                "sample_source": str(self.sample_path),
            }
        )

    def test_build_bbox_for_south_san_francisco(self) -> None:
        south, west, north, east = airlabs_bridge.build_bbox(37.6547, -122.4077, 8.0)

        self.assertAlmostEqual(south, 37.5828, places=3)
        self.assertAlmostEqual(west, -122.4985, places=3)
        self.assertAlmostEqual(north, 37.7266, places=3)
        self.assertAlmostEqual(east, -122.3169, places=3)

    def test_build_payload_selects_best_plane(self) -> None:
        payload = airlabs_bridge.build_payload(self.config)

        self.assertEqual(payload["area"]["label"], "South San Francisco")
        self.assertIsNotNone(payload["plane"])
        self.assertEqual(payload["plane"]["callsign"], "UAL123")
        self.assertEqual(payload["plane"]["carrier"], "United")
        self.assertEqual(payload["plane"]["origin"], "SFO")
        self.assertEqual(payload["plane"]["destination"], "LAX")
        self.assertLess(payload["plane"]["distance_km"], 1.0)

    def test_small_display_radius_returns_no_plane(self) -> None:
        config = airlabs_bridge.BridgeConfig.from_mapping(
            {
                **self.config.__dict__,
                "display_radius_km": 0.1,
            }
        )

        payload = airlabs_bridge.build_payload(config)

        self.assertIsNone(payload["plane"])
        self.assertEqual(payload["message"], "No likely audible aircraft nearby")

    def test_load_config_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = pathlib.Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "home_lat": 37.6547,
                        "home_lon": -122.4077,
                        "api_key": "abc123",
                    }
                ),
                encoding="utf-8",
            )

            config = airlabs_bridge.BridgeConfig.load(config_path)

        self.assertEqual(config.listen_port, 8787)
        self.assertEqual(config.bbox_radius_km, 8.0)


if __name__ == "__main__":
    unittest.main()
