import hashlib
import time
import random
from datetime import datetime
from urllib.parse import quote_plus

import feedparser
import httpx
from bs4 import BeautifulSoup
from textblob import TextBlob

from config import settings

# Набор User-Agent для ротации — снижает вероятность блокировки
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def build_sources(keyword: str) -> list[dict]:
    """
    Строит список RSS-источников для данного ключевого слова.
    Теперь включает Google News (RU/EN), Bing News и DuckDuckGo News —
    если один источник заблокирует запрос, другие компенсируют.
    """
    encoded = quote_plus(keyword)
    return [
        {
            "name": "Google News RU",
            "url": f"https://news.google.com/rss/search?q={encoded}&hl=ru&gl=RU&ceid=RU:ru",
        },
        {
            "name": "Google News EN",
            "url": f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en",
        },
        {
            "name": "Bing News",
            "url": f"https://www.bing.com/news/search?q={encoded}&format=rss",
        },
        {
            "name": "DuckDuckGo",
            "url": f"https://duckduckgo.com/?q={encoded}&t=h_&iar=news&ia=news&format=rss",
        },
    ]


def analyze_sentiment(text: str) -> tuple[str, float]:
    """Определяет тональность текста через TextBlob."""
    try:
        score = TextBlob(text).sentiment.polarity
        if score > 0.1:
            return "positive", round(score, 3)
        elif score < -0.1:
            return "negative", round(score, 3)
        return "neutral", round(score, 3)
    except Exception:
        return "neutral", 0.0


def fetch_rss_with_httpx(url: str, max_retries: int = 2) -> str | None:
    """
    Скачивает RSS через httpx с ротацией User-Agent и ретраями.
    Если первый запрос вернул не-200, пробует ещё раз с другим UA.
    """
    for attempt in range(max_retries):
        try:
            ua = _random_ua()
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": ua,
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept-Encoding": "gzip, deflate",
                    "Cache-Control": "no-cache",
                })
                if resp.status_code == 200:
                    return resp.text
                print(f"[Parser] HTTP {resp.status_code} для {url} (попытка {attempt + 1})")
        except Exception as e:
            print(f"[Parser] httpx ошибка (попытка {attempt + 1}): {e}")

        # Пауза перед ретраем — с небольшой рандомизацией чтобы не палить паттерн
        if attempt < max_retries - 1:
            time.sleep(1.5 + random.random())

    return None


def _extract_published_at(entry) -> datetime | None:
    """Извлекает дату публикации из RSS-записи, пробуя несколько полей."""
    for field in ["published_parsed", "updated_parsed", "created_parsed"]:
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except Exception:
                continue
    return None


def parse_rss_feed(source: dict) -> list[dict]:
    """
    Парсит одну RSS-ленту: скачивает через httpx, если не удалось —
    пробует feedparser напрямую. Возвращает список упоминаний.
    """
    results = []
    try:
        # Первый способ: httpx + feedparser.parse(строка)
        raw_xml = fetch_rss_with_httpx(source["url"])
        if raw_xml:
            feed = feedparser.parse(raw_xml)
        else:
            # Фоллбэк: feedparser сам делает HTTP-запрос
            feedparser.USER_AGENT = _random_ua()
            feed = feedparser.parse(source["url"])

        entry_count = len(feed.entries)
        print(f"[Parser] {source['name']}: {entry_count} записей")

        # Если RSS пуст — возможно источник заблокировал, это нормально
        if entry_count == 0 and feed.bozo:
            print(f"[Parser] {source['name']}: ошибка парсинга RSS — {feed.bozo_exception}")

        for entry in feed.entries[:25]:  # Берём до 25 записей на источник
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            snippet = entry.get("summary", "")

            if not title or not url:
                continue

            # Очищаем HTML-теги из сниппета
            if snippet:
                snippet = BeautifulSoup(snippet, "lxml").get_text(" ", strip=True)[:500]

            published_at = _extract_published_at(entry)
            sentiment, score = analyze_sentiment(f"{title} {snippet}")
            url_hash = hashlib.md5(url.encode()).hexdigest()

            results.append({
                "title": title[:500],
                "url": url[:1000],
                "url_hash": url_hash,
                "source": source["name"],
                "snippet": snippet,
                "sentiment": sentiment,
                "sentiment_score": score,
                "published_at": published_at,
            })

        # Задержка между запросами — чтобы не перегружать источник
        delay = settings.PARSER_DELAY + random.uniform(0.5, 1.5)
        time.sleep(delay)

    except Exception as e:
        print(f"[Parser] Ошибка {source['name']}: {e}")

    return results


def fetch_mentions(keywords: list[str]) -> list[dict]:
    """
    Основная функция: парсит все источники для всех ключевых слов.
    Дедуплицирует по хешу URL, считает статистику по источникам.
    """
    all_mentions = []
    seen_hashes = set()
    source_stats = {}

    for keyword in keywords:
        print(f"[Parser] Ищем: '{keyword}'")
        for source in build_sources(keyword):
            mentions = parse_rss_feed(source)
            source_name = source["name"]
            added = 0

            for mention in mentions:
                if mention["url_hash"] not in seen_hashes:
                    seen_hashes.add(mention["url_hash"])
                    all_mentions.append(mention)
                    added += 1

            source_stats[source_name] = source_stats.get(source_name, 0) + added

    # Логируем итоги по каждому источнику
    print(f"[Parser] === Итого: {len(all_mentions)} уникальных упоминаний ===")
    for src, count in source_stats.items():
        print(f"[Parser]   {src}: {count}")

    return all_mentions
