from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_db
from datetime import date

router = APIRouter()

# MET values (Metabolic Equivalent) aproximados
ACTIVITY_CALORIES = {
    "caminar": 4.0,
    "trotar": 7.0,
    "correr": 10.0,
    "gimnasio": 5.5,
    "pesas": 5.0,
    "ciclismo": 6.5,
    "natación": 7.0,
    "fútbol": 7.5,
    "básquetbol": 6.5,
    "tenis": 6.0,
    "yoga": 3.0,
    "pilates": 3.5,
    "baile": 5.0,
    "escalada": 8.0,
    "remo": 7.0,
    "elíptica": 6.0,
    "saltar cuerda": 10.0,
    "artes marciales": 7.5,
    "crossfit": 9.0,
    "estiramientos": 2.5,
    "default": 5.0
}

def calculate_calories(activity_name: str, duration_minutes: int, weight_kg: float = 75, intensity: str = "moderada") -> float:
    """Calcula calorías gastadas usando MET × peso × tiempo"""
    activity_key = activity_name.lower().strip()
    met = ACTIVITY_CALORIES.get(activity_key, ACTIVITY_CALORIES["default"])
    
    # Ajuste por intensidad
    intensity_mult = {"baja": 0.75, "moderada": 1.0, "alta": 1.3, "máxima": 1.6}
    mult = intensity_mult.get(intensity.lower(), 1.0)
    
    # Fórmula: MET × peso(kg) × tiempo(horas) × intensidad
    calories = met * weight_kg * (duration_minutes / 60) * mult
    return round(calories, 1)

@router.get("/types")
def get_activity_types():
    return [{"name": k, "met": v} for k, v in ACTIVITY_CALORIES.items() if k != "default"]

class ActivityLog(BaseModel):
    activity_name: str
    duration_minutes: int
    intensity: str = "moderada"
    notes: Optional[str] = None
    date: Optional[str] = None

@router.post("/log")
def log_activity(data: ActivityLog):
    conn = get_db()
    log_date = data.date or str(date.today())
    
    profile = conn.execute("SELECT weight FROM profile WHERE id=1").fetchone()
    weight = profile["weight"] if profile else 75
    
    calories = calculate_calories(data.activity_name, data.duration_minutes, weight, data.intensity)
    
    c = conn.cursor()
    c.execute("""INSERT INTO activity_logs (date, activity_name, duration_minutes, intensity, calories_burned, notes)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (log_date, data.activity_name, data.duration_minutes, data.intensity, calories, data.notes))
    log_id = c.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM activity_logs WHERE id=?", (log_id,)).fetchone()
    conn.close()
    return dict(row)

@router.get("/log/{log_date}")
def get_activity_log(log_date: str):
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM activity_logs WHERE date=? ORDER BY created_at
    """, (log_date,)).fetchall()
    
    total_calories = sum(r["calories_burned"] for r in rows)
    total_minutes = sum(r["duration_minutes"] for r in rows)
    
    conn.close()
    return {
        "date": log_date,
        "activities": [dict(r) for r in rows],
        "total_calories_burned": round(total_calories, 1),
        "total_minutes": total_minutes
    }

@router.delete("/log/{log_id}")
def delete_activity_log(log_id: int):
    conn = get_db()
    conn.execute("DELETE FROM activity_logs WHERE id=?", (log_id,))
    conn.commit()
    conn.close()
    return {"message": "Eliminado"}

@router.get("/summary/weekly")
def get_weekly_activity(days: int = 7):
    from datetime import timedelta
    today = date.today()
    start_date = str(today - timedelta(days=days-1))
    
    conn = get_db()
    rows = conn.execute("""
        SELECT date, SUM(calories_burned) as total_calories, SUM(duration_minutes) as total_minutes, COUNT(*) as sessions
        FROM activity_logs WHERE date >= ?
        GROUP BY date ORDER BY date
    """, (start_date,)).fetchall()
    conn.close()
    
    return {
        "days": [dict(r) for r in rows],
        "total_calories": round(sum(r["total_calories"] for r in rows), 1),
        "total_minutes": sum(r["total_minutes"] for r in rows)
    }
