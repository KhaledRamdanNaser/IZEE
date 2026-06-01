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
print(Base.metadata.tables)
print("Registered tables:", Base.metadata.tables.keys())
Base.metadata.create_all(bind=engine)

print("Tables created successfully")