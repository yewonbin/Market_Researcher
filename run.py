#!/usr/bin/env python3
"""AI 보험·금융 트렌드 리서치 Agent — 메인 실행기.

파이프라인: RSS 수집 → 신규 선별 → Gemini 요약/분류/시사점 → HTML 리포트
            → 이메일 + Google Sheets 발송

사용 예:
    python run.py                 # 전체 실행(수집→분석→발송)
    python run.py --dry-run       # 발송 안 함. HTML 만 reports/ 에 저장하고 미리보기
    python run.py --limit 5       # 이번 실행 분석 기사 수 제한
    python run.py --no-sheets     # 시트 저장만 건너뜀
    python run.py --json          # 결과를 JSON 으로 stdout 출력(n8n 연동용)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from src.analyze import analyze
from src.collect import collect
from src.config import load_config
from src.report import build_html, subject_line
from src.state import SeenStore

ROOT = Path(__file__).resolve().parent


def log(msg: str, *, quiet: bool) -> None:
    if not quiet:
        print(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 보험 트렌드 리서치 Agent")
    parser.add_argument("--config", default=None, help="config.yaml 경로")
    parser.add_argument("--limit", type=int, default=None, help="분석 기사 수 상한 override")
    parser.add_argument("--dry-run", action="store_true", help="발송하지 않고 HTML 만 저장")
    parser.add_argument("--no-email", action="store_true", help="이메일 발송 건너뜀")
    parser.add_argument("--no-sheets", action="store_true", help="Google Sheets 저장 건너뜀")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 으로 stdout 출력")
    args = parser.parse_args()

    quiet = args.json  # JSON 모드에서는 stdout 을 깨끗하게 유지
    cfg = load_config(args.config)
    if args.limit is not None:
        cfg.max_articles = args.limit

    if not cfg.gemini_api_key:
        print("ERROR: GEMINI_API_KEY 가 설정되지 않았습니다(.env 확인).", file=sys.stderr)
        return 1

    # 1) 수집 + 신규 선별
    seen = SeenStore()
    log(f"▶ RSS 수집 중… ({len(cfg.feeds)}개 피드)", quiet=quiet)
    articles = collect(cfg.feeds, seen, cfg.max_articles)
    log(f"  신규 기사 {len(articles)}건", quiet=quiet)

    if not articles:
        log("신규 기사가 없습니다. 종료합니다.", quiet=quiet)
        if args.json:
            print(json.dumps({"status": "no_new_articles", "articles": []}, ensure_ascii=False))
        return 0

    # 2) Gemini 분석
    log(f"▶ Gemini 분석 중… (model={cfg.model})", quiet=quiet)
    analyze(articles, cfg)

    # 3) 관련도 필터
    kept = [a for a in articles if a.relevance >= cfg.min_relevance]
    log(f"  관련도 {cfg.min_relevance}+ 통과: {len(kept)}/{len(articles)}건", quiet=quiet)
    if not kept:
        log("관련도 기준을 통과한 기사가 없습니다. 종료합니다.", quiet=quiet)
        if args.json:
            print(json.dumps({"status": "filtered_out", "articles": []}, ensure_ascii=False))
        # 분석은 했으므로 seen 에 기록(재분석 방지)
        if not args.dry_run:
            for a in articles:
                seen.add(a.url)
            seen.save()
        return 0

    # 4) HTML 리포트
    html = build_html(kept, cfg)
    subject = subject_line(kept, cfg)

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    out_path = reports_dir / f"report-{datetime.now():%Y%m%d-%H%M%S}.html"
    out_path.write_text(html, encoding="utf-8")
    log(f"▶ 리포트 저장: {out_path}", quiet=quiet)

    # 5) 발송
    email_sent = False
    sheets_rows = 0

    if args.dry_run:
        log("  (--dry-run) 발송 생략. seen 기록도 남기지 않습니다.", quiet=quiet)
    else:
        # 이메일
        if not args.no_email and cfg.email_enabled:
            try:
                from src.outputs.email_out import send_email

                send_email(cfg, subject, html)
                email_sent = True
                log(f"  ✉  이메일 발송 완료 → {', '.join(cfg.email_to)}", quiet=quiet)
            except Exception as e:  # noqa: BLE001  — 발송 실패가 전체를 막지 않도록
                log(f"  ! 이메일 발송 실패: {e}", quiet=quiet)
        elif not args.no_email:
            log("  (이메일 미설정 — .env 의 SMTP_PASSWORD/EMAIL_* 확인. 건너뜀)", quiet=quiet)

        # Google Sheets
        if not args.no_sheets and cfg.sheets_enabled:
            try:
                from src.outputs.sheets_out import append_to_sheet

                sheets_rows = append_to_sheet(cfg, kept)
                log(f"  📄 Google Sheets {sheets_rows}행 추가", quiet=quiet)
            except Exception as e:  # noqa: BLE001
                log(f"  ! Google Sheets 저장 실패: {e}", quiet=quiet)
        elif not args.no_sheets:
            log("  (Sheets 미설정 — .env 의 GOOGLE_SERVICE_ACCOUNT_FILE/SHEET_ID 확인. 건너뜀)", quiet=quiet)

        # seen 기록(재처리 방지) — 분석한 모든 기사 기준
        for a in articles:
            seen.add(a.url)
        seen.save()

    # 6) JSON 출력(n8n 등 외부 연동)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "subject": subject,
                    "report_path": str(out_path),
                    "email_sent": email_sent,
                    "sheets_rows": sheets_rows,
                    "count": len(kept),
                    "articles": [a.to_dict() for a in kept],
                },
                ensure_ascii=False,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
