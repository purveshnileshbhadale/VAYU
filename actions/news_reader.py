import sys
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime


def news_reader(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "headlines").strip().lower()
    category = params.get("category", "").strip().lower()
    query = params.get("query", "").strip()
    count = params.get("count", 5)

    if player:
        player.write_log(f"[News] action={action} category={category} query={query}")

    try:
        if action in ("headlines", "top", "top_stories"):
            return _fetch_headlines(category or "general", count)

        elif action == "search":
            if not query:
                return "Search query is required for news search."
            return _search_news(query, count)

        elif action == "latest":
            return _fetch_rss("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", count)

        elif action == "source":
            source = params.get("source", "bbc")
            sources = {
                "bbc": "https://feeds.bbci.co.uk/news/rss.xml",
                "cnn": "http://rss.cnn.com/rss/edition.rss",
                "nytimes": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
                "reuters": "https://www.reutersagency.com/feed/",
                "techcrunch": "https://techcrunch.com/feed/",
                "wired": "https://www.wired.com/feed/rss",
            }
            url = sources.get(source.lower())
            if not url:
                return f"Unknown source: {source}. Available: {', '.join(sources.keys())}"
            return _fetch_rss(url, count)

        elif action == "tech":
            return _fetch_rss("https://techcrunch.com/feed/", count)

        elif action == "sports":
            return _fetch_rss("https://www.espn.com/espn/rss/news", count)

        return (
            f"Unknown action: '{action}'. "
            f"Available: headlines, search, latest, source, tech, sports"
        )

    except Exception as e:
        return f"News reader failed: {e}"


def _fetch_headlines(category: str, count: int) -> str:
    url = f"https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    return _fetch_rss(url, count)


def _search_news(query: str, count: int) -> str:
    from urllib.parse import quote
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    return _fetch_rss(url, count)


def _fetch_rss(url: str, count: int) -> str:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
    except urllib.error.URLError as e:
        return f"Could not fetch news: {e.reason}"
    except Exception as e:
        return f"News fetch failed: {e}"

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return "Failed to parse RSS feed."

    ns = {"": "http://www.w3.org/2005/Atom"}
    items = []

    for item in root.iter("item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        desc = item.findtext("description", "")
        if title:
            items.append({"title": title, "link": link, "date": pub_date, "desc": desc})

    if not items:
        for entry in root.iter("entry"):
            title = entry.findtext("title", "")
            link_el = entry.find("link")
            link = link_el.get("href", "") if link_el is not None else ""
            pub_date = entry.findtext("published", "")
            desc = entry.findtext("summary", "")
            if title:
                items.append({"title": title, "link": link, "date": pub_date, "desc": desc})

    if not items:
        return "No news articles found."

    count = min(count, len(items))
    lines = [f"Top {count} news headlines:"]
    for i, item in enumerate(items[:count], 1):
        lines.append(f"\n{i}. {item['title']}")
        if item["date"]:
            try:
                dt = datetime.strptime(item["date"][:25], "%a, %d %b %Y %H:%M:%S")
                lines.append(f"   {dt.strftime('%b %d, %Y')}")
            except (ValueError, IndexError):
                pass

    return "\n".join(lines)
