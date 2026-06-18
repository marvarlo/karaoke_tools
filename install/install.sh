#!/usr/bin/env bash
# install.sh — Karaoke Tools setup for Linux / macOS / Git Bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================================"
echo "  Karaoke Tools — Instalacion"
echo "========================================================"

# ── Python ────────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 no encontrado. Instala Python 3.10 o superior."
    exit 1
fi

PYTHON=$(command -v python3)
PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python encontrado: $PYTHON ($PY_VERSION)"

# ── Entorno virtual ───────────────────────────────────────────────────────────
VENV_DIR="$ROOT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creando entorno virtual en .venv/ ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# Activar venv
source "$VENV_DIR/bin/activate"
echo "Entorno virtual activo: $VIRTUAL_ENV"

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
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MINOR" -ge 13 ]; then
    REQ_FILE="$ROOT_DIR/requirements.3.14.txt"
    echo "Python >= 3.13 detectado — usando $REQ_FILE"
else
    REQ_FILE="$ROOT_DIR/requirements.txt"
fi
echo "Instalando dependencias del pipeline principal..."
pip install --upgrade pip -q
pip install -r "$REQ_FILE"

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

    PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 13 ]; then
        SEP_DEPS="$SEP_DEPS audioop-lts onnx2torch-py313"
    else
        SEP_DEPS="$SEP_DEPS onnx2torch"
    fi

    pip install $SEP_DEPS

    if [[ "$USE_GPU" =~ ^[sS]$ ]]; then
        pip install "audio-separator[gpu]" --no-deps
    else
        pip install audio-separator --no-deps
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
echo "    source .venv/bin/activate"
echo "    python karaoke_web_server.py --port 8080"
echo "========================================================"
