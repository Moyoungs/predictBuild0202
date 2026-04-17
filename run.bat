@echo off
chcp 65001 >nul
echo ============================================
echo   교량 수량집계표 자동화 시스템
echo ============================================
echo.

REM Python 확인
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo.
    echo 설치 방법:
    echo   1. https://www.python.org/downloads/ 접속
    echo   2. Download Python 3.12 클릭
    echo   3. 설치 시 "Add Python to PATH" 반드시 체크!
    echo   4. 설치 완료 후 이 파일을 다시 실행하세요.
    echo.
    pause
    exit /b 1
)

REM uv 확인 및 설치
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [설치] uv 패키지 매니저 설치 중...
    pip install uv --quiet
)

REM 가상환경 없으면 최초 셋업
if not exist .venv (
    echo.
    echo [최초 실행] 환경 설정 중... 2-3분 걸릴 수 있습니다.
    echo.
    uv venv
    uv sync
    echo.
    echo [설치 완료]
    echo.
)

REM Streamlit 실행
echo.
echo 브라우저가 자동으로 열립니다. 잠시 기다려주세요...
echo 종료하려면 이 창을 닫으세요.
echo.
.venv\Scripts\streamlit run src\quantity_aggregator\ui\app.py --server.headless true
pause