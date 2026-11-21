@echo off
setlocal
cd /d "%~dp0\.."

echo === 1. Setup Python virtual environment ===
if not exist .venv (
    python -m venv .venv
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\pip.exe install fastapi uvicorn python-multipart pillow numpy faster-whisper yt-dlp opencv-python-headless pyinstaller

echo === 2. Download Cyrillic TikTok fonts ===
.venv\Scripts\python.exe -m backend.download_fonts

echo === 3. Build standalone Windows backend (.exe) ===
.venv\Scripts\python.exe scripts\build_backend.py

echo === 4. Build Windows Desktop Installer (NSIS .exe + Portable .exe) ===
cd desktop
call npm install
call npm run build:win

echo.
echo Done! Windows installers are in desktop\dist\
pause
