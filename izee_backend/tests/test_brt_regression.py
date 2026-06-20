import os
import unittest


os.environ["IZEE_ENABLE_EXPERIMENTAL_BRT"] = "1"

import main  # noqa: E402
from routing.journey_scorer import score_path  # noqa: E402
from routing.raptor_router import route_quality_rejection_reason  # noqa: E402


BRT_PATH = main.EXPERIMENTAL_BRT_GTFS_PATH


def ensure_brt_enabled_for_test_process():
    if BRT_PATH not in main.GTFS_PATHS:
        main.GTFS_PATHS.append(BRT_PATH)

    if main.RAPTOR_CACHE_VERSION != "raptor_indexes_v5_brt":
        main.RAPTOR_CACHE_VERSION = "raptor_indexes_v5_brt"
        main.RAPTOR_CACHE_PATH = os.path.join(
            os.path.dirname(main.__file__),
            ".cache",
            f"{main.RAPTOR_CACHE_VERSION}.pkl",
        )

    main.raptor_indexes_cache = None


def run_trip(origin, destination):
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
            debug=True,
            trace=None,
            street_geometry=False,
            db=db,
        )
    finally:
        db.close()


def transit_legs(route):
    return [
        leg
        for leg in route.get("legs", [])
        if leg.get("mode") != "walk"
    ]


def brt_routes(response):
    return [
        route
        for route in response.get("routes", [])
        if any(leg.get("mode") == "brt" for leg in route.get("legs", []))
    ]


def route_modes(route):
    return [leg.get("mode") for leg in route.get("legs", [])]


class BrtRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_brt_enabled_for_test_process()

    def test_khosous_to_marg_uses_single_direct_brt_leg(self):
        response = run_trip(
            {"lat": 30.1633334, "lon": 31.3230422},
            {"lat": 30.1634738, "lon": 31.3414397},
        )
        routes = brt_routes(response)

        self.assertTrue(routes)
        direct_route = routes[0]
        legs = transit_legs(direct_route)

        self.assertEqual(1, len(legs))
        self.assertEqual("brt", legs[0]["mode"])
        self.assertEqual("BRT_PHASE1", legs[0]["route_id"])
        self.assertEqual("BRT_KHOSOUS", legs[0]["from_stop_id"])
        self.assertEqual("BRT_MARG", legs[0]["to_stop_id"])
        self.assertEqual(0, direct_route["transfer_count"])
        self.assertEqual(15, direct_route["total_fare"])

    def test_marg_to_khosous_reverse_direction_uses_single_brt_leg(self):
        response = run_trip(
            {"lat": 30.1634738, "lon": 31.3414397},
            {"lat": 30.1633334, "lon": 31.3230422},
        )
        routes = brt_routes(response)

        self.assertTrue(routes)
        direct_route = routes[0]
        legs = transit_legs(direct_route)

        self.assertEqual(1, len(legs))
        self.assertEqual("BRT_PHASE1", legs[0]["route_id"])
        self.assertEqual("BRT_MARG", legs[0]["from_stop_id"])
        self.assertEqual("BRT_KHOSOUS", legs[0]["to_stop_id"])

    def test_long_brt_corridor_still_appears(self):
        response = run_trip(
            {"lat": 30.1577737, "lon": 31.2816413},
            {"lat": 30.1494873, "lon": 31.4178740},
        )

        self.assertTrue(brt_routes(response))

    def test_places_search_prefers_internal_brt_and_metro_marg(self):
        results = main.internal_stop_search("المرج", limit=5)

        self.assertGreaterEqual(len(results), 3)
        self.assertEqual("BRT_MARG", results[0]["stop_id"])
        self.assertEqual("brt", results[0]["mode"])
        self.assertTrue(
            any(result["mode"] == "metro" for result in results[1:]),
            results,
        )

    def test_brt_feeder_transfers_are_generated_bidirectionally(self):
        indexes = main.get_raptor_indexes()
        transfers = main.build_brt_feeder_transfers(indexes)

        ordinary_to_brt = [
            edge
            for edge in transfers.get("1425", [])
            if edge.get("to") == "BRT_KHOSOUS"
        ]
        brt_to_ordinary = [
            edge
            for edge in transfers.get("BRT_KHOSOUS", [])
            if edge.get("to") == "1425"
        ]

        self.assertTrue(ordinary_to_brt)
        self.assertTrue(brt_to_ordinary)
        self.assertEqual("brt_feeder_transfer", ordinary_to_brt[0]["walk_type"])
        self.assertEqual("generated_brt_feeder", ordinary_to_brt[0]["source"])
        self.assertEqual("medium", ordinary_to_brt[0]["confidence"])

    def test_feeder_transit_can_reach_brt_trunk(self):
        response = run_trip(
            {"lat": 30.137954, "lon": 31.293239},
            {"lat": 30.1634738, "lon": 31.3414397},
        )
        routes = brt_routes(response)

        self.assertTrue(routes)
        modes = route_modes(routes[0])
        self.assertIn("brt", modes)
        self.assertTrue(
            any(mode in {"bus", "microbus", "minibus", "metro"} for mode in modes[:modes.index("brt")]),
            modes,
        )

    def test_brt_can_transfer_to_metro(self):
        response = run_trip(
            {"lat": 30.1547353, "lon": 31.409471},
            {"lat": 30.0636, "lon": 31.2472},
        )
        routes = brt_routes(response)

        self.assertTrue(routes)
        self.assertTrue(
            any("brt" in route_modes(route) and "metro" in route_modes(route) for route in routes),
            [route_modes(route) for route in response.get("routes", [])],
        )

    def test_reverse_brt_feeder_path_survives_when_competitive(self):
        response = run_trip(
            {"lat": 30.1634738, "lon": 31.3414397},
            {"lat": 30.149155, "lon": 31.22889},
        )

        self.assertTrue(brt_routes(response))

    def test_surface_bus_chain_is_rejected_by_quality_guard(self):
        route = {
            "legs": [
                {"mode": "walk", "departure_time": 0, "arrival_time": 60},
                {
                    "mode": "bus",
                    "route_id": "CTA_505",
                    "from_stop_id": "a",
                    "to_stop_id": "b",
                    "departure_time": 60,
                    "arrival_time": 1200,
                },
                {
                    "mode": "bus",
                    "route_id": "CTA_1",
                    "from_stop_id": "b",
                    "to_stop_id": "c",
                    "departure_time": 1300,
                    "arrival_time": 2300,
                },
                {"mode": "walk", "departure_time": 2300, "arrival_time": 2500},
                {
                    "mode": "bus",
                    "route_id": "CTA_1032",
                    "from_stop_id": "d",
                    "to_stop_id": "e",
                    "departure_time": 2600,
                    "arrival_time": 3500,
                },
                {
                    "mode": "bus",
                    "route_id": "CTA_1027",
                    "from_stop_id": "e",
                    "to_stop_id": "f",
                    "departure_time": 3600,
                    "arrival_time": 5200,
                },
            ],
            "total_travel_time": 5200,
            "generalized_cost": 5200,
        }
        route["score"] = score_path(route["legs"], route["total_travel_time"])

        self.assertEqual(
            "non_trunk_route_exceeds_transfer_cap",
            route_quality_rejection_reason(route),
        )

    def test_brt_feeder_without_brt_is_rejected(self):
        route = {
            "legs": [
                {
                    "mode": "walk",
                    "walk_type": "brt_feeder_transfer",
                    "source": "generated_brt_feeder",
                    "departure_time": 0,
                    "arrival_time": 120,
                },
                {
                    "mode": "bus",
                    "route_id": "CTA_1",
                    "from_stop_id": "a",
                    "to_stop_id": "b",
                    "departure_time": 180,
                    "arrival_time": 900,
                },
            ],
            "total_travel_time": 900,
            "generalized_cost": 900,
        }
        route["score"] = score_path(route["legs"], route["total_travel_time"])

        self.assertEqual(
            "used_brt_feeder_transfer_without_boarding_brt",
            route_quality_rejection_reason(route),
        )


if __name__ == "__main__":
    unittest.main()
