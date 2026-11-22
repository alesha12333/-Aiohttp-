import sqlite3
from pathlib import Path

from flask import Flask, abort, g, jsonify, request, url_for
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.config["DATABASE"] = Path(__file__).with_name("ads.sqlite3")
app.json.ensure_ascii = False
FIELDS = ("title", "description", "owner")


def database():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT
                    (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
        """)
    return g.db


@app.teardown_appcontext
def close_database(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.errorhandler(HTTPException)
def http_error(error):
    response = error.get_response()
    response.data = app.json.dumps({"error": error.description})
    response.content_type = "application/json"
    return response


def read_fields(partial=False):
    data = request.get_json()
    if not isinstance(data, dict) or not data:
        abort(400, description="Нужен непустой JSON-объект.")
    if data.keys() - set(FIELDS):
        abort(400, description="Допустимые поля: title, description, owner.")
    if not partial and set(FIELDS) - data.keys():
        abort(400, description="Укажите title, description и owner.")
    for key, value in data.items():
        if not isinstance(value, str) or not value.strip():
            abort(400, description=f"Поле {key} должно содержать текст.")
    return {key: value.strip() for key, value in data.items()}


def find_ad(ad_id):
    row = database().execute("SELECT * FROM ads WHERE id = ?", (ad_id,)).fetchone()
    if row is None:
        abort(404, description="Объявление не найдено.")
    return dict(row)


@app.post("/ads")
def create_ad():
    data = read_fields()
    with database() as db:
        cursor = db.execute(
            "INSERT INTO ads (title, description, owner) VALUES (:title, :description, :owner)",
            data,
        )
        ad = find_ad(cursor.lastrowid)
    return jsonify(ad), 201, {"Location": url_for("get_ad", ad_id=ad["id"])}


@app.get("/ads/<int:ad_id>")
def get_ad(ad_id):
    return jsonify(find_ad(ad_id))


@app.patch("/ads/<int:ad_id>")
def update_ad(ad_id):
    data = read_fields(partial=True)
    assignments = ", ".join(f"{key} = :{key}" for key in FIELDS if key in data)
    with database() as db:
        db.execute(f"UPDATE ads SET {assignments} WHERE id = :id", {**data, "id": ad_id})
        ad = find_ad(ad_id)
    return jsonify(ad)


@app.delete("/ads/<int:ad_id>")
def delete_ad(ad_id):
    with database() as db:
        cursor = db.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        if cursor.rowcount == 0:
            abort(404, description="Объявление не найдено.")
    return "", 204
