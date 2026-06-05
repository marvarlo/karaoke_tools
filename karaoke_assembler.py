#!/usr/bin/env python3
"""
karaoke_assembler.py
═══════════════════════════════════════════════════════════════════════════════

Ensambla un video karaoke sincronizado a partir de:
  • Imágenes de fondo (generadas con Nano Banana Pro — una por sección)
  • SRT con timing por palabra (generado con karaoke_timing.py)
  • Archivo de audio (MP3)

Genera solo ~300 frames únicos (uno por cambio de estado) en lugar de
los ~6,700 que requeriría 30fps. Rápido y eficiente.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTALACIÓN
  pip install Pillow

  ffmpeg en el PATH:
    Mac     → brew install ffmpeg
    Windows → https://ffmpeg.org/download.html  (agrega /bin al PATH)
    Linux   → sudo apt install ffmpeg

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USO BÁSICO

  # 1. Genera el mapa de imágenes (solo la primera vez):
  python karaoke_assembler.py --generate-map \\
      --images ./fondos --srt Reencuentro_words.srt --audio Reencuentro.mp3

  # 2. Edita karaoke_map.json — asigna cada imagen a su rango de tiempo.

  # 3. Ensambla el video:
  python karaoke_assembler.py \\
      --images ./fondos \\
      --srt Reencuentro_words.srt \\
      --audio Reencuentro.mp3 \\
      --map karaoke_map.json \\
      --output Reencuentro_karaoke.mp4

  # Prueba rápida (solo primeros 30 segundos):
  python karaoke_assembler.py ... --preview

  # Con fuente personalizada y resolución 4K:
  python karaoke_assembler.py ... --font "CormorantGaramond-Light.ttf" --resolution 3840x2160

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO karaoke_map.json
  {
    "title": "Reencuentro",
    "segments": [
      { "start": 0.0,    "end": 13.72,  "image": "fondos/00_intro.png" },
      { "start": 13.72,  "end": 63.08,  "image": "fondos/01_verso1.png" },
      { "start": 63.08,  "end": 115.84, "image": "fondos/02_coro1.png" },
      { "start": 115.84, "end": 167.36, "image": "fondos/03_verso2.png" },
      { "start": 167.36, "end": 223.0,  "image": "fondos/04_coro2.png" }
    ]
  }

  Para Reencuentro los 5 fondos recomendados son (en orden):
    00_intro.png   → callejón vacío, niebla (0:00–0:13)
    01_verso1.png  → calle gris, frío, urbano (0:13–1:03)
    02_coro1.png   → transición luz, ventana ámbar (1:03–1:55)
    03_verso2.png  → interior café, madera, vapor (1:55–2:47)
    04_coro2.png   → callejón final con dos siluetas (2:47–3:41)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PALETA VISUAL (MINIMAL)
  Palabra activa    #C8903A  amber
  Palabra cantada   #F4EFE6  warm white
  Palabra pendiente #464646  dark grey
  Líneas adyacentes #2E2E2E  muy oscuro (faded)
═══════════════════════════════════════════════════════════════════════════════
"""

import sys, re, json, shutil, subprocess, tempfile, time, argparse
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

# ── Dependencias ──────────────────────────────────────────────────────────────

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌  Pillow no instalado.  pip install Pillow")
    sys.exit(1)


# ── Paleta ────────────────────────────────────────────────────────────────────

STYLES = {
    'minimal': dict(active=(200,144,58), sung=(244,239,230), unsung=(70,70,70),
                    adj=(45,42,38), bg=0.68, overlay=110),
    'dark':    dict(active=(255,205,90), sung=(215,215,195), unsung=(55,55,55),
                    adj=(28,28,28), bg=0.48, overlay=165),
    'neon':    dict(active=(0,255,180),  sung=(175,175,255), unsung=(65,65,65),
                    adj=(30,30,30), bg=0.35, overlay=185),
    'vintage': dict(active=(255,215,125),sung=(240,218,182), unsung=(95,85,62),
                    adj=(55,50,38), bg=0.65, overlay=125),
}
C_ACTIVE   = STYLES['minimal']['active']
C_SUNG     = STYLES['minimal']['sung']
C_UNSUNG   = STYLES['minimal']['unsung']
C_ADJACENT = STYLES['minimal']['adj']
C_SHADOW   = (0, 0, 0)
OVERLAY_A  = STYLES['minimal']['overlay']
BG_BRIGHT  = STYLES['minimal']['bg']


# ── Tipos ─────────────────────────────────────────────────────────────────────

@dataclass
class Word:
    text:  str
    start: float
    end:   float


@dataclass
class Line:
    words: List[Word]

    @property
    def start(self): return self.words[0].start

    @property
    def end(self): return self.words[-1].end


@dataclass
class State:
    t_start:   float
    t_end:     float
    line:      Optional[Line]
    active:    int               # índice de palabra activa; -1 = todas unsung
    prev_line: Optional[Line]
    next_line: Optional[Line]


# ── SRT ───────────────────────────────────────────────────────────────────────

def ts2sec(ts: str) -> float:
    h, m, rest = ts.split(':')
    s, ms = rest.split(',')
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000


def parse_srt(path: str) -> List[Word]:
    text = Path(path).read_text(encoding='utf-8-sig')
    pat  = re.compile(
        r'\d+\s*\n'
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'
        r'(.+?)(?=\n\s*\n|\Z)',
        re.DOTALL
    )
    words = []
    for m in pat.finditer(text):
        wtext = m.group(3).strip().replace('\n', ' ')
        if wtext:
            words.append(Word(wtext, ts2sec(m.group(1)), ts2sec(m.group(2))))
    return words


# ── Agrupación de líneas ──────────────────────────────────────────────────────

def group_lines(words: List[Word], gap: float) -> List[Line]:
    """Agrupa palabras en líneas líricas según gaps de silencio."""
    if not words:
        return []
    lines, current = [], [words[0]]
    for w in words[1:]:
        if w.start - current[-1].end > gap:
            lines.append(Line(current[:]))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(Line(current))
    return lines


def group_lines_from_json(json_path: str) -> List[Line]:
    """
    Usa el JSON de Whisper (generado por karaoke_timing.py) para agrupar
    palabras en líneas usando el campo segment_id.
    
    Esto da exactamente las mismas líneas que Whisper detectó originalmente,
    sin el problema de merge causado por segmentos adyacentes con 0s de gap.
    
    Recomendado sobre group_lines() cuando tienes el JSON disponible.
    """
    d    = json.loads(Path(json_path).read_text(encoding='utf-8'))
    segs = d.get('segments', [])

    lines = []
    for seg in segs:
        seg_words = [
            Word(w['word'], w['start'], w['end'])
            for w in seg.get('words', [])
            if w.get('word', '').strip()
        ]
        if seg_words:
            lines.append(Line(seg_words))

    return lines


# ── Estados ───────────────────────────────────────────────────────────────────

def make_states(lines: List[Line], total: float) -> List[State]:
    """
    Genera estados mínimos: un estado nuevo solo cuando cambia
    qué palabra está activa. Mucho más eficiente que frame-por-frame.
    """
    states = []

    def add(ts, te, line, active, prev=None, nxt=None):
        if te - ts > 0.01:
            states.append(State(ts, te, line, active, prev, nxt))

    # Intro instrumental
    if lines:
        add(0, lines[0].start, None, -1, None, lines[0])

    for li, line in enumerate(lines):
        prev_l = lines[li - 1] if li > 0 else None
        next_l = lines[li + 1] if li < len(lines) - 1 else None

        # Palabras de la línea
        for wi, word in enumerate(line.words):
            t_end = line.words[wi + 1].start if wi + 1 < len(line.words) else line.end
            add(word.start, t_end, line, wi, prev_l, next_l)

        # Gap después de la línea (instrumental o pausa)
        gap_end = lines[li + 1].start if li + 1 < len(lines) else total
        add(line.end, gap_end, None, -1, line, lines[li + 1] if li + 1 < len(lines) else None)

    # Outro
    if lines and lines[-1].end < total:
        add(lines[-1].end, total, None, -1, lines[-1], None)

    return states


def make_states_lyrics(lines: List[Line], total: float) -> List[State]:
    """
    Genera estados para modo LYRICS VIDEO: un estado por línea completa.
    active = -3 → todas las palabras de la línea se muestran en color activo.
    Mucho menos frames que KARAOKE (44 vs 291 para Reencuentro).
    """
    states = []

    def add(ts, te, line, active, prev=None, nxt=None):
        if te - ts > 0.01:
            states.append(State(ts, te, line, active, prev, nxt))

    if lines:
        add(0, lines[0].start, None, -1, None, lines[0])

    for li, line in enumerate(lines):
        prev_l = lines[li - 1] if li > 0 else None
        next_l = lines[li + 1] if li < len(lines) - 1 else None

        # Toda la línea como un único estado — active=-3 = todas las palabras activas
        add(line.start, line.end, line, -3, prev_l, next_l)

        gap_end = lines[li + 1].start if li + 1 < len(lines) else total
        add(line.end, gap_end, None, -1, line, next_l)

    if lines and lines[-1].end < total:
        add(lines[-1].end, total, None, -1, lines[-1], None)

    return states




SUPPORTED = {'.png', '.jpg', '.jpeg', '.webp'}


def discover_images(folder: str) -> List[Path]:
    return sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in SUPPORTED)


def load_map(map_path: Optional[str], images_dir: str, total: float) -> list:
    """Carga el mapa JSON o genera uno automático dividiendo el tiempo equitativamente."""
    if map_path and Path(map_path).exists():
        d = json.loads(Path(map_path).read_text(encoding='utf-8'))
        segments = d['segments']
        # Asegurar que todas las rutas de imagen sean relativas a images_dir o absolutas
        for seg in segments:
            img_path = Path(seg['image'])
            # Si la ruta no existe directamente, intentar resolverla dentro de images_dir
            if not img_path.exists():
                resolved = Path(images_dir) / img_path.name
                if resolved.exists():
                    seg['image'] = str(resolved)
        return segments

    imgs = discover_images(images_dir)
    if not imgs:
        raise FileNotFoundError(f"No se encontraron imágenes en '{images_dir}'")

    n    = len(imgs)
    step = total / n
    print(f"    Auto-map: {n} imágenes divididas en {step:.1f}s c/u")
    return [{"start": i*step, "end": (i+1)*step, "image": str(imgs[i])} for i in range(n)]


def get_bg(t: float, segments: list, cache: dict, size: tuple) -> Image.Image:
    """Devuelve la imagen de fondo para el tiempo t, levemente oscurecida y cacheada.
    
    Usa el segmento cuyo start sea menor o igual a t (último que empezó antes de t).
    Fallback: primer segmento para t < primer_segmento.start.
    """
    # Selecciona el último segmento que haya empezado antes o en t
    path = segments[0]['image']   # fallback = primer segmento (cubre intro)
    for seg in sorted(segments, key=lambda s: s['start']):
        if seg['start'] <= t:
            path = seg['image']   # sigue actualizando — gana el último válido

    if path not in cache:
        raw = Image.open(path).convert('RGB').resize(size, Image.LANCZOS)
        cache[path] = raw.point(lambda p: int(p * BG_BRIGHT))

    return cache[path].copy()


# ── Renderizado de texto ──────────────────────────────────────────────────────

def twidth(text: str, font) -> int:
    """Ancho en píxeles de un texto con la fuente dada."""
    try:
        bb = font.getbbox(text)
        return max(0, bb[2] - bb[0])
    except Exception:
        return len(text) * (getattr(font, 'size', 12) // 2)


def _line_height(font) -> int:
    """Altura de una línea de texto en píxeles."""
    try:
        bb = font.getbbox("Áyg")
        return bb[3] - bb[1]
    except Exception:
        return getattr(font, 'size', 40)


def _draw_row(draw, words: List[Word], widths: list, active: int,
              y: int, font, W: int,
              c_active, c_sung, c_unsung, shadow_offset: int = 2):
    """Dibuja una sola fila de palabras centrada horizontalmente."""
    total = sum(widths)
    x     = (W - total) / 2
    for i, (word, wp) in enumerate(zip(words, widths)):
        text = word.text + ' '
        if   active == -3: color = c_active    # LYRICS: toda la fila en color activo
        elif active == -2: color = c_sung      # fila completamente cantada
        elif i < active:   color = c_sung      # ya cantada
        elif i == active:  color = c_active    # activa ahora
        else:              color = c_unsung    # pendiente
        if shadow_offset:
            draw.text((x + shadow_offset, y + shadow_offset),
                      text, fill=C_SHADOW, font=font)
        draw.text((x, y), text, fill=color, font=font)
        x += wp


def draw_karaoke_line(draw, words: List[Word], active: int,
                       y: int, font, W: int,
                       c_active, c_sung, c_unsung,
                       shadow_offset: int = 2):
    """
    Dibuja una línea de karaoke centrada con highlight por palabra.
    Si la línea supera el 87% del ancho, la divide en 2 filas automáticamente.
    Si aún dividida en 2 filas supera el 87% del ancho, reduce el tamaño de la fuente.
    """
    if not words:
        return

    texts  = [w.text + ' ' for w in words]
    widths = [twidth(t, font) for t in texts]
    total  = sum(widths)

    if total <= W * 0.87:
        # ── Una sola fila — cabe perfectamente ──────────────────────────────
        _draw_row(draw, words, widths, active, y, font, W,
                  c_active, c_sung, c_unsung, shadow_offset)
        return

    # ── Wrapping a 2 filas ────────────────────────────────────────────────
    # Punto de corte más cercano a la mitad del ancho total
    half = total / 2.0
    cum, split = 0, max(1, len(words) // 2)
    for i, w in enumerate(widths):
        cum += w
        if cum >= half:
            split = i + 1
            break
    split = max(1, min(split, len(words) - 1))

    row1, row2 = words[:split], words[split:]
    w1s,  w2s  = widths[:split], widths[split:]

    # Verificar si alguna de las dos filas excede el ancho máximo
    if max(sum(w1s), sum(w2s)) > W * 0.87:
        # Intentar reducir el tamaño de la fuente
        try:
            f_path = getattr(font, 'path', None)
            f_size = getattr(font, 'size', None)
            if f_path and f_size and f_size > 20:
                new_size = int(f_size * 0.85)
                new_font = ImageFont.truetype(f_path, new_size)
                # Recursivamente intentar dibujar con la nueva fuente
                draw_karaoke_line(draw, words, active, y, new_font, W,
                                  c_active, c_sung, c_unsung, shadow_offset)
                return
        except Exception:
            pass

    # Mapear active_idx a cada fila
    if active == -3:
        act1 = -3
        act2 = -3
    else:
        act1 = active if 0 <= active < split else -2    # -2 = toda fila cantada
        act2 = active - split if active >= split else -1 # -1 = toda fila pendiente

    lh = _line_height(font) + 10   # separación entre las dos filas

    _draw_row(draw, row1, w1s, act1, y - lh // 2, font, W,
              c_active, c_sung, c_unsung, shadow_offset)
    _draw_row(draw, row2, w2s, act2, y + lh // 2, font, W,
              c_active, c_sung, c_unsung, shadow_offset)


def render_frame(state: State, bg: Image.Image,
                 fmain, fside, W: int, H: int,
                 title: Optional[str]) -> Image.Image:
    """Compone un frame completo con overlay y texto karaoke."""

    img  = bg.copy()
    draw = ImageDraw.Draw(img)

    # ── Panel semi-transparente solo cuando hay texto activo ──────────────────
    # Título solo en el intro inicial (prev_line=None = aún no hubo letra).
    # Gaps entre líneas (prev_line != None) → solo fondo limpio, sin panel ni texto.
    show_title = title and state.line is None and state.prev_line is None
    has_content = state.line is not None or show_title

    if has_content:
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        panel_h = int(H * 0.40)
        panel_y = int(H * 0.38)
        ov_draw.rounded_rectangle(
            [W * 0.03, panel_y, W * 0.97, panel_y + panel_h],
            radius=24, fill=(0, 0, 0, 110)
        )
        img_rgba = bg.convert('RGBA')
        img_rgba = Image.alpha_composite(img_rgba, overlay)
        img  = img_rgba.convert('RGB')
        draw = ImageDraw.Draw(img)

    # Posiciones verticales
    Y_PREV = int(H * 0.47)
    Y_MAIN = int(H * 0.575)   # centro de la zona de texto
    Y_NEXT = int(H * 0.690)

    # ── Línea anterior (faded, toda cantada) ──────────────────────────────────
    if state.prev_line and state.line:
        draw_karaoke_line(draw, state.prev_line.words, -2,
                          Y_PREV, fside, W,
                          C_ADJACENT, C_ADJACENT, C_ADJACENT,
                          shadow_offset=0)

    # ── Línea actual ──────────────────────────────────────────────────────────
    if state.line:
        draw_karaoke_line(draw, state.line.words, state.active,
                          Y_MAIN, fmain, W,
                          C_ACTIVE, C_SUNG, C_UNSUNG,
                          shadow_offset=2)
    elif show_title:
        # Título durante toda la intro/gap instrumental (no solo primeros 2s)
        tw_px = twidth(title, fmain)
        draw.text(((W - tw_px) / 2 + 2, int(H * 0.56) + 2),
                  title, fill=C_SHADOW, font=fmain)
        draw.text(((W - tw_px) / 2, int(H * 0.56)),
                  title, fill=C_SUNG, font=fmain)

    # ── Siguiente línea (preview, unsung) ────────────────────────────────────
    if state.next_line:
        draw_karaoke_line(draw, state.next_line.words, -1,
                          Y_NEXT, fside, W,
                          C_ADJACENT, C_ADJACENT, C_ADJACENT,
                          shadow_offset=0)

    return img


# ── Fuente ────────────────────────────────────────────────────────────────────

FONT_PATHS = [
    # Mac
    '/Library/Fonts/Cormorant Garamond Light.ttf',
    '/Library/Fonts/Garamond.ttf',
    '/System/Library/Fonts/Supplemental/Georgia.ttf',
    '/Library/Fonts/Georgia.ttf',
    # Windows
    'C:/Windows/Fonts/georgiai.ttf',
    'C:/Windows/Fonts/georgia.ttf',
    'C:/Windows/Fonts/cambria.ttc',
    'C:/Windows/Fonts/times.ttf',
    # Linux
    '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
    '/usr/share/fonts/TTF/DejaVuSerif.ttf',
]


def load_font(user_path: Optional[str], size: int):
    candidates = ([user_path] if user_path else []) + FONT_PATHS
    for p in candidates:
        if p and Path(p).exists():
            try:
                f = ImageFont.truetype(p, size)
                print(f"    Fuente: {Path(p).name}  {size}pt")
                return f
            except Exception:
                continue
    print("⚠️   Sin fuente TTF — usando default (calidad reducida).")
    print("    Descarga CormorantGaramond-Light.ttf de fonts.google.com")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ── Template de mapa ──────────────────────────────────────────────────────────

def generate_map(images_dir: str, words: List[Word], lines: List[Line], out: str):
    """Genera un karaoke_map.json con puntos de corte sugeridos."""
    imgs  = discover_images(images_dir)
    total = words[-1].end + 2.0
    n     = len(lines)

    # Puntos de corte naturales basados en gaps grandes entre líneas
    gaps = []
    for i in range(1, len(lines)):
        g = lines[i].start - lines[i-1].end
        gaps.append((g, lines[i-1].end, lines[i].start, i))
    gaps.sort(reverse=True)

    # Tomar los 4 gaps más grandes como separadores de sección
    break_pts = sorted([0] + [g[1] for g in gaps[:4]] + [total])

    segs = []
    for i, (t0, t1) in enumerate(zip(break_pts, break_pts[1:])):
        segs.append({
            "start": round(t0, 2),
            "end":   round(t1, 2),
            "image": str(imgs[i]) if i < len(imgs) else f"fondos/imagen_{i+1:02d}.png",
            "_label": f"sección {i+1}"
        })

    template = {
        "_instrucciones": [
            "Edita el campo 'image' de cada segmento para apuntar a tu imagen de fondo.",
            "Ajusta 'start' y 'end' en segundos según necesites.",
            "Los puntos de corte se detectaron en los gaps instrumentales más largos."
        ],
        "title":          "Reencuentro",
        "total_duration": round(total, 2),
        "segments":       segs
    }

    Path(out).write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n✅  Template generado: {out}")
    print(f"    {len(segs)} secciones detectadas:")
    for s in segs:
        t0m, t0s = divmod(s['start'], 60)
        t1m, t1s = divmod(s['end'],   60)
        print(f"      [{int(t0m)}:{t0s:05.2f} → {int(t1m)}:{t1s:05.2f}]  {s['image']}")
    print("\n    Edita 'image' en cada segmento y luego ejecuta el ensamblaje.")


# ── FFmpeg ────────────────────────────────────────────────────────────────────

def check_ffmpeg():
    if not shutil.which('ffmpeg'):
        print("❌  FFmpeg no encontrado.")
        sys.exit(1)


def run_ffmpeg(filelist: Path, audio: str, output: str,
               W: int, H: int, verbose: bool):
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0', '-i', str(filelist),
        '-i', audio,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-vf', f'scale={W}:{H}:flags=lanczos,format=yuv420p',
        '-movflags', '+faststart',
        '-shortest',
        output
    ]
    if verbose:
        subprocess.run(cmd, check=True)
    else:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"\n❌  FFmpeg error:\n{r.stderr[-3000:]}")
            sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Ensambla video karaoke con imágenes + SRT por palabra + audio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('--images',       required=True,
                    help='Carpeta con imágenes de fondo (.png/.jpg)')
    ap.add_argument('--srt',          required=True,
                    help='SRT con timing por palabra')
    ap.add_argument('--audio',        required=True,
                    help='Archivo de audio (MP3, WAV, etc.)')
    ap.add_argument('--output',       default='karaoke_output.mp4',
                    help='Video de salida (default: karaoke_output.mp4)')
    ap.add_argument('--map',          default=None,
                    help='karaoke_map.json con asignación imagen→tiempo')
    ap.add_argument('--font',         default=None,
                    help='Ruta a archivo .ttf (ej: CormorantGaramond-Light.ttf)')
    ap.add_argument('--font-size',    type=int, default=72,
                    help='Tamaño de fuente principal en pt (default: 72)')
    ap.add_argument('--resolution',   default='1920x1080',
                    help='Resolución del video (default: 1920x1080)')
    ap.add_argument('--json',         default=None,
                    help='JSON de Whisper (*_words.json) para agrupación exacta de líneas '
                         '(recomendado — evita merges incorrectos del modo --gap)')
    ap.add_argument('--mode',         default='karaoke',
                    choices=['karaoke', 'lyrics'],
                    help='karaoke=highlight por palabra | lyrics=línea completa (default: karaoke)')
    ap.add_argument('--style',        default='minimal',
                    choices=list(STYLES.keys()),
                    help='Paleta visual: minimal dark neon vintage (default: minimal)')
    ap.add_argument('--title',        default=None,
                    help='Título a mostrar durante intro instrumental')
    ap.add_argument('--generate-map', action='store_true',
                    help='Solo genera karaoke_map.json y sale (no produce video)')
    ap.add_argument('--preview',      action='store_true',
                    help='Renderiza solo los primeros 30s (prueba rápida)')
    ap.add_argument('--verbose',      action='store_true',
                    help='Muestra output completo de FFmpeg')
    ap.add_argument('--frames-dir',   default=None,
                    help='Carpeta para guardar frames (default: temporal auto-limpiada)')

    args = ap.parse_args()

    # ── Validaciones básicas ─────────────────────────────────────────────────
    check_ffmpeg()

    if not Path(args.images).is_dir():
        print(f"❌  Carpeta de imágenes no encontrada: {args.images}")
        sys.exit(1)
    if not Path(args.srt).exists():
        print(f"❌  SRT no encontrado: {args.srt}")
        sys.exit(1)
    if not Path(args.audio).exists():
        print(f"❌  Audio no encontrado: {args.audio}")
        sys.exit(1)

    W, H = map(int, args.resolution.split('x'))

    # ── Aplicar estilo ────────────────────────────────────────────────────────
    global C_ACTIVE, C_SUNG, C_UNSUNG, C_ADJACENT, OVERLAY_A, BG_BRIGHT
    st = STYLES.get(args.style, STYLES['minimal'])
    C_ACTIVE, C_SUNG, C_UNSUNG, C_ADJACENT, OVERLAY_A, BG_BRIGHT = (
        st['active'], st['sung'], st['unsung'], st['adj'], st['overlay'], st['bg'])
    print(f"\n🎨  Estilo: {args.style} | Modo: {args.mode}")
    print(f"\n📄  Leyendo SRT: {args.srt}")
    words = parse_srt(args.srt)
    if not words:
        print("❌  No se encontraron palabras en el SRT.")
        sys.exit(1)

    total_dur = words[-1].end + 2.5   # 2.5s de buffer al final

    if args.preview:
        words     = [w for w in words if w.start < 30]
        total_dur = min(32.0, total_dur)
        print("    [PREVIEW — solo primeros 30 segundos]")

    print(f"    {len(words)} palabras · {total_dur:.1f}s")

    # ── Líneas ───────────────────────────────────────────────────────────────
    if args.json and Path(args.json).exists():
        print(f"\n📦  Agrupando líneas desde JSON de Whisper: {args.json}")
        lines = group_lines_from_json(args.json)
        print(f"    {len(lines)} líneas (segmentos exactos de Whisper)")
    else:
        print(f"\n📦  Agrupando líneas por gap (umbral = {args.gap}s)...")
        lines = group_lines(words, args.gap)
        if any(sum(twidth(w.text+' ', ImageFont.load_default()) for w in l.words) > 800
               for l in lines):
            print("    ⚠️  Algunas líneas son muy largas. Usa --json para agrupación exacta.")
        print(f"    {len(lines)} líneas líricas")

    if args.generate_map:
        generate_map(args.images, words, lines, 'karaoke_map.json')
        return

    # ── Estados ──────────────────────────────────────────────────────────────
    if args.mode == 'lyrics':
        print(f"\n🎞️   Modo LYRICS — generando estados por línea...")
        states = make_states_lyrics(lines, total_dur)
    else:
        print(f"\n🎞️   Modo KARAOKE — generando estados por palabra...")
        states = make_states(lines, total_dur)
    print(f"    {len(states)} estados únicos (frames mínimos a renderizar)")

    # ── Mapa de imágenes ─────────────────────────────────────────────────────
    print(f"\n🖼️   Mapeando imágenes...")
    img_map   = load_map(args.map, args.images, total_dur)
    img_cache = {}
    print(f"    {len(img_map)} segmento(s) visual(es)")

    # ── Fuente ───────────────────────────────────────────────────────────────
    print(f"\n🔤  Cargando fuente...")
    fmain = load_font(args.font, args.font_size)
    fside = load_font(args.font, int(args.font_size * 0.60))

    # ── Renderizado ──────────────────────────────────────────────────────────
    def do_render(frames_path: Path):
        frames_path.mkdir(parents=True, exist_ok=True)
        fl_path   = frames_path / 'filelist.txt'
        fl_lines  = []
        n_rendered = 0
        t0 = time.time()

        print(f"\n🎨  Renderizando {len(states)} frames → {frames_path}")

        for i, state in enumerate(states):
            dur = state.t_end - state.t_start
            if dur < 0.005:
                continue

            bg    = get_bg(state.t_start, img_map, img_cache, (W, H))
            frame = render_frame(state, bg, fmain, fside, W, H, args.title)

            fp = frames_path / f'f{i:05d}.png'
            frame.save(fp, compress_level=1)

            # FFmpeg concat usa rutas absolutas
            fl_lines.append(f"file '{fp.resolve()}'")
            fl_lines.append(f"duration {dur:.4f}")
            n_rendered += 1

            if (i + 1) % 20 == 0 or i == len(states) - 1:
                ela = time.time() - t0
                eta = ela / (i + 1) * max(0, len(states) - i - 1)
                pct = (i + 1) / len(states) * 100
                bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
                print(f"\r    [{bar}] {pct:5.1f}%  {i+1}/{len(states)}  "
                      f"⏱ {ela:.0f}s  ETA {eta:.0f}s   ", end='', flush=True)

        fl_path.write_text('\n'.join(fl_lines), encoding='utf-8')
        print(f"\n✅  {n_rendered} frames renderizados en {time.time()-t0:.1f}s")
        return fl_path

    # ── Ensamblaje ────────────────────────────────────────────────────────────
    if args.frames_dir:
        # Guardar frames permanentemente (útil para debugging)
        fp_dir    = Path(args.frames_dir)
        fl_path   = do_render(fp_dir)
        print(f"\n🎬  Ensamblando video...")
        run_ffmpeg(fl_path, args.audio, args.output, W, H, args.verbose)
    else:
        # Carpeta temporal auto-limpiada
        with tempfile.TemporaryDirectory() as tmp:
            fl_path = do_render(Path(tmp))
            print(f"\n🎬  Ensamblando video con FFmpeg...")
            run_ffmpeg(fl_path, args.audio, args.output, W, H, args.verbose)

    # ── Resultado ─────────────────────────────────────────────────────────────
    out_path = Path(args.output)
    if out_path.exists():
        mb = out_path.stat().st_size / 1024 / 1024
        print(f"\n🎉  Video listo: {args.output}  ({mb:.1f} MB)")
        print(f"    Resolución : {W}×{H}")
        print(f"    Palabras   : {len(words)}")
        print(f"    Líneas     : {len(lines)}")
        print(f"    Frames gen : {len(states)}")
        if not args.preview:
            fps_equiv = len(states) / total_dur
            print(f"    Eficiencia : {fps_equiv:.1f} frames únicos/seg "
                  f"(vs {30} fps clásico = {int(total_dur*30)} frames)")
    else:
        print("⚠️   El archivo de salida no se encontró. Revisa los errores de FFmpeg.")


if __name__ == '__main__':
    main()
