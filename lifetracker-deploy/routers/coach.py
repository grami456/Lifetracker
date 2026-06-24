from fastapi import APIRouter
from database import get_db
from datetime import date, timedelta

router = APIRouter()

@router.get("/insights")
def get_coach_insights():
    today = date.today()
    insights = []
    
    conn = get_db()
    profile = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
    profile = dict(profile) if profile else {}
    
    goal = profile.get("goal", "maintain")
    target_cal = profile.get("daily_calorie_target", 2000)
    
    # === ANÁLISIS DE HÁBITOS ===
    
    # Hábitos incumplidos últimos 3 días
    for i in range(1, 4):
        d = str(today - timedelta(days=i))
        habits = conn.execute("SELECT COUNT(*) as n FROM habits WHERE active=1").fetchone()["n"]
        if habits == 0:
            break
        done = conn.execute("""
            SELECT COUNT(*) as n FROM habit_logs hl
            JOIN habits h ON h.id=hl.habit_id
            WHERE hl.date=? AND hl.completed=1 AND h.active=1
        """, (d,)).fetchone()["n"]
        
        pct = (done / habits * 100) if habits > 0 else 0
        if pct < 50:
            consecutive_bad = i
            break
    else:
        consecutive_bad = 0
    
    if consecutive_bad >= 2:
        insights.append({
            "type": "warning",
            "icon": "⚠️",
            "title": "Hábitos en riesgo",
            "message": f"Llevas {consecutive_bad} días con menos del 50% de hábitos completados. ¿Todo bien?"
        })
    
    # Streak check
    streak = 0
    check = today
    while True:
        d = str(check)
        habits = conn.execute("SELECT COUNT(*) as n FROM habits WHERE active=1").fetchone()["n"]
        if habits == 0:
            break
        done = conn.execute("""
            SELECT COUNT(*) as n FROM habit_logs hl
            JOIN habits h ON h.id=hl.habit_id
            WHERE hl.date=? AND hl.completed=1 AND h.active=1
        """, (d,)).fetchone()["n"]
        
        if done > 0:
            streak += 1
            check -= timedelta(days=1)
        else:
            break
        if streak > 365:
            break
    
    if streak >= 7:
        insights.append({
            "type": "success",
            "icon": "🔥",
            "title": f"¡{streak} días de racha!",
            "message": "Excelente consistencia. Mantén el ritmo, estás construyendo hábitos reales."
        })
    
    # === ANÁLISIS CALÓRICO ===
    
    cal_data = []
    for i in range(7):
        d = str(today - timedelta(days=i))
        consumed = conn.execute(
            "SELECT COALESCE(SUM(calories), 0) as cal FROM nutrition_logs WHERE date=?", (d,)
        ).fetchone()["cal"]
        burned = conn.execute(
            "SELECT COALESCE(SUM(calories_burned), 0) as cal FROM activity_logs WHERE date=?", (d,)
        ).fetchone()["cal"]
        cal_data.append({"date": d, "consumed": consumed, "burned": burned, "net": consumed - burned})
    
    # Déficit constante
    days_with_food = [d for d in cal_data if d["consumed"] > 0]
    if days_with_food:
        avg_net = sum(d["net"] for d in days_with_food) / len(days_with_food)
        
        if goal == "gain" and avg_net < target_cal:
            shortage = round(target_cal - avg_net)
            insights.append({
                "type": "warning",
                "icon": "🍽️",
                "title": "Calorías bajas para tu objetivo",
                "message": f"Para subir peso necesitas ~{shortage} kcal más por día. Tu promedio está por debajo de tu meta."
            })
        elif goal == "lose" and avg_net > target_cal:
            excess = round(avg_net - target_cal)
            insights.append({
                "type": "info",
                "icon": "📊",
                "title": "Superávit calórico",
                "message": f"Tu promedio supera tu meta en ~{excess} kcal. Reduce un poco para avanzar más rápido."
            })
        elif goal == "maintain" and abs(avg_net - target_cal) < 150:
            insights.append({
                "type": "success",
                "icon": "✅",
                "title": "Balance calórico óptimo",
                "message": "Estás muy cerca de tu objetivo calórico diario. ¡Buen control!"
            })
    
    # === ANÁLISIS DE ACTIVIDAD ===
    
    week_activity = conn.execute("""
        SELECT COALESCE(SUM(duration_minutes), 0) as total_min,
               COALESCE(SUM(calories_burned), 0) as total_cal,
               COUNT(DISTINCT date) as active_days
        FROM activity_logs WHERE date >= ?
    """, (str(today - timedelta(days=6)),)).fetchone()
    
    active_days = week_activity["active_days"]
    total_min = week_activity["total_min"]
    
    if active_days == 0:
        insights.append({
            "type": "warning",
            "icon": "🏃",
            "title": "Sin actividad esta semana",
            "message": "No has registrado ejercicio en los últimos 7 días. Cualquier movimiento cuenta."
        })
    elif active_days >= 4:
        insights.append({
            "type": "success",
            "icon": "💪",
            "title": f"{active_days} días activo esta semana",
            "message": f"Con {total_min} minutos de ejercicio total. ¡Muy bien!"
        })
    elif active_days <= 2:
        insights.append({
            "type": "info",
            "icon": "🏃",
            "title": "Actividad baja",
            "message": f"Solo {active_days} días con ejercicio esta semana. Intenta agregar una sesión más."
        })
    
    # === ANÁLISIS DE PESO ===
    
    weight_history = conn.execute("""
        SELECT date, weight FROM weight_logs ORDER BY date DESC LIMIT 7
    """).fetchall()
    
    if len(weight_history) >= 2:
        current_w = weight_history[0]["weight"]
        prev_w = weight_history[-1]["weight"]
        change = round(current_w - prev_w, 1)
        target_w = profile.get("weight")
        
        if goal == "gain" and change > 0:
            insights.append({
                "type": "success",
                "icon": "📈",
                "title": f"+{change} kg registrado",
                "message": "Progresando hacia tu objetivo de ganar peso. Mantén el superávit calórico."
            })
        elif goal == "lose" and change < 0:
            insights.append({
                "type": "success",
                "icon": "📉",
                "title": f"{change} kg registrado",
                "message": "Bajando de peso correctamente. Asegúrate de mantener la proteína alta."
            })
    
    # === RECOMENDACIÓN POR OBJETIVO ===
    
    goal_tips = {
        "gain": {
            "icon": "💡",
            "title": "Consejo para ganar masa",
            "message": "Prioriza proteína (1.8-2.2g/kg), entrena con pesas 3-4 veces por semana, y mantén superávit calórico moderado (+200-500 kcal)."
        },
        "lose": {
            "icon": "💡",
            "title": "Consejo para bajar grasa",
            "message": "Mantén déficit moderado (-300-500 kcal), alta proteína para preservar músculo, y cardio moderado 3-4 días."
        },
        "maintain": {
            "icon": "💡",
            "title": "Consejo para mantenimiento",
            "message": "Enfócate en consistencia: hábitos estables, alimentación equilibrada y ejercicio regular 3-5 días/semana."
        }
    }
    
    if goal in goal_tips:
        insights.append({
            "type": "tip",
            **goal_tips[goal]
        })
    
    conn.close()
    
    if not insights:
        insights.append({
            "type": "info",
            "icon": "📱",
            "title": "Empieza a registrar",
            "message": "Registra tus hábitos, comidas y actividades para recibir análisis personalizados."
        })
    
    return {"insights": insights, "generated_at": str(today)}
