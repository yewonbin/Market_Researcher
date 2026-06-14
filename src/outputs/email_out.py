"""HTML 리포트를 Gmail SMTP 로 발송."""
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import Config


def send_email(cfg: Config, subject: str, html: str) -> None:
    """cfg.email_to 의 모든 수신자에게 HTML 메일을 보낸다."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.email_from
    msg["To"] = ", ".join(cfg.email_to)
    msg.attach(MIMEText("HTML 메일입니다. 텍스트 클라이언트에서는 표시되지 않습니다.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
        server.starttls(context=context)
        server.login(cfg.smtp_user or cfg.email_from, cfg.smtp_password)
        server.sendmail(cfg.email_from, cfg.email_to, msg.as_string())
