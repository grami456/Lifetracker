from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from database import init_db
from routers import profile, habits, daily_log, nutrition, activity, calendar, coach, dashboard, gym

app = FastAPI(title="LifeTracker", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()

app.include_router(profile.router,   prefix="/api/profile",   tags=["profile"])
app.include_router(habits.router,    prefix="/api/habits",    tags=["habits"])
app.include_router(daily_log.router, prefix="/api/daily-log", tags=["daily-log"])
app.include_router(nutrition.router, prefix="/api/nutrition", tags=["nutrition"])
app.include_router(activity.router,  prefix="/api/activity",  tags=["activity"])
app.include_router(calendar.router,  prefix="/api/calendar",  tags=["calendar"])
app.include_router(coach.router,     prefix="/api/coach",     tags=["coach"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(gym.router,       prefix="/api/gym",       tags=["gym"])

frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "public")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
