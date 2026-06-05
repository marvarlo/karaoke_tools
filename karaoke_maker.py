#!/usr/bin/env python3
"""
karaoke_maker.py — Pipeline completo para karaoke y lyrics video
═══════════════════════════════════════════════════════════════════════════════

Un solo punto de entrada para producir videos de karaoke o lyrics
de cualquier canción. Gestiona proyectos, transcripción, imágenes y ensamblaje.

INSTALACIÓN (una sola vez):
  pip install Pillow openai-whisper
  # ffmpeg: brew install ffmpeg | apt install ffmpeg | ffmpeg.org

COMANDOS:
  init      Crea estructura de proyecto para una canción nueva
  build     Ejecuta el pipeline completo (transcribir → mapear → ensamblar)
  preview   Renderiza solo los primeros 30 segundos
  info      Muestra el estado del proyecto
  clean     Limpia archivos generados (mantiene audio e imágenes)

INICIO RÁPIDO:
  1. python karaoke_maker.py init "Mi Cancion" --audio cancion.mp3
  2. Pon tus imágenes en: Mi Cancion/images/
  3. python karaoke_maker.py build "Mi Cancion/"
  4. Edita Mi Cancion/output/map.json y vuelve a ejecutar el paso 3

MODOS:
  "mode": "karaoke"   → highlight palabra por palabra en tiempo real
  "mode": "lyrics"    → línea completa aparece (lyrics video clásico, más simple)

ESTILOS:
  "style": "minimal"  → ámbar sobre gris oscuro     (videoclip artístico)
  "style": "dark"     → dorado sobre negro           (pop/electrónica)
  "style": "neon"     → cyan sobre negro intenso     (reggaetón/urbano)
  "style": "vintage"  → crema cálido sobre sepia     (bolero/romántico)

ESTRUCTURA DEL PROYECTO:
  MiCancion/
  ├── config.json       ← configuración del proyecto (editable)
  ├── audio.mp3         ← tu archivo de audio
  ├── images/           ← imágenes de fondo generadas con Nano Banana
  └── output/
      ├── words.json    ← timing Whisper (generado automáticamente)
      ├── words.srt     ← SRT por palabra (generado automáticamente)
      ├── map.json      ← mapa imagen→tiempo (generado + editable)
      └── karaoke.mp4   ← video final
═══════════════════════════════════════════════════════════════════════════════
"""

import sys, json, shutil, subprocess, argparse
from pathlib import Path
from datetime import datetime

# ── Rutas a los scripts del pipeline ─────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
TIMING_BIN    = SCRIPT_DIR / 'karaoke_timing.py'
ASSEMBLER_BIN = SCRIPT_DIR / 'karaoke_assembler.py'

# ── Config por defecto ────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "_nota": "Edita este archivo para personalizar el proyecto.",
    "title":          "",
    "artist":         "",
    "audio":          "audio.mp3",
    "language":       "es",
    "whisper_model":  "medium",
    "mode":           "karaoke",
    "style":          "minimal",
    "resolution":     "1920x1080",
    "font":           None,
    "font_size":      72,
    "images_folder":  "images",
    "output_name":    "karaoke.mp4",
    "show_title":     True,
    "gap_threshold":  1.2,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_config(project_path: Path) -> dict:
    cfg_file = project_path / 'config.json'
    if not cfg_file.exists():
        print(f"❌  config.json no encontrado en '{project_path}'")
        print(f"    Crea el proyecto primero: python karaoke_maker.py init \"{project_path.name}\"")
        sys.exit(1)
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(json.loads(cfg_file.read_text(encoding='utf-8')))
    return cfg


def run(cmd: list, label: str = "") -> int:
    if label:
        print(f"\n{'─'*64}")
        print(f"  {label}")
        print(f"{'─'*64}")
    print(f"  $ {' '.join(str(c) for c in cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode


def images_in(folder: Path) -> list:
    exts = {'.png', '.jpg', '.jpeg', '.webp'}
    return [p for p in folder.iterdir() if p.suffix.lower() in exts] if folder.exists() else []


# ── COMANDO: init ─────────────────────────────────────────────────────────────

def cmd_init(args):
    name   = args.name
    folder = Path(name)

    if folder.exists():
        print(f"⚠️   La carpeta '{folder}' ya existe.")
        print(f"     Usa 'python karaoke_maker.py info \"{folder}\"' para ver su estado.")
        sys.exit(1)

    folder.mkdir()
    (folder / 'images').mkdir()
    (folder / 'output').mkdir()

    # Audio
    if args.audio:
        src = Path(args.audio)
        if not src.exists():
            print(f"❌  Audio no encontrado: {src}")
            sys.exit(1)
        dst = folder / 'audio.mp3'
        shutil.copy2(src, dst)
        print(f"✅  Audio copiado → {dst}")

    # Config
    cfg = DEFAULT_CONFIG.copy()
    cfg['title']    = args.title or name
    cfg['artist']   = args.artist or ""
    cfg['language'] = args.lang
    cfg['mode']     = args.mode
    cfg['style']    = args.style
    del cfg['_nota']
    cfg_out = {"_nota": DEFAULT_CONFIG['_nota']}
    cfg_out.update(cfg)

    (folder / 'config.json').write_text(
        json.dumps(cfg_out, ensure_ascii=False, indent=2), encoding='utf-8')

    # README
    readme = f"""# {cfg['title']} — Proyecto Karaoke
Creado: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Modo: {cfg['mode']} | Estilo: {cfg['style']} | Idioma: {cfg['language']}

PASOS:
─────
1. Pon tu MP3 en: {folder}/audio.mp3
2. Genera imágenes en Nano Banana Pro → ponlas en: {folder}/images/
3. Ejecuta: python karaoke_maker.py build "{folder}"
   (Si es la primera vez, generará output/map.json — edítalo y repite)
4. Opcional preview: python karaoke_maker.py preview "{folder}"

MODOS (edita config.json → "mode"):
  karaoke → highlight palabra por palabra (requiere Whisper medium/large)
  lyrics  → línea completa aparece/desaparece (más simple, menos granular)

ESTILOS (edita config.json → "style"):
  minimal · dark · neon · vintage

MODELOS WHISPER (edita config.json → "whisper_model"):
  small   → rápido, OK para voz clara
  medium  → recomendado para canciones cantadas  ← default
  large   → máxima calidad, lento sin GPU
"""
    (folder / 'README.txt').write_text(readme, encoding='utf-8')

    print(f"\n✅  Proyecto creado: {folder}/")
    print(f"\n   Próximos pasos:")
    if not args.audio:
        print(f"   1. Copia tu MP3 → {folder}/audio.mp3")
    print(f"   {'2' if not args.audio else '1'}. Genera imágenes → {folder}/images/")
    print(f"   {'3' if not args.audio else '2'}. python karaoke_maker.py build \"{folder}\"")


# ── COMANDO: build / preview ──────────────────────────────────────────────────

def cmd_build(args, preview: bool = False):
    folder = Path(args.project).resolve()
    cfg    = load_config(folder)
    out    = folder / 'output'
    out.mkdir(exist_ok=True)

    audio  = folder / cfg['audio']
    images = folder / cfg['images_folder']

    # Validaciones
    if not audio.exists():
        print(f"❌  Audio no encontrado: {audio}")
        sys.exit(1)

    imgs = images_in(images)
    if not imgs:
        print(f"❌  No hay imágenes en: {images}")
        print(f"   Genera fondos con Nano Banana Pro y ponlos en esa carpeta.")
        sys.exit(1)

    # ── Paso 1: Transcripción Whisper ─────────────────────────────────────────
    words_json = out / 'words.json'
    words_srt  = out / 'words.srt'

    if not words_json.exists() or getattr(args, 'retranscribe', False):
        code = run([
            sys.executable, str(TIMING_BIN),
            str(audio),
            '--model',    cfg['whisper_model'],
            '--language', cfg['language'],
            '--output',   str(out),
        ], f"Paso 1/3 — Transcripción Whisper ({cfg['whisper_model']})")
        if code != 0:
            print("❌  La transcripción falló.")
            sys.exit(1)
        # karaoke_timing.py guarda como <stem>_words.json — buscar el archivo
        stem_json = out / f"{Path(cfg['audio']).stem}_words.json"
        stem_srt  = out / f"{Path(cfg['audio']).stem}_words.srt"
        if stem_json.exists() and not words_json.exists():
            stem_json.rename(words_json)
        if stem_srt.exists() and not words_srt.exists():
            stem_srt.rename(words_srt)
    else:
        print(f"\n✅  Transcripción ya existe — saltando Whisper")
        print(f"    (usa --retranscribe para forzar de nuevo)")

    if not words_srt.exists():
        print(f"❌  SRT no encontrado: {words_srt}")
        sys.exit(1)

    # ── Paso 2: Mapa imagen→tiempo ────────────────────────────────────────────
    map_json = out / 'map.json'

    if not map_json.exists():
        # Generar mapa en una carpeta temporal y moverlo
        code = run([
            sys.executable, str(ASSEMBLER_BIN),
            '--generate-map',
            '--images', str(images),
            '--srt',    str(words_srt),
            '--audio',  str(audio),
            '--json',   str(words_json) if words_json.exists() else '',
        ], "Paso 2/3 — Generando mapa imagen→tiempo")

        gen = Path('karaoke_map.json')
        if gen.exists():
            shutil.move(str(gen), str(map_json))

        if map_json.exists():
            print(f"\n⚠️   Mapa generado: {map_json}")
            print(f"    → Edítalo para asignar tus imágenes a cada sección.")
            print(f"    → Luego ejecuta de nuevo: python karaoke_maker.py build \"{folder}\"")
        else:
            print("❌  No se pudo generar el mapa. Revisa los errores.")
        return

    # ── Paso 3: Ensamblaje ────────────────────────────────────────────────────
    out_name = cfg.get('output_name', 'karaoke.mp4')
    stem     = Path(out_name).stem
    out_mp4  = out / (f"{stem}_preview.mp4" if preview else out_name)

    cmd = [
        sys.executable, str(ASSEMBLER_BIN),
        '--images',     str(images),
        '--srt',        str(words_srt),
        '--audio',      str(audio),
        '--output',     str(out_mp4),
        '--mode',       cfg.get('mode',  'karaoke'),
        '--style',      cfg.get('style', 'minimal'),
        '--resolution', cfg.get('resolution', '1920x1080'),
        '--font-size',  str(cfg.get('font_size', 72)),
        '--map',        str(map_json),
    ]

    if words_json.exists():
        cmd += ['--json', str(words_json)]

    if cfg.get('font'):
        cmd += ['--font', str(cfg['font'])]

    if cfg.get('show_title') and cfg.get('title'):
        cmd += ['--title', cfg['title']]

    if preview:
        cmd.append('--preview')

    label = f"Paso 3/3 — Ensamblaje {'PREVIEW ' if preview else ''}({cfg['mode']} / {cfg['style']})"
    code  = run(cmd, label)

    if code != 0:
        print("❌  El ensamblaje falló.")
        sys.exit(1)

    if out_mp4.exists():
        mb = out_mp4.stat().st_size / 1024 / 1024
        print(f"\n🎉  Video listo: {out_mp4}  ({mb:.1f} MB)")
        print(f"    Modo: {cfg['mode']} | Estilo: {cfg['style']} | {cfg['resolution']}")


# ── COMANDO: info ─────────────────────────────────────────────────────────────

def cmd_info(args):
    folder = Path(args.project).resolve()
    cfg    = load_config(folder)
    out    = folder / 'output'

    def status(p: Path, label: str):
        ok   = p.exists()
        icon = "✅" if ok else "⬜"
        size = f" ({p.stat().st_size // 1024} KB)" if ok else ""
        print(f"  {icon}  {label}{size}")

    print(f"\n📁  {folder}")
    print(f"    {'─'*50}")
    print(f"    Título   : {cfg.get('title')  or '(sin título)'}")
    print(f"    Artista  : {cfg.get('artist') or '(sin artista)'}")
    print(f"    Modo     : {cfg.get('mode',   'karaoke')}")
    print(f"    Estilo   : {cfg.get('style',  'minimal')}")
    print(f"    Idioma   : {cfg.get('language', 'es')}")
    print(f"    Modelo   : Whisper {cfg.get('whisper_model', 'medium')}")
    print(f"    Resoluc. : {cfg.get('resolution', '1920x1080')}")
    print()
    print("  Archivos:")
    status(folder / cfg['audio'], f"Audio           ({cfg['audio']})")
    imgs = images_in(folder / cfg['images_folder'])
    print(f"  {'✅' if imgs else '⬜'}  Imágenes        ({len(imgs)} archivos en images/)")
    status(out / 'words.json', "Transcripción   (output/words.json)")
    status(out / 'words.srt',  "SRT palabras    (output/words.srt)")
    status(out / 'map.json',   "Mapa imágenes   (output/map.json)")
    out_name = cfg.get('output_name', 'karaoke.mp4')
    status(out / out_name, f"Video final     (output/{out_name})")

    # Próximo paso sugerido
    print()
    audio_ok = (folder / cfg['audio']).exists()
    imgs_ok  = bool(imgs)
    json_ok  = (out / 'words.json').exists()
    map_ok   = (out / 'map.json').exists()
    vid_ok   = (out / out_name).exists()

    if   not audio_ok: print(f"  ▶  Siguiente: Copia tu MP3 → {folder / cfg['audio']}")
    elif not imgs_ok:  print(f"  ▶  Siguiente: Genera imágenes → {folder / 'images'}/")
    elif not json_ok:  print(f"  ▶  Siguiente: python karaoke_maker.py build \"{folder}\"  [Whisper]")
    elif not map_ok:   print(f"  ▶  Siguiente: python karaoke_maker.py build \"{folder}\"  [Mapa]")
    elif not vid_ok:   print(f"  ▶  Siguiente: python karaoke_maker.py build \"{folder}\"  [Video]")
    else:              print(f"  🎉  Proyecto completo. ¡A publicar!")
    print()


# ── COMANDO: clean ────────────────────────────────────────────────────────────

def cmd_clean(args):
    folder = Path(args.project).resolve()
    cfg    = load_config(folder)
    out    = folder / 'output'

    targets = ['words.json', 'words.srt', 'words_karaoke.csv']
    if getattr(args, 'all', False):
        targets += ['map.json', cfg.get('output_name', 'karaoke.mp4')]

    removed = 0
    for name in targets:
        p = out / name
        if p.exists():
            p.unlink()
            print(f"  🗑️   {p}")
            removed += 1

    preview = out / f"{Path(cfg.get('output_name','karaoke.mp4')).stem}_preview.mp4"
    if preview.exists():
        preview.unlink()
        print(f"  🗑️   {preview}")
        removed += 1

    print(f"\n  {removed} archivo(s) eliminado(s).")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        prog='karaoke_maker.py',
        description='Pipeline unificado para karaoke y lyrics video',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest='cmd', required=True)

    # ── init ──────────────────────────────────────────────────────────────────
    p = sub.add_parser('init', help='Crea estructura de proyecto para una canción nueva')
    p.add_argument('name',        help='Nombre de la canción / carpeta del proyecto')
    p.add_argument('--audio',     default=None, help='Ruta al MP3 (lo copiará al proyecto)')
    p.add_argument('--title',     default=None, help='Título visible en el video')
    p.add_argument('--artist',    default=None, help='Nombre del artista')
    p.add_argument('--lang',      default='es', help='Código de idioma ISO (default: es)')
    p.add_argument('--mode',      default='karaoke', choices=['karaoke','lyrics'])
    p.add_argument('--style',     default='minimal', choices=['minimal','dark','neon','vintage'])

    # ── build ─────────────────────────────────────────────────────────────────
    p = sub.add_parser('build', help='Ejecuta el pipeline completo')
    p.add_argument('project',        help='Carpeta del proyecto')
    p.add_argument('--retranscribe', action='store_true',
                   help='Fuerza re-transcripción con Whisper aunque ya exista')

    # ── preview ───────────────────────────────────────────────────────────────
    p = sub.add_parser('preview', help='Renderiza solo los primeros 30s')
    p.add_argument('project', help='Carpeta del proyecto')

    # ── info ──────────────────────────────────────────────────────────────────
    p = sub.add_parser('info', help='Muestra estado del proyecto')
    p.add_argument('project', help='Carpeta del proyecto')

    # ── clean ─────────────────────────────────────────────────────────────────
    p = sub.add_parser('clean', help='Limpia archivos generados')
    p.add_argument('project', help='Carpeta del proyecto')
    p.add_argument('--all', action='store_true',
                   help='Elimina también el mapa y el video final')

    args = ap.parse_args()

    # Verificar que los scripts del pipeline existen
    for script in [TIMING_BIN, ASSEMBLER_BIN]:
        if not script.exists():
            print(f"❌  Script no encontrado: {script}")
            print(f"   Asegúrate de que karaoke_timing.py y karaoke_assembler.py")
            print(f"   estén en la misma carpeta que karaoke_maker.py")
            sys.exit(1)

    if   args.cmd == 'init':    cmd_init(args)
    elif args.cmd == 'build':   cmd_build(args, preview=False)
    elif args.cmd == 'preview': cmd_build(args, preview=True)
    elif args.cmd == 'info':    cmd_info(args)
    elif args.cmd == 'clean':   cmd_clean(args)


if __name__ == '__main__':
    main()
