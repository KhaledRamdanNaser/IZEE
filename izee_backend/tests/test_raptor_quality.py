import time
import unittest

import main


ORIGIN = {"lat": 30.1216748, "lon": 31.2426427}
DESTINATION = {"lat": 30.0098054, "lon": 31.2329537}


def run_known_trip(debug=True):
    request = main.TripPlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        departure_time="08:00:00",
        max_transfers=4,
        use_walking=True,
    )
    db = next(main.get_db())

    try:
        started_at = time.perf_counter()
        response = main.trip_plan(
            request,
            debug=debug,
            trace=None,
            street_geometry=False,
            db=db,
        )
        elapsed = time.perf_counter() - started_at
    finally:
        db.close()

    return response, elapsed


def route_labels(route):
    return [
        leg.get("route_label") or "walk"
        for leg in route.get("legs", [])
    ]


def route_modes(route):
    return [
        leg.get("mode")
        for leg in route.get("legs", [])
    ]


def has_metro_only_route(route):
    return (
        route_modes(route) == ["walk", "metro", "metro", "walk"]
        and route_labels(route) == ["walk", "M2", "M1", "walk"]
    )


class RaptorQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.response, cls.elapsed = run_known_trip()

    def test_metro_only_route_still_appears(self):
        self.assertTrue(
            any(has_metro_only_route(route) for route in self.response["routes"])
        )

    def test_zero_transfer_surface_alternative_still_appears(self):
        self.assertTrue(
            any(
                route.get("transfer_count") == 0
                and any(
                    mode in {"bus", "minibus", "microbus"}
                    for mode in route_modes(route)
                )
                for route in self.response["routes"]
            )
        )

    def test_duplicate_metro_alternatives_are_merged(self):
        metro_routes = [
            route
            for route in self.response["routes"]
            if has_metro_only_route(route)
        ]

        self.assertEqual(1, len(metro_routes))
        self.assertGreaterEqual(
            set(metro_routes[0]["badges"]),
            {"recommended", "fastest transit"},
        )

        signatures = [
            tuple(
                (
                    leg.get("mode"),
                    leg.get("route_id"),
                    leg.get("from_stop_id"),
                    leg.get("to_stop_id"),
                )
                for leg in route.get("legs", [])
            )
            for route in self.response["routes"]
        ]
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_metro_priority_preserves_quality_within_raptor_time_budget(self):
        prioritized_raptor = self.response["debug"]["timings"]["raptor_seconds"]

        self.assertTrue(
            any(has_metro_only_route(route) for route in self.response["routes"])
        )
        self.assertLessEqual(prioritized_raptor, 15.0)


if __name__ == "__main__":
    unittest.main()
