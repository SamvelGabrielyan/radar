import io
import pytest
from httpx import AsyncClient


# ─── Создание человека ────────────────────────────────────────────────────────

async def test_create_person_minimal(client: AsyncClient):
    resp = await client.post("/persons", data={
        "first_name": "Иван",
        "last_name": "Иванов",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["first_name"] == "Иван"
    assert data["last_name"] == "Иванов"
    assert data["id"] == 1
    assert data["middle_name"] is None
    assert data["birth_date"] is None
    assert data["photo_path"] is None


async def test_create_person_full(client: AsyncClient):
    resp = await client.post("/persons", data={
        "first_name": "Пётр",
        "last_name": "Петров",
        "middle_name": "Петрович",
        "birth_date": "1985-03-15",
        "notes": "CEO компании X",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["middle_name"] == "Петрович"
    assert data["birth_date"] == "1985-03-15"
    assert data["notes"] == "CEO компании X"


async def test_create_person_with_photo(client: AsyncClient):
    fake_image = io.BytesIO(b"fake_image_data")
    resp = await client.post(
        "/persons",
        data={"first_name": "Анна", "last_name": "Смирнова"},
        files={"photo": ("photo.jpg", fake_image, "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["photo_path"] is not None
    assert "photo.jpg" in data["photo_path"]


async def test_create_person_missing_required(client: AsyncClient):
    resp = await client.post("/persons", data={"first_name": "Только имя"})
    # last_name обязателен
    assert resp.status_code == 422


# ─── Список людей ─────────────────────────────────────────────────────────────

async def test_list_persons_empty(client: AsyncClient):
    resp = await client.get("/persons")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_persons(client: AsyncClient):
    await client.post("/persons", data={"first_name": "Иван",  "last_name": "Иванов"})
    await client.post("/persons", data={"first_name": "Пётр",  "last_name": "Петров"})

    resp = await client.get("/persons")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ─── Удаление человека ────────────────────────────────────────────────────────

async def test_delete_person(client: AsyncClient):
    create = await client.post("/persons", data={"first_name": "Удалить", "last_name": "Меня"})
    pid = create.json()["id"]

    resp = await client.delete(f"/persons/{pid}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    list_resp = await client.get("/persons")
    assert all(p["id"] != pid for p in list_resp.json())


async def test_delete_nonexistent_person(client: AsyncClient):
    resp = await client.delete("/persons/9999")
    assert resp.status_code == 404


# ─── Результаты поиска ────────────────────────────────────────────────────────

async def test_get_person_results_empty(client: AsyncClient):
    create = await client.post("/persons", data={"first_name": "Тест", "last_name": "Тестов"})
    pid = create.json()["id"]

    resp = await client.get(f"/persons/{pid}/results")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_person_stats_empty(client: AsyncClient):
    create = await client.post("/persons", data={"first_name": "Тест", "last_name": "Тестов"})
    pid = create.json()["id"]

    resp = await client.get(f"/persons/{pid}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["sources"] == {}
    assert data["types"] == {}


async def test_get_person_results_with_data(client: AsyncClient, db_session):
    from models.person import PersonResult
    from datetime import datetime

    create = await client.post("/persons", data={"first_name": "Тест", "last_name": "Данные"})
    pid = create.json()["id"]

    # Добавляем результаты напрямую в БД
    for i, rtype in enumerate(["news", "news", "image"]):
        db_session.add(PersonResult(
            person_id=pid,
            source="Google News" if rtype == "news" else "Yandex Images",
            result_type=rtype,
            title=f"Результат {i}",
            url=f"https://example.com/{i}",
            fetched_at=datetime.utcnow(),
        ))
    await db_session.commit()

    # Все результаты
    resp = await client.get(f"/persons/{pid}/results")
    assert len(resp.json()) == 3

    # Только фото
    resp = await client.get(f"/persons/{pid}/results?result_type=image")
    assert len(resp.json()) == 1
    assert resp.json()[0]["result_type"] == "image"


async def test_person_stats_aggregation(client: AsyncClient, db_session):
    from models.person import PersonResult
    from datetime import datetime

    create = await client.post("/persons", data={"first_name": "Стат", "last_name": "Тест"})
    pid = create.json()["id"]

    rows = [
        ("Google News", "news"),
        ("Google News", "news"),
        ("Bing News",   "news"),
        ("Yandex Images", "image"),
    ]
    for source, rtype in rows:
        db_session.add(PersonResult(
            person_id=pid, source=source, result_type=rtype,
            title="T", url="https://x.com", fetched_at=datetime.utcnow(),
        ))
    await db_session.commit()

    resp = await client.get(f"/persons/{pid}/stats")
    data = resp.json()
    assert data["total"] == 4
    assert data["sources"]["Google News"] == 2
    assert data["sources"]["Bing News"] == 1
    assert data["types"]["news"] == 3
    assert data["types"]["image"] == 1
