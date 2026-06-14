"""이미 처리한 기사를 기억하는 단순 dedup 저장소 (data/seen.json)."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEN_PATH = ROOT / "data" / "seen.json"

# 이 일수보다 오래된 기록은 정리한다(파일이 무한히 커지지 않도록).
_RETENTION_DAYS = 45


def _key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


class SeenStore:
    def __init__(self, path: Path = SEEN_PATH):
        self.path = path
        self._data: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        # 오래된 항목 정리
        cutoff = time.time() - _RETENTION_DAYS * 86400
        self._data = {k: v for k, v in self._data.items() if v >= cutoff}

    def has(self, url: str) -> bool:
        return _key(url) in self._data

    def add(self, url: str) -> None:
        self._data[_key(url)] = time.time()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False), encoding="utf-8"
        )
