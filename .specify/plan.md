# Plan: 교량 수량집계표 자동화 시스템

> specify.md의 요구사항을 어떻게 구현할지에 대한 기술 계획.

---

## 1. 아키텍처

### 레이어 구조
```
┌──────────────────────────────────────────────┐
│  UI Layer (Streamlit)                        │
│  - app.py                                    │
│  - pages/ (multi-page app)                   │
└──────────────────────────────────────────────┘
              ↓ ↑
┌──────────────────────────────────────────────┐
│  Orchestration Layer                         │
│  - services/pipeline.py (조정자)              │
│  - services/session.py (상태 관리)            │
└──────────────────────────────────────────────┘
              ↓ ↑
┌──────────────────────────────────────────────┐
│  Domain Layer (핵심 로직)                    │
│  - core/parser.py      (엑셀 파싱)          │
│  - core/normalizer.py  (용어 정규화)          │
│  - core/aggregator.py  (집계)               │
│  - core/validator.py   (검증)               │
│  - core/reporter.py    (Excel 출력)          │
└──────────────────────────────────────────────┘
              ↓ ↑
┌──────────────────────────────────────────────┐
│  Infrastructure Layer                        │
│  - ai/claude_client.py (Claude API 래퍼)      │
│  - ai/prompts/         (프롬프트 템플릿)      │
│  - storage/terminology.py (사전 로드/저장)    │
│  - storage/converter.py  (.xls → .xlsx)      │
└──────────────────────────────────────────────┘
              ↓ ↑
┌──────────────────────────────────────────────┐
│  Data (YAML/JSON)                            │
│  - terminology.yaml (용어 사전)              │
│  - project_configs/  (프로젝트별 설정)        │
│  - templates/        (출력 템플릿)           │
└──────────────────────────────────────────────┘
```

### 데이터 플로우
```
[사용자 업로드]
    → Parser (Record 리스트)
    → Normalizer (Record + normalized 필드)
    → [미매칭 존재 시] AI Fallback (사용자 검토)
    → Normalizer (재실행, 업데이트된 사전으로)
    → Aggregator (AggregateRow 리스트)
    → Validator (검증 결과)
    → Reporter (Excel 파일)
    → [사용자 다운로드]
```

---

## 2. 프로젝트 구조

```
quantity-aggregator/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── .gitignore
│
├── src/quantity_aggregator/
│   ├── __init__.py
│   ├── launcher.py              # ⭐ Phase 6 - exe 진입점 (Streamlit 서버 + 브라우저)
│   │
│   ├── core/                    # 순수 도메인 로직 (외부 의존성 최소)
│   │   ├── __init__.py
│   │   ├── models.py            # Pydantic 모델 (Record, AggregateRow 등)
│   │   ├── parser.py
│   │   ├── normalizer.py
│   │   ├── aggregator.py
│   │   ├── validator.py
│   │   └── reporter.py
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── claude_client.py     # Anthropic SDK 래퍼
│   │   ├── schemas.py           # Tool use JSON 스키마
│   │   └── prompts/
│   │       ├── system.md
│   │       └── work_type_mapping.md
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── terminology.py       # YAML 로드/저장
│   │   ├── converter.py         # .xls → .xlsx 변환
│   │   └── templates.py         # 출력 템플릿 관리
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pipeline.py          # 전체 플로우 조정
│   │   └── session.py           # Streamlit 세션 상태
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── app.py               # Streamlit 메인
│   │   └── pages/
│   │       ├── 01_upload.py
│   │       ├── 02_classify.py
│   │       ├── 03_review.py
│   │       └── 04_result.py
│   │
│   └── config.py                # 환경 변수, 경로 처리 (frozen 모드 대응)
│
├── data/                        # ⭐ exe 배포 시 외부에 둠 (사전 업데이트 자유도)
│   ├── terminology.yaml         # 용어 사전 (누적 자산)
│   ├── project_configs/
│   │   └── default.yaml
│   └── templates/
│       └── total_summary_template.xlsx
│
├── build/                       # ⭐ Phase 6 - exe 빌드 관련
│   ├── app.spec                 # PyInstaller 설정 (hidden imports, datas)
│   ├── build_exe.py             # 빌드 자동화 스크립트
│   └── version_info.txt         # exe 버전 메타데이터 (Windows)
│
├── dist/                        # ⭐ 빌드 결과물 (.gitignore)
│   └── quantity-aggregator/     # onedir 결과
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   └── galjeon7/            # 갈전7교 실제 파일 (익명화)
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_normalizer.py
│   │   ├── test_aggregator.py
│   │   └── test_reporter.py
│   ├── integration/
│   │   └── test_pipeline.py
│   └── regression/
│       └── test_galjeon7.py     # 수치 회귀 테스트
│
└── scripts/
    ├── run_app.sh               # streamlit run 편의
    └── bootstrap_terminology.py # 신규 프로젝트용 사전 초기화
```

---

## 3. 기술 선택 (Rationale)

### 3.1 Streamlit 선택
- **장점:** 파일 업로드, 진행 표시, 데이터프레임 미리보기 → 모두 기본 제공
- **대안 비교:**
  - Flask: 프론트엔드 별도 작성 필요 → 초기 비용 5배
  - Gradio: 가능하지만 다단계 폼 UX가 Streamlit 대비 제약적
  - FastAPI + Jinja: 과도한 복잡도
- **결정:** Streamlit (MVP 단계에서 압도적 유리)

### 3.2 uv 선택
- **장점:** pip 대비 10배 빠른 설치, `pyproject.toml` 네이티브 지원
- **결정:** uv

### 3.3 Claude API 선택
- 긴 구조화 데이터 처리 강함
- **Tool use**로 JSON 스키마 강제 가능 → 파싱 실패 제로
- **Prompt caching**으로 공통 컨텍스트(용어 사전) 90% 할인
- 한국어 토목 용어 이해도 충분

### 3.4 Pydantic 선택
- Record, AggregateRow 등 데이터 모델 타입 안전성
- Claude API `input_schema`로 바로 변환 가능 (`model_json_schema()`)
- 직렬화(JSON dump) 내장

---

## 4. 핵심 알고리즘 결정

### 4.1 집계표 시트 식별
```python
def find_aggregate_sheets(wb, terminology):
    candidates = [s for s in wb.sheetnames if "집계" in s or "총괄" in s]
    # 부분 집계표(본체/방호벽 개별)는 전체 집계표가 있으면 제외 → 중복 방지
    has_full = any("교량" in s or "수량집계표" in s for s in candidates)
    if has_full:
        candidates = [s for s in candidates if not any(p in s for p in ["본체", "방호벽", "접속슬래브"])]
    return candidates
```

### 4.2 규격 상속 (병합 셀 대응)
공종이 같은데 규격1이 빈칸이면 직전 규격을 상속.
공종이 바뀌면 리셋.

### 4.3 AI Fallback 배치 처리
```python
async def map_unmatched(unmatched_items, terminology):
    """미매칭 항목을 배치로 Claude API에 전달"""
    # 1. 프롬프트 = 시스템(용어 사전 전체, 캐시) + 유저(미매칭 배치)
    # 2. Tool use: submit_mappings(list[Mapping])
    # 3. 응답 파싱 → UI 검토 큐로
```

한 번에 최대 50개 항목을 배치로 전달하여 호출 수 최소화.

### 4.4 출력 전략
**MVP v1:** 새 워크북 생성 (지금 prototype 방식)
**MVP v2+:** 00번 템플릿을 복제 + 값만 채움 (서식 보존)

---

## 5. 개발 단계

### Phase 0: 프로젝트 셋업 (0.5일)
- `uv init quantity-aggregator`
- `pyproject.toml` 의존성 정의
- 디렉토리 구조 생성
- `.env.example`, `.gitignore` 설정
- 갈전7교 픽스처를 `tests/fixtures/` 로 이동 (익명화)

### Phase 1: 프로토타입 이식 (1일)
- 현재 prototype의 `parser/normalizer/aggregator/reporter` 를 src 구조로 이식
- Pydantic 모델 정의
- 단위 테스트 작성 (각 모듈당 5개 이상)
- 갈전7교 회귀 테스트 1개 (100% 통과 목표)

### Phase 2: AI Fallback 연결 (1.5일)
- Claude API 클라이언트 구현
- Tool use 스키마 정의 (`schemas.py`)
- 프롬프트 템플릿 작성
- 배치 처리 로직
- Mock 테스트 + 실제 호출 integration 테스트

### Phase 3: Streamlit UI (1.5일)
- 4개 페이지 레이아웃
- 세션 상태 관리
- 파일 업로드 → 파싱 → 매핑 검토 → 결과 플로우
- AI 매핑 승인/수정/거부 UX

### Phase 4: 검증 & 품질 (1일)
- 검증 리포트 생성기 강화
- 에러 핸들링 (빈 파일, 깨진 파일 등)
- 로깅 (파이프라인 전체)
- README / 사용법 문서

### Phase 5: 사내 템플릿 대응 (1일, MVP 후속)
- 00번 서식을 템플릿으로 등록
- 셀 위치 매핑 테이블 관리
- 서식 보존 출력

### Phase 6: exe 패키징 및 배포 (1.5일)
**목표:** Python 미설치 PC에서도 더블클릭만으로 실행 가능한 배포물 제작.
**배포 대상:** 사내 토목 설계 엔지니어 (비개발자)

**빌드 방식:** PyInstaller + onedir + Streamlit (웹 UI 유지)

**실행 UX:**
```
[quantity-aggregator.exe 더블클릭]
  → 콘솔 창 (Streamlit 서버 시작 메시지)
  → 기본 브라우저 자동 열림 (http://localhost:8501)
  → 엔지니어 파일 업로드 → 결과 다운로드
  → 콘솔 창 닫으면 종료
```

**핵심 구성 요소:**
- `src/quantity_aggregator/launcher.py`: exe 진입점
  - Streamlit 서버 서브프로세스 기동
  - `webbrowser.open()`으로 브라우저 자동 열기
  - 종료 시 서버 정리
- `build/app.spec`: PyInstaller 설정
  - Streamlit 정적 리소스 포함
  - hidden imports 명시 (`pkg_resources`, `importlib.metadata`, `streamlit.web` 등)
  - 데이터 파일(`data/`, `templates/`) 외부 분리
- `build/build_exe.py`: 빌드 자동화 스크립트

**구성 파일의 외부화 (중요):**
사전·설정 파일은 **exe 내부에 묶지 않고** 같은 폴더에 둠.
이유: 사전 업데이트 시 재빌드 불필요 + 사용자가 직접 편집 가능.

```
quantity-aggregator-v0.1/         ← 배포 zip 내용
├── quantity-aggregator.exe       ← 진입점
├── _internal/                    ← PyInstaller 의존성
├── data/
│   ├── terminology.yaml          ← 사용자 편집 가능
│   └── project_configs/
├── templates/                    ← Phase 5 산출물
├── outputs/                      ← 결과 저장 (자동 생성)
├── .env.example
└── README.txt                    ← 설치 / 사용 / API 키 안내
```

**주요 제약 및 대응:**
| 항목 | 제약 | 대응 |
|------|------|------|
| 파일 크기 | 250~400 MB | onedir 방식, 사내 공유폴더 zip 배포 |
| 첫 실행 속도 | 2~5초 | onedir로 압축 해제 비용 제거 |
| `.xls` 변환 | LibreOffice 번들 불가 | `xlrd`로 직접 읽기 (변환 없이 처리) |
| 사내 백신 오탐 | 발생 가능성 있음 | IT팀에 예외 등록 요청 |
| API 키 보안 | exe 하드코딩 금지 | 아래 전략 중 택1 |

**API 키 배포 전략 (택1):**
1. **사용자 입력 방식:** 최초 실행 시 UI에서 입력 → `%APPDATA%/quantity-aggregator/config.ini` 저장
2. **사내 프록시 방식:** 사내 API 프록시 서버 구축 → exe는 프록시 URL만 호출
3. **IT팀 동봉 방식:** `.env` 파일을 IT팀이 직접 배포 시 동봉 (소규모 팀 한정)

**테스트 환경:**
- Windows 10 / Windows 11 (사내 표준 OS 가정)
- Python 미설치 가상머신에서 동작 확인 필수
- 사내망 환경(프록시·인증서)에서의 Anthropic API 호출 검증

**총 예상: 8일 (1인 기준, Phase 0~6 전체)**

---

## 6. 의존성 및 환경

### pyproject.toml (핵심)
```toml
[project]
name = "quantity-aggregator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "streamlit>=1.36",
  "openpyxl>=3.1",
  "xlrd>=2.0",
  "pandas>=2.2",
  "pydantic>=2.7",
  "anthropic>=0.39",
  "pyyaml>=6.0",
  "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "ruff>=0.5",
  "mypy>=1.10",
]

build = [
  "pyinstaller>=6.10",            # ⭐ Phase 6 - exe 빌드
]
```

**빌드 명령:**
```bash
# Phase 6 - exe 생성
uv sync --group build
uv run pyinstaller build/app.spec --clean
# 결과: dist/quantity-aggregator/quantity-aggregator.exe
```

### 환경 변수 (`.env`)
```
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-haiku-4-5-20251001
LOG_LEVEL=INFO
MAX_UPLOAD_MB=30
```

### 실행
```bash
# 개발
uv sync
uv run streamlit run src/quantity_aggregator/ui/app.py

# 테스트
uv run pytest tests/ -v
uv run pytest tests/regression/ -v  # 갈전7교 회귀 테스트
```

---

## 7. 리스크 및 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 다른 프로젝트의 시트 구조가 갈전7교와 크게 다름 | 높음 | Phase 4 이후 실제 다른 프로젝트 2~3건 테스트 후 파서 보강 |
| AI 호출 지연 (10초 이상) | 중간 | 배치 처리 + UI 진행 표시로 완화 |
| 방호벽/접속슬래브 합산 vs 분리 정책 충돌 | 중간 | `project_config.yaml`로 사용자 선택 가능하게 |
| 미매칭 항목 대량 발생 | 중간 | 용어 사전을 프로젝트 초기에 검토·보강하는 워크플로우 마련 |
| 00번 템플릿 서식 복잡도 (14시트, 병합셀 다수) | 낮음 | MVP v1은 자체 서식으로 생성, v2에서 템플릿 방식 도입 |
| **exe 빌드 시 Streamlit 정적 리소스 누락** | 중간 | `app.spec`에 `--collect-all streamlit` 옵션 또는 datas 명시 |
| **사내 백신의 PyInstaller exe 오탐** | 중간 | 사내 IT팀에 사전 협의 + 코드서명 인증서 검토 |
| **사내망에서 Anthropic API 차단** | 높음 | Phase 6 시작 전 IT팀에 도메인(api.anthropic.com) 화이트리스트 요청 |
| **사용자 PC의 Windows 버전 차이** | 낮음 | Win10/Win11 양쪽에서 빌드물 동작 확인 |

---

## 8. 측정 지표

- **회귀 테스트 통과율** (갈전7교 15 케이스 기준)
- **평균 처리 시간** (파이프라인 전체)
- **평균 AI 호출 수** (1회 집계당)
- **미매칭률** (전체 레코드 대비 AI fallback 필요 비율)
- **사용자 개입 횟수** (UI 매핑 검토 단계에서의 수정 건수)
