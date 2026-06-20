import os
import sys
from fastapi.testclient import TestClient
from main import app
from database.connection import SessionLocal
from models.trips_workflow import DriverAssignment

client = TestClient(app)

db = SessionLocal()
# Find any active assignment
assignment = db.query(DriverAssignment).filter(DriverAssignment.status == 'active').first()
if not assignment:
    print('No active assignment found.')
    sys.exit(1)

vehicle_id = assignment.vehicle_id
print(f'Testing vehicle_id: {vehicle_id}')
resp = client.get(f'/driver/route-info?vehicle_id={vehicle_id}')
print('Status code:', resp.status_code)
print('Response JSON:', resp.json())

db.close()
