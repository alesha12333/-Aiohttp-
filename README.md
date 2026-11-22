# Flask API объявлений о металлопрокате

Для запуска в PowerShell откройте папку проекта и выполните:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m flask --app app run
```

Сервер принимает запросы на http://127.0.0.1:5000. При первом обращении к базе рядом с app.py появится файл ads.sqlite3. Дата создания задаётся сервером в UTC.

| Метод | Путь | Результат |
|---|---|---|
| POST | /ads | Создаёт объявление и возвращает его с кодом 201 |
| GET | /ads/<id> | Возвращает объявление с кодом 200 |
| PATCH | /ads/<id> | Меняет указанные поля и возвращает объявление с кодом 200 |
| DELETE | /ads/<id> | Удаляет объявление и возвращает 204 без тела |

Пример для второго окна PowerShell:

```powershell
$base = 'http://127.0.0.1:5000/ads'
$json = @{title='Лист стальной 09Г2С'; description='Толщина 8 мм, партия 2 т'; owner='МеталлСнаб'} | ConvertTo-Json
$type = 'application/json; charset=utf-8'
$ad = Invoke-RestMethod $base -Method Post -ContentType $type -Body ([Text.Encoding]::UTF8.GetBytes($json))
$url = "$base/$($ad.id)"
Invoke-RestMethod $url
$change = @{description='Остаток 1 т'} | ConvertTo-Json
Invoke-RestMethod $url -Method Patch -ContentType $type -Body ([Text.Encoding]::UTF8.GetBytes($change))
Invoke-RestMethod $url -Method Delete
```

После удаления GET по тому же адресу вернёт 404. При создании обязательны три непустых текстовых поля: title, description, owner. При редактировании достаточно одного из них.
