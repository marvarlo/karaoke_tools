# install_uv.ps1 — Karaoke Tools setup using uv para PowerShell en Windows
#
# Uso:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\install\install_uv.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir

Write-Host ""
Write-Host "========================================================"
Write-Host "  Karaoke Tools -- Instalacion (uv)"
Write-Host "========================================================"

# ── uv ────────────────────────────────────────────────────────────────────────
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv no encontrado. Instalando..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}
$uvVersion = & uv --version 2>&1
Write-Host "uv encontrado: $uvVersion"

# ── Python ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Creando entorno virtual con uv..."
& uv venv (Join-Path $RootDir ".venv")
Write-Host "Entorno virtual: $(Join-Path $RootDir '.venv')"

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
$pyMinor = & uv run python -c "import sys; print(sys.version_info.minor)"
if ([int]$pyMinor -ge 13) {
    $reqFile = Join-Path $RootDir "requirements.3.14.txt"
    Write-Host "Python >= 3.13 detectado — usando requirements.3.14.txt"
} else {
    $reqFile = Join-Path $RootDir "requirements.txt"
}
Write-Host "Instalando dependencias del pipeline principal..."
& uv pip install -r "$reqFile"

# ── audio-separator (opcional) ────────────────────────────────────────────────
Write-Host ""
$installSep = Read-Host "Instalar audio-separator para separacion vocal/instrumental? [s/N]"
if ($installSep -match '^[sS]$') {
    Write-Host ""
    $useGpu = Read-Host "Usar GPU (NVIDIA CUDA)? [s/N]"

    Write-Host "Instalando dependencias de audio-separator..."
    $sepDeps = @(
        "beartype", "einops", "julius", "ml_collections", "numpy",
        "pydub", "pyyaml", "requests", "resampy",
        "rotary-embedding-torch", "samplerate", "scipy", "six",
        "soundfile", "torch", "tqdm"
    )
    if ([int]$pyMinor -ge 13) {
        $sepDeps += @("audioop-lts", "onnx2torch-py313")
    } else {
        $sepDeps += "onnx2torch"
    }
    & uv pip install $sepDeps

    if ($useGpu -match '^[sS]$') {
        & uv pip install "audio-separator[gpu]" --no-deps
    } else {
        & uv pip install audio-separator --no-deps
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
Write-Host "    uv run python karaoke_web_server.py --port 8080"
Write-Host "========================================================"
