
# archivo: app.py
from flask import Flask, request, redirect, url_for, render_template_string, send_file, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import csv
import io
import os

DB_PATH = "pisos.db"
DATE_FORMAT = "%Y-%m-%d"

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_secreto"

def connect():
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url, sslmode="require", cursor_factory=RealDictCursor)

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

    return render_template_string(TEMPLATE_INDEX,
        pisos=pisos,
        avg_s=avg_s,
        avg_p=avg_p,
        avg_ratio=avg_ratio,
        filtros={
            "direccion": direccion,
            "min_precio": min_precio or "",
            "max_precio": max_precio or "",
            "min_superficie": min_sup or "",
            "max_superficie": max_sup or "",
        }
    )

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        fecha = request.form.get("fecha", "").strip()
        direccion = request.form.get("direccion", "").strip()
        superficie = request.form.get("superficie", "").strip()
        planta = request.form.get("planta", "").strip()
        precio = request.form.get("precio", "").strip()
        enlace = request.form.get("enlace", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        f = safe_date(fecha)
        if not f:
            flash("Fecha inválida. Usa YYYY-MM-DD.", "danger")
            return redirect(url_for("add"))
        try:
            superficie_f = float(superficie)
            if superficie_f <= 0:
                raise ValueError
        except:
            flash("Superficie debe ser un número > 0.", "danger")
            return redirect(url_for("add"))
        try:
            precio_f = float(precio)
            if precio_f <= 0:
                raise ValueError
        except:
            flash("Precio debe ser un número > 0.", "danger")
            return redirect(url_for("add"))
        if not direccion:
            flash("Dirección es obligatoria.", "danger")
            return redirect(url_for("add"))

        with connect() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO pisos (fecha_visita, direccion, superficie, planta, precio, enlace, observaciones)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (f, direccion, superficie_f, planta, precio_f, enlace, observaciones))
                conn.commit()
        flash("Piso agregado.", "success")
        return redirect(url_for("index"))

    return render_template_string(TEMPLATE_FORM, action="Agregar piso", piso=None, endpoint=url_for("add"))

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

TEMPLATE_INDEX = """<html><body><h1>Tu HTML original estilizado estaría aquí</h1></body></html>"""
TEMPLATE_FORM = """<html><body><h1>Formulario para agregar pisos (restaurado)</h1></body></html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
