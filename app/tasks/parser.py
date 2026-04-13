import hashlib
import time
from datetime import datetime
from urllib.parse import quote_plus

import feedparser
import httpx
from bs4 import BeautifulSoup
from textblob import TextBlob

from config import settings

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# feedparser использует этот заголовок глобально
feedparser.USER_AGENT = USER_AGENT


def build_sources(keyword: str) -> list[dict]:
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
    ]


def analyze_sentiment(text: str) -> tuple[str, float]:
    try:
        score = TextBlob(text).sentiment.polarity
        if score > 0.1:
            return "positive", round(score, 3)
        elif score < -0.1:
            return "negative", round(score, 3)
        return "neutral", round(score, 3)
    except Exception:
        return "neutral", 0.0


def fetch_rss_with_httpx(url: str) -> str | None:
    """Fallback: качаем RSS через httpx с правильными заголовками."""
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            })
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        print(f"[Parser] httpx error: {e}")
    return None


def parse_rss_feed(source: dict) -> list[dict]:
    results = []
    try:
        # Сначала пробуем через httpx, потом feedparser
        raw_xml = fetch_rss_with_httpx(source["url"])
        if raw_xml:
            feed = feedparser.parse(raw_xml)
        else:
            feed = feedparser.parse(source["url"])

        print(f"[Parser] {source['name']}: найдено {len(feed.entries)} записей")

        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            snippet = entry.get("summary", "")

            if not title or not url:
                continue

            if snippet:
                snippet = BeautifulSoup(snippet, "lxml").get_text(" ", strip=True)[:500]

            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

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

        time.sleep(settings.PARSER_DELAY)

    except Exception as e:
        print(f"[Parser] Ошибка {source['name']}: {e}")

    return results


def fetch_mentions(keywords: list[str]) -> list[dict]:
    all_mentions = []
    seen_hashes = set()

    for keyword in keywords:
        print(f"[Parser] Ищем: '{keyword}'")
        for source in build_sources(keyword):
            for mention in parse_rss_feed(source):
                if mention["url_hash"] not in seen_hashes:
                    seen_hashes.add(mention["url_hash"])
                    all_mentions.append(mention)

    print(f"[Parser] Итого уникальных упоминаний: {len(all_mentions)}")
    return all_mentions
