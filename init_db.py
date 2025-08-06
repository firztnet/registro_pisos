
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def connect():
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url, sslmode="require", cursor_factory=RealDictCursor)

def init_db():
    with connect() as conn:
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS pisos (
                    id SERIAL PRIMARY KEY,
                    fecha_visita TEXT NOT NULL,
                    direccion TEXT NOT NULL,
                    superficie REAL NOT NULL CHECK(superficie > 0),
                    planta TEXT,
                    precio REAL NOT NULL CHECK(precio > 0),
                    enlace TEXT,
                    observaciones TEXT
                );
            """)
        conn.commit()
    print("✅ Tabla 'pisos' creada o ya existía.")

if __name__ == "__main__":
    init_db()
