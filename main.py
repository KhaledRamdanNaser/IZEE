from fastapi import FastAPI
from api.routes.vehicle import router as vehicle_router

app = FastAPI()

app.include_router(vehicle_router)