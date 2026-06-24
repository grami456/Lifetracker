from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter()

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    goal: Optional[str] = None
    daily_calorie_target: Optional[int] = None
    calorie_adjustment: Optional[int] = None

@router.get("/")
def get_profile():
    conn = get_db()
    row = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return dict(row)

@router.put("/")
def update_profile(data: ProfileUpdate):
    conn = get_db()
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if not fields:
        conn.close()
        return {"message": "Sin cambios"}
    
    set_clause = ", ".join([f"{k}=?" for k in fields])
    values = list(fields.values()) + [1]
    conn.execute(f"UPDATE profile SET {set_clause}, updated_at=datetime('now') WHERE id=?", values)
    
    # Also log weight if updated
    if "weight" in fields:
        from datetime import date
        conn.execute(
            "INSERT OR REPLACE INTO weight_logs (date, weight) VALUES (?, ?)",
            (str(date.today()), fields["weight"])
        )
    
    conn.commit()
    row = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
    conn.close()
    return dict(row)

@router.get("/weight-history")
def get_weight_history(days: int = 30):
    conn = get_db()
    rows = conn.execute("""
        SELECT date, weight FROM weight_logs
        ORDER BY date DESC LIMIT ?
    """, (days,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
