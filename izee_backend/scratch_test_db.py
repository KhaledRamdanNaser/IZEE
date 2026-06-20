import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.connection import Base
from models.gtfs import Stop, Route

engine = create_engine('sqlite:///c:/Users/omaro/Desktop/semeser 8/izee_backend/izee.db')
Session = sessionmaker(bind=engine)
session = Session()

print("Stops with شبرا الخيمة:")
for s in session.query(Stop).filter(Stop.name.like('%شبرا الخيمة%')).all():
    print(f"  Stop: {s.stop_id} - {s.name}")

print("Routes with شبرا الخيمة:")
for r in session.query(Route).filter(Route.route_name.like('%شبرا الخيمة%')).all():
    print(f"  Route: {r.route_id} - {r.route_name}")

print("\nStops with التحرير:")
for s in session.query(Stop).filter(Stop.name.like('%التحرير%')).all():
    print(f"  Stop: {s.stop_id} - {s.name}")

print("Routes with التحرير:")
for r in session.query(Route).filter(Route.route_name.like('%التحرير%')).all():
    print(f"  Route: {r.route_id} - {r.route_name}")
