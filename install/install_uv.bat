@echo off
REM install_uv.bat — Karaoke Tools setup using uv para CMD de Windows
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."

echo ========================================================
echo   Karaoke Tools -- Instalacion (uv)
echo ========================================================

REM ── uv ──────────────────────────────────────────────────────────────────────
where uv >nul 2>&1
if errorlevel 1 (
    echo uv no encontrado. Instalando...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
for /f "tokens=*" %%v in ('uv --version 2^>^&1') do set UV_VERSION=%%v
echo uv encontrado: %UV_VERSION%

REM ── Python ────────────────────────────────────────────────────────────────
echo.
echo Creando entorno virtual con uv...
uv venv "%ROOT_DIR%\.venv"
echo Entorno virtual: %ROOT_DIR%\.venv

REM ── FFmpeg ─────────────────────────────────────────────────────────────────
echo.
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo ADVERTENCIA: FFmpeg no encontrado en PATH.
    echo   Descarga desde https://ffmpeg.org/download.html
    echo   y agrega la carpeta /bin a la variable PATH del sistema.
) else (
    echo FFmpeg encontrado.
)

REM ── Dependencias principales ───────────────────────────────────────────────
echo.
uv run python -c "import sys; exit(0 if sys.version_info.minor >= 13 else 1)" 2>nul
if errorlevel 1 (
    set "REQ_FILE=%ROOT_DIR%\requirements.txt"
) else (
    set "REQ_FILE=%ROOT_DIR%\requirements.3.14.txt"
    echo Python ^>= 3.13 detectado — usando requirements.3.14.txt
)
echo Instalando dependencias del pipeline principal...
uv pip install -r "!REQ_FILE!"

REM ── audio-separator (opcional) ─────────────────────────────────────────────
echo.
set /p INSTALL_SEP="Instalar audio-separator para separacion vocal/instrumental? [s/N]: "
if /i "%INSTALL_SEP%"=="s" (
    echo.
    set /p USE_GPU="Usar GPU (NVIDIA CUDA)? [s/N]: "

    echo Instalando dependencias de audio-separator...
    set "SEP_DEPS=beartype einops julius ml_collections numpy pydub pyyaml requests resampy rotary-embedding-torch samplerate scipy six soundfile torch tqdm"
    uv run python -c "import sys; exit(0 if sys.version_info.minor >= 13 else 1)" 2>nul
    if errorlevel 1 (
        set "SEP_DEPS=!SEP_DEPS! onnx2torch"
    ) else (
        set "SEP_DEPS=!SEP_DEPS! audioop-lts onnx2torch-py313"
    )
    uv pip install !SEP_DEPS!

    if /i "!USE_GPU!"=="s" (
        uv pip install "audio-separator[gpu]" --no-deps
    ) else (
        uv pip install audio-separator --no-deps
    )
    echo audio-separator instalado correctamente.
)

REM ── Carpetas necesarias ────────────────────────────────────────────────────
if not exist "%ROOT_DIR%\projects\" mkdir "%ROOT_DIR%\projects"
if not exist "%ROOT_DIR%\loop_videos\" mkdir "%ROOT_DIR%\loop_videos"

REM ── Fin ────────────────────────────────────────────────────────────────────
echo.
echo ========================================================
echo   Instalacion completada.
echo   Para iniciar el servidor:
echo     uv run python karaoke_web_server.py --port 8080
echo ========================================================
pause
