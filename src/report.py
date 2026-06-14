"""분석 결과를 카테고리별 HTML 리포트로 만든다."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime

from jinja2 import Environment

from .collect import Article
from .config import Config

# 깔끔한 뉴스레터/리서치 브리프 스타일(이메일 클라이언트 호환 위해 인라인 스타일)
_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#eceae5;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#23252b;-webkit-font-smoothing:antialiased;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;">

    <!-- 헤더 -->
    <div style="padding:34px 40px 24px;border-bottom:3px solid #1a3d6b;">
      <div style="font-size:12px;letter-spacing:2px;color:#8a8f99;text-transform:uppercase;margin-bottom:8px;">Daily Research Brief</div>
      <h1 style="font-size:23px;margin:0;font-weight:700;color:#1a3d6b;letter-spacing:-0.3px;">{{ title }}</h1>
      <div style="color:#8a8f99;font-size:13px;margin-top:8px;">{{ date }}</div>
      <!-- 카테고리 요약 -->
      <div style="margin-top:16px;line-height:2;">
        {% for category, items in groups.items() %}<span style="display:inline-block;font-size:12px;color:#4a4f5a;background:#f1f0ec;border:1px solid #e2e0d9;border-radius:14px;padding:3px 11px;margin:0 4px 4px 0;">{{ category }} <b style="color:#1a3d6b;">{{ items|length }}</b></span>{% endfor %}
      </div>
    </div>

    <!-- 본문 -->
    <div style="padding:8px 40px 16px;">
    {% set ns = namespace(idx=0) %}
    {% for category, items in groups.items() %}
      <div style="margin-top:30px;">
        <div style="font-size:14px;font-weight:700;color:#1a3d6b;border-left:4px solid #c2873f;padding-left:10px;margin-bottom:4px;">
          {{ category }}
        </div>

        {% for a in items %}
        {% set ns.idx = ns.idx + 1 %}
        <div style="padding:18px 0;border-bottom:1px solid #eeece6;">
          <div style="font-size:11px;color:#b9bdc6;font-weight:700;float:left;width:26px;line-height:1.5;">{{ "%02d"|format(ns.idx) }}</div>
          <div style="margin-left:30px;">
            <a href="{{ a.url }}" style="font-size:15.5px;font-weight:600;color:#1a2230;text-decoration:none;line-height:1.45;">{{ a.title }}</a>
            <div style="font-size:11.5px;color:#9a9ea8;margin:5px 0 9px;">
              {{ a.source }}{% if a.published %} · {{ a.published[:10] }}{% endif %}
              <span style="color:{{ '#c2873f' if a.relevance >= 4 else '#b9bdc6' }};margin-left:6px;letter-spacing:1px;">{{ '●' * a.relevance }}{{ '○' * (5 - a.relevance) }}</span>
            </div>
            <p style="font-size:13.5px;line-height:1.6;margin:0;color:#3a3d44;">{{ a.ai_summary }}</p>
            {% if a.business_implication or a.insurer_use_case %}
            <div style="background:#f8f7f3;border-radius:6px;padding:11px 14px;margin-top:11px;font-size:12.5px;line-height:1.6;">
              {% if a.business_implication %}<div style="margin-bottom:{{ '6px' if a.insurer_use_case else '0' }};"><span style="color:#1a3d6b;font-weight:700;">시사점</span> &nbsp;{{ a.business_implication }}</div>{% endif %}
              {% if a.insurer_use_case %}<div><span style="color:#c2873f;font-weight:700;">활용 방안</span> &nbsp;{{ a.insurer_use_case }}</div>{% endif %}
            </div>
            {% endif %}
          </div>
          <div style="clear:both;"></div>
        </div>
        {% endfor %}
      </div>
    {% endfor %}
    </div>

    <!-- 푸터 -->
    <div style="padding:20px 40px 30px;border-top:1px solid #eeece6;color:#b3b7bf;font-size:11px;text-align:center;line-height:1.6;">
      신규 {{ total }}건 · 카테고리 {{ groups|length }}개<br>
      AI 보험·금융 트렌드 리서치 Agent · {{ model }}
    </div>

  </div>
</body>
</html>"""


def _group_by_category(
    articles: list[Article], categories: list[str]
) -> "OrderedDict[str, list[Article]]":
    """config 의 카테고리 순서를 유지하며 그룹핑. 각 그룹은 관련도 높은 순."""
    groups: "OrderedDict[str, list[Article]]" = OrderedDict()
    for cat in categories:
        bucket = [a for a in articles if a.category == cat]
        if bucket:
            bucket.sort(key=lambda a: a.relevance, reverse=True)
            groups[cat] = bucket
    leftover = [a for a in articles if a.category not in categories]
    if leftover:
        groups.setdefault("기타", []).extend(leftover)
    return groups


def build_html(articles: list[Article], cfg: Config) -> str:
    groups = _group_by_category(articles, cfg.categories)
    env = Environment(autoescape=True)
    template = env.from_string(_TEMPLATE)
    return template.render(
        title=cfg.report_title,
        date=datetime.now().strftime("%Y년 %m월 %d일 (%a)"),
        total=len(articles),
        groups=groups,
        model=cfg.model,
    )


def subject_line(articles: list[Article], cfg: Config) -> str:
    return f"[{cfg.report_title}] {datetime.now():%Y-%m-%d} · 신규 {len(articles)}건"
