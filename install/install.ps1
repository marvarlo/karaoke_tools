# install.ps1 — Karaoke Tools setup para PowerShell en Windows
#
# Uso:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\install\install.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir

Write-Host ""
Write-Host "========================================================"
Write-Host "  Karaoke Tools -- Instalacion"
Write-Host "========================================================"

# ── Python ────────────────────────────────────────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python no encontrado. Instala Python 3.10 o superior desde https://www.python.org/downloads/"
    exit 1
}

$pyVersion = & python --version 2>&1
Write-Host "Python encontrado: $pyVersion"

# ── Entorno virtual ───────────────────────────────────────────────────────────
$VenvDir = Join-Path $RootDir ".venv"
if (-not (Test-Path "$VenvDir\Scripts\Activate.ps1")) {
    Write-Host ""
    Write-Host "Creando entorno virtual en .venv\ ..."
    python -m venv $VenvDir
}

& "$VenvDir\Scripts\Activate.ps1"
Write-Host "Entorno virtual activo."

# ── FFmpeg ────────────────────────────────────────────────────────────────────
Write-Host ""
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "FFmpeg encontrado: $($(Get-Command ffmpeg).Source)"
} else {
    Write-Warning "FFmpeg no encontrado en PATH."
    Write-Host "  Descarga desde https://ffmpeg.org/download.html"
    Write-Host "  y agrega la carpeta /bin a la variable PATH del sistema."
}

# ── Dependencias principales ──────────────────────────────────────────────────
Write-Host ""
Write-Host "Instalando dependencias del pipeline principal..."
python -m pip install --upgrade pip -q
python -m pip install -r "$RootDir\requirements.txt"

# ── audio-separator (opcional) ────────────────────────────────────────────────
Write-Host ""
$installSep = Read-Host "Instalar audio-separator para separacion vocal/instrumental? [s/N]"
if ($installSep -match '^[sS]$') {
    Write-Host ""
    $useGpu = Read-Host "Usar GPU (NVIDIA CUDA)? [s/N]"

    Write-Host "Instalando dependencias de audio-separator..."
    python -m pip install `
        audioop-lts beartype einops julius ml_collections numpy `
        onnx-weekly onnx2torch-py313 pydub pyyaml requests resampy `
        rotary-embedding-torch samplerate scipy six soundfile torch tqdm

    if ($useGpu -match '^[sS]$') {
        python -m pip install "audio-separator[gpu]" --no-deps
    } else {
        python -m pip install audio-separator --no-deps
    }
    Write-Host "audio-separator instalado correctamente."
}

# ── Carpetas necesarias ───────────────────────────────────────────────────────
New-Item -ItemType Directory -Force "$RootDir\projects"   | Out-Null
New-Item -ItemType Directory -Force "$RootDir\loop_videos" | Out-Null

# ── Fin ───────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================"
Write-Host "  Instalacion completada."
Write-Host "  Para iniciar el servidor:"
Write-Host "    .venv\Scripts\Activate.ps1"
Write-Host "    python karaoke_web_server.py --port 8080"
Write-Host "========================================================"
