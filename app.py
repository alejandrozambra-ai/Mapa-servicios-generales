"""
Servidor del Mapa de Aseo UCN, listo para desplegar en Render (hosting gratis en la nube).

Guarda los datos como archivos JSON en la carpeta "data/".

NOTA SOBRE PERSISTENCIA: en el plan gratuito de Render, el disco no está
garantizado como permanente entre despliegues (si vuelves a subir código nuevo,
podría reiniciarse el almacenamiento). Para un uso liviano/piloto esto funciona
bien. Si más adelante esto se vuelve una herramienta crítica con mucho historial,
conviene migrar a una base de datos (Render ofrece Postgres gratis) -- avísame
cuando llegue ese momento y lo actualizamos.
"""

from flask import Flask, request, jsonify, send_from_directory
import os
import json

app = Flask(__name__, static_folder='.', static_url_path='')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)


def key_to_path(key):
    safe = key.replace(':', '__').replace('/', '_').replace('..', '_')
    return os.path.join(DATA_DIR, safe + '.json')


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/api/storage', methods=['GET'])
def get_storage():
    key = request.args.get('key')
    if not key:
        return jsonify({'error': 'falta parametro key'}), 400
    path = key_to_path(key)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            value = f.read()
        return jsonify({'key': key, 'value': value})
    return jsonify({'error': 'not found'}), 404


@app.route('/api/storage', methods=['POST'])
def set_storage():
    data = request.get_json(force=True, silent=True)
    if not data or 'key' not in data or 'value' not in data:
        return jsonify({'error': 'body invalido'}), 400
    key = data['key']
    value = data['value']
    path = key_to_path(key)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(value if isinstance(value, str) else json.dumps(value))
    return jsonify({'key': key, 'ok': True})


if __name__ == '__main__':
    # Solo se usa si lo corres en tu propio computador (python app.py).
    # En Render, gunicorn levanta la app directamente, esto no se ejecuta.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
