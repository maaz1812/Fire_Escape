@echo off
echo ==============================================
echo   Fire Commander - Wokwi Simulation Launcher
echo ==============================================

if not exist ".env" (
    echo [ERROR] .env file is missing!
    pause
    exit /b
)

echo Loading environment variables from .env...
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "%%A=%%B"
)

if "%WOKWI_CLI_TOKEN%"=="" (
    echo [ERROR] WOKWI_CLI_TOKEN is missing or empty in .env!
    echo Please get a token from https://wokwi.com/dashboard/ci and paste it into .env
    pause
    exit /b
)

if "%WOKWI_CLI_TOKEN%"=="your_token_here" (
    echo [ERROR] You have not set your WOKWI_CLI_TOKEN in the .env file!
    echo Please get a free token from https://wokwi.com/dashboard/ci and replace "your_token_here" with it.
    pause
    exit /b
)

echo Starting Wokwi Simulation Engine...
%USERPROFILE%\.wokwi\bin\wokwi-cli.exe --timeout 40000 --serial-log-file serial_output.txt
pause
