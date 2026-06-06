@echo off
REM install.bat — Karaoke Tools setup para CMD de Windows
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."

echo ========================================================
echo   Karaoke Tools -- Instalacion
echo ========================================================

REM ── Python ────────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instala Python 3.10 o superior.
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo Python encontrado: %PY_VERSION%

REM ── Entorno virtual ────────────────────────────────────────────────────────
set "VENV_DIR=%ROOT_DIR%\.venv"
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo.
    echo Creando entorno virtual en .venv\ ...
    python -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"
echo Entorno virtual activo.

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
echo Instalando dependencias del pipeline principal...
python -m pip install --upgrade pip -q
python -m pip install -r "%ROOT_DIR%\requirements.txt"

REM ── audio-separator (opcional) ─────────────────────────────────────────────
echo.
set /p INSTALL_SEP="Instalar audio-separator para separacion vocal/instrumental? [s/N]: "
if /i "%INSTALL_SEP%"=="s" (
    echo.
    set /p USE_GPU="Usar GPU (NVIDIA CUDA)? [s/N]: "

    echo Instalando dependencias de audio-separator...
    python -m pip install audioop-lts beartype einops julius ml_collections numpy ^
        onnx-weekly onnx2torch-py313 pydub pyyaml requests resampy ^
        rotary-embedding-torch samplerate scipy six soundfile torch tqdm

    if /i "!USE_GPU!"=="s" (
        python -m pip install "audio-separator[gpu]" --no-deps
    ) else (
        python -m pip install audio-separator --no-deps
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
echo     .venv\Scripts\activate
echo     python karaoke_web_server.py --port 8080
echo ========================================================
pause
