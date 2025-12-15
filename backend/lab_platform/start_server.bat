@echo off
echo Starting Django server with Daphne (ASGI) for WebSocket support...
echo.
echo Make sure you are in the backend/lab_platform directory
echo.
cd /d "%~dp0"
python manage.py runserver 0.0.0.0:8000

