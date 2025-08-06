
from flask import Flask, request, redirect, url_for, render_template_string, flash
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_secreto"
DATE_FORMAT = "%Y-%m-%d"

def connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require", cursor_factory=RealDictCursor)

def safe_date(s):
    try:
        return datetime.strptime(s, DATE_FORMAT).strftime(DATE_FORMAT)
    except:
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
        except: pass
    if max_precio:
        try:
            conditions.append("precio <= %s")
            params.append(float(max_precio))
        except: pass
    if min_sup:
        try:
            conditions.append("superficie >= %s")
            params.append(float(min_sup))
        except: pass
    if max_sup:
        try:
            conditions.append("superficie <= %s")
            params.append(float(max_sup))
        except: pass

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

    return render_template_string(TEMPLATE_INDEX, pisos=pisos, avg_s=avg_s, avg_p=avg_p, avg_ratio=avg_ratio,
        filtros={"direccion": direccion, "min_precio": min_precio or "", "max_precio": max_precio or "", "min_superficie": min_sup or "", "max_superficie": max_sup or ""})

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
            flash("Fecha inválida.", "danger")
            return redirect(url_for("add"))
        try:
            superficie_f = float(superficie)
            precio_f = float(precio)
        except:
            flash("Superficie y precio deben ser números.", "danger")
            return redirect(url_for("add"))

        with connect() as conn:
            with conn.cursor() as c:
                c.execute("INSERT INTO pisos (fecha_visita, direccion, superficie, planta, precio, enlace, observaciones) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (f, direccion, superficie_f, planta, precio_f, enlace, observaciones))
                conn.commit()
        flash("Piso agregado correctamente.", "success")
        return redirect(url_for("index"))
    return render_template_string(TEMPLATE_FORM, action="Agregar Piso", piso=None)

@app.route("/check")
def check_db():
    try:
        with connect() as conn:
            with conn.cursor() as c:
                c.execute("SELECT COUNT(*) as count FROM pisos")
                count = c.fetchone()["count"]
        return f"✅ La tabla 'pisos' existe. Total registros: {count}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

TEMPLATE_INDEX = """<!doctype html>
<html>
<head>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <title>Registro de Pisos</title>
  <style>
    body { font-family: Arial; padding: 20px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
    th { background: #eee; }
    .form-filtro input { margin: 4px; }
    .acciones { margin-top: 20px; }
    .acciones a { margin-right: 10px; }
  </style>
</head>
<body>
  <h1>Registro de Pisos</h1>
  <form method="get" class="form-filtro">
    <input name="direccion" placeholder="Dirección" value="{{ filtros.direccion }}">
    <input name="min_precio" placeholder="Precio mínimo" value="{{ filtros.min_precio }}">
    <input name="max_precio" placeholder="Precio máximo" value="{{ filtros.max_precio }}">
    <input name="min_superficie" placeholder="Superficie mínima" value="{{ filtros.min_superficie }}">
    <input name="max_superficie" placeholder="Superficie máxima" value="{{ filtros.max_superficie }}">
    <button type="submit">Filtrar</button>
    <a href="/">Limpiar</a>
  </form>

  <div class="acciones">
    <a href="/add">➕ Agregar nuevo piso</a>
    <a href="/check">✅ Verificar tabla</a>
  </div>

  <p>Total pisos: {{ pisos|length }}</p>
  <p>Promedio superficie: {{ '%.2f'|format(avg_s) }} m²</p>
  <p>Promedio precio: {{ '%.2f'|format(avg_p) }} €</p>
  <p>Precio medio por m²: {{ '%.2f'|format(avg_ratio) }} €/m²</p>

  <table>
    <tr>
      <th>Fecha</th><th>Dirección</th><th>Superficie</th><th>Planta</th><th>Precio</th><th>€/m²</th><th>Enlace</th><th>Obs.</th>
    </tr>
    {% for p in pisos %}
    <tr>
      <td>{{ p.fecha_visita }}</td>
      <td>{{ p.direccion }}</td>
      <td>{{ p.superficie }}</td>
      <td>{{ p.planta }}</td>
      <td>{{ p.precio }}</td>
      <td>{{ (p.precio / p.superficie)|round(2) if p.superficie > 0 else '' }}</td>
      <td><a href="{{ p.enlace }}" target="_blank">Enlace</a></td>
      <td>{{ p.observaciones }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>"""

TEMPLATE_FORM = """<!doctype html>
<html>
<head>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <title>{{ action }}</title>
  <style>
    body { font-family: Arial; padding: 20px; }
    form input, form textarea { display: block; width: 100%; margin-bottom: 10px; padding: 8px; }
    button { padding: 8px 16px; }
  </style>
</head>
<body>
  <h1>{{ action }}</h1>
  <form method="post">
    <input type="date" name="fecha" value="{{ piso.fecha_visita if piso else '' }}" required>
    <input name="direccion" placeholder="Dirección" value="{{ piso.direccion if piso else '' }}" required>
    <input name="superficie" placeholder="Superficie en m²" value="{{ piso.superficie if piso else '' }}" required>
    <input name="planta" placeholder="Planta" value="{{ piso.planta if piso else '' }}">
    <input name="precio" placeholder="Precio" value="{{ piso.precio if piso else '' }}" required>
    <input name="enlace" placeholder="Enlace" value="{{ piso.enlace if piso else '' }}">
    <textarea name="observaciones" placeholder="Observaciones">{{ piso.observaciones if piso else '' }}</textarea>
    <button type="submit">Guardar</button>
  </form>
  <p><a href="/">⬅ Volver al inicio</a></p>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
