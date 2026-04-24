from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, requests, datetime, os

app = Flask(__name__)
CORS(app)

DB_FILE = "delivery.db"

# ------------------ DATABASE INIT ------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            temp_min REAL,
            temp_max REAL,
            humidity_min REAL,
            humidity_max REAL,
            vibration_limit REAL,
            rain_allowed INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT,
            alert_type TEXT,
            value REAL,
            timestamp TEXT
        )
    """)

    # Ensure selected_products exists to avoid query errors
    c.execute("""
        CREATE TABLE IF NOT EXISTS selected_products (
            name TEXT UNIQUE
        )
    """)

    conn.commit()
    conn.close()

# ------------------ HELPER FUNCTIONS ------------------

def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    if fetch:
        result = c.fetchall()
        conn.close()
        return result
    conn.close()

def send_pushover(title, message):
    token = "ao8car3ht2xzr9kpo5vavhj42bs81h"
    user = "u9nad52vn2n3hy8sbxu9e4h86t4tzc"
    url = "https://api.pushover.net/1/messages.json"
    data = {"token": token, "user": user, "title": title, "message": message}
    try:
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print("⚠️ Pushover send failed:", e)

# ------------------ ROUTES ------------------

@app.route("/init_products", methods=["POST"])
def init_products():
    """Populate DB with product thresholds"""
    products = request.json.get("products", [])
    for p in products:
        db_query("""
            INSERT OR REPLACE INTO products (name, temp_min, temp_max, humidity_min, humidity_max, vibration_limit, rain_allowed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (p["name"], p["temp_min"], p["temp_max"], p["humidity_min"], p["humidity_max"], p["vibration_limit"], int(p["rain_allowed"])))
    return jsonify({"status": "success"})

@app.route("/get_products", methods=["GET"])
def get_products():
    """Return all products for driver selection"""
    rows = db_query("SELECT name FROM products ORDER BY name", fetch=True)
    return jsonify([r[0] for r in rows])

@app.route("/set_products", methods=["POST"])
def set_products():
    """Save selected products by driver"""
    products = request.json.get("products", [])
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # replace table contents safely
    c.execute("DELETE FROM selected_products")
    for p in products:
        c.execute("INSERT OR IGNORE INTO selected_products (name) VALUES (?)", (p,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "selected": products})

@app.route("/get_thresholds", methods=["GET"])
def get_thresholds():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT p.name, p.temp_min, p.temp_max, p.humidity_min, p.humidity_max, p.vibration_limit, p.rain_allowed
        FROM products p
        JOIN selected_products s ON LOWER(p.name) = LOWER(s.name)
    """)
    data = c.fetchall()
    conn.close()

    products = []
    for row in data:
        products.append({
            "product": row[0],
            "temp_min": row[1],
            "temp_max": row[2],
            "humidity_min": row[3],
            "humidity_max": row[4],
            "vibration_limit": row[5],
            "rain_allowed": bool(row[6])
        })
    return jsonify(products)

@app.route("/alert", methods=["POST"])
def receive_alert():
    """ESP32 sends alert when threshold exceeded"""
    data = request.get_json(force=True)
    product = data.get("product")
    alert_type = data.get("alert_type")
    value = data.get("value")
    timestamp = datetime.datetime.now().isoformat()

    db_query("INSERT INTO alerts (product, alert_type, value, timestamp) VALUES (?, ?, ?, ?)",
             (product, alert_type, value, timestamp))

    # friendly message (include some extra info if present)
    lat = data.get("lat")
    lng = data.get("lng")
    extra = ""
    if lat is not None and lng is not None:
        extra = f" @ ({lat:.6f},{lng:.6f})"
    msg = f"{product}: {alert_type} exceeded ({value}){extra}"
    print("🚨 ALERT RECEIVED ->", msg)
    send_pushover("🚨 Delivery Alert", msg)

    return jsonify({"status": "Alert stored and notification sent"})

@app.route("/alerts", methods=["GET"])
def get_alerts():
    rows = db_query("SELECT product, alert_type, value, timestamp FROM alerts ORDER BY timestamp DESC", fetch=True)
    alerts = [{"product": r[0], "type": r[1], "value": r[2], "time": r[3]} for r in rows]
    return jsonify(alerts)

# ------------------ MAIN ------------------

if __name__ == "__main__":
    init_db()
    print("🚚 Last-Mile Server Running!")
    app.run(host="0.0.0.0", port=5000, debug=True)
