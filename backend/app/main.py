from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import calendars, events
from app.routers import daily_rhythm, schedule

app = FastAPI(
    title="Calia API",
    version="0.1.0",
)

# CORS for local frontend dev. Origins are read from config (env-driven).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calendars.router)
app.include_router(events.router)
app.include_router(schedule.router)
app.include_router(daily_rhythm.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
