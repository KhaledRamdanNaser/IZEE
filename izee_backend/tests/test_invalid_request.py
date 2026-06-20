import unittest
from fastapi import HTTPException
import main

class InvalidRequestTests(unittest.TestCase):
    def test_invalid_departure_time_raises_422(self):
        request = main.TripPlanRequest(
            origin={"lat": 30.0444, "lon": 31.2357},
            destination={"lat": 30.0610, "lon": 31.3370},
            departure_time="not-a-date",
            max_transfers=2,
            use_walking=True,
        )
        db = next(main.get_db())
        try:
            with self.assertRaises(HTTPException) as context:
                main.trip_plan(
                    request,
                    debug=False,
                    trace=None,
                    street_geometry=False,
                    db=db,
                )
            self.assertEqual(context.exception.status_code, 422)
            self.assertEqual(
                context.exception.detail,
                "Invalid departure_time format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
