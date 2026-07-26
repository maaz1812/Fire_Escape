@echo off
echo ==================================================
echo      Fire Commander - Simulation Injector
echo ==================================================
echo.

python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed on this computer!
    echo.
    echo Please download and install Python from: https://www.python.org/downloads/
    echo **IMPORTANT**: Make sure to check the box "Add Python to PATH" during installation!
    echo.
    pause
    exit /b
)

echo [INFO] Python is installed. Setting up the environment...
IF NOT EXIST "venv" (
    echo [INFO] Creating an isolated virtual environment...
    python -m venv venv
)

echo [INFO] Activating virtual environment...
call venv\Scripts\activate

echo [INFO] Installing required libraries (this only takes a few seconds)...
pip install -r requirements.txt -q

echo [INFO] Starting Fire Commander...
echo.
python data\injector_tool.py

pause
