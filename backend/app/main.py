from fastapi import FastAPI

from app.routers import calendars, events

app = FastAPI(
    title="Smart Scheduling API",
    version="0.1.0",
)

app.include_router(calendars.router)
app.include_router(events.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
