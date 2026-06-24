from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from datetime import date

router = APIRouter()

# ── MODELS ──
class ExerciseItem(BaseModel):
    name: str
    sets: int = 3
    reps: str = "10"       # can be "10", "8-12", "al fallo"
    weight: Optional[str] = None   # "60kg", "corporal", etc.
    rest_seconds: Optional[int] = 90
    notes: Optional[str] = None
    order_index: int = 0

class MuscleGroup(BaseModel):
    name: str              # "Pecho", "Espalda", "Piernas", etc.
    color: str = "#6c63ff"
    exercises: List[ExerciseItem] = []
    order_index: int = 0

class RoutineCreate(BaseModel):
    name: str              # "Push Day", "Full Body Lunes", etc.
    description: Optional[str] = None
    muscle_groups: List[MuscleGroup] = []
    estimated_duration: Optional[int] = 60  # minutes

class RoutineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    muscle_groups: Optional[List[MuscleGroup]] = None
    estimated_duration: Optional[int] = None

# ── ROUTINES CRUD ──
@router.get("/routines")
def list_routines():
    import json
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM gym_routines ORDER BY created_at DESC"
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["muscle_groups"] = json.loads(d.get("muscle_groups_json") or "[]")
        result.append(d)
    conn.close()
    return result

@router.post("/routines")
def create_routine(data: RoutineCreate):
    import json
    conn = get_db()
    c = conn.cursor()
    mg_json = json.dumps([g.dict() for g in data.muscle_groups], ensure_ascii=False)
    total_sets = sum(
        len(g.exercises) * (e.sets if hasattr(e, 'sets') else 0)
        for g in data.muscle_groups
        for e in g.exercises
    )
    total_exercises = sum(len(g.exercises) for g in data.muscle_groups)
    c.execute("""
        INSERT INTO gym_routines (name, description, muscle_groups_json, estimated_duration, total_exercises)
        VALUES (?,?,?,?,?)
    """, (data.name, data.description, mg_json, data.estimated_duration, total_exercises))
    rid = c.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM gym_routines WHERE id=?", (rid,)).fetchone()
    d = dict(row)
    d["muscle_groups"] = json.loads(d.get("muscle_groups_json") or "[]")
    conn.close()
    return d

@router.get("/routines/{routine_id}")
def get_routine(routine_id: int):
    import json
    conn = get_db()
    row = conn.execute("SELECT * FROM gym_routines WHERE id=?", (routine_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Rutina no encontrada")
    d = dict(row)
    d["muscle_groups"] = json.loads(d.get("muscle_groups_json") or "[]")
    return d

@router.put("/routines/{routine_id}")
def update_routine(routine_id: int, data: RoutineUpdate):
    import json
    conn = get_db()
    fields = {}
    if data.name is not None: fields["name"] = data.name
    if data.description is not None: fields["description"] = data.description
    if data.estimated_duration is not None: fields["estimated_duration"] = data.estimated_duration
    if data.muscle_groups is not None:
        fields["muscle_groups_json"] = json.dumps([g.dict() for g in data.muscle_groups], ensure_ascii=False)
        fields["total_exercises"] = sum(len(g.exercises) for g in data.muscle_groups)
    if not fields:
        conn.close()
        return {"message": "Sin cambios"}
    set_clause = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE gym_routines SET {set_clause}, updated_at=datetime('now') WHERE id=?",
                 list(fields.values()) + [routine_id])
    conn.commit()
    row = conn.execute("SELECT * FROM gym_routines WHERE id=?", (routine_id,)).fetchone()
    d = dict(row)
    d["muscle_groups"] = json.loads(d.get("muscle_groups_json") or "[]")
    conn.close()
    return d

@router.delete("/routines/{routine_id}")
def delete_routine(routine_id: int):
    conn = get_db()
    conn.execute("DELETE FROM gym_routines WHERE id=?", (routine_id,))
    conn.commit()
    conn.close()
    return {"message": "Eliminada"}

# ── GYM LOG (completed sessions) ──
class GymSessionLog(BaseModel):
    date: Optional[str] = None
    routine_id: int
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None

@router.post("/sessions")
def log_session(data: GymSessionLog):
    conn = get_db()
    log_date = data.date or str(date.today())
    routine = conn.execute("SELECT * FROM gym_routines WHERE id=?", (data.routine_id,)).fetchone()
    if not routine:
        conn.close()
        raise HTTPException(404, "Rutina no encontrada")
    c = conn.cursor()
    c.execute("""
        INSERT INTO gym_sessions (date, routine_id, routine_name, notes, duration_minutes)
        VALUES (?,?,?,?,?)
    """, (log_date, data.routine_id, routine["name"], data.notes, data.duration_minutes or routine["estimated_duration"]))
    conn.commit()
    conn.close()
    return {"message": "Sesión registrada"}

@router.get("/sessions")
def get_sessions(limit: int = 20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM gym_sessions ORDER BY date DESC, created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
