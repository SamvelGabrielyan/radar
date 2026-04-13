import hashlib
import time
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import httpx
from bs4 import BeautifulSoup

from config import settings

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
feedparser.USER_AGENT = USER_AGENT

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}


# ─── Поиск по имени ──────────────────────────────────────────────────────────

def search_by_name(full_name: str, birth_date: str = None) -> list[dict]:
    results = []
    seen = set()

    queries = [f'"{full_name}"']
    if birth_date:
        queries.append(f'"{full_name}" {birth_date}')

    for query in queries:
        encoded = quote_plus(query)
        sources = [
            {"name": "Google News RU", "url": f"https://news.google.com/rss/search?q={encoded}&hl=ru&gl=RU&ceid=RU:ru"},
            {"name": "Google News EN", "url": f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"},
            {"name": "Bing News",      "url": f"https://www.bing.com/news/search?q={encoded}&format=rss"},
        ]

        for source in sources:
            try:
                with httpx.Client(timeout=15, follow_redirects=True) as client:
                    resp = client.get(source["url"], headers=HEADERS)
                    raw = resp.text if resp.status_code == 200 else None

                feed = feedparser.parse(raw or source["url"])
                print(f"[PersonParser] {source['name']}: {len(feed.entries)} записей")

                for entry in feed.entries[:15]:
                    url   = entry.get("link", "").strip()
                    title = entry.get("title", "").strip()
                    if not url or not title:
                        continue

                    url_hash = hashlib.md5(url.encode()).hexdigest()
                    if url_hash in seen:
                        continue
                    seen.add(url_hash)

                    snippet = entry.get("summary", "")
                    if snippet:
                        snippet = BeautifulSoup(snippet, "lxml").get_text(" ", strip=True)[:400]

                    published_at = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        from datetime import datetime
                        try:
                            published_at = datetime(*entry.published_parsed[:6]).isoformat()
                        except Exception:
                            pass

                    results.append({
                        "source": source["name"],
                        "result_type": "news",
                        "title": title[:500],
                        "url": url[:1000],
                        "snippet": snippet,
                        "image_url": None,
                        "published_at": published_at,
                    })

                time.sleep(settings.PARSER_DELAY)

            except Exception as e:
                print(f"[PersonParser] Ошибка {source['name']}: {e}")

    print(f"[PersonParser] По имени найдено: {len(results)}")
    return results


# ─── Reverse Image Search: Yandex ────────────────────────────────────────────

def _yandex_reverse_search(image_data: bytes) -> list[dict]:
    results = []
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            upload = client.post(
                "https://yandex.ru/images/search",
                files={"upfile": ("photo.jpg", image_data, "image/jpeg")},
                data={"prg": "1", "rpt": "imageview"},
                headers={**HEADERS, "Referer": "https://yandex.ru/images/"},
            )

            if upload.status_code in (200, 302):
                soup = BeautifulSoup(upload.text, "lxml")
                for item in soup.select(".serp-item")[:15]:
                    title_el = item.select_one(".serp-item__title, .organic__title")
                    url_el   = item.select_one("a[href]")
                    img_el   = item.select_one("img")

                    title = title_el.get_text(strip=True) if title_el else ""
                    url   = url_el.get("href", "") if url_el else ""
                    image_url = img_el.get("src") if img_el else None

                    if not url or not title:
                        continue
                    if url.startswith("/"):
                        url = "https://yandex.ru" + url

                    results.append({
                        "source": "Yandex Images",
                        "result_type": "image",
                        "title": title[:500],
                        "url": url[:1000],
                        "snippet": "",
                        "image_url": image_url,
                        "published_at": None,
                    })

        print(f"[ImageSearch] Yandex: {len(results)} результатов")
    except Exception as e:
        print(f"[ImageSearch] Yandex ошибка: {e}")
    return results


# ─── Reverse Image Search: Bing ──────────────────────────────────────────────

def _bing_reverse_search(image_data: bytes) -> list[dict]:
    results = []
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            upload = client.post(
                "https://www.bing.com/images/search",
                files={"imgurl": ("photo.jpg", image_data, "image/jpeg")},
                data={"FORM": "IRSBIQ"},
                headers={**HEADERS, "Referer": "https://www.bing.com/images/"},
            )

            if upload.status_code in (200, 302):
                soup = BeautifulSoup(upload.text, "lxml")
                for item in soup.select(".b_algo")[:10]:
                    a_tag  = item.select_one("h2 a")
                    snip   = item.select_one(".b_caption p")
                    img_el = item.select_one("img")

                    if not a_tag:
                        continue

                    results.append({
                        "source": "Bing Visual Search",
                        "result_type": "image",
                        "title": a_tag.get_text(strip=True)[:500],
                        "url": a_tag.get("href", "")[:1000],
                        "snippet": snip.get_text(strip=True)[:400] if snip else "",
                        "image_url": img_el.get("src") if img_el else None,
                        "published_at": None,
                    })

        print(f"[ImageSearch] Bing: {len(results)} результатов")
    except Exception as e:
        print(f"[ImageSearch] Bing ошибка: {e}")
    return results


# ─── Reverse Image Search: Google ────────────────────────────────────────────

def _google_reverse_search(image_data: bytes) -> list[dict]:
    results = []
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            upload = client.post(
                "https://lens.google.com/upload",
                files={"encoded_image": ("photo.jpg", image_data, "image/jpeg")},
                data={"sbisrc": "cr_1", "hl": "ru"},
                headers={**HEADERS, "Referer": "https://lens.google.com/"},
            )

            if upload.status_code in (200, 302):
                soup = BeautifulSoup(upload.text, "lxml")
                for item in soup.select(".g")[:10]:
                    a_tag  = item.select_one("h3")
                    url_el = item.select_one("a[href]")
                    snip   = item.select_one(".VwiC3b")

                    if not a_tag or not url_el:
                        continue

                    results.append({
                        "source": "Google Lens",
                        "result_type": "image",
                        "title": a_tag.get_text(strip=True)[:500],
                        "url": url_el.get("href", "")[:1000],
                        "snippet": snip.get_text(strip=True)[:400] if snip else "",
                        "image_url": None,
                        "published_at": None,
                    })

        print(f"[ImageSearch] Google Lens: {len(results)} результатов")
    except Exception as e:
        print(f"[ImageSearch] Google Lens ошибка: {e}")
    return results


# ─── Главная функция поиска по фото ──────────────────────────────────────────

def reverse_image_search(photo_path: str) -> list[dict]:
    path = Path(photo_path)
    if not path.exists():
        print(f"[ImageSearch] Файл не найден: {photo_path}")
        return []

    with open(photo_path, "rb") as f:
        image_data = f.read()

    all_results = []
    seen_urls = set()

    for search_fn in [_yandex_reverse_search, _bing_reverse_search, _google_reverse_search]:
        try:
            for r in search_fn(image_data):
                if r["url"] not in seen_urls and r["url"]:
                    seen_urls.add(r["url"])
                    all_results.append(r)
        except Exception as e:
            print(f"[ImageSearch] Ошибка: {e}")

    if not all_results:
        print("[ImageSearch] Автопоиск не дал результатов, добавляем ручные ссылки")
        all_results = [
            {
                "source": "Yandex Images",
                "result_type": "image",
                "title": "Поиск по фото в Яндекс Картинках",
                "url": "https://yandex.ru/images/",
                "snippet": "Загрузи фото вручную — нажми на иконку фотоаппарата",
                "image_url": None,
                "published_at": None,
            },
            {
                "source": "Google Lens",
                "result_type": "image",
                "title": "Поиск по фото в Google Lens",
                "url": "https://lens.google.com/",
                "snippet": "Перетащи фото или вставь URL изображения",
                "image_url": None,
                "published_at": None,
            },
            {
                "source": "PimEyes",
                "result_type": "image",
                "title": "Поиск лица в PimEyes",
                "url": "https://pimeyes.com/",
                "snippet": "Специализированный поиск лиц по открытым источникам",
                "image_url": None,
                "published_at": None,
            },
        ]

    print(f"[ImageSearch] Итого: {len(all_results)} результатов")
    return all_results
