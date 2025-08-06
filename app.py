# archivo: app_pisos.py
from flask import Flask, request, redirect, url_for, render_template_string, send_file, flash
import sqlite3
from datetime import datetime
import csv
import io
import os

DB_PATH = "pisos.db"
DATE_FORMAT = "%Y-%m-%d"

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_secreto"  # para mensajes flash

# --- DB helpers ---
import psycopg2
from psycopg2.extras import RealDictCursor
import os

def connect():
    url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(url, sslmode="require", cursor_factory=RealDictCursor)
    return conn

def init_db():
    with connect() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS pisos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_visita TEXT NOT NULL,
                direccion TEXT NOT NULL,
                superficie REAL NOT NULL CHECK(superficie>0),
                planta TEXT,
                precio REAL NOT NULL CHECK(precio>0),
                enlace TEXT,
                observaciones TEXT
            )
        """)
        c.commit()

def safe_date(s):
    try:
        dt = datetime.strptime(s, DATE_FORMAT)
        return dt.strftime(DATE_FORMAT)
    except Exception:
        return None

# --- Routes ---
@app.route("/")
def index():
    # filtros
    direccion = request.args.get("direccion", "").strip()
    min_precio = request.args.get("min_precio")
    max_precio = request.args.get("max_precio")
    min_sup = request.args.get("min_superficie")
    max_sup = request.args.get("max_superficie")

    query = "SELECT * FROM pisos"
    conditions = []
    params = []

    if direccion:
        conditions.append("direccion LIKE %s")
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

    with connect() as c:
        pisos = c.execute(query, params).fetchall()

    # estadísticas
    with connect() as c:
        stats_row = c.execute("SELECT AVG(superficie) AS avg_s, AVG(precio) AS avg_p FROM pisos").fetchone()
        ratio_rows = c.execute("SELECT precio, superficie FROM pisos WHERE superficie>0").fetchall()
    avg_s = stats_row["avg_s"] if stats_row["avg_s"] is not None else 0
    avg_p = stats_row["avg_p"] if stats_row["avg_p"] is not None else 0
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

        # validaciones simples
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

        with connect() as c:
            c.execute("""
                INSERT INTO pisos (fecha_visita, direccion, superficie, planta, precio, enlace, observaciones)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (f, direccion, superficie_f, planta, precio_f, enlace, observaciones))
            c.commit()
        flash("Piso agregado.", "success")
        return redirect(url_for("index"))

    return render_template_string(TEMPLATE_FORM, action="Agregar piso", piso=None, endpoint=url_for("add"))

@app.route("/edit/<int:piso_id>", methods=["GET", "POST"])
def edit(piso_id):
    with connect() as c:
        piso = c.execute("SELECT * FROM pisos WHERE id=%s", (piso_id,)).fetchone()
    if not piso:
        flash("Piso no encontrado.", "warning")
        return redirect(url_for("index"))

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
            return redirect(url_for("edit", piso_id=piso_id))
        try:
            superficie_f = float(superficie)
            if superficie_f <= 0:
                raise ValueError
        except:
            flash("Superficie debe ser un número > 0.", "danger")
            return redirect(url_for("edit", piso_id=piso_id))
        try:
            precio_f = float(precio)
            if precio_f <= 0:
                raise ValueError
        except:
            flash("Precio debe ser un número > 0.", "danger")
            return redirect(url_for("edit", piso_id=piso_id))
        if not direccion:
            flash("Dirección es obligatoria.", "danger")
            return redirect(url_for("edit", piso_id=piso_id))

        with connect() as c:
            c.execute("""
                UPDATE pisos SET fecha_visita=%s, direccion=%s, superficie=%s, planta=%s, precio=%s, enlace=%s, observaciones=%s
                WHERE id=%s
            """, (f, direccion, superficie_f, planta, precio_f, enlace, observaciones, piso_id))
            c.commit()
        flash("Piso actualizado.", "success")
        return redirect(url_for("index"))

    return render_template_string(TEMPLATE_FORM, action="Editar piso", piso=piso, endpoint=url_for("edit", piso_id=piso_id))

@app.route("/delete/<int:piso_id>", methods=["POST"])
def delete(piso_id):
    with connect() as c:
        c.execute("DELETE FROM pisos WHERE id=%s", (piso_id,))
        c.commit()
    flash("Piso eliminado.", "info")
    return redirect(url_for("index"))

@app.route("/export")
def export():
    with connect() as c:
        rows = c.execute("SELECT * FROM pisos ORDER BY fecha_visita DESC").fetchall()
    if not rows:
        flash("No hay datos para exportar.", "warning")
        return redirect(url_for("index"))

    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["id", "fecha_visita", "direccion", "superficie", "planta", "precio", "enlace", "observaciones", "precio_m2"]
    writer.writerow(headers)
    for r in rows:
        sup = r["superficie"]
        pri = r["precio"]
        precio_m2 = pri / sup if sup and sup > 0 else ""
        writer.writerow([
            r["id"], r["fecha_visita"], r["direccion"], f"{sup:.2f}", r["planta"],
            f"{pri:.2f}", r["enlace"], r["observaciones"],
            f"{precio_m2:.2f}" if precio_m2 != "" else ""
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="pisos_export.csv"
    )

# --- Templates ---
TEMPLATE_INDEX = """
<!doctype html>
<title>Registro de Pisos</title>
<style>
 body { font-family: sans-serif; max-width: 1100px; margin: 0 auto; padding: 12px; background:#f5f7fa; }
 table { border-collapse: collapse; width: 100%; margin-bottom:16px; }
 th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; font-size:14px; }
 th { background:#354d7a; color:#fff; position: sticky; top:0; }
 tr:nth-child(odd){ background:#ffffff; }
 tr:nth-child(even){ background:#eef2f7; }
 .small { font-size:12px; color:#555; }
 .badge { padding:4px 8px; border-radius:4px; background:#2d9cdb; color:#fff; font-size:12px; }
 .actions a { margin-right:6px; text-decoration:none; }
 .flash { padding:10px; border-radius:4px; margin-bottom:10px; }
 .success { background:#d4edda; color:#155724; }
 .danger { background:#f8d7da; color:#721c24; }
 .warning { background:#fff3cd; color:#856404; }
 .info { background:#d1ecf1; color:#0c5460; }
 .filter-box { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
 .filter-box input { padding:6px; border-radius:4px; border:1px solid #ccc; }
 .btn { padding:8px 14px; border:none; border-radius:6px; cursor:pointer; font-weight:600; }
 .btn-primary { background:#4f81bd; color:#fff; }
 .btn-secondary { background:#6c757d; color:#fff; }
 .btn-danger { background:#e74c3c; color:#fff; }
 .summary { background:#fff; padding:10px; border-radius:6px; border:1px solid #d0d7e0; margin-bottom:16px; display:flex; gap:24px; }
 .stat { flex:1; }
</style>
<h1>Registro de Pisos</h1>

{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    {% for cat, msg in messages %}
      <div class="flash {{cat}}">{{msg}}</div>
    {% endfor %}
  {% endif %}
{% endwith %}

<div style="margin-bottom:8px;">
  <a href="{{ url_for('add') }}" class="btn btn-primary">+ Agregar piso</a>
  <a href="{{ url_for('export') }}" class="btn btn-secondary">Exportar CSV</a>
</div>

<div class="summary">
  <div class="stat">
    <div><strong>Promedio superficie:</strong></div>
    <div>{{ "%.2f"|format(avg_s) }} m²</div>
  </div>
  <div class="stat">
    <div><strong>Promedio precio:</strong></div>
    <div>{{ "%.2f"|format(avg_p) }} €</div>
  </div>
  <div class="stat">
    <div><strong>Precio medio por m²:</strong></div>
    <div>{{ "%.2f"|format(avg_ratio) }} €/m²</div>
  </div>
</div>

<form method="get" class="filter-box">
  <input name="direccion" placeholder="Dirección contiene" value="{{ filtros.direccion }}">
  <input name="min_precio" placeholder="Precio min" value="{{ filtros.min_precio }}">
  <input name="max_precio" placeholder="Precio max" value="{{ filtros.max_precio }}">
  <input name="min_superficie" placeholder="Superficie min" value="{{ filtros.min_superficie }}">
  <input name="max_superficie" placeholder="Superficie max" value="{{ filtros.max_superficie }}">
  <button class="btn btn-primary" type="submit">Filtrar</button>
  <a href="{{ url_for('index') }}" class="btn btn-secondary" style="text-decoration:none;">Limpiar</a>
</form>

<table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Fecha</th>
      <th>Dirección</th>
      <th>Superficie (m²)</th>
      <th>Planta</th>
      <th>Precio (€)</th>
      <th>Precio/m²</th>
      <th>Enlace</th>
      <th>Observaciones</th>
      <th>Acciones</th>
    </tr>
  </thead>
  <tbody>
    {% for p in pisos %}
      <tr>
        <td>{{ p.id }}</td>
        <td>{{ p.fecha_visita }}</td>
        <td>{{ p.direccion }}</td>
        <td>{{ "%.2f"|format(p.superficie) }}</td>
        <td>{{ p.planta }}</td>
        <td>{{ "%.2f"|format(p.precio) }}</td>
        <td>
          {% if p.superficie and p.superficie>0 %}
            {{ "%.2f"|format(p.precio / p.superficie) }}
          {% else %}
            -
          {% endif %}
        </td>
        <td>
          {% if p.enlace %}
            <a href="{{ p.enlace }}" target="_blank">Ver</a>
          {% endif %}
        </td>
        <td>{{ p.observaciones }}</td>
        <td class="actions">
          <a href="{{ url_for('edit', piso_id=p.id) }}">Editar</a>
          <form style="display:inline" method="post" action="{{ url_for('delete', piso_id=p.id) }}" onsubmit="return confirm('Eliminar piso%s');">
            <button class="btn btn-danger" style="padding:4px 8px; font-size:12px;">Borrar</button>
          </form>
        </td>
      </tr>
    {% endfor %}
    {% if pisos|length == 0 %}
      <tr><td colspan="10" style="text-align:center;">No hay registros.</td></tr>
    {% endif %}
  </tbody>
</table>
<small class="small">Registro local en <code>{{ DB_PATH if false else "pisos.db" }}</code></small>
"""

TEMPLATE_FORM = """
<!doctype html>
<title>{{ action }}</title>
<style>
 body { font-family:sans-serif; max-width:800px; margin:0 auto; padding:12px; background:#f5f7fa; }
 form { background:#fff; padding:16px; border-radius:8px; border:1px solid #d0d7e0; }
 label { display:block; margin-top:8px; font-weight:600; }
 input, textarea { width:100%; padding:8px; margin-top:4px; border:1px solid #bbb; border-radius:4px; font-size:14px; }
 .row { display:flex; gap:16px; flex-wrap:wrap; }
 .half { flex:1; min-width:200px; }
 .btn { margin-top:12px; padding:10px 16px; border:none; border-radius:6px; cursor:pointer; font-weight:600; }
 .btn-primary { background:#4f81bd; color:#fff; }
 .btn-secondary { background:#6c757d; color:#fff; }
 .flash { padding:10px; border-radius:4px; margin-bottom:10px; }
 .success { background:#d4edda; color:#155724; }
 .danger { background:#f8d7da; color:#721c24; }
</style>
<h1>{{ action }}</h1>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    {% for cat, msg in messages %}
      <div class="flash {{cat}}">{{msg}}</div>
    {% endfor %}
  {% endif %}
{% endwith %}
<form method="post" action="{{ endpoint }}">
  <div class="row">
    <div class="half">
      <label>Fecha visita (YYYY-MM-DD)</label>
      <input name="fecha" required value="{{ piso.fecha_visita if piso else '' }}">
    </div>
    <div class="half">
      <label>Dirección</label>
      <input name="direccion" required value="{{ piso.direccion if piso else '' }}">
    </div>
  </div>
  <div class="row">
    <div class="half">
      <label>Superficie (m²)</label>
      <input name="superficie" required value="{{ piso.superficie if piso else '' }}">
    </div>
    <div class="half">
      <label>Planta</label>
      <input name="planta" value="{{ piso.planta if piso else '' }}">
    </div>
  </div>
  <div class="row">
    <div class="half">
      <label>Precio (€)</label>
      <input name="precio" required value="{{ piso.precio if piso else '' }}">
    </div>
    <div class="half">
      <label>Enlace</label>
      <input name="enlace" value="{{ piso.enlace if piso else '' }}">
    </div>
  </div>
  <div>
    <label>Observaciones</label>
    <textarea name="observaciones" rows="3">{{ piso.observaciones if piso else '' }}</textarea>
  </div>
  <div style="margin-top:12px;">
    <button class="btn btn-primary" type="submit">Guardar</button>
    <a href="{{ url_for('index') }}" class="btn btn-secondary" style="text-decoration:none;">Cancelar</a>
  </div>
</form>
"""

# --- inicio ---
if __name__ == "__main__":
    #init_db()
    port = int(os.environ.get("PORT", 5000))
    # levantar en http://localhost:5000
    app.run(host="0.0.0.0", port=port)


@app.route("/check")
def check_db():
    try:
        with connect() as conn:
            with conn.cursor() as c:
                c.execute("SELECT COUNT(*) FROM pisos;")
                count = c.fetchone()[0]
        return f"✅ La tabla 'pisos' existe. Total registros: {count}"
    except Exception as e:
        import traceback
        return f"❌ Error:\n{traceback.format_exc()}"

