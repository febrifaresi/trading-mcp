"""
Ambil headline berita crypto terbaru dari RSS publik (tidak butuh API key).
Dipakai sebagai konteks tambahan untuk LLM advisor — sesuatu yang angka
indikator tidak bisa baca.

Desain penting: fungsi di sini TIDAK BOLEH raise exception ke pemanggil.
Kalau RSS gagal diambil/di-parse, return list kosong — bot tetap jalan,
cuma LLM advisor dapat konteks berita yang lebih sedikit.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

# Tag-feed per base currency — lebih presisi daripada keyword filter di feed umum.
_SYMBOL_TAG_FEEDS: dict[str, str] = {
    "BTC": "https://cointelegraph.com/rss/tag/bitcoin",
    "ETH": "https://cointelegraph.com/rss/tag/ethereum",
}

# Feed umum sebagai fallback/pelengkap — di-filter manual pakai keyword.
_GENERAL_FEEDS: list[str] = [
    "https://cointelegraph.com/rss",
]

_REQUEST_TIMEOUT = 8.0


@dataclass
class Headline:
    title: str
    published: datetime
    link: str


def _base_currency(symbol: str) -> str:
    """'BTC/USDT' -> 'BTC'"""
    return symbol.split("/")[0].upper().strip()


def _parse_rss(xml_text: str) -> list[Headline]:
    items: list[Headline] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for item in root.findall(".//item"):
        title_el = item.find("title")
        pubdate_el = item.find("pubDate")
        link_el = item.find("link")
        if title_el is None or title_el.text is None:
            continue

        published = datetime.now(timezone.utc)
        if pubdate_el is not None and pubdate_el.text:
            try:
                published = parsedate_to_datetime(pubdate_el.text)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass

        items.append(Headline(
            title=title_el.text.strip(),
            published=published,
            link=(link_el.text.strip() if link_el is not None and link_el.text else ""),
        ))

    return items


def _fetch_feed(url: str) -> list[Headline]:
    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT, headers={"User-Agent": "trading-mcp-bot/1.0"})
        resp.raise_for_status()
    except requests.RequestException:
        return []
    return _parse_rss(resp.text)


def fetch_headlines(
    symbol: str,
    max_items: int = 8,
    lookback_hours: int = 24,
) -> list[Headline]:
    """
    Ambil headline terbaru yang relevan untuk base currency dari `symbol`
    (misal 'BTC/USDT' -> cari berita BTC/Bitcoin), dalam window `lookback_hours`.
    Tidak pernah raise — return [] kalau semua sumber gagal.
    """
    base = _base_currency(symbol)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    collected: list[Headline] = []

    tag_feed = _SYMBOL_TAG_FEEDS.get(base)
    if tag_feed:
        collected.extend(_fetch_feed(tag_feed))

    if len(collected) < max_items:
        name_hint = {"BTC": "bitcoin", "ETH": "ethereum"}.get(base, base.lower())
        for feed_url in _GENERAL_FEEDS:
            for h in _fetch_feed(feed_url):
                if base.lower() in h.title.lower() or name_hint in h.title.lower():
                    collected.append(h)

    # Dedup by title, filter lookback window, sort terbaru dulu
    seen_titles: set[str] = set()
    filtered: list[Headline] = []
    for h in sorted(collected, key=lambda x: x.published, reverse=True):
        if h.title in seen_titles:
            continue
        if h.published < cutoff:
            continue
        seen_titles.add(h.title)
        filtered.append(h)

    return filtered[:max_items]
