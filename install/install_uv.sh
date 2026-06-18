#!/usr/bin/env bash
# install_uv.sh — Karaoke Tools setup using uv (Linux / macOS / Git Bash)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================================"
echo "  Karaoke Tools — Instalacion (uv)"
echo "========================================================"

# ── uv ────────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "uv no encontrado. Instalando..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Añadir uv al PATH para esta sesión
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv encontrado: $(command -v uv) ($(uv --version))"

# ── Python ────────────────────────────────────────────────────────────────────
PY_VERSION=$(uv python list --only-version 2>/dev/null | head -1 || true)
echo "Python preferido: ${PY_VERSION:-auto}"

# ── Entorno virtual ───────────────────────────────────────────────────────────
VENV_DIR="$ROOT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creando entorno virtual en .venv/ ..."
    uv venv "$VENV_DIR"
fi
echo "Entorno virtual: $VENV_DIR"

# ── FFmpeg ────────────────────────────────────────────────────────────────────
echo ""
if command -v ffmpeg &>/dev/null; then
    echo "FFmpeg encontrado: $(command -v ffmpeg)"
else
    echo "ADVERTENCIA: FFmpeg no encontrado en PATH."
    echo "  Linux:  sudo apt install ffmpeg"
    echo "  macOS:  brew install ffmpeg"
fi

# ── Dependencias principales ──────────────────────────────────────────────────
echo ""
PY_MINOR=$(uv python list --only-version 2>/dev/null | grep -oP '\.\K\d+' | head -1 || echo "12")
if [ "$PY_MINOR" -ge 13 ] 2>/dev/null; then
    REQ_FILE="$ROOT_DIR/requirements.3.14.txt"
    echo "Python >= 3.13 detectado — usando $REQ_FILE"
else
    REQ_FILE="$ROOT_DIR/requirements.txt"
fi
echo "Instalando dependencias del pipeline principal..."
uv pip install -r "$REQ_FILE"

# ── audio-separator (opcional) ────────────────────────────────────────────────
echo ""
read -r -p "Instalar audio-separator para separacion vocal/instrumental? [s/N]: " INSTALL_SEP
if [[ "$INSTALL_SEP" =~ ^[sS]$ ]]; then
    echo ""
    read -r -p "Usar GPU (NVIDIA CUDA)? [s/N]: " USE_GPU

    echo "Instalando dependencias de audio-separator..."
    SEP_DEPS="beartype einops julius ml_collections numpy \
        pydub pyyaml requests resampy \
        rotary-embedding-torch samplerate scipy six soundfile torch tqdm"

    PY_MAJOR=$(uv python list --only-version 2>/dev/null | grep -oP '^\K\d+' | head -1 || echo "3")
    PY_MINOR=$(uv python list --only-version 2>/dev/null | grep -oP '\.\K\d+' | head -1 || echo "12")

    if [ "$PY_MAJOR" -ge 3 ] 2>/dev/null && [ "$PY_MINOR" -ge 13 ] 2>/dev/null; then
        SEP_DEPS="$SEP_DEPS audioop-lts onnx2torch-py313"
    else
        SEP_DEPS="$SEP_DEPS onnx2torch"
    fi

    uv pip install $SEP_DEPS

    if [[ "$USE_GPU" =~ ^[sS]$ ]]; then
        uv pip install "audio-separator[gpu]" --no-deps
    else
        uv pip install audio-separator --no-deps
    fi
    echo "audio-separator instalado correctamente."
fi

# ── Carpetas necesarias ───────────────────────────────────────────────────────
mkdir -p "$ROOT_DIR/projects"
mkdir -p "$ROOT_DIR/loop_videos"

# ── Fin ───────────────────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  Instalacion completada."
echo "  Para iniciar el servidor:"
echo "    uv run python karaoke_web_server.py --port 8080"
echo "========================================================"
