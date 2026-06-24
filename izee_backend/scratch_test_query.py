from database.connection import SessionLocal
from models.trips_workflow import OperationalRoute
from models.route import Route
from models.trip import Trip
from models.agency import Agency
from sqlalchemy import exists

db = SessionLocal()
try:
    results = db.query(OperationalRoute, Route.agency_id, Agency.name)\
        .join(Route, Route.route_id == OperationalRoute.route_id)\
        .join(Agency, Agency.agency_id == Route.agency_id)\
        .filter(
            OperationalRoute.is_active == True,
            OperationalRoute.mode == "bus",
            OperationalRoute.route_type == 3
        )\
        .filter(exists().where(Trip.route_id == OperationalRoute.route_id))\
        .all()
    print("SUCCESS: results count =", len(results))
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
