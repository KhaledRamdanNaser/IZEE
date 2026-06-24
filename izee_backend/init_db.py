from database.connection import engine, Base

#Import ALL models
import models.agency
import models.route
import models.trip
import models.stop
import models.stop_time
import models.shape
import models.vehicle_live_state
import models.transit_event
import models.transit_observation
import models.trips_workflow
import models.transit_incident
import models.walking_transfer
from sqlalchemy import text

print("Registered tables:", Base.metadata.tables.keys())
print("Dropping existing transit_incidents table to recreate with new column...")
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS transit_incidents CASCADE;"))
    conn.commit()

Base.metadata.create_all(bind=engine)
print("Tables created successfully")