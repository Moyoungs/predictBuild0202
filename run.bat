@echo off
chcp 65001 >nul
echo ============================================
echo   Bridge Quantity Aggregator
echo ============================================
echo.
echo Starting... Please wait.
echo Close this window to stop.
echo.
start "" http://localhost:8501
%~dp0python-embed\python.exe -m streamlit run %~dp0src\quantity_aggregator\ui\app.py --server.headless true
pause
