# Tasks: 교량 수량집계표 자동화 시스템

> plan.md의 단계를 실제 작업 단위로 쪼갠 체크리스트.
> 각 작업은 독립적으로 완료 가능하며 완료 기준이 명시되어 있다.

---

## Phase 0: 프로젝트 셋업 (0.5일)

- [ ] **T0.1** `uv init quantity-aggregator`로 프로젝트 스캐폴딩
- [ ] **T0.2** `pyproject.toml`에 의존성 정의 (plan.md 섹션 6 참조)
- [ ] **T0.3** plan.md의 디렉토리 구조 생성 (`src/`, `tests/`, `data/`, `scripts/`)
- [ ] **T0.4** `.gitignore` (.env, __pycache__, .venv, *.xlsx~$*, outputs/)
- [ ] **T0.5** `.env.example` 템플릿
- [ ] **T0.6** `data/terminology.yaml` 복사 (프로토타입의 사전 이식)
- [ ] **T0.7** `tests/fixtures/galjeon7/`에 5개 입력 파일 + 1개 예상 출력 복사
  - 파일명은 실제 그대로 유지 (파서가 어차피 읽음)
  - **프로젝트 식별자(현장명/발주처)가 있으면 제거**
- [ ] **T0.8** README.md 초안 (설치/실행 방법)

**완료 기준:** `uv sync` 성공, `uv run python -c "import quantity_aggregator"` 성공

---

## Phase 1: 프로토타입 이식 (1일)

### Models
- [ ] **T1.1** `core/models.py`에 Pydantic 모델 정의
  - `Quantities` (dict wrapper)
  - `NormalizedRecord`
  - `Record` (raw 필드 + normalized 옵션)
  - `AggregateRow`
  - `ValidationResult`

### Storage
- [ ] **T1.2** `storage/terminology.py`
  - `load_terminology(path) -> Terminology` (Pydantic)
  - `save_terminology(term, path)`
- [ ] **T1.3** `storage/converter.py`
  - `.xls → .xlsx` 변환 (LibreOffice 서브프로세스 또는 xlrd로 직접 읽기)

### Parser
- [ ] **T1.4** `core/parser.py` 이식 (prototype/parser.py 기반)
  - 함수 시그니처 Pydantic 모델로 변경
  - 내부 상태 의존 제거 (순수 함수화)
- [ ] **T1.5** 테스트 `tests/unit/test_parser.py`
  - 집계 시트 식별
  - 헤더 행 탐지 (2가지 레이아웃)
  - 규격 상속
  - 소계 행 제외
  - 빈 파일 처리

### Normalizer
- [ ] **T1.6** `core/normalizer.py` 이식
- [ ] **T1.7** 테스트 `tests/unit/test_normalizer.py`
  - 단위 매칭 (모든 변형)
  - 공종 매칭
  - 미매칭 수집
  - 구조물 `aggregate_into` 로직

### Aggregator
- [ ] **T1.8** `core/aggregator.py` 이식
- [ ] **T1.9** 테스트 `tests/unit/test_aggregator.py`
  - 카테고리별 집계
  - 동일 키 합산
  - 빈 입력 처리

### Validator
- [ ] **T1.10** `core/validator.py` 신규 작성
  - 원본 소계 vs 재계산 비교
  - 허용 오차(epsilon) 매개변수화

### Reporter
- [ ] **T1.11** `core/reporter.py` 이식
  - 시트별 write 함수 분리
  - 스타일을 상수로 분리
- [ ] **T1.12** 테스트 `tests/unit/test_reporter.py`
  - 시트 생성
  - 스타일 적용
  - 숫자 포맷

### Regression
- [ ] **T1.13** `tests/regression/test_galjeon7.py`
  - 전체 파이프라인 실행 → 15개 검증 케이스 모두 통과
  - `pytest tests/regression/`가 100% 성공

**완료 기준:** 회귀 테스트 100% 통과, 단위 테스트 커버리지 70% 이상

---

## Phase 2: AI Fallback 연결 (1.5일)

### Claude Client
- [ ] **T2.1** `ai/claude_client.py`
  - `anthropic.Anthropic()` 래퍼
  - Prompt caching 설정
  - 에러 핸들링 + 재시도 (tenacity)
  - 토큰 사용량 로깅

### Schemas
- [ ] **T2.2** `ai/schemas.py` Pydantic 스키마
  - `WorkTypeMappingRequest`, `WorkTypeMappingResponse`
  - Tool use용 JSON Schema 자동 생성

### Prompts
- [ ] **T2.3** `ai/prompts/system.md` 시스템 프롬프트
  - 역할: 토목 수량 매핑 전문가
  - 규칙: 모르면 모른다고 답할 것
- [ ] **T2.4** `ai/prompts/work_type_mapping.md` 공종 매핑 프롬프트
  - 입력: 용어 사전 요약 + 미매칭 항목 리스트
  - 출력: 각 항목에 대한 표준 공종명 제안 + 신뢰도

### Pipeline 통합
- [ ] **T2.5** `services/pipeline.py`에 AI 단계 추가
  - Normalizer 1차 → 미매칭 수집 → Claude → 매핑 적용 → Normalizer 2차
- [ ] **T2.6** 테스트 (mock 기반)
  - Mock 응답으로 전체 플로우 검증
  - 재시도 로직
  - 토큰 로깅

### Integration Test
- [ ] **T2.7** `tests/integration/test_ai_mapping.py`
  - 실제 API 호출 (CI에서는 skip, 로컬 수동 실행)
  - 갈전7교에서 일부 공종을 사전에서 지운 후 AI로 복원 성공 여부

**완료 기준:** Mock 테스트 100%, 실제 호출로 미매칭 5개 중 4개 이상 복원

---

## Phase 3: Streamlit UI (1.5일)

### 기본 구조
- [ ] **T3.1** `ui/app.py` 진입점
  - 타이틀, 사이드바 메뉴
  - `st.session_state` 초기화
- [ ] **T3.2** `services/session.py` 세션 상태 모델 정의

### 페이지 1: 업로드
- [ ] **T3.3** `ui/pages/01_upload.py`
  - 프로젝트명 입력
  - 다중 파일 업로드
  - 파일 크기 검증
  - 업로드 파일을 임시 디렉토리에 저장
  - "다음" 버튼 → 세션에 파일 경로 저장

### 페이지 2: 시트 분류 확인
- [ ] **T3.4** `ui/pages/02_classify.py`
  - 각 파일의 시트 목록 표시
  - 자동 분류 결과 (집계표/산출근거/간지)
  - 수정 가능 (라디오)
  - "파싱 & 정규화" 버튼

### 페이지 3: 매핑 검토
- [ ] **T3.5** `ui/pages/03_review.py`
  - 성공 매핑 요약
  - 미매칭 항목 테이블
  - AI 제안 호출 버튼
  - 각 항목 승인/수정/거부 UI
  - "집계 실행" 버튼

### 페이지 4: 결과
- [ ] **T3.6** `ui/pages/04_result.py`
  - 각 집계 시트 미리보기 (st.dataframe)
  - 검증 리포트 요약 지표
  - Excel 다운로드 버튼
  - "사전에 반영" 버튼 → YAML에 승인된 매핑 추가

### UX 폴리싱
- [ ] **T3.7** 진행 상황 표시 (st.progress, st.status)
- [ ] **T3.8** 에러 메시지 친절화
- [ ] **T3.9** 각 페이지에 "이전 단계로" 버튼

**완료 기준:** 갈전7교 파일 5개 업로드 → 완성된 Excel 다운로드까지 60초 이내

---

## Phase 4: 검증 & 품질 (1일)

### 검증 강화
- [ ] **T4.1** 원본 소계 추출 기능 (입력에서 '계' 행 별도 수집)
- [ ] **T4.2** 재계산값과 비교 → 검증 리포트 시트 강화
- [ ] **T4.3** 누락 감지 (입력에 있으나 출력에 없는 항목)

### 에러 처리
- [ ] **T4.4** 빈 파일 / 깨진 파일 / 시트 없음
- [ ] **T4.5** API 실패 (네트워크/인증/rate limit)
- [ ] **T4.6** 사용자에게 유의미한 에러 메시지 노출

### 로깅
- [ ] **T4.7** 구조적 로깅 (structlog 또는 표준 logging)
- [ ] **T4.8** 파이프라인 각 단계의 입출력 카운트 기록
- [ ] **T4.9** 비용 추적: 누적 토큰 사용량

### 문서
- [ ] **T4.10** README.md 완성 (스크린샷 포함)
- [ ] **T4.11** CHANGELOG.md
- [ ] **T4.12** 용어 사전 보강 가이드 (docs/terminology_guide.md)

**완료 기준:** 실제 사내 다른 프로젝트 1건 투입 후 문제 없이 완료

---

## Phase 5 (후속): 사내 템플릿 대응 (1일)

- [ ] **T5.1** 00번 파일을 분석하여 셀 위치 매핑 JSON 생성
- [ ] **T5.2** 템플릿 복제 기반 출력기 구현
- [ ] **T5.3** 원본 서식/수식/병합 유지 검증
- [ ] **T5.4** 기존 MVP v1 출력과 결과 수치 동일성 확인

---

## Phase 6 (배포): exe 패키징 (1.5일)

> 목표: Python 미설치 PC에서 더블클릭만으로 실행 가능한 단일 폴더 배포물.
> 전제: Phase 0~4가 완료되어 Streamlit UI가 동작하는 상태.

### 6.1 사전 준비
- [ ] **T6.0** 사내 IT팀에 사전 협의
  - `api.anthropic.com` 도메인 화이트리스트 요청
  - 사내 백신의 PyInstaller exe 정책 확인
  - 코드서명 인증서 보유 여부 확인 (없어도 진행 가능)
- [ ] **T6.0.1** 배포 대상 OS 명세 확정 (Win10 / Win11 / 둘 다)

### 6.2 진입점 (launcher) 구현
- [ ] **T6.1** `src/quantity_aggregator/launcher.py` 작성
  - PyInstaller frozen 모드 감지 (`sys.frozen`, `sys._MEIPASS`)
  - Streamlit 서버를 서브프로세스로 기동
  - 서버 기동 대기 (포트 헬스체크 또는 sleep)
  - `webbrowser.open()`으로 기본 브라우저 자동 열기
  - 종료 시 서브프로세스 정리 (KeyboardInterrupt, atexit)
- [ ] **T6.2** `config.py`에 경로 처리 추가
  - frozen 모드: exe 옆의 `data/`, `templates/` 참조
  - dev 모드: 프로젝트 루트의 `data/`, `templates/` 참조
- [ ] **T6.3** Streamlit 페이지 모듈을 절대 경로로 참조 가능하도록 수정
  - frozen 모드에서 `pages/` 자동 발견 동작 확인

### 6.3 PyInstaller 설정
- [ ] **T6.4** `build/app.spec` 작성
  - `hiddenimports`: `streamlit.web`, `pkg_resources`, `importlib_metadata`,
    `pandas._libs`, `openpyxl`, `xlrd`, `anthropic`
  - `datas`: streamlit 정적 리소스 포함
    (`(streamlit_path / 'static', 'streamlit/static')` 패턴)
  - `console=True` (서버 메시지 노출 위해)
  - 아이콘 파일 지정 (`icon='build/app.ico'`)
- [ ] **T6.5** `build/version_info.txt` 작성 (Windows 메타데이터)
- [ ] **T6.6** `build/build_exe.py` 자동화 스크립트
  - 이전 빌드 정리 (`dist/`, `build/quantity-aggregator/`)
  - PyInstaller 실행
  - `data/`, `templates/`, `.env.example`, `README.txt`를 `dist/`에 복사
  - 결과를 zip으로 묶기

### 6.4 외부 데이터 분리
- [ ] **T6.7** `terminology.yaml`을 exe 외부 `data/` 폴더에서 로드하도록 변경
- [ ] **T6.8** `templates/`도 외부 폴더에서 로드
- [ ] **T6.9** `.env` 파일이 없을 때의 fallback (UI에서 API 키 입력 받기)

### 6.5 API 키 처리
- [ ] **T6.10** API 키 저장 위치 결정 및 구현
  - 옵션 1: `%APPDATA%/quantity-aggregator/config.ini`
  - 옵션 2: 사내 프록시 URL을 `.env`로
  - 옵션 3: IT팀 동봉 `.env`
- [ ] **T6.11** UI에 "API 키 설정" 페이지 추가 (옵션 1 채택 시)

### 6.6 빌드 및 검증
- [ ] **T6.12** 첫 빌드 실행 및 에러 해결 (대부분 hidden imports 누락)
- [ ] **T6.13** 빌드된 exe를 **개발 PC에서** 실행 → Streamlit UI 정상 동작 확인
- [ ] **T6.14** 빌드된 exe를 **Python 미설치 가상머신**에서 실행 → 동작 확인
- [ ] **T6.15** 갈전7교 5개 파일로 end-to-end 동작 확인
  - 업로드 → 매핑 → 집계 → Excel 다운로드까지 정상

### 6.7 배포 패키지
- [ ] **T6.16** `README.txt` 작성 (사용자용)
  - 압축 해제 방법
  - 최초 실행 시 API 키 입력 안내
  - `data/terminology.yaml` 편집 안내
  - 백신 차단 시 대처법
- [ ] **T6.17** zip 패키지 생성 스크립트
  - 파일명: `quantity-aggregator-v{version}-win64.zip`
- [ ] **T6.18** 사내 공유 폴더에 업로드 + 공지

### 6.8 사후 모니터링
- [ ] **T6.19** 사용자 피드백 수렴 채널 마련 (사내 메신저 채널 또는 폼)
- [ ] **T6.20** 알려진 이슈 문서화 (`docs/known_issues.md`)

**완료 기준:**
- Python 미설치 가상머신에서 zip만 풀고 exe 실행 → 갈전7교 집계표 생성 성공
- 배포 zip 크기 400MB 이하
- 첫 실행 ~ 브라우저 열림까지 5초 이내

---

## 보조 작업 (Optional)

- [ ] **B1** CI 설정 (GitHub Actions): pytest + ruff
- [ ] **B2** Docker 이미지 (사내 배포용)
- [ ] **B3** 다국어 지원 (한글 UI + 영문 옵션)
- [ ] **B4** 사용 로그 대시보드 (누가 언제 어떤 프로젝트를 처리했는지)

---

## 작업 순서 의존성

```
T0.* (셋업)
  └─> T1.1~1.3 (모델·스토리지)
        └─> T1.4~1.11 (도메인 모듈)
              └─> T1.13 (회귀 테스트)
                    └─> T2.* (AI)
                          └─> T3.* (UI)
                                └─> T4.* (품질)
                                      └─> T5.* (템플릿) ─┐
                                                        ├─> T6.* (exe 배포)
                                      └─────────────────┘
                                      (T5는 선택, T6는 T4까지만 완료되면 시작 가능)
```

**병렬 가능 구간:**
- T6.0(IT팀 협의)는 Phase 1부터 미리 시작 가능 (사내 절차에 시간 걸림)
- T5와 T6는 독립적 — 동시 진행 가능

---

## 우선순위 높은 5가지

1. **T1.13 회귀 테스트 성공** — MVP v1의 합격선
2. **T3.5 매핑 검토 UI** — 이게 있어야 실제 사용 가능
3. **T4.10 README** — 사내 공유·피드백 수렴
4. **T6.0 IT팀 사전 협의** — 절차에 시간 걸리므로 미리 착수
5. **T6.14 Python 미설치 PC 동작 확인** — 배포 합격선

나머지는 이 5가지가 굳은 뒤에 채워도 된다.
