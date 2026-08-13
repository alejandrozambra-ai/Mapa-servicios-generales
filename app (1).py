"""
Servidor del Mapa de Aseo UCN -- Campus Coquimbo, listo para desplegar en Render.

Guarda los datos en una base de datos Postgres gratuita de Supabase (persistente
de verdad, no se borra cuando el servicio "duerme" o se redespliega).

Si la variable de entorno DATABASE_URL no está configurada, usa archivos JSON
locales como respaldo (útil solo para pruebas en tu propio computador -- en
Render SIEMPRE hay que configurar DATABASE_URL, o los datos se seguirán perdiendo).
"""

from flask import Flask, request, jsonify, send_from_directory
import os
import json

app = Flask(__name__, static_folder='.', static_url_path='')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

# ============================================================
#  MODO 1: Postgres (Supabase) -- persistente de verdad
# ============================================================
if DATABASE_URL:
    import psycopg2
    from psycopg2 import pool

    # Supabase a veces entrega la URL con el esquema "postgres://" en vez de
    # "postgresql://" -- psycopg2 necesita el segundo.
    conn_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    db_pool = psycopg2.pool.SimpleConnectionPool(1, 5, conn_url, sslmode='require')

    def init_db():
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS storage_kv (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMPTZ DEFAULT now()
                    );
                """)
            conn.commit()
        finally:
            db_pool.putconn(conn)

    def db_get(key):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM storage_kv WHERE key = %s", (key,))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            db_pool.putconn(conn)

    def db_set(key, value):
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO storage_kv (key, value, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                """, (key, value))
            conn.commit()
        finally:
            db_pool.putconn(conn)

    init_db()
    STORAGE_MODE = 'postgres'

# ============================================================
#  MODO 2: Archivos locales -- solo respaldo para pruebas locales
# ============================================================
else:
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    os.makedirs(DATA_DIR, exist_ok=True)

    def key_to_path(key):
        safe = key.replace(':', '__').replace('/', '_').replace('..', '_')
        return os.path.join(DATA_DIR, safe + '.json')

    def db_get(key):
        path = key_to_path(key)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def db_set(key, value):
        path = key_to_path(key)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(value)

    STORAGE_MODE = 'archivos locales (sin persistencia real en Render -- configura DATABASE_URL)'


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/api/storage', methods=['GET'])
def get_storage():
    key = request.args.get('key')
    if not key:
        return jsonify({'error': 'falta parametro key'}), 400
    value = db_get(key)
    if value is not None:
        return jsonify({'key': key, 'value': value})
    return jsonify({'error': 'not found'}), 404


@app.route('/api/storage', methods=['POST'])
def set_storage():
    data = request.get_json(force=True, silent=True)
    if not data or 'key' not in data or 'value' not in data:
        return jsonify({'error': 'body invalido'}), 400
    key = data['key']
    value = data['value']
    db_set(key, value if isinstance(value, str) else json.dumps(value))
    return jsonify({'key': key, 'ok': True})


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'storage_mode': STORAGE_MODE})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
