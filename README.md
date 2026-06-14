# AI 보험·금융 트렌드 리서치 자동화 Agent

보험·AI·금융 디지털 혁신 뉴스를 매일 자동으로 **수집 → 분류 → 요약 → 비즈니스 시사점 도출 → 발송**하는 에이전트입니다.

```
RSS 피드 ─▶ 기사 수집 ─▶ Gemini 요약·분류 ─▶ 보험사 Use Case 도출 ─▶ 리포트
                                                              ├─▶ 📧 이메일(HTML)
                                                              └─▶ 📄 Google Sheets(누적)
```

- **수집**: RSS 피드(Google News 키워드 검색 + 업계 매체)
- **분석**: Google **Gemini(무료 등급)** 가 기사별로 카테고리 분류 + 한국어 요약 + 비즈니스 시사점 + 보험사 적용 Use Case + 관련도(1~5) 생성 (structured output)
- **발송**: 이메일(Gmail SMTP) + Google Sheets 누적 저장
- **자동화**: cron 또는 n8n 으로 매일 자동 실행

분류 카테고리(기본): `LLM/생성형 AI`, `보험금 청구 자동화`, `언더라이팅/인수심사`, `콜센터/상담 AI`, `RPA/업무 자동화`, `사기탐지(Fraud Detection)`, `헬스케어/디지털 헬스`, `데이터/마이데이터`, `규제/컴플라이언스`, `기타`

---

## 1. 설치

```bash
cd /mnt/c/Users/ybin002/Documents/Market_researcher

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. 설정

```bash
cp .env.example .env
```

`.env` 를 열어 채웁니다 (자세한 안내는 파일 안 주석 참고):

| 항목 | 필수 | 설명 |
|------|:---:|------|
| `GEMINI_API_KEY` | ✅ | **무료** Gemini API 키 ([발급](https://aistudio.google.com/apikey) — 구글 로그인 후 "Create API key") |
| `SMTP_PASSWORD` | 이메일용 | Gmail **앱 비밀번호** 16자리 ([발급](https://myaccount.google.com/apppasswords)) |
| `EMAIL_FROM` / `EMAIL_TO` | 이메일용 | 발신/수신 주소 (기본 `prongs0423@gmail.com`) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` / `SHEET_ID` | 시트용 | 서비스 계정 JSON 경로 + 스프레드시트 ID |

> 이메일/시트 설정값이 비어 있으면 해당 발송 단계는 자동으로 **건너뜁니다**. 먼저 `--dry-run` 으로 동작만 확인해도 됩니다.

수집 피드·카테고리·모델·기사 수 상한 등은 [`config.yaml`](config.yaml) 에서 조정합니다.

## 3. 실행

```bash
# 발송 없이 동작 확인 (HTML 만 reports/ 에 저장)
python run.py --dry-run

# 실제 실행 (수집→분석→이메일+시트 발송)
python run.py

# 옵션
python run.py --limit 5      # 이번 실행 분석 기사 수 제한(비용 테스트)
python run.py --no-sheets    # 시트 저장만 생략
python run.py --json         # 결과를 JSON 으로 stdout 출력(n8n/스크립트 연동)
```

처음 실행 시 신규 기사를 모두 분석하고, 이후에는 `data/seen.json` 으로 **이미 본 기사를 건너뛰어** 중복 발송을 방지합니다.

---

## 4. 매일 자동 실행

### 방법 A — cron (가장 간단)

```bash
crontab -e
# 매일 오전 8시(평일) 실행:
0 8 * * 1-5 cd /opt/market_researcher && /opt/market_researcher/.venv/bin/python run.py >> /var/log/insur-agent.log 2>&1
```

### 방법 B — n8n

[`n8n/workflow.json`](n8n/workflow.json) 을 n8n 에 import 하세요. 구조:

```
[Schedule Trigger] ─▶ [Execute Command: python run.py --json] ─▶ [Code: 결과 파싱]
```

`run.py` 가 전체 파이프라인(수집·분석·발송)을 수행하고 결과를 JSON 으로 반환하므로, n8n 은 **스케줄링·모니터링·후속 알림(Slack 등)** 만 담당하면 됩니다. Execute Command 노드의 경로(`/opt/market_researcher`)를 실제 배포 위치로 바꾸세요.

> n8n 의 네이티브 노드(RSS Read → OpenAI → Google Sheets)로 플로우를 직접 구성할 수도 있지만, 본 저장소는 **코어 로직을 Python 에 두고 n8n 은 오케스트레이션만** 맡기는 방식을 권장합니다. 분류 enum·프롬프트·dedup·재시도 로직을 한곳에서 관리할 수 있어 유지보수가 쉽습니다.

---

## 5. 구조

```
Market_researcher/
├── run.py                 # 메인 실행기(오케스트레이터 / CLI)
├── config.yaml            # 피드·카테고리·모델·상한 설정
├── .env.example           # API 키·SMTP·시트 자격증명 템플릿
├── requirements.txt
├── src/
│   ├── config.py          # 설정/환경변수 로딩
│   ├── collect.py         # RSS 수집 + 신규 선별
│   ├── analyze.py         # Gemini 요약·분류·시사점(structured output)
│   ├── report.py          # 카테고리별 HTML 리포트
│   ├── state.py           # dedup 저장소(seen.json)
│   └── outputs/
│       ├── email_out.py   # Gmail SMTP 발송
│       └── sheets_out.py  # Google Sheets 누적 저장
└── n8n/workflow.json      # n8n 스케줄 워크플로우
```

## 비용 메모

- **무료입니다.** 기본 모델 `gemini-2.0-flash` 는 Google AI Studio **무료 등급**으로 동작하며, 별도 결제수단 등록 없이 시작할 수 있습니다.
- **분당 요청 한도(RPM)**: 무료 등급은 분당 요청 수가 제한됩니다(2.0-flash 약 15회, 2.5-flash 약 5회). Agent 는 `config.yaml` 의 `rpm` 값(기본 12)에 맞춰 자동으로 **요청 간격을 띄우고, 429(한도 초과) 시 자동 재시도**하므로 기사가 누락되지 않습니다. 모델을 바꾸면 `rpm` 도 그에 맞게 낮춰주세요(2.5-flash → 4).
- **일일 한도**: 무료 등급엔 하루 요청 한도도 있습니다. 부족하면 `config.yaml` 의 `max_articles` 를 줄이세요.
- 더 높은 품질이 필요하고 소액 과금이 괜찮다면, 분석 모듈을 Claude(`claude-haiku-4-5`, 월 ~2,700원 수준)로 바꿀 수도 있습니다. 필요하면 알려주세요.
