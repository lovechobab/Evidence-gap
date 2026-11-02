"""LLM 공급자 래퍼. 환경변수(또는 st.secrets)로 공급자를 고른다.

LLM_PROVIDER = anthropic | openai | none   (키가 없으면 자동으로 none = 데모 모드)
LLM_MODEL    = 사용할 모델 이름 (공급자 문서에서 최신 이름 확인 후 지정)
"""
from __future__ import annotations

import json
import os
import re

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o-mini",
}


def provider() -> str:
    p = os.getenv("LLM_PROVIDER", "").lower()
    if p in ("anthropic", "openai"):
        return p
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "none"


def _model(p: str) -> str:
    return os.getenv("LLM_MODEL") or DEFAULT_MODELS[p]


def _extract_json(text: str):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"[\[{].*[\]}]", text, flags=re.S)
    return json.loads(m.group(0) if m else text)


def chat_json(system: str, user: str, max_tokens: int = 1500):
    """시스템/유저 프롬프트를 보내고 JSON(dict 또는 list)을 돌려받는다."""
    p = provider()
    if p == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=_model(p), max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_json(msg.content[0].text)
    if p == "openai":
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=_model(p), max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return _extract_json(resp.choices[0].message.content)
    raise RuntimeError("LLM API 키가 설정되지 않았습니다 (데모 모드).")
