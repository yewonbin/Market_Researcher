"""config.yaml + .env 로딩."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Feed:
    name: str
    url: str


@dataclass
class Config:
    # config.yaml
    model: str
    rpm: int
    max_articles: int
    min_relevance: int
    report_title: str
    feeds: list[Feed]
    categories: list[str]
    # .env
    gemini_api_key: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: list[str] = field(default_factory=list)
    google_service_account_file: str = ""
    sheet_id: str = ""
    sheet_worksheet: str = "리포트"

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_password and self.email_from and self.email_to)

    @property
    def sheets_enabled(self) -> bool:
        return bool(self.google_service_account_file and self.sheet_id)


def load_config(config_path: str | os.PathLike | None = None) -> Config:
    """config.yaml 과 .env 를 읽어 Config 를 만든다."""
    load_dotenv(ROOT / ".env")

    path = Path(config_path) if config_path else ROOT / "config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    feeds = [Feed(name=f["name"], url=f["url"]) for f in raw.get("feeds", [])]

    email_to_raw = os.getenv("EMAIL_TO", "")
    email_to = [e.strip() for e in email_to_raw.split(",") if e.strip()]

    return Config(
        model=raw.get("model", "gemini-2.0-flash"),
        rpm=int(raw.get("rpm", 12)),
        max_articles=int(raw.get("max_articles", 25)),
        min_relevance=int(raw.get("min_relevance", 2)),
        report_title=raw.get("report_title", "AI 보험·금융 트렌드 리서치"),
        feeds=feeds,
        categories=raw.get("categories", []),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        email_to=email_to,
        google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", ""),
        sheet_id=os.getenv("SHEET_ID", ""),
        sheet_worksheet=os.getenv("SHEET_WORKSHEET", "리포트"),
    )
