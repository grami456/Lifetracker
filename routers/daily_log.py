from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_db
from datetime import date

router = APIRouter()

class DailyNote(BaseModel):
    notes: Optional[str] = None
    mood: Optional[int] = 3
    date: Optional[str] = None

@router.get("/{log_date}")
def get_daily_log(log_date: str):
    conn = get_db()
    note = conn.execute("SELECT * FROM daily_notes WHERE date=?", (log_date,)).fetchone()
    conn.close()
    return dict(note) if note else {"date": log_date, "notes": None, "mood": 3}

@router.post("/")
def save_daily_note(data: DailyNote):
    log_date = data.date or str(date.today())
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO daily_notes (date, notes, mood, updated_at)
        VALUES (?, ?, ?, datetime('now'))
    """, (log_date, data.notes, data.mood))
    conn.commit()
    row = conn.execute("SELECT * FROM daily_notes WHERE date=?", (log_date,)).fetchone()
    conn.close()
    return dict(row)
