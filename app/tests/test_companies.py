import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient


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
    await client.post("/companies", json={"name": "First",  "keywords": []})
    await client.post("/companies", json={"name": "Second", "keywords": []})
    resp = await client.get("/companies")
    names = [c["name"] for c in resp.json()]
    assert names[0] == "Second"


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
                company_id=cid, title=f"Test {sentiment} {i}",
                url=f"https://example.com/{sentiment}/{i}", source="Test Source",
                sentiment=sentiment,
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
            company_id=cid, title=f"{sent} news", url=f"https://example.com/{sent}",
            source="RSS", sentiment=sent, sentiment_score=0.0, fetched_at=datetime.utcnow(),
        ))
    await db_session.commit()
    resp = await client.get(f"/companies/{cid}/mentions?sentiment=negative")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["sentiment"] == "negative"


async def test_get_mentions_filter_by_source(client: AsyncClient, db_session):
    from models.mention import Mention
    create = await client.post("/companies", json={"name": "Source Co", "keywords": []})
    cid = create.json()["id"]
    for i, src in enumerate(["Google News RU", "Bing News", "Google News RU"]):
        db_session.add(Mention(
            company_id=cid, title=f"News {i}", url=f"https://example.com/s/{i}",
            source=src, sentiment="neutral", sentiment_score=0.0, fetched_at=datetime.utcnow(),
        ))
    await db_session.commit()
    resp = await client.get(f"/companies/{cid}/mentions?source=Bing+News")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["source"] == "Bing News"
    resp = await client.get(f"/companies/{cid}/mentions?source=Google+News+RU")
    assert len(resp.json()) == 2


async def test_get_mentions_filter_by_date_range(client: AsyncClient, db_session):
    from models.mention import Mention
    create = await client.post("/companies", json={"name": "Date Co", "keywords": []})
    cid = create.json()["id"]
    now = datetime.utcnow()
    dates = [
        ("Today news",  now),
        ("10 days ago", now - timedelta(days=10)),
        ("40 days ago", now - timedelta(days=40)),
    ]
    for title, pub_date in dates:
        db_session.add(Mention(
            company_id=cid, title=title, url=f"https://example.com/{title.replace(' ','-')}",
            source="Test", sentiment="neutral", sentiment_score=0.0,
            published_at=pub_date, fetched_at=now,
        ))
    await db_session.commit()

    date_from_7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    resp = await client.get(f"/companies/{cid}/mentions?date_from={date_from_7}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Today news"

    date_from_30 = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    resp = await client.get(f"/companies/{cid}/mentions?date_from={date_from_30}")
    assert len(resp.json()) == 2

    date_from_45 = (now - timedelta(days=45)).strftime("%Y-%m-%d")
    date_to_15 = (now - timedelta(days=15)).strftime("%Y-%m-%d")
    resp = await client.get(f"/companies/{cid}/mentions?date_from={date_from_45}&date_to={date_to_15}")
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "40 days ago"


async def test_get_mentions_date_fallback_to_fetched_at(client: AsyncClient, db_session):
    from models.mention import Mention
    create = await client.post("/companies", json={"name": "Fallback Co", "keywords": []})
    cid = create.json()["id"]
    now = datetime.utcnow()
    db_session.add(Mention(
        company_id=cid, title="No pub date", url="https://example.com/nopub",
        source="Test", sentiment="neutral", sentiment_score=0.0,
        published_at=None, fetched_at=now,
    ))
    db_session.add(Mention(
        company_id=cid, title="Old fetch", url="https://example.com/old",
        source="Test", sentiment="neutral", sentiment_score=0.0,
        published_at=None, fetched_at=now - timedelta(days=60),
    ))
    await db_session.commit()
    date_from = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    resp = await client.get(f"/companies/{cid}/mentions?date_from={date_from}")
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "No pub date"


async def test_get_mentions_invalid_date(client: AsyncClient):
    create = await client.post("/companies", json={"name": "Bad", "keywords": []})
    cid = create.json()["id"]
    resp = await client.get(f"/companies/{cid}/mentions?date_from=not-a-date")
    assert resp.status_code == 400


async def test_stats_with_date_range(client: AsyncClient, db_session):
    from models.mention import Mention
    create = await client.post("/companies", json={"name": "DateStats", "keywords": []})
    cid = create.json()["id"]
    now = datetime.utcnow()
    for i in range(2):
        db_session.add(Mention(
            company_id=cid, title=f"Good {i}", url=f"https://example.com/g/{i}",
            source="Test", sentiment="positive", sentiment_score=0.5,
            published_at=now, fetched_at=now,
        ))
    db_session.add(Mention(
        company_id=cid, title="Old bad", url="https://example.com/bad",
        source="Test", sentiment="negative", sentiment_score=-0.5,
        published_at=now - timedelta(days=30), fetched_at=now - timedelta(days=30),
    ))
    await db_session.commit()
    resp = await client.get(f"/companies/{cid}/stats")
    assert resp.json()["total"] == 3
    date_from_7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    resp = await client.get(f"/companies/{cid}/stats?date_from={date_from_7}")
    data = resp.json()
    assert data["total"] == 2
    assert data["positive"] == 2
    assert data["negative"] == 0


async def test_combined_filters(client: AsyncClient, db_session):
    from models.mention import Mention
    create = await client.post("/companies", json={"name": "Multi", "keywords": []})
    cid = create.json()["id"]
    now = datetime.utcnow()
    rows = [
        ("Recent pos Google", "positive", "Google News RU", now),
        ("Recent neg Google", "negative", "Google News RU", now),
        ("Recent pos Bing",   "positive", "Bing News",      now),
        ("Old pos Google",    "positive", "Google News RU", now - timedelta(days=60)),
    ]
    for title, sent, src, pub in rows:
        db_session.add(Mention(
            company_id=cid, title=title, url=f"https://example.com/{title.replace(' ','-')}",
            source=src, sentiment=sent,
            sentiment_score=0.5 if sent == "positive" else -0.5,
            published_at=pub, fetched_at=pub,
        ))
    await db_session.commit()
    date_from = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    resp = await client.get(
        f"/companies/{cid}/mentions?sentiment=positive&source=Google+News+RU&date_from={date_from}"
    )
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Recent pos Google"


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
