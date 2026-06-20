import importlib
import os
import unittest


os.environ["IZEE_ENABLE_EXPERIMENTAL_LRT"] = "1"
os.environ["IZEE_ENABLE_LRT_FEEDER_TRANSFERS"] = "1"

import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if "main" in sys.modules:
    del sys.modules["main"]

import main  # noqa: E402



def reload_main(lrt_enabled=True):
    os.environ["IZEE_ENABLE_EXPERIMENTAL_LRT"] = "1" if lrt_enabled else "0"
    os.environ["IZEE_ENABLE_LRT_FEEDER_TRANSFERS"] = "1"
    # Reload the main module if it is already imported; otherwise import it fresh.
    if "main" in sys.modules:
        return importlib.reload(sys.modules["main"])
    else:
        import main
        return main


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
            trace="lrt" if debug else None,
            street_geometry=False,
            db=db,
        )
    finally:
        db.close()


def lrt_routes(response):
    return [
        route
        for route in response.get("routes", [])
        if any(leg.get("mode") == "lrt" for leg in route.get("legs", []))
    ]


def transit_legs(route):
    return [
        leg
        for leg in route.get("legs", [])
        if leg.get("mode") != "walk"
    ]


class LrtRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reload_main(lrt_enabled=True)

    def test_lrt_feed_loads_when_enabled(self):
        indexes = main.get_raptor_indexes()
        route_modes = indexes["route_modes"]

        self.assertEqual("lrt", route_modes.get("LRT_ADLY_10RAMADAN"))
        self.assertEqual("lrt", route_modes.get("LRT_ADLY_CAPITAL"))
        self.assertEqual(
            19,
            sum(
                1
                for stop_id in indexes["stop_details"]
                if str(stop_id).startswith("LRT_")
            ),
        )

    def test_adly_mansour_to_badr_uses_lrt(self):
        response = run_trip(
            {"lat": 30.146415463, "lon": 31.421308868},
            {"lat": 30.175123862, "lon": 31.71602145},
        )
        routes = lrt_routes(response)

        self.assertTrue(routes)
        legs = transit_legs(routes[0])
        self.assertEqual("lrt", legs[0]["mode"])
        self.assertIn(
            legs[0]["route_id"],
            {"LRT_ADLY_10RAMADAN", "LRT_ADLY_CAPITAL"},
        )

    def test_badr_to_tenth_of_ramadan_branch_uses_lrt(self):
        response = run_trip(
            {"lat": 30.175123862, "lon": 31.71602145},
            {"lat": 30.306790796, "lon": 31.703193893},
        )
        routes = lrt_routes(response)

        self.assertTrue(routes)
        self.assertEqual("LRT_ADLY_10RAMADAN", transit_legs(routes[0])[0]["route_id"])

    def test_adly_mansour_to_arts_and_culture_uses_lrt(self):
        response = run_trip(
            {"lat": 30.146415463, "lon": 31.421308868},
            {"lat": 30.013641883, "lon": 31.724961031},
        )
        routes = lrt_routes(response)

        self.assertTrue(routes)
        self.assertEqual("LRT_ADLY_CAPITAL", transit_legs(routes[0])[0]["route_id"])

    def test_adly_mansour_to_tenth_of_ramadan_uses_lrt_branch(self):
        response = run_trip(
            {"lat": 30.146415463, "lon": 31.421308868},
            {"lat": 30.306790796, "lon": 31.703193893},
        )
        routes = lrt_routes(response)

        self.assertTrue(routes)
        self.assertEqual("LRT_ADLY_10RAMADAN", transit_legs(routes[0])[0]["route_id"])

    def test_badr_to_central_capital_uses_lrt_capital_branch(self):
        response = run_trip(
            {"lat": 30.175123862, "lon": 31.71602145},
            {"lat": 29.884908875, "lon": 31.715984882},
        )
        routes = lrt_routes(response)

        self.assertTrue(routes)
        self.assertEqual("LRT_ADLY_CAPITAL", transit_legs(routes[0])[0]["route_id"])

    def test_badr_to_city_center_uses_lrt_tenth_branch(self):
        response = run_trip(
            {"lat": 30.175123862, "lon": 31.71602145},
            {"lat": 30.318500229, "lon": 31.735602865},
        )
        routes = lrt_routes(response)

        self.assertTrue(routes)
        self.assertEqual("LRT_ADLY_10RAMADAN", transit_legs(routes[0])[0]["route_id"])

    def test_khosous_to_badr_keeps_lrt_alternative(self):
        response = run_trip(
            {"lat": 30.1633208, "lon": 31.3231549},
            {"lat": 30.1751239, "lon": 31.7160215},
        )
        routes = lrt_routes(response)

        self.assertTrue(routes)
        self.assertTrue(
            any(
                leg.get("route_id") == "LRT_ADLY_10RAMADAN"
                for route in routes
                for leg in route.get("legs", [])
            )
        )

    def test_khosous_to_capital_airport_keeps_brt_lrt_alternative(self):
        response = run_trip(
            {"lat": 30.1633208, "lon": 31.3231549},
            {"lat": 30.0758872, "lon": 31.782474},
        )

        combined_routes = [
            route
            for route in response.get("routes", [])
            if "brt" in [leg.get("mode") for leg in route.get("legs", [])]
            and "lrt" in [leg.get("mode") for leg in route.get("legs", [])]
        ]

        self.assertTrue(combined_routes)
        self.assertIn("brt + lrt", combined_routes[0].get("badges", []))

    def test_internal_search_returns_lrt_when_enabled(self):
        results = main.internal_stop_search("badr", limit=5)

        self.assertTrue(results)
        self.assertEqual("LRT_BADR", results[0]["stop_id"])
        self.assertEqual("lrt", results[0]["mode"])

    def test_lrt_feed_disappears_when_disabled(self):
        reloaded = reload_main(lrt_enabled=False)
        indexes = reloaded.get_raptor_indexes()

        self.assertFalse(
            any(mode == "lrt" for mode in indexes["route_modes"].values())
        )
        self.assertFalse(
            any(
                str(stop_id).startswith("LRT_")
                for stop_id in indexes["stop_details"]
            )
        )
        self.assertFalse(
            any(
                result["mode"] == "lrt"
                for result in reloaded.internal_stop_search("badr", limit=5)
            )
        )

        reload_main(lrt_enabled=True)


if __name__ == "__main__":
    unittest.main()
