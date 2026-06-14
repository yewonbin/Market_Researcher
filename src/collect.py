"""RSS 피드에서 기사를 수집하고 신규 기사만 골라낸다."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import mktime

import feedparser

from .config import Feed
from .state import SeenStore

_TAG_RE = re.compile(r"<[^>]+>")
_BRACKET_RE = re.compile(r"[\[\(【][^\]\)】]*[\]\)】]")  # [코너명] (분류) 제거
_NONWORD_RE = re.compile(r"[^0-9a-z가-힣]")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub("", text)          # HTML 태그 제거
    text = html.unescape(text)            # &amp; 등 엔티티 복원
    return re.sub(r"\s+", " ", text).strip()


def _norm_title(title: str) -> str:
    """중복 판정용 제목 정규화 — 매체명 접미사·괄호·공백·기호 제거."""
    t = title
    # 끝의 " - 매체명" 접미사 제거(뉴스 제목 관행)
    if " - " in t:
        t = t.rsplit(" - ", 1)[0]
    t = _BRACKET_RE.sub("", t)            # [ABC AI금융시대=...] 같은 코너명 제거
    t = _NONWORD_RE.sub("", t.lower())   # 공백·기호 제거
    return t


@dataclass
class Article:
    title: str
    url: str
    source: str           # 피드 이름
    published: str         # ISO8601 문자열 (없으면 "")
    summary: str           # RSS 원문 요약/설명 (분석 입력)
    # 분석 단계에서 채워짐
    category: str = ""
    ai_summary: str = ""
    business_implication: str = ""
    insurer_use_case: str = ""
    relevance: int = 0

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published": self.published,
            "category": self.category,
            "summary": self.ai_summary,
            "business_implication": self.business_implication,
            "insurer_use_case": self.insurer_use_case,
            "relevance": self.relevance,
        }


def _published_iso(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime.fromtimestamp(mktime(t), tz=timezone.utc).isoformat()
    return ""


def collect(feeds: list[Feed], seen: SeenStore, limit: int) -> list[Article]:
    """모든 피드를 파싱해 아직 처리하지 않은 신규 기사를 최대 limit건 반환."""
    new_articles: list[Article] = []
    seen_urls: set[str] = set()    # 이번 실행 내 URL 중복 방지
    seen_titles: set[str] = set()  # 같은 헤드라인(다른 매체) 중복 방지

    for feed in feeds:
        parsed = feedparser.parse(feed.url)
        for entry in parsed.entries:
            url = getattr(entry, "link", "").strip()
            title = _clean(getattr(entry, "title", ""))
            if not url or not title:
                continue
            if url in seen_urls or seen.has(url):
                continue
            norm = _norm_title(title)
            if norm and norm in seen_titles:   # 동일 기사가 여러 매체로 들어온 경우 1건만
                continue
            seen_urls.add(url)
            if norm:
                seen_titles.add(norm)

            new_articles.append(
                Article(
                    title=title,
                    url=url,
                    source=feed.name,
                    published=_published_iso(entry),
                    summary=_clean(getattr(entry, "summary", "")),
                )
            )

    # 최신순 정렬(발행시각 없는 건 뒤로)
    new_articles.sort(key=lambda a: a.published or "", reverse=True)
    return new_articles[:limit]
