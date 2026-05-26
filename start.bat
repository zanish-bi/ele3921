@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: 'uv' is not installed.
    echo.
    echo   Install it with:
    echo     powershell -c "irm https://astral.sh/uv/install.ps1 ^| iex"
    echo   or:
    echo     pip install uv
    echo.
    echo   Then re-run this script.
    pause
    exit /b 1
)

echo ==^> Syncing dependencies...
uv sync --quiet
if errorlevel 1 ( echo ERROR: uv sync failed & pause & exit /b 1 )

echo ==^> Running migrations...
uv run python manage.py migrate --run-syncdb
if errorlevel 1 ( echo ERROR: migrate failed & pause & exit /b 1 )

if not exist ".seeded" (
    echo ==^> Seeding test data (first run)...
    uv run python manage.py seed && echo. > .seeded
)

echo.
echo ==^> StudentGig is running at http://127.0.0.1:8000
echo.
echo     Home       http://127.0.0.1:8000/
echo     Login      http://127.0.0.1:8000/accounts/login/
echo     Admin      http://127.0.0.1:8000/admin/  (admin / admin)
echo.
echo     Test accounts:
echo       student1 / pass1234   KYC verified
echo       client1  / pass1234   KYC verified
echo       student2 / pass1234   KYC pending (use Simulate KYC button)
echo.

uv run python manage.py runserver 8000
