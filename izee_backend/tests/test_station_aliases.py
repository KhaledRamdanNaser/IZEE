import unittest

import main


class StationAliasTests(unittest.TestCase):
    def test_official_station_area_map_metadata_improves_search(self):
        results = main.internal_stop_search("fair zone", limit=5)
        metadata_results = [
            result for result in results
            if result.get("station_metadata")
        ]

        self.assertTrue(metadata_results)
        first = metadata_results[0]
        self.assertIn("Official Mobility Cairo station-area map", first["subtitle"])
        self.assertEqual(
            "official_station_area_map",
            first["station_metadata"]["confidence"],
        )
        self.assertEqual("metadata_only", first["station_metadata"]["usage"])

    def test_station_area_alias_does_not_create_routing_modes(self):
        indexes = main.get_raptor_indexes()
        route_modes = set(indexes["route_modes"].values())

        self.assertNotIn("station_area_map", route_modes)
        self.assertNotIn("landmark", route_modes)


if __name__ == "__main__":
    unittest.main()
