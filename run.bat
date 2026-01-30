@echo off
echo ========================================
echo LangGraph Invoice AI - Startup Script
echo ========================================
echo.

:: Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found. Please create it first.
    exit /b 1
)

:: Activate virtual environment
call .venv\Scripts\activate

:: Start FastAPI in background
echo Starting FastAPI server on http://localhost:8000...
start "FastAPI Server" cmd /c "uvicorn app:app --reload --port 8000"

:: Wait for API to start
echo Waiting for API to start...
timeout /t 5 /nobreak > nul

:: Start Streamlit
echo Starting Streamlit on http://localhost:8501...
streamlit run streamlit_app.py

pause
