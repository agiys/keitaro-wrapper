# Keitaro wrapper

Обёртка над Keitaro Admin API на FastAPI + SQLAlchemy с простым веб-интерфейсом.

- **Создание кампании**: название, гео (`MX,AU,RO`), оффер (поиск с автокомплитом), группа / домен / источник из API.
  Кампания получает два потока: `Flow 1` — все из указанных стран на `https://google.com`, `Flow 2` — на выбранный оффер.
- **Редактор кампании**: добавление и удаление офферов, ручная правка долей, статистика (клики, уники, боты, конверсии) по потокам и офферам, история изменений.
  При добавлении и удалении оффера доли выравниваются до суммы 100% (например, 34/33/33).

## Запуск

Нужен Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

В `.env` укажите `KEITARO_API_KEY` (админка Keitaro → Профиль → API ключи) и при необходимости
`DEFAULT_GROUP_ID`, `DEFAULT_DOMAIN_ID`, `DEFAULT_SOURCE_ID` — они подставятся в форму по умолчанию.

### Миграции

```bash
alembic upgrade head
```

База по умолчанию — SQLite (`keitaro_wrapper.db`), другая задаётся через `DATABASE_URL`.
Новая миграция после изменения моделей: `alembic revision --autogenerate -m "message"`.

### Сервер

```bash
uvicorn app.main:app --reload
```

Интерфейс: http://localhost:8000, документация API: http://localhost:8000/docs.

### Тесты

```bash
pytest
```

Тесты работают на подменённом клиенте Keitaro, доступ к трекеру не нужен.

## Домен и источник

Список доменов и источников приложение берёт из Keitaro (`GET /domains`, `GET /traffic_sources`) и показывает в форме создания.
У тестового аккаунта `fortests@etolegko.com` эти разделы недоступны (в админке они пустые, создание запрещено), поэтому выпадающие списки пустые,
а кампании создаются с группой, но без домена и источника. На аккаунте с доступом списки заполнятся сами;
фиксированные значения можно задать в `.env` через `DEFAULT_DOMAIN_ID` и `DEFAULT_SOURCE_ID`.

## API

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/offers?q=` | поиск офферов по названию или ID |
| GET | `/api/options` | группы, домены, источники и значения по умолчанию |
| POST | `/api/campaigns` | создать кампанию `{name, geo, offer_id, group_id?, domain_id?, source_id?}` |
| GET | `/api/campaigns` | кампании, созданные через приложение |
| GET | `/api/campaigns/{id}` | кампания с потоками, офферами и статистикой |
| POST | `/api/campaigns/{id}/offers` | добавить оффер `{offer_id}` |
| DELETE | `/api/campaigns/{id}/offers/{offer_id}` | удалить оффер (последний удалить нельзя) |
| PUT | `/api/campaigns/{id}/shares` | задать доли `{shares: [{offer_id, share}]}`, сумма должна быть 100 |

## Структура

- `app/keitaro.py` — клиент Keitaro Admin API
- `app/services.py` — логика создания кампании и редактирования офферов
- `app/routers/` — HTTP-эндпоинты
- `app/models.py`, `migrations/` — локальная БД (созданные кампании, история изменений офферов)
- `static/` — веб-интерфейс на чистом HTML/JS
