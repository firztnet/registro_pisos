
from flask import Flask, request, redirect, url_for, render_template_string, flash
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)
app.secret_key = "algo_secreto"
DATE_FORMAT = "%Y-%m-%d"

TEMPLATE_INDEX = """
<!doctype html>
<html>
<head>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <title>Registro de Pisos</title>
</head>
<body class="container mt-4">
  <h1 class="mb-4">Registro de Pisos</h1>
  <form method="get" class="row g-2 mb-4">
    <div class="col-md-2"><input class="form-control" name="direccion" placeholder="Dirección" value="{{ filtros.direccion }}"></div>
    <div class="col-md-2"><input class="form-control" name="min_precio" placeholder="Precio mínimo" value="{{ filtros.min_precio }}"></div>
    <div class="col-md-2"><input class="form-control" name="max_precio" placeholder="Precio máximo" value="{{ filtros.max_precio }}"></div>
    <div class="col-md-2"><input class="form-control" name="min_superficie" placeholder="Superficie mínima" value="{{ filtros.min_superficie }}"></div>
    <div class="col-md-2"><input class="form-control" name="max_superficie" placeholder="Superficie máxima" value="{{ filtros.max_superficie }}"></div>
    <div class="col-md-2"><button type="submit" class="btn btn-primary w-100">Filtrar</button></div>
  </form>
  <div class="mb-3">
    <a href="/add" class="btn btn-success btn-sm">➕ Agregar nuevo piso</a>
    <a href="/check" class="btn btn-info btn-sm text-white">✅ Verificar tabla</a>
    <a href="/" class="btn btn-secondary btn-sm">Limpiar</a>
  </div>
  <p>Total pisos: {{ pisos|length }}</p>
  <p>Promedio superficie: {{ '%.2f'|format(avg_s) }} m²</p>
  <p>Promedio precio: {{ '%.2f'|format(avg_p) }} €</p>
  <p>Precio medio por m²: {{ '%.2f'|format(avg_ratio) }} €/m²</p>
  <div class="table-responsive">
    <table class="table table-striped table-bordered align-middle">
      <thead class="table-light">
        <tr>
          <th>Fecha</th><th>Dirección</th><th>Superficie</th><th>Planta</th><th>Precio</th><th>€/m²</th><th>Enlace</th><th>Obs.</th><th>Acción</th>
        </tr>
      </thead>
      <tbody>
        {% for p in pisos %}
        <tr>
          <td>{{ p.fecha_visita }}</td>
          <td>{{ p.direccion }}</td>
          <td>{{ p.superficie }}</td>
          <td>{{ p.planta }}</td>
          <td>{{ p.precio }}</td>
          <td>{{ (p.precio / p.superficie)|round(2) if p.superficie > 0 else '' }}</td>
          <td>  
            {% if p.enlace %}
              <a href="{{ p.enlace }}" target="_blank">Enlace</a>
            {% else %}—{% endif %}
          </td>
          <td>{{ p.observaciones }}</td>
          <td class="text-nowrap">
            <a href="/edit/{{ p.id }}" class="btn btn-warning btn-sm">✏️ Editar</a>
            <form method="post" action="/delete/{{ p.id }}" style="display:inline"
                  onsubmit="return confirm('¿Seguro que deseas eliminar este registro?');">
              <button type="submit" class="btn btn-danger btn-sm">🗑️ Eliminar</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</body>
</html>
"""

TEMPLATE_FORM = """
<!doctype html>
<html>
<head>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <title>{{ action }}</title>
</head>
<body class="container mt-4">
  <h1 class="mb-4">{{ action }}</h1>
  <form method="post" class="row g-3">
    <div class="col-md-6"><input type="date" name="fecha" class="form-control" value="{{ piso.fecha_visita if piso else '' }}" required></div>
    <div class="col-md-6"><input name="direccion" placeholder="Dirección" class="form-control" value="{{ piso.direccion if piso else '' }}" required></div>
    <div class="col-md-4"><input name="superficie" placeholder="Superficie en m²" class="form-control" value="{{ piso.superficie if piso else '' }}" required></div>
    <div class="col-md-4"><input name="planta" placeholder="Planta" class="form-control" value="{{ piso.planta if piso else '' }}"></div>
    <div class="col-md-4"><input name="precio" placeholder="Precio" class="form-control" value="{{ piso.precio if piso else '' }}" required></div>
    <div class="col-md-12"><input name="enlace" placeholder="Enlace" class="form-control" value="{{ piso.enlace if piso else '' }}"></div>
    <div class="col-md-12"><textarea name="observaciones" class="form-control" placeholder="Observaciones">{{ piso.observaciones if piso else '' }}</textarea></div>
    <div class="col-md-12"><button type="submit" class="btn btn-primary">Guardar</button></div>
  </form>
  <a href="/" class="btn btn-secondary mt-3">⬅ Volver al inicio</a>
</body>
</html>
"""

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
        try: conditions.append("precio >= %s"); params.append(float(min_precio))
        except: pass
    if max_precio:
        try: conditions.append("precio <= %s"); params.append(float(max_precio))
        except: pass
    if min_sup:
        try: conditions.append("superficie >= %s"); params.append(float(min_sup))
        except: pass
    if max_sup:
        try: conditions.append("superficie <= %s"); params.append(float(max_sup))
        except: pass

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY fecha_visita DESC"

    with connect() as conn:
        with conn.cursor() as c:
            c.execute(query, params)
            pisos = c.fetchall()
            c.execute("SELECT AVG(superficie) AS avg_s, AVG(precio) AS avg_p FROM pisos")
            stats = c.fetchone()
            c.execute("SELECT precio, superficie FROM pisos WHERE superficie>0")
            ratios = c.fetchall()

    avg_s = stats["avg_s"] or 0
    avg_p = stats["avg_p"] or 0
    avg_ratio = sum(r["precio"]/r["superficie"] for r in ratios if r["superficie"] > 0) / len(ratios) if ratios else 0

    return render_template_string(TEMPLATE_INDEX, pisos=pisos, avg_s=avg_s, avg_p=avg_p, avg_ratio=avg_ratio,
        filtros={"direccion": direccion, "min_precio": min_precio or "", "max_precio": max_precio or "", "min_superficie": min_sup or "", "max_superficie": max_sup or ""})

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        return guardar_piso()
    return render_template_string(TEMPLATE_FORM, action="Agregar Piso", piso=None)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    with connect() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM pisos WHERE id = %s", (id,))
            piso = c.fetchone()
    if not piso:
        flash("Piso no encontrado.", "danger")
        return redirect(url_for("index"))
    if request.method == "POST":
        return guardar_piso(id, piso)
    return render_template_string(TEMPLATE_FORM, action="Editar Piso", piso=piso)

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    with connect() as conn:
        with conn.cursor() as c:
            c.execute("SELECT 1 FROM pisos WHERE id = %s", (id,))
            if not c.fetchone():
                flash("Piso no encontrado.", "danger")
                return redirect(url_for("index"))
            c.execute("DELETE FROM pisos WHERE id = %s", (id,))
            conn.commit()
            flash("Piso eliminado correctamente.", "success")
    return redirect(url_for("index"))

def guardar_piso(id=None, piso=None):
    f = safe_date(request.form.get("fecha", "").strip())
    try:
        superficie = float(request.form.get("superficie", "").strip())
        precio = float(request.form.get("precio", "").strip())
    except:
        flash("Superficie y precio deben ser números.", "danger")
        return redirect(url_for("edit", id=id) if id else url_for("add"))
    direccion = request.form.get("direccion", "").strip()
    planta = request.form.get("planta", "").strip()
    enlace = request.form.get("enlace", "").strip()
    observaciones = request.form.get("observaciones", "").strip()

    with connect() as conn:
        with conn.cursor() as c:
            if id:
                c.execute("""UPDATE pisos SET fecha_visita=%s, direccion=%s, superficie=%s, planta=%s,
                             precio=%s, enlace=%s, observaciones=%s WHERE id=%s""",
                          (f, direccion, superficie, planta, precio, enlace, observaciones, id))
                flash("Piso actualizado correctamente.", "success")
            else:
                c.execute("""INSERT INTO pisos (fecha_visita, direccion, superficie, planta, precio, enlace, observaciones)
                             VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                          (f, direccion, superficie, planta, precio, enlace, observaciones))
                flash("Piso agregado correctamente.", "success")
            conn.commit()
    return redirect(url_for("index"))

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

if __name__ == "__main__":
    app.run(debug=True)
