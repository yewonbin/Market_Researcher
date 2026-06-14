"""Google Gemini 로 기사를 요약·분류하고 보험사 비즈니스 시사점을 생성한다.

Gemini 무료 등급(예: gemini-2.5-flash)으로 동작하므로 API 비용이 들지 않습니다.
API 키 발급: https://aistudio.google.com/apikey  →  .env 의 GEMINI_API_KEY
"""
from __future__ import annotations

import json
import time

from google import genai
from google.genai import types

from .collect import Article
from .config import Config

# 429(속도 제한) 발생 시 한 기사당 최대 재시도 횟수
_MAX_RETRIES = 4


def _is_rate_limit(err: Exception) -> bool:
    msg = str(err)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg

SYSTEM_PROMPT = """\
당신은 보험사 디지털전략팀의 시니어 리서치 애널리스트입니다.
뉴스 기사를 읽고 실무자가 바로 읽을 수 있는 브리핑을 작성합니다.

작성 원칙:
- 모든 출력은 한국어. 원문이 영어면 자연스러운 한국어로 옮긴다.
- 사실에 근거해 핵심만. 과장·홍보성 표현 금지.
- "이 기사는", "본 기사에서는", "~에 대해 다룬다" 같은 상투적·기계적 도입부 금지.
  바로 핵심 사실부터 쓴다.
- 기사에 없는 가상의 회사명(예: ABC사, A생명)이나 수치를 지어내지 않는다.
- 시사점·활용 방안은 일반론("효율이 높아진다")이 아니라 구체적으로 쓴다."""

# 사용자 프롬프트 템플릿 — 기사별로 채워 넣는다.
USER_TEMPLATE = """\
다음 뉴스를 분석하세요.

[제목] {title}
[출처] {source}
[원문 요약] {summary}

요구사항:
1. category: 아래 분류 중 가장 적합한 하나 — {categories}
2. summary: 핵심 내용을 한국어 2~3문장으로 요약
3. business_implication: 보험·금융 비즈니스 관점의 시사점 1~2문장
4. insurer_use_case: 보험사가 실제로 적용해볼 수 있는 구체적 Use Case 1~2문장
5. relevance: 보험산업 관련도를 1(무관)~5(매우 높음) 정수로 평가"""


def _schema(categories: list[str]) -> dict:
    """Gemini structured output 스키마(OpenAPI subset)."""
    return {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": categories},
            "summary": {"type": "string"},
            "business_implication": {"type": "string"},
            "insurer_use_case": {"type": "string"},
            "relevance": {"type": "integer"},
        },
        "required": [
            "category",
            "summary",
            "business_implication",
            "insurer_use_case",
            "relevance",
        ],
        "propertyOrdering": [
            "category",
            "summary",
            "business_implication",
            "insurer_use_case",
            "relevance",
        ],
    }


def analyze(
    articles: list[Article], cfg: Config, client: "genai.Client | None" = None
) -> list[Article]:
    """각 기사를 Gemini 로 분석해 필드를 채운 뒤 반환(원본 리스트를 수정)."""
    if not articles:
        return articles

    client = client or genai.Client(api_key=cfg.gemini_api_key or None)
    categories = cfg.categories
    fallback_category = categories[-1] if categories else "기타"

    gen_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_schema(categories),
        temperature=0.3,
    )

    # 무료 등급 분당 한도 보호: 요청 간 최소 간격(초)
    min_interval = 60.0 / max(1, cfg.rpm)
    last_call = 0.0

    for idx, art in enumerate(articles, 1):
        user = USER_TEMPLATE.format(
            title=art.title,
            source=art.source,
            summary=art.summary or "(요약 없음 — 제목 기준으로 판단)",
            categories=", ".join(categories),
        )

        for attempt in range(_MAX_RETRIES + 1):
            # 호출 간 간격 유지(속도 제한 예방)
            wait = min_interval - (time.time() - last_call)
            if wait > 0:
                time.sleep(wait)
            last_call = time.time()
            try:
                resp = client.models.generate_content(
                    model=cfg.model, contents=user, config=gen_config
                )
                data = json.loads(resp.text)
                cat = data.get("category", fallback_category)
                art.category = cat if cat in categories else fallback_category
                art.ai_summary = data.get("summary", "")
                art.business_implication = data.get("business_implication", "")
                art.insurer_use_case = data.get("insurer_use_case", "")
                art.relevance = max(1, min(5, int(data.get("relevance", 0) or 0)))
                break  # 성공
            except Exception as e:  # noqa: BLE001
                if _is_rate_limit(e) and attempt < _MAX_RETRIES:
                    # 분 단위 창이 풀리도록 점증 대기 후 재시도
                    backoff = min(60.0, min_interval * (attempt + 1) + 5.0)
                    print(
                        f"  · [{idx}/{len(articles)}] 속도 제한 — {backoff:.0f}s 대기 후 재시도"
                        f" ({attempt + 1}/{_MAX_RETRIES})"
                    )
                    time.sleep(backoff)
                    last_call = time.time()
                    continue
                # 재시도 소진 또는 기타 오류 → 건너뛰고 계속
                art.category = fallback_category
                art.ai_summary = art.summary[:200]
                art.business_implication = ""
                art.insurer_use_case = ""
                art.relevance = 0
                print(f"  ! 분석 실패(건너뜀): {art.title[:50]} - {e}")
                break

    return articles
