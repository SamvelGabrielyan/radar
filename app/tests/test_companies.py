import pytest
from datetime import datetime
from httpx import AsyncClient


# ─── Создание компании ────────────────────────────────────────────────────────

async def test_create_company(client: AsyncClient):
    resp = await client.post("/companies", json={
        "name": "Apple",
        "keywords": ["Apple Inc", "iPhone", "Tim Cook"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Apple"
    assert data["keywords"] == ["Apple Inc", "iPhone", "Tim Cook"]
    assert data["id"] == 1
    assert data["is_active"] is True


async def test_create_company_empty_name(client: AsyncClient):
    resp = await client.post("/companies", json={"name": "", "keywords": []})
    assert resp.status_code in (200, 422)


async def test_create_company_no_keywords(client: AsyncClient):
    resp = await client.post("/companies", json={"name": "Tesla", "keywords": []})
    assert resp.status_code == 200
    assert resp.json()["keywords"] == []


# ─── Список компаний ──────────────────────────────────────────────────────────

async def test_list_companies_empty(client: AsyncClient):
    resp = await client.get("/companies")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_companies(client: AsyncClient):
    await client.post("/companies", json={"name": "Apple",  "keywords": ["Apple"]})
    await client.post("/companies", json={"name": "Google", "keywords": ["Google"]})

    resp = await client.get("/companies")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Apple" in names
    assert "Google" in names


async def test_list_companies_order(client: AsyncClient):
    """Компании возвращаются от новых к старым."""
    await client.post("/companies", json={"name": "First",  "keywords": []})
    await client.post("/companies", json={"name": "Second", "keywords": []})

    resp = await client.get("/companies")
    names = [c["name"] for c in resp.json()]
    assert names[0] == "Second"


# ─── Удаление компании ────────────────────────────────────────────────────────

async def test_delete_company(client: AsyncClient):
    create = await client.post("/companies", json={"name": "ToDelete", "keywords": []})
    cid = create.json()["id"]

    resp = await client.delete(f"/companies/{cid}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    list_resp = await client.get("/companies")
    assert all(c["id"] != cid for c in list_resp.json())


async def test_delete_nonexistent_company(client: AsyncClient):
    resp = await client.delete("/companies/9999")
    assert resp.status_code == 404


# ─── Статистика ───────────────────────────────────────────────────────────────

async def test_stats_empty(client: AsyncClient):
    create = await client.post("/companies", json={"name": "Empty Co", "keywords": []})
    cid = create.json()["id"]

    resp = await client.get(f"/companies/{cid}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["positive"] == 0
    assert data["neutral"] == 0
    assert data["negative"] == 0
    assert data["positive_pct"] == 0.0
    assert data["negative_pct"] == 0.0
    assert data["sources"] == {}


async def test_stats_with_mentions(client: AsyncClient, db_session):
    from models.mention import Mention

    create = await client.post("/companies", json={"name": "Stats Co", "keywords": []})
    cid = create.json()["id"]

    for sentiment, count in [("positive", 3), ("neutral", 5), ("negative", 2)]:
        for i in range(count):
            db_session.add(Mention(
                company_id=cid,
                title=f"Test {sentiment} {i}",
                url=f"https://example.com/{sentiment}/{i}",
                source="Test Source",
                sentiment=sentiment,         # строка, не Enum
                sentiment_score=0.5 if sentiment == "positive" else -0.5 if sentiment == "negative" else 0.0,
                fetched_at=datetime.utcnow(),
            ))
    await db_session.commit()

    resp = await client.get(f"/companies/{cid}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["positive"] == 3
    assert data["neutral"] == 5
    assert data["negative"] == 2
    assert data["positive_pct"] == 30.0
    assert data["negative_pct"] == 20.0


# ─── Упоминания ───────────────────────────────────────────────────────────────

async def test_get_mentions_empty(client: AsyncClient):
    create = await client.post("/companies", json={"name": "Co", "keywords": []})
    cid = create.json()["id"]
    resp = await client.get(f"/companies/{cid}/mentions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_mentions_filter_by_sentiment(client: AsyncClient, db_session):
    from models.mention import Mention

    create = await client.post("/companies", json={"name": "Filter Co", "keywords": []})
    cid = create.json()["id"]

    for sent in ["positive", "negative", "neutral"]:
        db_session.add(Mention(
            company_id=cid,
            title=f"{sent} news",
            url=f"https://example.com/{sent}",
            source="RSS",
            sentiment=sent,                  # строка, не Enum
            sentiment_score=0.0,
            fetched_at=datetime.utcnow(),
        ))
    await db_session.commit()

    resp = await client.get(f"/companies/{cid}/mentions?sentiment=negative")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["sentiment"] == "negative"


# ─── Health check ─────────────────────────────────────────────────────────────

async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
