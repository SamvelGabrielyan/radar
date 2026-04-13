# Radar — OSINT & Reputation Monitoring

## Быстрый старт

### 1. Клонируй / распакуй проект

```bash
cd radar
```

### 2. Настрой переменные окружения

```bash
cp .env.example .env
# Отредактируй .env если нужно (можно оставить как есть для теста)
```

### 3. Запусти всё через Docker

```bash
docker-compose up --build
```

Первый запуск займёт 2-3 минуты (скачивает образы, ставит зависимости).

### 4. Проверь что всё работает

```bash
curl http://localhost:8000/health
# → {"status":"ok","timestamp":"..."}
```

---

## API — основные эндпоинты

### Добавить компанию для мониторинга
```bash
curl -X POST http://localhost:8000/companies \
  -H "Content-Type: application/json" \
  -d '{"name": "Apple", "keywords": ["Apple Inc", "Tim Cook", "iPhone"]}'
```

### Запустить парсинг прямо сейчас
```bash
curl -X POST http://localhost:8000/companies/1/parse
# → {"task_id": "...", "status": "queued"}
```

### Проверить статус задачи
```bash
curl http://localhost:8000/tasks/{task_id}
```

### Посмотреть упоминания
```bash
curl http://localhost:8000/companies/1/mentions
curl http://localhost:8000/companies/1/mentions?sentiment=negative
```

### Статистика
```bash
curl http://localhost:8000/companies/1/stats
```

### Swagger UI (интерактивная документация)
Открой в браузере: http://localhost:8000/docs

---

## Архитектура

```
docker-compose
├── api        — FastAPI, порт 8000
├── worker     — Celery воркер (выполняет задачи парсинга)
├── beat       — Celery beat (запускает парсинг каждые 30 мин)
├── redis      — брокер задач, порт 6379
└── db         — PostgreSQL, порт 5432
```

## Что парсит

- Google News RSS (RU + EN)
- Bing News RSS

Для каждого упоминания определяет тональность (positive / neutral / negative) через TextBlob.

## Следующие шаги

- [ ] Добавить Telegram-канальный парсинг
- [ ] Подключить OpenAI для более точного sentiment
- [ ] Добавить риск-скор
- [ ] Построить Vue.js дашборд
