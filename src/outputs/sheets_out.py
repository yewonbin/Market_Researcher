"""분석 결과를 Google Sheets 에 누적 저장(선택 기능)."""
from __future__ import annotations

from datetime import datetime

from ..collect import Article
from ..config import Config

_HEADER = [
    "수집일시",
    "카테고리",
    "관련도",
    "제목",
    "요약",
    "비즈니스 시사점",
    "보험사 적용 Use Case",
    "출처",
    "발행일",
    "URL",
]


def append_to_sheet(cfg: Config, articles: list[Article]) -> int:
    """기사들을 워크시트 맨 아래에 한 행씩 추가. 추가한 행 수를 반환.

    gspread / google-auth 가 설치돼 있어야 한다(requirements.txt 포함).
    """
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(
        cfg.google_service_account_file, scopes=scopes
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(cfg.sheet_id)

    try:
        ws = sh.worksheet(cfg.sheet_worksheet)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=cfg.sheet_worksheet, rows=1000, cols=len(_HEADER))

    # 헤더가 없으면 먼저 기록
    if not ws.get_all_values():
        ws.append_row(_HEADER, value_input_option="USER_ENTERED")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = [
        [
            now,
            a.category,
            a.relevance,
            a.title,
            a.ai_summary,
            a.business_implication,
            a.insurer_use_case,
            a.source,
            a.published[:10] if a.published else "",
            a.url,
        ]
        for a in articles
    ]
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)
