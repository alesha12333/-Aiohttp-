import asyncio
from pathlib import Path

import aiosqlite
from aiohttp import web

FIELDS = ("title", "description", "owner")
DATABASE = web.AppKey("database", Path)
DB = web.AppKey("db", aiosqlite.Connection)
DB_LOCK = web.AppKey("db_lock", asyncio.Lock)


@web.middleware
async def http_error(request, handler):
    try:
        return await handler(request)
    except web.HTTPException as error:
        headers = error.headers.copy()
        headers.pop("Content-Type", None)
        return web.json_response(
            {"error": error.text}, status=error.status, headers=headers
        )


async def database_context(app):
    async with aiosqlite.connect(app[DATABASE], isolation_level=None) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT
                    (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
        """)
        app[DB] = db
        app[DB_LOCK] = asyncio.Lock()
        yield


async def read_fields(request, partial=False):
    if request.content_type != "application/json" and not (
        request.content_type.startswith("application/")
        and request.content_type.endswith("+json")
    ):
        raise web.HTTPUnsupportedMediaType(text="Ожидается application/json.")
    try:
        data = await request.json()
    except (ValueError, UnicodeError):
        raise web.HTTPBadRequest(text="Некорректный JSON.")
    if not isinstance(data, dict) or not data:
        raise web.HTTPBadRequest(text="Нужен непустой JSON-объект.")
    if data.keys() - set(FIELDS):
        raise web.HTTPBadRequest(text="Допустимые поля: title, description, owner.")
    if not partial and set(FIELDS) - data.keys():
        raise web.HTTPBadRequest(text="Укажите title, description и owner.")
    for key, value in data.items():
        if not isinstance(value, str) or not value.strip():
            raise web.HTTPBadRequest(text=f"Поле {key} должно содержать текст.")
    return {key: value.strip() for key, value in data.items()}


async def find_ad(db, ad_id):
    async with db.execute("SELECT * FROM ads WHERE id = ?", (ad_id,)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise web.HTTPNotFound(text="Объявление не найдено.")
    return dict(row)


async def create_ad(request):
    data = await read_fields(request)
    db = request.app[DB]
    async with request.app[DB_LOCK]:
        async with db.execute(
            "INSERT INTO ads (title, description, owner) VALUES (:title, :description, :owner)",
            data,
        ) as cursor:
            ad = await find_ad(db, cursor.lastrowid)
    return web.json_response(ad, status=201, headers={"Location": f"/ads/{ad['id']}"})


async def get_ad(request):
    async with request.app[DB_LOCK]:
        ad = await find_ad(request.app[DB], request.match_info["ad_id"])
    return web.json_response(ad)


async def update_ad(request):
    data = await read_fields(request, partial=True)
    assignments = ", ".join(f"{key} = :{key}" for key in FIELDS if key in data)
    db = request.app[DB]
    ad_id = request.match_info["ad_id"]
    async with request.app[DB_LOCK]:
        async with db.execute(
            f"UPDATE ads SET {assignments} WHERE id = :id", {**data, "id": ad_id}
        ):
            pass
        ad = await find_ad(db, ad_id)
    return web.json_response(ad)


async def delete_ad(request):
    async with request.app[DB_LOCK]:
        async with request.app[DB].execute(
            "DELETE FROM ads WHERE id = ?", (request.match_info["ad_id"],)
        ) as cursor:
            if cursor.rowcount == 0:
                raise web.HTTPNotFound(text="Объявление не найдено.")
    return web.Response(status=204)


def init_app(argv=None):
    app = web.Application(middlewares=[http_error])
    app[DATABASE] = Path(__file__).with_name("ads.sqlite3")
    app.cleanup_ctx.append(database_context)
    app.router.add_post("/ads", create_ad)
    app.router.add_get(r"/ads/{ad_id:\d+}", get_ad)
    app.router.add_patch(r"/ads/{ad_id:\d+}", update_ad)
    app.router.add_delete(r"/ads/{ad_id:\d+}", delete_ad)
    return app


if __name__ == "__main__":
    web.run_app(init_app(), host="127.0.0.1", port=8080)
