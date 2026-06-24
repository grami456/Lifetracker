from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from datetime import date, timedelta

router = APIRouter()

class HabitCreate(BaseModel):
    name: str
    category: str
    target_value: float = 1
    unit: str = "veces"
    period: str = "daily"

class HabitLogUpdate(BaseModel):
    value: float
    date: Optional[str] = None

@router.get("/")
def get_habits():
    conn = get_db()
    rows = conn.execute("SELECT * FROM habits WHERE active=1 ORDER BY category, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/")
def create_habit(data: HabitCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO habits (name, category, target_value, unit, period)
                 VALUES (?, ?, ?, ?, ?)""",
              (data.name, data.category, data.target_value, data.unit, data.period))
    habit_id = c.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
    conn.close()
    return dict(row)

@router.delete("/{habit_id}")
def delete_habit(habit_id: int):
    conn = get_db()
    conn.execute("UPDATE habits SET active=0 WHERE id=?", (habit_id,))
    conn.commit()
    conn.close()
    return {"message": "Hábito eliminado"}

@router.post("/{habit_id}/log")
def log_habit(habit_id: int, data: HabitLogUpdate):
    conn = get_db()
    log_date = data.date or str(date.today())
    
    habit = conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
    if not habit:
        conn.close()
        raise HTTPException(status_code=404, detail="Hábito no encontrado")
    
    completed = 1 if data.value >= habit["target_value"] else 0
    
    conn.execute("""INSERT OR REPLACE INTO habit_logs (habit_id, date, value, completed)
                    VALUES (?, ?, ?, ?)""",
                 (habit_id, log_date, data.value, completed))
    conn.commit()
    conn.close()
    return {"message": "Registrado", "completed": bool(completed)}

@router.get("/logs/{log_date}")
def get_habit_logs(log_date: str):
    conn = get_db()
    rows = conn.execute("""
        SELECT h.*, hl.value, hl.completed, hl.date as log_date
        FROM habits h
        LEFT JOIN habit_logs hl ON h.id = hl.habit_id AND hl.date = ?
        WHERE h.active = 1
        ORDER BY h.category, h.name
    """, (log_date,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/completion/weekly")
def get_weekly_completion(start_date: Optional[str] = None):
    if not start_date:
        today = date.today()
        start_date = str(today - timedelta(days=today.weekday()))
    
    end_date = str(date.fromisoformat(start_date) + timedelta(days=6))
    
    conn = get_db()
    habits = conn.execute("SELECT * FROM habits WHERE active=1").fetchall()
    logs = conn.execute("""
        SELECT habit_id, date, value, completed
        FROM habit_logs
        WHERE date BETWEEN ? AND ?
    """, (start_date, end_date)).fetchall()
    conn.close()
    
    if not habits:
        return {"completion_pct": 0, "total_habits": 0, "completed_logs": 0}
    
    completed_count = sum(1 for l in logs if l["completed"])
    total_possible = len(habits) * 7
    pct = round((completed_count / total_possible) * 100) if total_possible > 0 else 0
    
    return {
        "completion_pct": pct,
        "total_habits": len(habits),
        "completed_logs": completed_count,
        "total_possible": total_possible,
        "week_start": start_date,
        "week_end": end_date
    }

@router.get("/streak/{habit_id}")
def get_habit_streak(habit_id: int):
    conn = get_db()
    logs = conn.execute("""
        SELECT date, completed FROM habit_logs
        WHERE habit_id=? AND completed=1
        ORDER BY date DESC
    """, (habit_id,)).fetchall()
    conn.close()
    
    streak = 0
    check_date = date.today()
    
    dates_set = {l["date"] for l in logs}
    
    while str(check_date) in dates_set:
        streak += 1
        check_date -= timedelta(days=1)
    
    return {"habit_id": habit_id, "streak": streak}
