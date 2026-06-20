import os
import unittest
from unittest.mock import patch


os.environ["IZEE_ENABLE_EXPERIMENTAL_BRT"] = "1"
os.environ["IZEE_ENABLE_EXPERIMENTAL_LRT"] = "1"

import main  # noqa: E402


def fake_osm_results(query, limit=10):
    normalized = query.strip().lower()
    if "الخصوص" in normalized:
        return [{
            "name": "الخصوص, القليوبية, مصر",
            "lat": 30.155,
            "lon": 31.315,
            "source": "openstreetmap",
            "result_type": "district",
            "type": "district",
        }]
    if "العاشر" in normalized:
        return [{
            "name": "العاشر من رمضان, الشرقية, مصر",
            "lat": 30.306,
            "lon": 31.742,
            "source": "openstreetmap",
            "result_type": "district",
            "type": "district",
        }]
    return [{
        "name": f"{query}, مصر",
        "lat": 30.05,
        "lon": 31.24,
        "source": "openstreetmap",
        "result_type": "osm_place",
        "type": "osm_place",
    }]


class PlacesSearchRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.get_raptor_indexes()

    def search(self, query):
        with patch.object(main, "search_places_with_nominatim", fake_osm_results):
            return main.merged_place_search(query, limit=10)

    def test_explicit_brt_query_prioritizes_brt_stop(self):
        results = self.search("BRT الخصوص")

        self.assertTrue(results)
        self.assertEqual("BRT_KHOSOUS", results[0].get("stop_id"))
        self.assertEqual("transit_stop", results[0].get("result_type"))
        self.assertEqual("brt", results[0].get("mode"))

    def test_generic_khosous_mixes_brt_and_osm(self):
        results = self.search("الخصوص")

        self.assertTrue(any(item.get("stop_id") == "BRT_KHOSOUS" for item in results))
        self.assertTrue(any(item.get("source") == "openstreetmap" for item in results))
        self.assertEqual("BRT_KHOSOUS", results[0].get("stop_id"))
        self.assertEqual("openstreetmap", results[1].get("source"))

    def test_explicit_lrt_query_prioritizes_lrt_stop(self):
        results = self.search("LRT العاشر من رمضان")

        self.assertTrue(results)
        self.assertEqual("LRT_10TH_RAMADAN", results[0].get("stop_id"))
        self.assertEqual("lrt", results[0].get("mode"))

    def test_generic_tenth_of_ramadan_mixes_lrt_and_osm(self):
        results = self.search("العاشر من رمضان")

        self.assertTrue(
            any(item.get("stop_id") == "LRT_10TH_RAMADAN" for item in results)
        )
        self.assertTrue(any(item.get("source") == "openstreetmap" for item in results))

    def test_station_query_prioritizes_adly_mansour_transit(self):
        results = self.search("محطة عدلي منصور")

        self.assertTrue(results)
        self.assertEqual("transit_stop", results[0].get("result_type"))
        self.assertIn(results[0].get("mode"), {"metro", "lrt", "brt"})


if __name__ == "__main__":
    unittest.main()
