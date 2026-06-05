#!/usr/bin/env python3
"""
karaoke_timing.py
═════════════════════════════════════════════════════════════════════════════
Extrae timing por palabra de un audio musical usando OpenAI Whisper.
Genera 3 archivos listos para el pipeline de LYRIC KARAOKE.

INSTALACIÓN (una sola vez)
──────────────────────────
  pip install openai-whisper

  ffmpeg debe estar instalado en el sistema:
    Windows → https://ffmpeg.org/download.html  (agregar al PATH)
    Mac     → brew install ffmpeg
    Linux   → sudo apt install ffmpeg

  GPU opcional (acelera x5–x10):
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    (solo si tienes GPU NVIDIA con CUDA)

USO
───
  python karaoke_timing.py Reencuentro.mp3
  python karaoke_timing.py Reencuentro.mp3 --model medium
  python karaoke_timing.py Reencuentro.mp3 --model medium --output ./mi_carpeta

MODELOS DISPONIBLES
───────────────────
  tiny    ~75  MB  · Muy rápido · Impreciso con letras cantadas
  base    ~150 MB  · Rápido     · Mejor para voz hablada clara
  small   ~500 MB  · Equilibrio · Funciona con voz clara sin autotune
  medium  ~1.5 GB  · Recomendado para letras cantadas en español  ← USA ESTE
  large   ~3.0 GB  · Máxima calidad · Muy lento sin GPU
  turbo   ~1.5 GB  · Rápido y muy preciso · Requiere Whisper ≥ 20230918

  La primera vez que uses un modelo, Whisper lo descarga automáticamente
  a ~/.cache/whisper/ y lo reutiliza en ejecuciones posteriores.

ARCHIVOS GENERADOS
──────────────────
  <nombre>_words.json      → Datos completos. Pásaselo a Claude para
                              generar la tabla de producción KARAOKE.
  <nombre>_words.srt       → SRT por palabra. Importa directo en
                              CapCut Pro, DaVinci Resolve o Premiere Pro.
  <nombre>_karaoke.csv     → Tabla editable. Abre en Excel o Sheets para
                              ajustar timings manualmente.

═════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import json
import argparse
import shutil
import csv
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from pathlib import Path
from datetime import timedelta


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS DE FORMATO
# ──────────────────────────────────────────────────────────────────────────────

def fmt_srt(sec: float) -> str:
    """Segundos → HH:MM:SS,mmm  (formato SRT estándar)"""
    total_ms = int(round(sec * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_display(sec: float) -> str:
    """Segundos → MM:SS.mm  (para terminal)"""
    m = int(sec // 60)
    s = sec % 60
    return f"{m:02d}:{s:05.2f}"


def fmt_ms(sec: float) -> int:
    """Segundos → milisegundos (int)"""
    return int(round(sec * 1000))


# ──────────────────────────────────────────────────────────────────────────────
# VERIFICACIÓN DE DEPENDENCIAS
# ──────────────────────────────────────────────────────────────────────────────

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("\n❌  ffmpeg no encontrado en el PATH.")
        print("    Windows → https://ffmpeg.org/download.html  (agrega la carpeta /bin al PATH)")
        print("    Mac     → brew install ffmpeg")
        print("    Linux   → sudo apt install ffmpeg\n")
        sys.exit(1)


def import_whisper():
    try:
        import whisper
        return whisper
    except ImportError:
        print("\n❌  openai-whisper no está instalado. Ejecuta:")
        print("    pip install openai-whisper\n")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# TRANSCRIPCIÓN
# ──────────────────────────────────────────────────────────────────────────────

MODEL_SIZES = {
    "tiny": "~75 MB",
    "base": "~150 MB",
    "small": "~500 MB",
    "medium": "~1.5 GB",
    "large": "~3.0 GB",
    "large-v2": "~3.0 GB",
    "large-v3": "~3.0 GB",
    "turbo": "~1.5 GB",
}


def load_model(whisper, model_name: str):
    size = MODEL_SIZES.get(model_name, "?")
    print(f"\n⏳  Cargando modelo '{model_name}' ({size})…")
    print("    Primera vez: se descarga a ~/.cache/whisper/  (espera un momento)")
    model = whisper.load_model(model_name)
    print(f"✅  Modelo listo.\n")
    return model


def transcribe(model, audio_path: Path, language: str) -> dict:
    print(f"🎵  Transcribiendo: {audio_path.name}")
    print(f"    Idioma forzado: {language}")
    print("    Esto puede tardar entre 1 y 5 minutos según tu hardware…\n")

    result = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,  # ← LA CLAVE: activa timing por palabra
        verbose=False,
        condition_on_previous_text=False,  # Reduce alucinaciones en música
        no_speech_threshold=0.4,           # Ignora silencios largos
        logprob_threshold=-1.0,            # Más tolerante con voz cantada
    )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN Y PROCESAMIENTO
# ──────────────────────────────────────────────────────────────────────────────

def extract_words(result: dict) -> list:
    """
    Aplana todos los segmentos en una lista plana de palabras.
    Cada entrada tiene: word, start, end, duration_ms, confidence, segment_id, line_text.
    """
    words = []
    for seg_idx, seg in enumerate(result.get("segments", [])):
        for w in seg.get("words", []):
            text = w.get("word", "").strip()
            if not text:
                continue
            start = w.get("start", 0.0)
            end   = w.get("end",   0.0)
            words.append({
                "word":        text,
                "start":       round(start, 3),
                "end":         round(end, 3),
                "duration_ms": fmt_ms(end - start),
                "confidence":  round(w.get("probability", 0.0), 3),
                "segment_id":  seg_idx,
                "line_text":   seg.get("text", "").strip(),
            })
    return words


# ──────────────────────────────────────────────────────────────────────────────
# SALIDAS
# ──────────────────────────────────────────────────────────────────────────────

def save_json(words: list, result: dict, path: Path, language: str):
    """
    JSON estructurado por segmentos + lista plana de palabras.
    Este es el archivo que se le pasa a Claude para generar
    la tabla de producción LYRIC KARAOKE.
    """
    segments_out = []
    for i, seg in enumerate(result.get("segments", [])):
        seg_words = [
            {k: v for k, v in w.items() if k != "line_text"}
            for w in words
            if w["segment_id"] == i
        ]
        segments_out.append({
            "id":         i,
            "start":      round(seg["start"], 3),
            "end":        round(seg["end"], 3),
            "start_fmt":  fmt_display(seg["start"]),
            "end_fmt":    fmt_display(seg["end"]),
            "text":       seg["text"].strip(),
            "word_count": len(seg_words),
            "words":      seg_words,
        })

    payload = {
        "language":    language,
        "total_words": len(words),
        "total_segments": len(segments_out),
        "words_flat":  words,
        "segments":    segments_out,
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def save_srt(words: list, path: Path):
    """
    SRT con una entrada por palabra.
    Compatible con CapCut Pro, DaVinci Resolve, Premiere Pro y Final Cut.
    
    En CapCut Pro: Importar → Subtítulos → Importar SRT
    En DaVinci:   Timeline → Subtítulos → Importar subtítulos
    """
    entries = []
    for i, w in enumerate(words, 1):
        entries.append(
            f"{i}\n"
            f"{fmt_srt(w['start'])} --> {fmt_srt(w['end'])}\n"
            f"{w['word']}\n"
        )
    path.write_text("\n".join(entries), encoding="utf-8")


def save_csv(words: list, path: Path):
    """
    CSV de producción — una fila por palabra.
    Abre en Excel o Google Sheets para ajuste manual de timings.
    Columnas: #, palabra, inicio_s, fin_s, duracion_ms, confianza_%, segmento, linea
    """
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        # utf-8-sig para compatibilidad con Excel en Windows
        writer = csv.writer(f)
        writer.writerow([
            "#", "palabra", "inicio_s", "fin_s",
            "duracion_ms", "confianza_%", "segmento_id", "linea_completa"
        ])
        for i, w in enumerate(words, 1):
            writer.writerow([
                i,
                w["word"],
                f"{w['start']:.3f}",
                f"{w['end']:.3f}",
                w["duration_ms"],
                int(round(w["confidence"] * 100)),
                w["segment_id"],
                w["line_text"],
            ])


# ──────────────────────────────────────────────────────────────────────────────
# RESUMEN EN TERMINAL
# ──────────────────────────────────────────────────────────────────────────────

def print_results(result: dict, words: list):
    """Imprime el resultado agrupado por segmento, con indicadores de confianza."""
    print("\n" + "═" * 72)
    print("  TIMING POR PALABRA — RESULTADO COMPLETO")
    print("═" * 72)

    for seg_i, seg in enumerate(result.get("segments", [])):
        seg_words = [w for w in words if w["segment_id"] == seg_i]
        if not seg_words:
            continue

        print(f"\n  [{fmt_display(seg['start'])} → {fmt_display(seg['end'])}]  "
              f"segmento {seg_i + 1}")
        print(f'  "{seg["text"].strip()}"')
        print()

        col_w = max(len(w["word"]) for w in seg_words) + 2
        header = f"  {'PALABRA':<{col_w}}  {'INICIO':>8}  {'FIN':>8}  {'ms':>6}  {'conf':>5}"
        print(header)
        print("  " + "─" * (len(header) - 2))

        for w in seg_words:
            conf_pct = int(round(w["confidence"] * 100))
            flag = "  ⚠️  baja confianza" if conf_pct < 60 else ""
            print(
                f"  {w['word']:<{col_w}}  "
                f"{fmt_display(w['start']):>8}  "
                f"{fmt_display(w['end']):>8}  "
                f"{w['duration_ms']:>6}  "
                f"{conf_pct:>4}%"
                f"{flag}"
            )

    # Advertencias globales
    low_conf = [w for w in words if w["confidence"] < 0.6]
    if low_conf:
        print(f"\n  ⚠️  {len(low_conf)} palabra(s) con confianza < 60%.")
        print("      Revísalas en el CSV o usa --model medium / --model large.")


def print_summary(words: list, result: dict, output_dir: Path, stem: str, model: str):
    detected_lang = result.get("language", "?")
    print(f"\n{'═' * 72}")
    print(f"  ✅  Transcripción completada")
    print(f"      Idioma detectado : {detected_lang}")
    print(f"      Total palabras   : {len(words)}")
    print(f"      Total segmentos  : {len(result.get('segments', []))}")
    print(f"      Modelo usado     : {model}")
    print(f"\n  📁  Archivos en: {output_dir}/")
    print(f"      📄  {stem}_words.json    ← pásale esto a Claude")
    print(f"      📄  {stem}_words.srt     ← importa en CapCut / DaVinci")
    print(f"      📄  {stem}_karaoke.csv   ← tabla editable en Excel")
    print(f"{'═' * 72}")

    if model in ("tiny", "base"):
        print(f"\n  💡  Consejo: usaste '{model}', que no es óptimo para letras cantadas.")
        print(f"      Re-ejecuta con --model medium para mayor precisión:\n")
        print(f"      python karaoke_timing.py {stem}.mp3 --model medium\n")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrae timing por palabra de un audio musical usando Whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "audio",
        help="Ruta al archivo de audio (MP3, WAV, M4A, FLAC, OGG, etc.)"
    )
    parser.add_argument(
        "--model", default="small",
        choices=list(MODEL_SIZES.keys()),
        help="Modelo de Whisper a usar (default: small / recomendado: medium)"
    )
    parser.add_argument(
        "--language", default="es",
        help="Código de idioma ISO 639-1 (default: es)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Carpeta de salida (default: <nombre_audio>_karaoke/)"
    )

    args = parser.parse_args()

    # ── Validar input ────────────────────────────────────────────────────────
    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"\n❌  Archivo no encontrado: {audio_path}\n")
        sys.exit(1)

    # ── Dependencias ─────────────────────────────────────────────────────────
    check_ffmpeg()
    whisper = import_whisper()

    # ── Carpeta de salida ────────────────────────────────────────────────────
    output_dir = (
        Path(args.output)
        if args.output
        else audio_path.parent / f"{audio_path.stem}_karaoke"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = audio_path.stem

    # ── Transcribir ──────────────────────────────────────────────────────────
    model  = load_model(whisper, args.model)
    result = transcribe(model, audio_path, args.language)
    words  = extract_words(result)

    if not words:
        print("\n⚠️  Whisper no detectó palabras con timestamp.")
        print("    Posibles causas:")
        print("    · La voz tiene mucho reverb o autotune")
        print("    · El modelo 'tiny' o 'base' no es suficiente")
        print("    Intenta: python karaoke_timing.py <archivo> --model medium\n")
        sys.exit(1)

    # ── Guardar outputs ──────────────────────────────────────────────────────
    json_path = output_dir / f"{stem}_words.json"
    srt_path  = output_dir / f"{stem}_words.srt"
    csv_path  = output_dir / f"{stem}_karaoke.csv"

    save_json(words, result, json_path, result.get("language", args.language))
    save_srt(words, srt_path)
    save_csv(words, csv_path)

    # ── Mostrar resultados ───────────────────────────────────────────────────
    print_results(result, words)
    print_summary(words, result, output_dir, stem, args.model)


if __name__ == "__main__":
    main()
