import importlib
import os
import unittest


os.environ["IZEE_ENABLE_EXPERIMENTAL_MONORAIL"] = "1"
os.environ["IZEE_ENABLE_MONORAIL_FEEDER_TRANSFERS"] = "1"
# Ensure other modes are enabled too for full integration testing
os.environ["IZEE_ENABLE_EXPERIMENTAL_LRT"] = "1"
os.environ["IZEE_ENABLE_LRT_FEEDER_TRANSFERS"] = "1"

import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if "main" in sys.modules:
    del sys.modules["main"]

import main  # noqa: E402


def reload_main(monorail_enabled=True):
    os.environ["IZEE_ENABLE_EXPERIMENTAL_MONORAIL"] = "1" if monorail_enabled else "0"
    os.environ["IZEE_ENABLE_MONORAIL_FEEDER_TRANSFERS"] = "1" if monorail_enabled else "0"
    return importlib.reload(main)


def run_trip(origin, destination, debug=False):
    request = main.TripPlanRequest(
        origin=origin,
        destination=destination,
        departure_time="08:00:00",
        max_transfers=4,
        use_walking=True,
    )
    db = next(main.get_db())

    try:
        return main.trip_plan(
            request,
            debug=debug,
            trace="monorail" if debug else None,
            street_geometry=False,
            db=db,
        )
    finally:
        db.close()


def monorail_routes(response):
    return [
        route
        for route in response.get("routes", [])
        if any(leg.get("mode") == "monorail" for leg in route.get("legs", []))
    ]


def transit_legs(route):
    return [
        leg
        for leg in route.get("legs", [])
        if leg.get("mode") != "walk"
    ]


class MonorailRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reload_main(monorail_enabled=True)

    def test_monorail_feed_loads_when_enabled(self):
        indexes = main.get_raptor_indexes()
        route_modes = indexes["route_modes"]

        self.assertEqual("monorail", route_modes.get("MONORAIL_EAST_NILE"))
        self.assertEqual(
            21,
            sum(
                1
                for stop_id in indexes["stop_details"]
                if str(stop_id).startswith("MONORAIL_")
            ),
        )

    def test_stadium_to_justice_city_uses_monorail(self):
        # Coordinates of Stadium and Justice City
        response = run_trip(
            {"lat": 30.071569, "lon": 31.317643},
            {"lat": 30.006103, "lon": 31.770341},
        )
        routes = monorail_routes(response)

        self.assertTrue(routes)
        legs = transit_legs(routes[0])
        self.assertEqual("monorail", legs[0]["mode"])
        self.assertEqual("MONORAIL_EAST_NILE", legs[0]["route_id"])

    def test_stadium_to_hesham_barakat_uses_monorail(self):
        # Short hop on Monorail
        response = run_trip(
            {"lat": 30.071569, "lon": 31.317643},
            {"lat": 30.063404, "lon": 31.321853},
        )
        routes = monorail_routes(response)

        self.assertTrue(routes)
        legs = transit_legs(routes[0])
        self.assertEqual("monorail", legs[0]["mode"])
        self.assertEqual("MONORAIL_EAST_NILE", legs[0]["route_id"])

    def test_internal_search_returns_monorail_when_enabled(self):
        results = main.internal_stop_search("الاستاد", limit=5)

        self.assertTrue(results)
        self.assertEqual("MONORAIL_STADIUM", results[0]["stop_id"])
        self.assertEqual("monorail", results[0]["mode"])

    def test_monorail_feed_disappears_when_disabled(self):
        reloaded = reload_main(monorail_enabled=False)
        indexes = reloaded.get_raptor_indexes()

        self.assertFalse(
            any(mode == "monorail" for mode in indexes["route_modes"].values())
        )
        self.assertFalse(
            any(
                str(stop_id).startswith("MONORAIL_")
                for stop_id in indexes["stop_details"]
            )
        )
        self.assertFalse(
            any(
                result["mode"] == "monorail"
                for result in reloaded.internal_stop_search("الاستاد", limit=5)
            )
        )

        reload_main(monorail_enabled=True)


if __name__ == "__main__":
    unittest.main()
