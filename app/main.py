import shutil
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db import create_tables, get_db
from models.mention import Company, Mention, SentimentEnum
from models.person import Person, PersonResult


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    await create_tables()
    yield

app = FastAPI(title="Radar API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    keywords: list[str]


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    keywords: list
    is_active: bool
    created_at: datetime


class MentionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    url: str
    source: str
    snippet: Optional[str]
    sentiment: str
    sentiment_score: float
    published_at: Optional[datetime]
    fetched_at: datetime


class StatsOut(BaseModel):
    total: int
    positive: int
    neutral: int
    negative: int
    positive_pct: float
    negative_pct: float
    sources: dict


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    middle_name: Optional[str]
    birth_date: Optional[date]
    photo_path: Optional[str]
    notes: Optional[str]
    created_at: datetime


class PersonResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    result_type: str
    title: str
    url: str
    snippet: Optional[str]
    image_url: Optional[str]
    fetched_at: datetime


# ─── Helpers: date-фильтры ────────────────────────────────────────────────────
# Вынесены в отдельную функцию, т.к. используются и в mentions, и в stats.
# Используем coalesce(published_at, fetched_at): если у упоминания есть
# дата публикации — фильтруем по ней, иначе по дате сбора.

def _parse_date_filters(date_from: str | None, date_to: str | None) -> list:
    filters = []
    date_col = func.coalesce(Mention.published_at, Mention.fetched_at)

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            filters.append(date_col >= dt_from)
        except ValueError:
            raise HTTPException(400, "Неверный формат date_from. Используйте YYYY-MM-DD")

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59)
            filters.append(date_col <= dt_to)
        except ValueError:
            raise HTTPException(400, "Неверный формат date_to. Используйте YYYY-MM-DD")

    return filters


# ─── Companies CRUD ───────────────────────────────────────────────────────────

@app.post("/companies", response_model=CompanyOut)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db)):
    company = Company(name=data.name, keywords=data.keywords)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@app.get("/companies", response_model=list[CompanyOut])
async def list_companies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).order_by(desc(Company.created_at)))
    return result.scalars().all()


@app.delete("/companies/{company_id}")
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Компания не найдена")
    await db.delete(company)
    await db.commit()
    return {"ok": True}


@app.post("/companies/{company_id}/parse")
async def trigger_parse(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Компания не найдена")
    from celery_app import parse_company_mentions
    task = parse_company_mentions.delay(company.id, company.name, company.keywords)
    return {"task_id": task.id, "status": "queued"}


# ─── Mentions: теперь с date_from, date_to и source ──────────────────────────

@app.get("/companies/{company_id}/mentions", response_model=list[MentionOut])
async def get_mentions(
    company_id: int,
    sentiment: Optional[str] = None,
    source: Optional[str] = Query(None, description="Фильтр по источнику"),
    date_from: Optional[str] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Mention)
        .where(Mention.company_id == company_id)
        .order_by(desc(Mention.fetched_at))
        .limit(limit).offset(offset)
    )

    if sentiment:
        query = query.where(Mention.sentiment == sentiment)
    if source:
        query = query.where(Mention.source == source)

    for f in _parse_date_filters(date_from, date_to):
        query = query.where(f)

    result = await db.execute(query)
    return result.scalars().all()


# ─── Stats: теперь тоже с date range ─────────────────────────────────────────

@app.get("/companies/{company_id}/stats", response_model=StatsOut)
async def get_stats(
    company_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    base_filters = [Mention.company_id == company_id]
    base_filters.extend(_parse_date_filters(date_from, date_to))

    counts = {}
    for sent in ["positive", "neutral", "negative"]:
        r = await db.execute(
            select(func.count(Mention.id)).where(
                and_(*base_filters, Mention.sentiment == sent)
            )
        )
        counts[sent] = r.scalar() or 0

    total = sum(counts.values())

    sources_r = await db.execute(
        select(Mention.source, func.count(Mention.id))
        .where(and_(*base_filters))
        .group_by(Mention.source)
        .order_by(desc(func.count(Mention.id)))
    )
    sources = {row[0]: row[1] for row in sources_r.fetchall()}

    return StatsOut(
        total=total,
        positive=counts["positive"],
        neutral=counts["neutral"],
        negative=counts["negative"],
        positive_pct=round(counts["positive"] / total * 100, 1) if total else 0,
        negative_pct=round(counts["negative"] / total * 100, 1) if total else 0,
        sources=sources,
    )


# ─── Tasks ────────────────────────────────────────────────────────────────────

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    from celery_app import app as celery_app
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


# ─── Persons ──────────────────────────────────────────────────────────────────

@app.post("/persons", response_model=PersonOut)
async def create_person(
    first_name:  str = Form(...),
    last_name:   str = Form(...),
    middle_name: str = Form(""),
    birth_date:  str = Form(""),
    notes:       str = Form(""),
    photo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    photo_path = None
    if photo and photo.filename:
        import os
        os.makedirs("/app/uploads", exist_ok=True)
        filename = f"{datetime.utcnow().timestamp()}_{photo.filename}"
        photo_path = f"/app/uploads/{filename}"
        with open(photo_path, "wb") as f:
            shutil.copyfileobj(photo.file, f)

    bd = None
    if birth_date:
        try:
            bd = date.fromisoformat(birth_date)
        except ValueError:
            pass

    person = Person(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        middle_name=middle_name.strip() or None,
        birth_date=bd,
        photo_path=photo_path,
        notes=notes.strip() or None,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


@app.get("/persons", response_model=list[PersonOut])
async def list_persons(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).order_by(desc(Person.created_at)))
    return result.scalars().all()


@app.delete("/persons/{person_id}")
async def delete_person(person_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(404, "Не найден")
    await db.delete(person)
    await db.commit()
    return {"ok": True}


@app.post("/persons/{person_id}/search")
async def trigger_person_search(person_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(404, "Не найден")

    full_name = " ".join(filter(None, [person.last_name, person.first_name, person.middle_name]))
    birth_date_str = person.birth_date.isoformat() if person.birth_date else None

    from celery_app import search_person
    task = search_person.delay(person.id, full_name, birth_date_str, person.photo_path)
    return {"task_id": task.id, "status": "queued"}


@app.get("/persons/{person_id}/results", response_model=list[PersonResultOut])
async def get_person_results(
    person_id: int,
    result_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(PersonResult)
        .where(PersonResult.person_id == person_id)
        .order_by(desc(PersonResult.fetched_at))
    )
    if result_type:
        query = query.where(PersonResult.result_type == result_type)
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/persons/{person_id}/stats")
async def get_person_stats(person_id: int, db: AsyncSession = Depends(get_db)):
    total_r = await db.execute(
        select(func.count(PersonResult.id)).where(PersonResult.person_id == person_id)
    )
    sources_r = await db.execute(
        select(PersonResult.source, func.count(PersonResult.id))
        .where(PersonResult.person_id == person_id)
        .group_by(PersonResult.source)
        .order_by(desc(func.count(PersonResult.id)))
    )
    types_r = await db.execute(
        select(PersonResult.result_type, func.count(PersonResult.id))
        .where(PersonResult.person_id == person_id)
        .group_by(PersonResult.result_type)
    )
    return {
        "total":   total_r.scalar() or 0,
        "sources": {r[0]: r[1] for r in sources_r.fetchall()},
        "types":   {r[0]: r[1] for r in types_r.fetchall()},
    }


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}
