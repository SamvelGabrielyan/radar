import pytest
from unittest.mock import patch, MagicMock
from tasks.parser import analyze_sentiment, fetch_mentions, build_sources
from tasks.person_parser import search_by_name


# ─── Sentiment analysis ───────────────────────────────────────────────────────

def test_sentiment_positive():
    label, score = analyze_sentiment("This is excellent amazing wonderful news!")
    assert label == "positive"
    assert score > 0.1


def test_sentiment_negative():
    label, score = analyze_sentiment("This is terrible awful horrible disaster crash failure")
    assert label == "negative"
    assert score < -0.1


def test_sentiment_neutral():
    label, score = analyze_sentiment("The company released a report on Tuesday.")
    assert label == "neutral"
    assert -0.1 <= score <= 0.1


def test_sentiment_empty_string():
    label, score = analyze_sentiment("")
    assert label == "neutral"
    assert score == 0.0


def test_sentiment_returns_tuple():
    result = analyze_sentiment("Some text")
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], float)


def test_sentiment_score_range():
    for text in ["great profit growth", "bankruptcy fraud scandal", "quarterly report"]:
        _, score = analyze_sentiment(text)
        assert -1.0 <= score <= 1.0


# ─── build_sources ────────────────────────────────────────────────────────────

def test_build_sources_returns_list():
    sources = build_sources("Apple Inc")
    assert isinstance(sources, list)
    assert len(sources) > 0


def test_build_sources_have_required_keys():
    sources = build_sources("Tesla")
    for s in sources:
        assert "name" in s
        assert "url" in s


def test_build_sources_encode_keyword():
    sources = build_sources("Газпром нефть")
    for s in sources:
        # Пробелы должны быть закодированы
        assert " " not in s["url"]


def test_build_sources_different_keywords():
    s1 = build_sources("Apple")
    s2 = build_sources("Google")
    # URL-ы должны отличаться
    urls1 = {s["url"] for s in s1}
    urls2 = {s["url"] for s in s2}
    assert urls1 != urls2


# ─── fetch_mentions (с моком HTTP) ───────────────────────────────────────────

def make_mock_feed(entries):
    """Создаёт mock feedparser feed объект."""
    feed = MagicMock()
    feed.entries = entries
    return feed


def make_entry(title, url, summary="", published_parsed=None):
    entry = MagicMock()
    entry.get = lambda key, default="": {
        "title": title, "link": url, "summary": summary
    }.get(key, default)
    entry.published_parsed = published_parsed
    return entry


@patch("tasks.parser.feedparser.parse")
@patch("tasks.parser.fetch_rss_with_httpx")
def test_fetch_mentions_basic(mock_http, mock_feedparser):
    mock_http.return_value = "<rss/>"
    mock_feedparser.return_value = make_mock_feed([
        make_entry("Apple reports record profits", "https://news.com/apple-1"),
        make_entry("Apple launches new iPhone",   "https://news.com/apple-2"),
    ])

    results = fetch_mentions(["Apple"])
    assert len(results) > 0
    urls = [r["url"] for r in results]
    assert "https://news.com/apple-1" in urls


@patch("tasks.parser.feedparser.parse")
@patch("tasks.parser.fetch_rss_with_httpx")
def test_fetch_mentions_deduplication(mock_http, mock_feedparser):
    """Одинаковые URL не должны дублироваться."""
    same_url = "https://news.com/article"
    mock_http.return_value = "<rss/>"
    mock_feedparser.return_value = make_mock_feed([
        make_entry("Title 1", same_url),
        make_entry("Title 2", same_url),  # дубль
    ])

    results = fetch_mentions(["Apple"])
    urls = [r["url"] for r in results]
    assert urls.count(same_url) <= 1


@patch("tasks.parser.feedparser.parse")
@patch("tasks.parser.fetch_rss_with_httpx")
def test_fetch_mentions_skips_empty(mock_http, mock_feedparser):
    """Записи без заголовка или URL пропускаются."""
    mock_http.return_value = "<rss/>"
    mock_feedparser.return_value = make_mock_feed([
        make_entry("", "https://news.com/1"),       # нет заголовка
        make_entry("Title", ""),                     # нет URL
        make_entry("Good title", "https://news.com/good"),  # норм
    ])

    results = fetch_mentions(["Apple"])
    for r in results:
        assert r["title"] != ""
        assert r["url"] != ""


@patch("tasks.parser.feedparser.parse")
@patch("tasks.parser.fetch_rss_with_httpx")
def test_fetch_mentions_sentiment_assigned(mock_http, mock_feedparser):
    """Каждое упоминание должно иметь sentiment."""
    mock_http.return_value = "<rss/>"
    mock_feedparser.return_value = make_mock_feed([
        make_entry("Great success record profit", "https://news.com/1"),
    ])

    results = fetch_mentions(["Apple"])
    for r in results:
        assert r["sentiment"] in ("positive", "neutral", "negative")
        assert isinstance(r["sentiment_score"], float)


@patch("tasks.parser.feedparser.parse")
@patch("tasks.parser.fetch_rss_with_httpx")
def test_fetch_mentions_multiple_keywords(mock_http, mock_feedparser):
    """Несколько ключевых слов — результаты объединяются."""
    call_count = 0

    def side_effect(xml):
        nonlocal call_count
        call_count += 1
        return make_mock_feed([
            make_entry(f"News {call_count}", f"https://news.com/{call_count}")
        ])

    mock_http.return_value = "<rss/>"
    mock_feedparser.side_effect = side_effect

    results = fetch_mentions(["Apple", "iPhone"])
    assert len(results) >= 2


# ─── search_by_name (с моком) ─────────────────────────────────────────────────

@patch("tasks.person_parser.feedparser.parse")
@patch("tasks.person_parser.httpx.Client")
def test_search_by_name_basic(mock_client_cls, mock_feedparser):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<rss/>"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

    mock_feedparser.return_value = make_mock_feed([
        make_entry("Иванов Иван назначен директором", "https://news.com/ivanov"),
    ])

    results = search_by_name("Иванов Иван")
    assert len(results) > 0
    assert results[0]["result_type"] == "news"


@patch("tasks.person_parser.feedparser.parse")
@patch("tasks.person_parser.httpx.Client")
def test_search_by_name_with_birth_date(mock_client_cls, mock_feedparser):
    """С датой рождения добавляется дополнительный запрос."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<rss/>"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response
    mock_feedparser.return_value = make_mock_feed([])

    # Не должен упасть с датой рождения
    results = search_by_name("Петров Пётр", birth_date="1985-03-15")
    assert isinstance(results, list)


@patch("tasks.person_parser.feedparser.parse")
@patch("tasks.person_parser.httpx.Client")
def test_search_by_name_handles_http_error(mock_client_cls, mock_feedparser):
    """HTTP ошибка не должна ронять всё приложение."""
    mock_client_cls.return_value.__enter__.return_value.get.side_effect = Exception("Connection error")
    mock_feedparser.return_value = make_mock_feed([])

    results = search_by_name("Тест Тестов")
    assert isinstance(results, list)  # не упало
