from fastapi import APIRouter
from database import get_db
from datetime import date, timedelta

router = APIRouter()

@router.get("/today")
def get_today_dashboard():
    today = str(date.today())
    today_obj = date.today()
    week_start = str(today_obj - timedelta(days=today_obj.weekday()))
    
    conn = get_db()
    
    # Profile
    profile = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
    profile = dict(profile) if profile else {}
    
    # Habits today
    habits = conn.execute("""
        SELECT h.*, hl.value, hl.completed
        FROM habits h
        LEFT JOIN habit_logs hl ON h.id=hl.habit_id AND hl.date=?
        WHERE h.active=1
    """, (today,)).fetchall()
    
    total_habits = len(habits)
    completed_habits = sum(1 for h in habits if h["completed"])
    habit_completion = round((completed_habits / total_habits * 100)) if total_habits > 0 else 0
    
    # Weekly habit completion
    week_logs = conn.execute("""
        SELECT hl.habit_id, hl.completed
        FROM habit_logs hl
        JOIN habits h ON h.id=hl.habit_id
        WHERE hl.date >= ? AND h.active=1
    """, (week_start,)).fetchall()
    
    week_possible = total_habits * 7
    week_completed = sum(1 for l in week_logs if l["completed"])
    week_completion = round((week_completed / week_possible * 100)) if week_possible > 0 else 0
    
    # Nutrition today
    nutrition = conn.execute("""
        SELECT COALESCE(SUM(calories), 0) as total FROM nutrition_logs WHERE date=?
    """, (today,)).fetchone()
    calories_consumed = round(nutrition["total"], 1) if nutrition else 0
    
    # Activity today
    activity = conn.execute("""
        SELECT COALESCE(SUM(calories_burned), 0) as total, 
               COALESCE(SUM(duration_minutes), 0) as minutes
        FROM activity_logs WHERE date=?
    """, (today,)).fetchone()
    calories_burned = round(activity["total"], 1) if activity else 0
    active_minutes = activity["minutes"] if activity else 0
    
    # Calorie balance
    daily_target = profile.get("daily_calorie_target", 2000)
    calorie_adjustment = profile.get("calorie_adjustment", 0)
    effective_target = daily_target + calorie_adjustment
    calorie_balance = calories_consumed - calories_burned
    calorie_vs_target = calorie_balance - effective_target
    
    # Weight progress
    weight_history = conn.execute("""
        SELECT date, weight FROM weight_logs ORDER BY date DESC LIMIT 2
    """).fetchall()
    
    weight_change = None
    if len(weight_history) >= 2:
        weight_change = round(weight_history[0]["weight"] - weight_history[1]["weight"], 1)
    
    # Streak (global habit streak)
    streak = 0
    check_date = today_obj
    while True:
        check_str = str(check_date)
        day_logs = conn.execute("""
            SELECT COUNT(*) as completed FROM habit_logs hl
            JOIN habits h ON h.id=hl.habit_id
            WHERE hl.date=? AND hl.completed=1 AND h.active=1
        """, (check_str,)).fetchone()
        
        if day_logs["completed"] > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
        
        if streak > 365:
            break
    
    # Notes today
    note = conn.execute("SELECT * FROM daily_notes WHERE date=?", (today,)).fetchone()
    
    conn.close()
    
    return {
        "date": today,
        "profile": profile,
        "habits": {
            "total": total_habits,
            "completed": completed_habits,
            "daily_pct": habit_completion,
            "weekly_pct": week_completion,
            "streak": streak
        },
        "nutrition": {
            "calories_consumed": calories_consumed,
            "daily_target": effective_target,
            "remaining": round(effective_target - calories_consumed, 1)
        },
        "activity": {
            "calories_burned": calories_burned,
            "active_minutes": active_minutes
        },
        "calorie_balance": {
            "net": round(calorie_balance, 1),
            "vs_target": round(calorie_vs_target, 1),
            "status": "superávit" if calorie_vs_target > 0 else "déficit" if calorie_vs_target < 0 else "en meta"
        },
        "weight": {
            "current": profile.get("weight"),
            "change": weight_change
        },
        "notes": dict(note) if note else None
    }

@router.get("/weekly")
def get_weekly_dashboard():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    days = []
    
    conn = get_db()
    profile = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
    target = profile["daily_calorie_target"] if profile else 2000
    
    for i in range(7):
        d = str(week_start + timedelta(days=i))
        
        nutrition = conn.execute(
            "SELECT COALESCE(SUM(calories), 0) as cal FROM nutrition_logs WHERE date=?", (d,)
        ).fetchone()
        
        activity = conn.execute(
            "SELECT COALESCE(SUM(calories_burned), 0) as cal FROM activity_logs WHERE date=?", (d,)
        ).fetchone()
        
        habits_total = conn.execute(
            "SELECT COUNT(*) as n FROM habits WHERE active=1"
        ).fetchone()["n"]
        
        habits_done = conn.execute(
            "SELECT COUNT(*) as n FROM habit_logs hl JOIN habits h ON h.id=hl.habit_id WHERE hl.date=? AND hl.completed=1 AND h.active=1", (d,)
        ).fetchone()["n"]
        
        days.append({
            "date": d,
            "calories_consumed": round(nutrition["cal"], 1),
            "calories_burned": round(activity["cal"], 1),
            "balance": round(nutrition["cal"] - activity["cal"], 1),
            "habits_pct": round((habits_done / habits_total * 100)) if habits_total > 0 else 0
        })
    
    conn.close()
    return {"week_start": str(week_start), "daily_target": target, "days": days}
