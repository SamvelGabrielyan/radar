import json
from datetime import datetime

from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import Session

from config import settings
from tasks.parser import fetch_mentions

app = Celery("radar", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Автозапуск парсинга каждые 30 минут
    beat_schedule={
        "parse-all-companies": {
            "task": "celery_app.parse_all_companies",
            "schedule": crontab(minute="*/30"),
        },
    },
)


# ─── Задача: парсинг одной компании ─────────────────────────────────────────

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def parse_company_mentions(self, company_id: int, company_name: str, keywords_json: str):
    """Парсит упоминания для одной компании и сохраняет в БД."""
    try:
        from db import sync_engine
        from models.mention import Mention, Company
        from sqlalchemy import select, text

        keywords = keywords_json if isinstance(keywords_json, list) else json.loads(keywords_json)
        print(f"[Celery] Парсинг: {company_name} | keywords: {keywords}")

        mentions_data = fetch_mentions(keywords)

        # Сохраняем в БД через sync session
        with Session(sync_engine) as session:
            # Получаем существующие URL чтобы не дублировать
            existing_urls = set(
                row[0]
                for row in session.execute(
                    text("SELECT url FROM mentions WHERE company_id = :cid"),
                    {"cid": company_id},
                ).fetchall()
            )

            new_count = 0
            for m in mentions_data:
                if m["url"] not in existing_urls:
                    mention = Mention(
                        company_id=company_id,
                        title=m["title"],
                        url=m["url"],
                        source=m["source"],
                        snippet=m.get("snippet"),
                        sentiment=m["sentiment"],
                        sentiment_score=m["sentiment_score"],
                        published_at=m.get("published_at"),
                        fetched_at=datetime.utcnow(),
                    )
                    session.add(mention)
                    new_count += 1

            session.commit()
            print(f"[Celery] Сохранено {new_count} новых упоминаний для {company_name}")

        return {"company_id": company_id, "new_mentions": new_count}

    except Exception as exc:
        print(f"[Celery] Ошибка: {exc}")
        raise self.retry(exc=exc)


# ─── Задача: парсинг всех активных компаний ─────────────────────────────────

@app.task
def parse_all_companies():
    """Запускает парсинг для всех активных компаний."""
    from db import sync_engine
    from models.mention import Company
    from sqlalchemy.orm import Session as SyncSession

    with SyncSession(sync_engine) as session:
        companies = session.query(Company).filter(Company.is_active == True).all()
        print(f"[Celery Beat] Запускаем парсинг для {len(companies)} компаний")
        for company in companies:
            parse_company_mentions.delay(
                company.id,
                company.name,
                company.keywords,
            )


# ─── Задача: поиск по человеку ───────────────────────────────────────────────

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def search_person(self, person_id: int, full_name: str, birth_date: str = None, photo_path: str = None):
    """Ищет информацию о человеке из открытых источников."""
    try:
        from db import sync_engine
        from models.person import Person, PersonResult
        from sqlalchemy.orm import Session
        from tasks.person_parser import search_by_name, reverse_image_search

        print(f"[Celery] Поиск человека: {full_name}")
        all_results = []

        # Поиск по имени
        all_results += search_by_name(full_name, birth_date)

        # Поиск по фото если загружено
        if photo_path:
            all_results += reverse_image_search(photo_path)

        # Сохраняем в БД
        with Session(sync_engine) as session:
            # Удаляем старые результаты
            session.query(PersonResult).filter(
                PersonResult.person_id == person_id
            ).delete()

            for r in all_results:
                result = PersonResult(
                    person_id=person_id,
                    source=r["source"],
                    result_type=r["result_type"],
                    title=r["title"],
                    url=r["url"],
                    snippet=r.get("snippet"),
                    image_url=r.get("image_url"),
                )
                session.add(result)

            session.commit()
            print(f"[Celery] Сохранено {len(all_results)} результатов для {full_name}")

        return {"person_id": person_id, "results_count": len(all_results)}

    except Exception as exc:
        print(f"[Celery] Ошибка поиска: {exc}")
        raise self.retry(exc=exc)
