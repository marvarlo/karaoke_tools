#!/usr/bin/env python3
"""
video_enhancements.py
═══════════════════════════════════════════════════════════════════════════════
Módulo helper para añadir marcas de agua, stickers de redes sociales,
pantalla de outro y transiciones de video al karaoke.
"""

import os
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def generate_preset_watermark(preset, output_path):
    """
    Genera una marca de agua (badge) de red social usando Pillow.
    Presets soportados: 'youtube', 'tiktok', 'instagram', 'facebook'
    """
    W, H = 240, 60
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Intentar cargar una fuente sans-serif en negrita
    font = None
    font_paths = [
        'C:/Windows/Fonts/segoeuib.ttf',      # Segoe UI Bold (Windows)
        'C:/Windows/Fonts/arialbd.ttf',       # Arial Bold (Windows)
        '/Library/Fonts/Arial Bold.ttf',      # Arial Bold (Mac)
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        '/System/Library/Fonts/Helvetica.ttc' # Helvetica (Mac)
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 18)
                break
            except Exception:
                pass
    if font is None:
        try:
            font = ImageFont.load_default(size=18)
        except TypeError:
            font = ImageFont.load_default()

    if preset == 'youtube':
        # Botón rojo clásico con play en blanco y "YouTube" / "SUBSCRIBE"
        draw.rounded_rectangle([10, 10, W-10, H-10], radius=15, fill=(255, 0, 0, 230))
        # Triángulo de Play
        draw.polygon([(32, 22), (32, 38), (46, 30)], fill=(255, 255, 255, 255))
        # Texto
        try:
            draw.text((60, 18), "SUBSCRIBE", fill=(255, 255, 255, 255), font=font)
        except Exception:
            draw.text((60, 20), "SUBSCRIBE", fill=(255, 255, 255, 255))
            
    elif preset == 'tiktok':
        # Fondo oscuro, logo estilo nota musical con desfase cian/magenta y "TikTok"
        draw.rounded_rectangle([10, 10, W-10, H-10], radius=15, fill=(20, 20, 20, 230))
        # Nota musical (efecto 3D desfasado)
        # Magenta offset
        draw.ellipse([27, 27, 39, 39], outline=(254, 44, 85, 255), width=3)
        draw.line([(39, 21), (39, 33)], fill=(254, 44, 85, 255), width=3)
        draw.arc([39, 15, 51, 27], start=90, end=180, fill=(254, 44, 85, 255), width=3)
        # Cian offset
        draw.ellipse([25, 25, 37, 37], outline=(37, 244, 238, 255), width=3)
        draw.line([(37, 19), (37, 31)], fill=(37, 244, 238, 255), width=3)
        draw.arc([37, 13, 49, 25], start=90, end=180, fill=(37, 244, 238, 255), width=3)
        # Texto
        try:
            draw.text((65, 18), "TikTok", fill=(255, 255, 255, 255), font=font)
        except Exception:
            draw.text((65, 20), "TikTok", fill=(255, 255, 255, 255))
            
    elif preset == 'instagram':
        # Fondo degradado rosa-naranja o rosa fuerte y logo de cámara
        draw.rounded_rectangle([10, 10, W-10, H-10], radius=15, fill=(225, 48, 108, 230))
        # Silueta cámara
        draw.rounded_rectangle([25, 22, 45, 38], radius=4, outline=(255, 255, 255, 255), width=2)
        draw.ellipse([31, 26, 39, 34], outline=(255, 255, 255, 255), width=2)
        draw.ellipse([40, 24, 42, 26], fill=(255, 255, 255, 255))
        # Texto
        try:
            draw.text((60, 18), "Instagram", fill=(255, 255, 255, 255), font=font)
        except Exception:
            draw.text((60, 20), "Instagram", fill=(255, 255, 255, 255))
            
    elif preset == 'facebook':
        # Fondo azul Facebook con el logo 'f' y el texto "Facebook"
        draw.rounded_rectangle([10, 10, W-10, H-10], radius=15, fill=(24, 119, 242, 230))
        # Círculo blanco para f
        draw.ellipse([22, 18, 42, 38], fill=(255, 255, 255, 255))
        # Letra f
        fb_font = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    fb_font = ImageFont.truetype(fp, 18)
                    break
                except Exception:
                    pass
        if fb_font:
            draw.text((29, 17), "f", fill=(24, 119, 242, 255), font=fb_font)
        else:
            draw.text((29, 20), "f", fill=(24, 119, 242, 255))
        # Texto
        try:
            draw.text((55, 18), "Facebook", fill=(255, 255, 255, 255), font=font)
        except Exception:
            draw.text((55, 20), "Facebook", fill=(255, 255, 255, 255))
            
    else:
        # Genérico gris oscuro
        draw.rounded_rectangle([10, 10, W-10, H-10], radius=15, fill=(60, 60, 60, 200))
        try:
            draw.text((20, 18), preset.upper(), fill=(255, 255, 255, 255), font=font)
        except Exception:
            draw.text((20, 20), preset.upper(), fill=(255, 255, 255, 255))

    # Guardar
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")

def apply_watermark(frame, watermark_path, pos_name, dur_mode, t, total_dur, W, H):
    """
    Superpone la imagen de la marca de agua sobre el frame.
    Controla la posición (pos_name) y duración (dur_mode).
    """
    # Si la duración se limita al intro (primeros 15s) y ya pasaron, no superponer
    if dur_mode == 'intro' and t > 15.0:
        return frame
        
    if not os.path.exists(watermark_path):
        return frame
        
    try:
        wm = Image.open(watermark_path).convert('RGBA')
    except Exception as e:
        print(f"[WARNING] Error al abrir marca de agua {watermark_path}: {e}")
        return frame
        
    # Escalar marca de agua proporcionalmente al video (~15% del ancho, min 100px y max 300px)
    wm_w = int(W * 0.15)
    wm_w = max(100, min(wm_w, 300))
    aspect = wm.height / wm.width
    wm_h = int(wm_w * aspect)
    wm = wm.resize((wm_w, wm_h), Image.LANCZOS)
    
    # Calcular coordenadas x, y según pos_name
    margin = 30
    if pos_name == 'top-left':
        x, y = margin, margin
    elif pos_name == 'bottom-left':
        x, y = margin, H - wm_h - margin
    elif pos_name == 'top-right':
        x, y = W - wm_w - margin, margin
    else: # bottom-right
        x, y = W - wm_w - margin, H - wm_h - margin
        
    # Crear overlay
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    overlay.paste(wm, (x, y))
    
    # Unir usando alpha composite
    frame_rgba = frame.convert('RGBA')
    merged = Image.alpha_composite(frame_rgba, overlay)
    
    if frame.mode == 'RGB':
        return merged.convert('RGB')
    return merged

def apply_outro_text(frame, outro_text, font, W, H, state):
    """
    Dibuja el texto de disclaimer/outro centrado en pantalla si nos encontramos
    en el gap instrumental final (outro) después del fin de las letras.
    """
    # Detectamos outro: no hay línea actual (state.line es None) pero ya hubo una anterior (state.prev_line no es None)
    if state.line is not None or state.prev_line is None:
        return frame
        
    if not outro_text:
        return frame
        
    img = frame.copy()
    draw = ImageDraw.Draw(img)
    
    # Ajustar ancho máximo (~80% del video)
    max_w = int(W * 0.8)
    
    # Ajustar saltos de línea automáticos
    words = outro_text.replace('\n', ' \n ').split(' ')
    lines = []
    current_line = []
    
    for word in words:
        if word == '\n':
            lines.append(' '.join(current_line))
            current_line = []
            continue
            
        test_line = ' '.join(current_line + [word])
        try:
            bb = font.getbbox(test_line)
            w = bb[2] - bb[0]
        except Exception:
            w = len(test_line) * (getattr(font, 'size', 40) // 2)
            
        if w > max_w:
            lines.append(' '.join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
            
    if current_line:
        lines.append(' '.join(current_line))
        
    # Panel semitransparente detrás del texto para máxima legibilidad
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    
    try:
        bb = font.getbbox("Áyg")
        lh = bb[3] - bb[1]
    except Exception:
        lh = getattr(font, 'size', 40)
        
    line_spacing = 15
    total_text_h = len(lines) * lh + (len(lines) - 1) * line_spacing
    
    panel_w = max_w + 60
    panel_h = total_text_h + 60
    panel_x = (W - panel_w) // 2
    panel_y = (H - panel_h) // 2
    
    ov_draw.rounded_rectangle(
        [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
        radius=20, fill=(0, 0, 0, 140)
    )
    
    img_rgba = img.convert('RGBA')
    img_rgba = Image.alpha_composite(img_rgba, overlay)
    if img.mode == 'RGB':
        img = img_rgba.convert('RGB')
    else:
        img = img_rgba
    draw = ImageDraw.Draw(img)
    
    # Dibujar las líneas centradas
    curr_y = panel_y + 30
    for line_text in lines:
        if not line_text.strip():
            curr_y += lh + line_spacing
            continue
        try:
            bb = font.getbbox(line_text)
            line_w = bb[2] - bb[0]
        except Exception:
            line_w = len(line_text) * (getattr(font, 'size', 40) // 2)
            
        x = (W - line_w) // 2
        # Sombra
        draw.text((x + 2, curr_y + 2), line_text, fill=(0, 0, 0, 255), font=font)
        # Texto principal
        draw.text((x, curr_y), line_text, fill=(244, 239, 230, 255), font=font)
        curr_y += lh + line_spacing
        
    return img
