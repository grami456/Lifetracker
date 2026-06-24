from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_db
from datetime import date, timedelta

router = APIRouter()

# MET values for calorie estimation
ACTIVITY_MET = {
    "fútbol": 7.5, "padel": 6.5, "tenis": 7.0, "básquetbol": 6.5,
    "volleyball": 4.0, "natación": 7.0, "ciclismo": 6.5,
    "pesas": 5.0, "gimnasio": 5.5, "crossfit": 9.0,
    "caminar": 3.5, "trotar": 7.0, "correr": 10.0,
    "yoga": 3.0, "pilates": 3.5, "default": 5.0
}

def estimate_calories(activity_name: str, duration_min: int, weight_kg: float = 70) -> float:
    key = activity_name.lower().strip()
    met = ACTIVITY_MET.get(key, ACTIVITY_MET["default"])
    return round(met * weight_kg * (duration_min / 60), 0)

class CalendarEvent(BaseModel):
    date: str
    title: str
    type: str = "activity"          # activity | class | other
    activity_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    color: Optional[str] = "#6c63ff"
    notes: Optional[str] = None
    recurring: Optional[str] = "none"   # none | weekly
    recurring_days: Optional[str] = ""  # "0,1,2,3,4" (Mon-Fri)

@router.get("/events")
def get_events(start: str, end: str):
    conn = get_db()
    profile = conn.execute("SELECT weight FROM profile WHERE id=1").fetchone()
    weight = profile["weight"] if profile else 70

    # Direct events in range
    rows = conn.execute("""
        SELECT * FROM calendar_events WHERE date BETWEEN ? AND ? ORDER BY date, time_start
    """, (start, end)).fetchall()
    events = [dict(r) for r in rows]

    # Expand recurring events
    recurring = conn.execute("""
        SELECT * FROM calendar_events WHERE recurring='weekly' AND date <= ?
    """, (end,)).fetchall()

    start_d = date.fromisoformat(start)
    end_d   = date.fromisoformat(end)

    for rec in recurring:
        rec = dict(rec)
        days = [int(x) for x in rec["recurring_days"].split(",") if x.strip()]
        cur = start_d
        while cur <= end_d:
            if cur.weekday() in days:
                ds = str(cur)
                # check not already in events
                if not any(e["id"] == rec["id"] and e["date"] == ds for e in events):
                    # check not manually completed/modified for this date
                    override = conn.execute(
                        "SELECT * FROM calendar_events WHERE recurring='override' AND notes LIKE ? AND date=?",
                        (f'%ref:{rec["id"]}%', ds)
                    ).fetchone()
                    if not override:
                        copy = dict(rec)
                        copy["date"] = ds
                        copy["_recurring_source"] = rec["id"]
                        events.append(copy)
            cur += timedelta(days=1)

    # Attach estimated calories for activity events
    for ev in events:
        if ev["type"] == "activity" and ev.get("activity_name") and ev.get("duration_minutes"):
            ev["estimated_calories"] = estimate_calories(ev["activity_name"], ev["duration_minutes"], weight)
        else:
            ev["estimated_calories"] = 0

    events.sort(key=lambda e: (e["date"], e.get("time_start") or ""))
    conn.close()
    return events

@router.post("/events")
def create_event(data: CalendarEvent):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO calendar_events
                 (date, title, type, activity_name, duration_minutes, time_start, time_end,
                  color, notes, recurring, recurring_days)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
              (data.date, data.title, data.type, data.activity_name,
               data.duration_minutes, data.time_start, data.time_end,
               data.color or "#6c63ff", data.notes,
               data.recurring or "none", data.recurring_days or ""))
    event_id = c.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM calendar_events WHERE id=?", (event_id,)).fetchone()
    conn.close()
    return dict(row)

@router.patch("/events/{event_id}/complete")
def toggle_complete(event_id: int):
    conn = get_db()
    cur = conn.execute("SELECT completed FROM calendar_events WHERE id=?", (event_id,)).fetchone()
    if not cur:
        conn.close()
        return {"error": "Not found"}
    new = 0 if cur["completed"] else 1
    conn.execute("UPDATE calendar_events SET completed=? WHERE id=?", (new, event_id))
    conn.commit()
    conn.close()
    return {"completed": bool(new)}

@router.delete("/events/{event_id}")
def delete_event(event_id: int):
    conn = get_db()
    conn.execute("DELETE FROM calendar_events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    return {"message": "Eliminado"}

@router.get("/day-summary/{day_date}")
def day_summary(day_date: str):
    """Calories planned for a day from calendar activities"""
    conn = get_db()
    profile = conn.execute("SELECT weight FROM profile WHERE id=1").fetchone()
    weight = profile["weight"] if profile else 70
    rows = conn.execute("""
        SELECT * FROM calendar_events WHERE date=? AND type='activity' AND duration_minutes IS NOT NULL
    """, (day_date,)).fetchall()
    total = sum(estimate_calories(r["activity_name"] or "default", r["duration_minutes"], weight) for r in rows)
    conn.close()
    return {"date": day_date, "planned_calories": round(total)}
