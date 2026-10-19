from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import requests

from trading_mcp.execution import news_feed


_SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <item>
      <title>Bitcoin breaks key resistance level</title>
      <pubDate>{recent}</pubDate>
      <link>https://example.com/1</link>
    </item>
    <item>
      <title>Unrelated altcoin news</title>
      <pubDate>{recent}</pubDate>
      <link>https://example.com/2</link>
    </item>
    <item>
      <title>Old Bitcoin news from last week</title>
      <pubDate>{old}</pubDate>
      <link>https://example.com/3</link>
    </item>
  </channel>
</rss>"""


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


class _FakeResponse:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_parse_rss_extracts_items():
    now = datetime.now(timezone.utc)
    xml = _SAMPLE_RSS.format(recent=_rfc822(now), old=_rfc822(now - timedelta(days=10)))
    items = news_feed._parse_rss(xml)
    assert len(items) == 3
    assert items[0].title == "Bitcoin breaks key resistance level"


def test_fetch_headlines_filters_by_symbol_and_lookback():
    now = datetime.now(timezone.utc)
    xml = _SAMPLE_RSS.format(recent=_rfc822(now), old=_rfc822(now - timedelta(days=10)))

    with patch.object(news_feed.requests, "get", return_value=_FakeResponse(xml)):
        headlines = news_feed.fetch_headlines("BTC/USDT", max_items=8, lookback_hours=24)

    titles = [h.title for h in headlines]
    assert "Bitcoin breaks key resistance level" in titles
    assert "Old Bitcoin news from last week" not in titles  # di luar lookback window


def test_fetch_headlines_never_raises_on_network_failure():
    with patch.object(news_feed.requests, "get", side_effect=requests.ConnectionError("boom")):
        headlines = news_feed.fetch_headlines("BTC/USDT")
    assert headlines == []


def test_fetch_headlines_never_raises_on_malformed_xml():
    with patch.object(news_feed.requests, "get", return_value=_FakeResponse("<not valid xml")):
        headlines = news_feed.fetch_headlines("BTC/USDT")
    assert headlines == []


def test_fetch_headlines_unknown_symbol_uses_general_feed_keyword_filter():
    now = datetime.now(timezone.utc)
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>Solana rallies 10 percent</title><pubDate>{d}</pubDate><link>x</link></item>
      <item><title>Unrelated Dogecoin news</title><pubDate>{d}</pubDate><link>y</link></item>
    </channel></rss>""".format(d=_rfc822(now))

    with patch.object(news_feed.requests, "get", return_value=_FakeResponse(xml)):
        headlines = news_feed.fetch_headlines("SOL/USDT")

    titles = [h.title for h in headlines]
    assert "Solana rallies 10 percent" in titles
    assert "Unrelated Dogecoin news" not in titles
