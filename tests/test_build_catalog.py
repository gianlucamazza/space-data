"""Unit tests for catalog merges. No network."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import spacedata.build_catalog as catalog


class ParseTests(unittest.TestCase):
    def test_next_link(self):
        header = (
            '<https://network.satnogs.org/api/observations/?cursor=abc&format=json>; rel="next"'
        )
        self.assertEqual(
            catalog.parse_next_link(header),
            "https://network.satnogs.org/api/observations/?cursor=abc&format=json",
        )

    def test_next_link_absent(self):
        self.assertIsNone(catalog.parse_next_link('<https://example.test/>; rel="prev"'))
        self.assertIsNone(catalog.parse_next_link(None))

    def test_as_int_accepts_six_digit_catalog_numbers(self):
        self.assertEqual(catalog.as_int(100001), 100001)
        self.assertEqual(catalog.as_int(" 98238 "), 98238)
        self.assertIsNone(catalog.as_int(None))
        self.assertIsNone(catalog.as_int("ISS"))


class MergeTests(unittest.TestCase):
    def test_newer_epoch_wins_and_groups_accumulate(self):
        gp = {
            "active": [
                {
                    "NORAD_CAT_ID": 25544,
                    "OBJECT_NAME": "ISS (ZARYA)",
                    "OBJECT_ID": "1998-067A",
                    "EPOCH": "2026-10-12T03:27:40.741056",
                    "INCLINATION": 51.63,
                    "MEAN_MOTION": 15.49,
                }
            ],
            "stations": [
                {
                    "NORAD_CAT_ID": 25544,
                    "OBJECT_NAME": "ISS (ZARYA)",
                    "EPOCH": "2026-10-11T00:00:00",
                    "INCLINATION": 51.00,
                }
            ],
        }
        orbits = catalog.merge_orbits(gp, [], [])
        self.assertEqual(len(orbits), 1)
        self.assertEqual(orbits[0]["inclination_deg"], 51.63)
        self.assertEqual(orbits[0]["groups"], ["active", "stations"])
        self.assertEqual(orbits[0]["object_id"], "1998-067A")

    def test_satcat_fills_owner_and_satnogs_identity(self):
        gp = {
            "amateur": [
                {
                    "NORAD_CAT_ID": 123,
                    "OBJECT_NAME": "CUBE",
                    "EPOCH": "2026-10-01T00:00:00",
                }
            ]
        }
        satcat = [
            {
                "NORAD_CAT_ID": 123,
                "OWNER": "IT",
                "LAUNCH_DATE": "2024-01-02",
                "OPS_STATUS_CODE": "+",
                "OBJECT_TYPE": "PAY",
                "PERIOD": 95.1,
                "APOGEE": 520,
                "PERIGEE": 500,
            }
        ]
        satnogs = [
            {
                "sat_id": "AAAA",
                "norad_cat_id": 123,
                "name": "CUBE",
                "status": "in orbit",
                "countries": "IT",
                "operator": "None",
                "names": "ALT",
                "decayed": None,
            },
            {
                "sat_id": "BBBB",
                "norad_cat_id": 123,
                "name": "CUBE-OLD",
                "status": "re-entered",
                "decayed": "2020-01-01T00:00:00Z",
            },
        ]
        orbits = catalog.merge_orbits(gp, satcat, satnogs)
        self.assertEqual(orbits[0]["owner"], "IT")
        self.assertEqual(orbits[0]["ops_status"], "+")
        self.assertEqual(orbits[0]["satnogs_id"], "AAAA")
        self.assertIsNone(orbits[0]["operator"])
        self.assertEqual(orbits[0]["names"], "ALT")

    def test_decayed_satnogs_only_objects_stay_out_of_orbits(self):
        satnogs = [
            {
                "sat_id": "OLD",
                "norad_cat_id": 9,
                "name": "TRANSIT",
                "status": "re-entered",
                "decayed": "1970-01-01T00:00:00Z",
            }
        ]
        self.assertEqual(catalog.merge_orbits({}, [], satnogs), [])

    def test_signals_skip_dead_transmitters_and_attach_names(self):
        transmitters = [
            {
                "uuid": "b",
                "alive": True,
                "norad_cat_id": 5,
                "sat_id": "S",
                "downlink_low": 145825000,
                "mode": "AFSK",
                "baud": 1200,
                "description": "APRS",
                "service": "Amateur",
            },
            {"uuid": "a", "alive": False, "norad_cat_id": 5, "downlink_low": 1},
        ]
        satnogs = [{"sat_id": "S", "norad_cat_id": 5, "name": "FOO", "status": "in orbit"}]
        signals = catalog.build_signals(transmitters, satnogs, [])
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["name"], "FOO")
        self.assertEqual(signals[0]["downlink_hz"], 145825000)


class SlimTests(unittest.TestCase):
    def test_observation_drops_operator_and_caps_demod_urls(self):
        raw = {
            "id": 1,
            "start": "2026-10-12T10:58:05Z",
            "end": "2026-10-12T11:03:50Z",
            "norad_cat_id": 98238,
            "observer": "qualcuno",
            "vetted_user": "revisore",
            "station_name": "stazione",
            "station_lat": 45.0,
            "waterfall": "https://example.test/waterfall.png",
            "demoddata": [{"payload_demod": f"https://example.test/{i}"} for i in range(12)],
            "transmitter_mode": "FSK",
            "transmitter_downlink_low": 436000000,
        }
        slim = catalog.slim_observation(raw)
        self.assertNotIn("observer", slim)
        self.assertNotIn("vetted_user", slim)
        self.assertEqual(slim["demod_count"], 12)
        self.assertEqual(len(slim["demod_urls"]), 8)
        self.assertTrue(slim["has_waterfall"])
        self.assertEqual(slim["norad_cat_id"], 98238)
        self.assertEqual(slim["station_name"], "stazione")

    def test_window_parse(self):
        parsed = catalog.parse_time("2026-10-12T10:58:05Z")
        self.assertEqual(parsed, datetime(2026, 10, 12, 10, 58, 5, tzinfo=timezone.utc))

    def test_stac_and_pds_trim_text(self):
        stac = catalog.slim_stac(
            {
                "id": "sentinel-2-l2a",
                "title": "S2",
                "description": "  linea   uno  ",
                "license": "other",
                "links": [{"rel": "license", "href": "https://example.test/license"}],
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [["2015-06-23T00:00:00Z", None]]},
                },
                "keywords": ["Sentinel"],
            }
        )
        self.assertEqual(stac["description"], "linea uno")
        self.assertEqual(stac["license_href"], "https://example.test/license")
        self.assertEqual(stac["bbox"], [-180, -90, 180, 90])
        pds = catalog.slim_pds(
            {
                "lid": "urn:nasa:pds:example",
                "title": "Example",
                "description": ["  testo   lungo  "],
                "agency_name": ["NASA"],
            }
        )
        self.assertEqual(pds["description"], "testo lungo")
        self.assertEqual(pds["agency"], "NASA")


class ReadmeTests(unittest.TestCase):
    def test_cached_files_are_not_listed_as_errors(self):
        text = catalog.render_snapshot_readme(
            {
                "retrieved_at": "2026-10-12T00:00:00Z",
                "orbits": 1,
                "signals_alive": 0,
                "observations": 0,
                "observation_earliest": None,
                "observation_latest": None,
                "stac_collections": 0,
                "pds_bundles": 0,
                "orbits_by_group": {"stations": 1},
                "signals_by_mode": {},
                "sources": [
                    {
                        "id": "celestrak-gp-stations",
                        "status": "cached",
                        "records": 1,
                        "bytes": 10,
                        "path": "data/raw/x",
                        "license": "celestrak-attribution",
                    },
                    {
                        "id": "celestrak-gp-active",
                        "status": "absent",
                        "records": None,
                        "bytes": None,
                        "path": None,
                        "license": "celestrak-attribution",
                    },
                ],
            }
        )
        self.assertNotIn("stato cached", text)
        self.assertIn("## Lacune", text)
        self.assertIn("`celestrak-gp-active` — absent", text)
        self.assertIn("GP CelesTrak", text)


if __name__ == "__main__":
    unittest.main()
