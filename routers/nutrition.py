from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_db
from datetime import date

router = APIRouter()

@router.get("/foods/search")
def search_foods(q: str = "", category: str = ""):
    conn = get_db()
    query = "SELECT * FROM food_items WHERE 1=1"
    params = []
    if q:
        query += " AND name LIKE ?"
        params.append(f"%{q}%")
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY custom DESC, name LIMIT 40"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/foods/categories")
def get_categories():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT category FROM food_items ORDER BY category").fetchall()
    conn.close()
    return [r["category"] for r in rows]

@router.get("/foods/recent")
def get_recent_foods():
    conn = get_db()
    rows = conn.execute("""
        SELECT rf.*, fi.calories_per_100g, fi.protein_per_100g, fi.carbs_per_100g,
               fi.fat_per_100g, fi.default_serving_g, fi.default_serving_label, fi.category
        FROM recent_foods rf
        JOIN food_items fi ON fi.id = rf.food_id
        ORDER BY rf.used_at DESC LIMIT 10
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

class NutritionLog(BaseModel):
    food_id: int
    grams: float
    meal_type: str = "almuerzo"
    date: Optional[str] = None

@router.post("/log")
def log_food(data: NutritionLog):
    conn = get_db()
    log_date = data.date or str(date.today())
    food = conn.execute("SELECT * FROM food_items WHERE id=?", (data.food_id,)).fetchone()
    if not food:
        conn.close()
        return {"error": "Alimento no encontrado"}

    factor = data.grams / 100.0
    calories = round(food["calories_per_100g"] * factor, 1)
    protein  = round((food["protein_per_100g"] or 0) * factor, 1)
    carbs    = round((food["carbs_per_100g"] or 0) * factor, 1)
    fat      = round((food["fat_per_100g"] or 0) * factor, 1)

    c = conn.cursor()
    c.execute("""INSERT INTO nutrition_logs
                 (date, food_name, food_id, grams, calories, protein, carbs, fat, meal_type)
                 VALUES (?,?,?,?,?,?,?,?,?)""",
              (log_date, food["name"], data.food_id, data.grams, calories, protein, carbs, fat, data.meal_type))
    log_id = c.lastrowid

    conn.execute("""INSERT OR REPLACE INTO recent_foods (food_id, food_name, grams, meal_type, used_at)
                    VALUES (?,?,?,?,datetime('now'))""",
                 (data.food_id, food["name"], data.grams, data.meal_type))
    conn.commit()
    row = conn.execute("SELECT * FROM nutrition_logs WHERE id=?", (log_id,)).fetchone()
    conn.close()
    return dict(row)

class CustomFoodLog(BaseModel):
    food_name: str
    calories: float
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    grams: float = 100
    meal_type: str = "almuerzo"
    date: Optional[str] = None
    save_food: bool = False

@router.post("/log/custom")
def log_custom_food(data: CustomFoodLog):
    conn = get_db()
    log_date = data.date or str(date.today())
    food_id = None

    if data.save_food:
        c = conn.cursor()
        c.execute("""INSERT OR IGNORE INTO food_items
                     (name, calories_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g,
                      default_serving_g, default_serving_label, category, custom)
                     VALUES (?,?,?,?,?,?,?,?,1)""",
                  (data.food_name,
                   round(data.calories / data.grams * 100, 1),
                   round(data.protein / data.grams * 100, 1),
                   round(data.carbs / data.grams * 100, 1),
                   round(data.fat / data.grams * 100, 1),
                   data.grams, f"{data.grams}g", "mis alimentos"))
        food_id = c.lastrowid or None

    conn.execute("""INSERT INTO nutrition_logs
                    (date, food_name, food_id, grams, calories, protein, carbs, fat, meal_type)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                 (log_date, data.food_name, food_id, data.grams,
                  data.calories, data.protein, data.carbs, data.fat, data.meal_type))
    conn.commit()
    conn.close()
    return {"message": "Registrado"}

@router.get("/log/{log_date}")
def get_log(log_date: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM nutrition_logs WHERE date=? ORDER BY meal_type, created_at", (log_date,)).fetchall()
    total_cal  = sum(r["calories"] for r in rows)
    total_prot = sum(r["protein"] or 0 for r in rows)
    total_carb = sum(r["carbs"] or 0 for r in rows)
    total_fat  = sum(r["fat"] or 0 for r in rows)
    conn.close()
    return {
        "date": log_date,
        "total_calories": round(total_cal, 1),
        "total_protein":  round(total_prot, 1),
        "total_carbs":    round(total_carb, 1),
        "total_fat":      round(total_fat, 1),
        "items": [dict(r) for r in rows]
    }

@router.delete("/log/{log_id}")
def delete_log(log_id: int):
    conn = get_db()
    conn.execute("DELETE FROM nutrition_logs WHERE id=?", (log_id,))
    conn.commit()
    conn.close()
    return {"message": "Eliminado"}

@router.get("/summary/weekly")
def weekly_summary(days: int = 7):
    from datetime import timedelta
    start = str(date.today() - timedelta(days=days-1))
    conn = get_db()
    profile = conn.execute("SELECT daily_calorie_target FROM profile WHERE id=1").fetchone()
    target = profile["daily_calorie_target"] if profile else 2000
    rows = conn.execute("""
        SELECT date, SUM(calories) as cal FROM nutrition_logs WHERE date>=? GROUP BY date ORDER BY date
    """, (start,)).fetchall()
    conn.close()
    avg = round(sum(r["cal"] for r in rows)/len(rows)) if rows else 0
    return {"daily_target": target, "days": [dict(r) for r in rows], "avg_calories": avg}
