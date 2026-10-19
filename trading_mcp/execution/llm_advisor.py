"""
Panggil Qwen lewat OpenRouter untuk memutuskan arah sinyal (LONG_ENTRY / EXIT / NONE).

Kontrak keamanan yang TIDAK BOLEH dilanggar:
  - Fungsi ini TIDAK PERNAH raise ke pemanggil. Network error, timeout, JSON
    rusak, model ngaco — semua jatuh ke fallback direction="NONE".
  - LLM cuma boleh pilih ARAH. Ukuran posisi, stop-loss, circuit breaker,
    kill switch — itu semua tetap di RiskManager, LLM tidak pernah menyentuhnya.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

from .config import ExecutionConfig
from .news_feed import Headline

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_VALID_DIRECTIONS = {"LONG_ENTRY", "EXIT", "NONE"}

_SYSTEM_PROMPT = """Kamu adalah analis trading crypto yang hati-hati dan konservatif.
Tugasmu HANYA menentukan arah: LONG_ENTRY, EXIT, atau NONE. Kamu TIDAK menentukan
ukuran posisi atau stop-loss — itu di luar wewenangmu.

Jawab HANYA dengan JSON valid, tanpa teks lain, format persis:
{"direction": "LONG_ENTRY" | "EXIT" | "NONE", "confidence": 0.0-1.0, "reasoning": "alasan singkat 1-2 kalimat dalam Bahasa Indonesia"}

Aturan:
- LONG_ENTRY hanya jika ada alasan kuat (teknikal + berita searah, bukan cuma salah satu).
- EXIT hanya jika ada sinyal jelas bahwa tren berbalik atau ada risiko signifikan dari berita.
- Kalau ragu atau sinyal bercampur/tidak jelas -> NONE. Lebih baik tidak bertindak daripada salah.
- Ini spot market, long-only. Tidak ada short."""


@dataclass
class AdvisorDecision:
    direction: str
    confidence: float
    reasoning: str


def _fallback(reason: str) -> AdvisorDecision:
    return AdvisorDecision(direction="NONE", confidence=0.0, reasoning=f"[fallback] {reason}")


def _build_user_prompt(
    symbol: str,
    price: float,
    trend_bias: str,
    confluence_score: int,
    confluence_reasons: list[str],
    headlines: list[Headline],
) -> str:
    reasons_txt = "\n".join(f"  - {r}" for r in confluence_reasons) or "  (tidak ada)"
    if headlines:
        news_txt = "\n".join(f"  - [{h.published:%Y-%m-%d %H:%M}] {h.title}" for h in headlines)
    else:
        news_txt = "  (tidak ada berita terbaru yang relevan)"

    return f"""Simbol: {symbol}
Harga sekarang: {price}
Trend bias teknikal: {trend_bias}
Confluence score teknikal: {confluence_score}/8
Alasan teknikal:
{reasons_txt}

Berita terbaru ({len(headlines)} headline):
{news_txt}

Tentukan arah untuk simbol ini sekarang."""


def _extract_json(text: str) -> dict | None:
    """Model kadang bungkus JSON dengan teks lain walau sudah diminta JSON murni — ambil blok {...} pertama."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class LLMAdvisor:
    def __init__(self, config: ExecutionConfig):
        self.config = config

    def decide(
        self,
        symbol: str,
        price: float,
        trend_bias: str,
        confluence_score: int,
        confluence_reasons: list[str],
        headlines: list[Headline],
    ) -> AdvisorDecision:
        prompt = _build_user_prompt(symbol, price, trend_bias, confluence_score, confluence_reasons, headlines)

        try:
            resp = requests.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self.config.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.llm_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
                timeout=self.config.llm_timeout_seconds,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            return _fallback(f"OpenRouter request gagal: {e}")

        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            return _fallback(f"Response OpenRouter tidak sesuai bentuk yang diharapkan: {e}")

        parsed = _extract_json(content)
        if parsed is None:
            return _fallback("Model tidak mengembalikan JSON valid.")

        direction = parsed.get("direction")
        if direction not in _VALID_DIRECTIONS:
            return _fallback(f"Direction tidak valid dari model: {direction!r}")

        try:
            confidence = float(parsed.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        reasoning = str(parsed.get("reasoning", "")).strip() or "(tidak ada alasan dari model)"

        return AdvisorDecision(direction=direction, confidence=confidence, reasoning=reasoning)
