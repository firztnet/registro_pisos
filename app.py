
from flask import Flask, request, redirect, url_for, render_template_string, send_file, flash
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import csv
import io

DB_PATH = "pisos.db"
DATE_FORMAT = "%Y-%m-%d"

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_secreto"

def connect():
    url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(url, sslmode="require", cursor_factory=RealDictCursor)
    return conn

def safe_date(s):
    try:
        dt = datetime.strptime(s, DATE_FORMAT)
        return dt.strftime(DATE_FORMAT)
    except Exception:
        return None

@app.route("/")
def index():
    direccion = request.args.get("direccion", "").strip()
    min_precio = request.args.get("min_precio")
    max_precio = request.args.get("max_precio")
    min_sup = request.args.get("min_superficie")
    max_sup = request.args.get("max_superficie")

    query = "SELECT * FROM pisos"
    conditions = []
    params = []

    if direccion:
        conditions.append("direccion ILIKE %s")
        params.append(f"%{direccion}%")
    if min_precio:
        try:
            conditions.append("precio >= %s")
            params.append(float(min_precio))
        except ValueError:
            pass
    if max_precio:
        try:
            conditions.append("precio <= %s")
            params.append(float(max_precio))
        except ValueError:
            pass
    if min_sup:
        try:
            conditions.append("superficie >= %s")
            params.append(float(min_sup))
        except ValueError:
            pass
    if max_sup:
        try:
            conditions.append("superficie <= %s")
            params.append(float(max_sup))
        except ValueError:
            pass

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY fecha_visita DESC"

    with connect() as conn:
        with conn.cursor() as c:
            c.execute(query, params)
            pisos = c.fetchall()

    with connect() as conn:
        with conn.cursor() as c:
            c.execute("SELECT AVG(superficie) AS avg_s, AVG(precio) AS avg_p FROM pisos")
            stats_row = c.fetchone()
            c.execute("SELECT precio, superficie FROM pisos WHERE superficie>0")
            ratio_rows = c.fetchall()

    avg_s = stats_row["avg_s"] or 0
    avg_p = stats_row["avg_p"] or 0
    ratios = [r["precio"] / r["superficie"] for r in ratio_rows if r["superficie"] > 0]
    avg_ratio = sum(ratios)/len(ratios) if ratios else 0

    return render_template_string("App cargada correctamente. Total pisos: {{pisos|length}}", pisos=pisos, avg_s=avg_s, avg_p=avg_p, avg_ratio=avg_ratio, filtros={})

@app.route("/check")
def check_db():
    try:
        with connect() as conn:
            with conn.cursor() as c:
                c.execute("SELECT COUNT(*) as count FROM pisos;")
                count = c.fetchone()["count"]
        return f"✅ La tabla 'pisos' existe. Total registros: {count}"
    except Exception as e:
        import traceback
        return f"❌ Error:\n{traceback.format_exc()}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
