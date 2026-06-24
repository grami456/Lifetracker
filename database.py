import sqlite3, os, json

# On Railway, use /data for persistence. Locally, use current dir.
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(__file__))
DB_PATH = os.path.join(DATA_DIR, "lifetracker.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY DEFAULT 1,
        name TEXT DEFAULT 'Usuario',
        weight REAL, height REAL,
        goal TEXT DEFAULT 'maintain',
        daily_calorie_target INTEGER DEFAULT 2200,
        calorie_adjustment INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT (datetime('now'))
    );
    INSERT OR IGNORE INTO profile (id,name,weight,height,goal,daily_calorie_target)
    VALUES (1,'Usuario',70.0,175.0,'maintain',2200);

    CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, category TEXT NOT NULL,
        target_value REAL NOT NULL DEFAULT 1,
        unit TEXT DEFAULT 'veces', period TEXT DEFAULT 'daily',
        active INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS habit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER NOT NULL, date TEXT NOT NULL,
        value REAL NOT NULL DEFAULT 0, completed INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (habit_id) REFERENCES habits(id), UNIQUE(habit_id,date)
    );
    CREATE TABLE IF NOT EXISTS food_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        calories_per_100g REAL NOT NULL DEFAULT 0,
        protein_per_100g REAL DEFAULT 0,
        carbs_per_100g REAL DEFAULT 0,
        fat_per_100g REAL DEFAULT 0,
        default_serving_g REAL DEFAULT 100,
        default_serving_label TEXT DEFAULT '100g',
        category TEXT DEFAULT 'general',
        calorie_note TEXT DEFAULT '',
        custom INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS nutrition_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, food_name TEXT NOT NULL,
        food_id INTEGER, grams REAL NOT NULL DEFAULT 100,
        calories REAL NOT NULL DEFAULT 0,
        protein REAL DEFAULT 0, carbs REAL DEFAULT 0, fat REAL DEFAULT 0,
        meal_type TEXT DEFAULT 'almuerzo',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (food_id) REFERENCES food_items(id)
    );
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, activity_name TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL, intensity TEXT DEFAULT 'moderada',
        calories_burned REAL DEFAULT 0, notes TEXT,
        source TEXT DEFAULT 'manual', created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS weight_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, weight REAL NOT NULL,
        created_at TEXT DEFAULT (datetime('now')), UNIQUE(date)
    );
    CREATE TABLE IF NOT EXISTS daily_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE, notes TEXT, mood INTEGER DEFAULT 3,
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS calendar_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, title TEXT NOT NULL,
        type TEXT DEFAULT 'activity',
        activity_name TEXT, duration_minutes INTEGER,
        time_start TEXT, time_end TEXT,
        color TEXT DEFAULT '#6c63ff', notes TEXT,
        completed INTEGER DEFAULT 0,
        recurring TEXT DEFAULT 'none', recurring_days TEXT DEFAULT '',
        routine_id INTEGER DEFAULT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS recent_foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_id INTEGER NOT NULL, food_name TEXT NOT NULL,
        grams REAL NOT NULL, meal_type TEXT,
        used_at TEXT DEFAULT (datetime('now')), UNIQUE(food_id)
    );
    CREATE TABLE IF NOT EXISTS gym_routines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, description TEXT,
        muscle_groups_json TEXT DEFAULT '[]',
        estimated_duration INTEGER DEFAULT 60,
        total_exercises INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS gym_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, routine_id INTEGER,
        routine_name TEXT, notes TEXT, duration_minutes INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)

    foods = [
        ("Arroz blanco cocido",130,2.7,28.2,0.3,150,"plato (150g)","cereales",""),
        ("Arroz integral cocido",122,2.6,25.6,1.0,150,"plato (150g)","cereales",""),
        ("Pasta cocida",158,5.8,31.0,0.9,180,"plato (180g)","cereales",""),
        ("Pan blanco",265,9.0,49.0,3.2,30,"rebanada (30g)","cereales",""),
        ("Pan integral",247,8.0,41.0,3.4,30,"rebanada (30g)","cereales",""),
        ("Avena cruda",389,17.0,66.0,7.0,40,"porción (40g)","cereales",""),
        ("Granola",471,10.0,64.0,20.0,45,"porción (45g)","cereales",""),
        ("Quinoa cocida",120,4.4,21.3,1.9,150,"porción (150g)","cereales",""),
        ("Pechuga de pollo cocida",165,31.0,0.0,3.6,120,"porción (120g)","proteínas",""),
        ("Muslo de pollo cocido",209,26.0,0.0,11.0,100,"100g","proteínas",""),
        ("Carne vacuno magra",218,26.0,0.0,12.0,120,"bistec (120g)","proteínas",""),
        ("Carne molida 80/20",254,26.0,0.0,17.0,100,"100g","proteínas",""),
        ("Salmón cocido",206,20.4,0.0,13.4,120,"filete (120g)","proteínas",""),
        ("Atún en agua",116,25.5,0.0,0.9,100,"lata (100g)","proteínas",""),
        ("Huevo entero",155,13.0,1.1,11.0,60,"unidad L (60g)","proteínas",""),
        ("Claras de huevo",52,10.9,0.7,0.2,33,"clara (33g)","proteínas",""),
        ("Pavo pechuga",135,29.9,0.0,1.0,100,"100g","proteínas",""),
        ("Proteína whey (scoop)",380,75.0,10.0,7.0,30,"scoop (30g)","suplementos",""),
        ("Barra proteica",340,30.0,25.0,8.0,60,"barra (60g)","suplementos",""),
        ("Leche entera",61,3.2,4.8,3.3,250,"vaso (250ml)","lácteos",""),
        ("Leche descremada",35,3.4,5.0,0.1,250,"vaso (250ml)","lácteos",""),
        ("Yogur griego natural",100,9.0,4.0,5.0,170,"pote (170g)","lácteos",""),
        ("Queso cheddar",402,25.0,1.3,33.0,30,"loncha (30g)","lácteos",""),
        ("Queso fresco",264,18.0,3.4,21.0,50,"porción (50g)","lácteos",""),
        ("Requesón/Cottage",98,11.0,3.4,4.3,100,"100g","lácteos",""),
        ("Manzana",52,0.3,13.8,0.2,182,"mediana (182g)","frutas",""),
        ("Banana/Plátano",89,1.1,23.0,0.3,118,"mediana (118g)","frutas",""),
        ("Naranja",47,0.9,11.8,0.1,131,"mediana (131g)","frutas",""),
        ("Palta/Aguacate",160,2.0,9.0,15.0,100,"mitad (100g)","grasas",""),
        ("Almendras",579,21.0,22.0,50.0,30,"puñado (30g)","grasas",""),
        ("Nueces",654,15.2,14.0,65.0,30,"puñado (30g)","grasas",""),
        ("Mantequilla maní",588,25.0,20.0,50.0,32,"2 cuch. (32g)","grasas",""),
        ("Aceite de oliva",884,0.0,0.0,100.0,10,"cucharada (10g)","grasas",""),
        ("Brócoli cocido",34,2.8,7.2,0.4,150,"porción (150g)","verduras",""),
        ("Espinaca cruda",23,2.9,3.6,0.4,100,"100g","verduras",""),
        ("Papa cocida",77,2.0,17.0,0.1,150,"mediana (150g)","verduras",""),
        ("Camote/Batata cocida",86,1.6,20.1,0.1,150,"porción (150g)","verduras",""),
        ("Tomate",18,0.9,3.9,0.2,100,"100g","verduras",""),
        ("Zanahoria",41,0.9,9.6,0.2,100,"100g","verduras",""),
        ("Lentejas cocidas",116,9.0,20.0,0.4,200,"plato (200g)","legumbres",""),
        ("Garbanzos cocidos",164,8.9,27.4,2.6,200,"plato (200g)","legumbres",""),
        ("Porotos negros cocidos",132,8.9,23.7,0.5,200,"plato (200g)","legumbres",""),
        ("Café negro",2,0.3,0.0,0.0,240,"taza (240ml)","bebidas",""),
        ("Jugo naranja natural",45,0.7,10.4,0.2,250,"vaso (250ml)","bebidas",""),
        ("Bebida cola",42,0.0,10.6,0.0,330,"lata (330ml)","bebidas",""),
        ("Leche de avena",48,1.3,6.7,1.4,250,"vaso (250ml)","bebidas",""),
        ("Chocolate negro 70%",598,7.8,46.0,43.0,30,"porción (30g)","snacks",""),
        ("Papas fritas",536,7.0,53.0,35.0,50,"porción (50g)","snacks",""),
        ("Sushi (maki roll)",140,5.5,27.0,1.2,200,"8 piezas (~200g)","platos","~280 kcal/8pzas · varía según relleno"),
        ("Sashimi (10 piezas)",90,18.0,0.5,1.5,170,"10 piezas (~170g)","platos","~150 kcal · solo pescado crudo"),
        ("Ceviche clásico",60,12.0,3.5,0.8,250,"plato (250g)","platos","~150 kcal · puede variar con leche de tigre"),
        ("Pizza margarita",266,11.0,33.0,10.0,107,"porción (~107g)","platos","~285 kcal/porción · varía por grosor"),
        ("Pizza pepperoni",298,12.5,34.0,13.0,107,"porción (~107g)","platos","~320 kcal/porción"),
        ("Hamburguesa completa",265,13.5,23.0,13.0,200,"unidad (~200g)","platos","~530 kcal · con pan, carne, queso"),
        ("Hamburguesa doble",310,18.0,23.0,17.0,260,"unidad (~260g)","platos","~800 kcal aprox"),
        ("Hot dog completo",260,9.5,23.0,15.0,150,"unidad (~150g)","platos","~390 kcal"),
        ("Shawarma/Döner",215,14.0,22.0,8.0,250,"porción (~250g)","platos","~540 kcal con pan pita"),
        ("Taco (carne/pollo)",155,9.0,18.0,5.0,100,"unidad (~100g)","platos","~155 kcal/taco"),
        ("Empanada de pino",290,11.0,30.0,14.0,140,"unidad (~140g)","platos","~405 kcal"),
        ("Empanada de queso",310,10.0,32.0,16.0,130,"unidad (~130g)","platos","~400 kcal aprox"),
        ("Pad thai",180,8.5,26.0,5.5,300,"plato (~300g)","platos","~540 kcal"),
        ("Ramen",105,6.5,14.0,2.5,500,"bowl (~500ml)","platos","~525 kcal con caldo y toppings"),
        ("Pasta boloñesa",162,9.5,22.0,4.5,350,"plato (~350g)","platos","~565 kcal"),
        ("Pasta carbonara",220,10.0,24.0,10.0,300,"plato (~300g)","platos","~660 kcal"),
        ("Ensalada César",130,7.0,6.0,9.0,200,"plato (~200g)","platos","~260 kcal sin pollo"),
        ("Bowl de açaí",160,2.5,28.0,5.5,300,"bowl (~300g)","platos","~480 kcal con granola"),
        ("Burrito/Wrap",205,11.0,24.0,7.5,250,"unidad (~250g)","platos","~510 kcal"),
        ("Lasaña",155,10.0,14.0,6.5,300,"porción (~300g)","platos","~465 kcal"),
        ("Pancakes (3 unid.)",220,6.0,38.0,5.0,150,"3 unidades (~150g)","platos","~330 kcal sin toppings"),
        ("Granola bowl con yogur",185,8.0,28.0,5.0,250,"bowl (~250g)","platos","~465 kcal"),
        ("Salmón teriyaki + arroz",170,15.5,16.0,5.0,350,"plato (~350g)","platos","~595 kcal"),
        ("Stir fry vegetal + pollo",105,12.0,8.0,3.0,350,"plato (~350g)","platos","~370 kcal"),
        ("Caldo de pollo",40,4.5,3.5,1.0,400,"tazón (~400ml)","platos","~160 kcal"),
        ("Milanesa + papas fritas",260,16.0,20.0,13.0,300,"plato (~300g)","platos","~780 kcal"),
        ("Cazuela chilena",105,9.5,10.0,2.5,450,"plato (~450g)","platos","~470 kcal"),
        ("Churrasco italiano",310,20.0,28.0,13.0,220,"sandwich (~220g)","platos","~680 kcal"),
        ("Completo/Italiano",290,10.0,30.0,15.0,200,"unidad (~200g)","platos","~580 kcal"),
        ("Sopaipillas (3 unid.)",350,5.0,43.0,18.0,120,"3 unid. (~120g)","platos","~420 kcal"),
        ("Hummus",170,8.0,14.0,10.0,60,"porción (60g)","platos","~100 kcal"),
        ("Falafel (4 unid.)",333,13.0,32.0,18.0,120,"4 unid. (~120g)","platos","~400 kcal"),
        ("Dumplings/Gyoza (6 unid.)",185,8.5,22.0,6.5,150,"6 unid. (~150g)","platos","~280 kcal"),
        ("Carne asada/BBQ",250,28.0,0.0,15.0,150,"porción (~150g)","platos","~375 kcal solo carne"),
        ("Costillas BBQ",290,25.0,8.0,17.0,200,"porción (~200g)","platos","~580 kcal"),
        ("Pollo asado",215,25.0,0.0,13.0,150,"pierna+muslo","platos","~320 kcal con piel"),
        ("Brownie",410,5.0,57.0,20.0,70,"porción (~70g)","platos","~285 kcal"),
        ("Tiramisú",280,5.5,31.0,15.0,120,"porción (~120g)","platos","~335 kcal"),
        ("Cheesecake",320,5.5,31.0,20.0,120,"porción (~120g)","platos","~385 kcal"),
        ("Helado de vainilla",207,3.5,23.5,11.0,100,"2 bochas (~100g)","platos","~207 kcal"),
        ("Mote con huesillos",80,0.8,20.0,0.1,350,"vaso (~350ml)","platos","~280 kcal"),
        ("Milkshake/Batido",130,3.5,20.0,5.0,400,"vaso grande (~400ml)","platos","~520 kcal"),
        ("Limonada de coco",85,0.5,20.0,1.5,400,"vaso (~400ml)","platos","~340 kcal"),
        ("Arroz con leche",120,3.0,22.0,2.5,200,"porción (~200g)","platos","~240 kcal"),
        ("Curry de pollo",130,12.0,7.0,6.0,350,"plato (~350g)","platos","~455 kcal"),
        ("Paella",165,10.5,23.0,4.0,300,"plato (~300g)","platos","~495 kcal"),
    ]
    for f in foods:
        c.execute("""INSERT OR IGNORE INTO food_items
            (name,calories_per_100g,protein_per_100g,carbs_per_100g,fat_per_100g,
             default_serving_g,default_serving_label,category,calorie_note)
            VALUES (?,?,?,?,?,?,?,?,?)""", f)

    for habit in [("Beber agua","salud",8,"vasos"),("Dormir 8 horas","salud",8,"horas"),("Meditar","hábitos",10,"minutos"),("Leer","productividad",20,"minutos")]:
        c.execute("SELECT id FROM habits WHERE name=?", (habit[0],))
        if not c.fetchone():
            c.execute("INSERT INTO habits (name,category,target_value,unit) VALUES (?,?,?,?)", habit)

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")
