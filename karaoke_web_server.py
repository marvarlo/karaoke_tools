#!/usr/bin/env python3
"""
karaoke_web_server.py — Servidor HTTP local para la interfaz gráfica de Karaoke Maker
═══════════════════════════════════════════════════════════════════════════════
Ejecuta la interfaz de usuario web interactiva (Wizard) en http://localhost:8080.

USO:
  python karaoke_web_server.py [--port 8080]
"""

import sys
import os
import json
import shutil
import subprocess
import threading
import mimetypes
import urllib.parse
import unicodedata
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

def get_clean_audio_name(cfg, project_name):
    # Intentar obtener de original_audio_name
    name = cfg.get('original_audio_name', '')
    if not name:
        # Intentar obtener del título
        name = cfg.get('title', '')
    if not name:
        # Si no, usar el nombre del proyecto
        name = project_name
    
    # Quitar extensión si tiene
    if '.' in name:
        name = Path(name).stem
        
    # Reemplazar espacios por guiones y normalizar
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')
    # Reemplazar espacios por guiones
    name = name.replace(' ', '-')
    # Solo caracteres alfanuméricos, guiones y guiones bajos
    clean_name = "".join(c for c in name if c.isalnum() or c in ('-', '_'))
    # Quitar guiones duplicados y extremos
    while '--' in clean_name:
        clean_name = clean_name.replace('--', '-')
    return clean_name.strip('-')

def get_dynamic_output_name(cfg, project_name, preview=False, mode=None):
    if mode is None:
        mode = cfg.get('mode', 'karaoke')
    # Mode can be 'lyrics' or 'karaoke'
    suffix = "Lyrics" if mode == "lyrics" else "karaoke"
    clean_audio = get_clean_audio_name(cfg, project_name)
    if preview:
        return f"{clean_audio}-{suffix}-preview.mp4"
    else:
        return f"{clean_audio}-{suffix}.mp4"


# Intentar registrar mime-types adicionales
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('video/mp4', '.mp4')

# Rutas globales
WORKSPACE_DIR = Path(__file__).parent.resolve()
WEB_UI_DIR = WORKSPACE_DIR / 'web_ui'
VENV_PYTHON = WORKSPACE_DIR / '.venv' / 'Scripts' / 'python.exe'

# Fallback si no existe la de .venv
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

# ──────────────────────────────────────────────────────────────────────────────
# GESTOR DE TAREAS EN SEGUNDO PLANO
# ──────────────────────────────────────────────────────────────────────────────

class TaskManager:
    def __init__(self):
        self.lock = threading.Lock()
        # project_name -> task_info
        self.tasks = {}

    def get_status(self, project_name):
        with self.lock:
            if project_name not in self.tasks:
                return {"status": "idle", "task": None, "progress": 0, "logs": ""}
            return self.tasks[project_name]

    def set_task(self, project_name, task_type, status="running", progress=0, logs=""):
        with self.lock:
            self.tasks[project_name] = {
                "status": status,
                "task": task_type,
                "progress": progress,
                "logs": logs
            }

    def append_log(self, project_name, text):
        with self.lock:
            if project_name in self.tasks:
                self.tasks[project_name]["logs"] += text
                # Limitar logs a últimas 100 líneas
                lines = self.tasks[project_name]["logs"].split('\n')
                if len(lines) > 200:
                    self.tasks[project_name]["logs"] = '\n'.join(lines[-200:])

    def update_progress(self, project_name, progress):
        with self.lock:
            if project_name in self.tasks:
                self.tasks[project_name]["progress"] = progress

    def run_command_async(self, project_name, cmd, task_type, total_duration=None):
        def worker():
            print(f"[RUN] Iniciando comando para {project_name} ({task_type}): {' '.join(cmd)}")
            self.set_task(project_name, task_type, status="running", progress=0, logs=f"--- Iniciando {task_type} ---\n")
            try:
                # Forzar codificación UTF-8 en el subproceso Python en Windows
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(WORKSPACE_DIR),
                    encoding='utf-8',
                    errors='ignore',
                    env=env
                )

                # Leer salida en tiempo real
                while True:
                    # Lee un caracter o una línea
                    # El assembler usa \r para actualizar la barra en la misma línea.
                    # Vamos a leer línea por línea, pero permitiendo separar por \r
                    char_buffer = []
                    while True:
                        char = process.stdout.read(1)
                        if not char:
                            break
                        if char == '\n' or char == '\r':
                            char_buffer.append(char)
                            break
                        char_buffer.append(char)
                    
                    if not char_buffer:
                        break
                        
                    line = ''.join(char_buffer)
                    self.append_log(project_name, line)
                    
                    # Intentar parsear progreso
                    if task_type in ('assembler', 'separator'):
                        # Formato: [██████░░░░]  60.5%  180/300 or tqdm bar
                        if '%' in line:
                            try:
                                parts = line.split('%')[0].split()
                                if parts:
                                    val = parts[-1].strip('[ ')
                                    pct = float(val)
                                    self.update_progress(project_name, int(pct))
                            except Exception:
                                pass
                    elif task_type == 'whisper':
                        # Whisper de por sí no tiene una barra numérica directa en stdout,
                        # pero muestra segmentos como: [00:15.50 -> 00:18.00]
                        # Si conocemos la duración total, podemos aproximar.
                        if '->' in line and total_duration:
                            try:
                                # Extraer segundos del timestamp
                                # Ej: [01:23.45 -> ...
                                ts = line.split('->')[0].replace('[', '').strip()
                                parts = ts.split(':')
                                seconds = 0.0
                                if len(parts) == 2: # MM:SS.ss
                                    seconds = int(parts[0]) * 60 + float(parts[1])
                                elif len(parts) == 3: # HH:MM:SS.ss
                                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                                pct = min(99, int((seconds / total_duration) * 100))
                                self.update_progress(project_name, pct)
                            except Exception:
                                pass

                process.wait()
                if process.returncode == 0:
                    self.set_task(project_name, task_type, status="success", progress=100, 
                                  logs=self.tasks[project_name]["logs"] + f"\n--- {task_type} completado con éxito! ---")
                else:
                    self.set_task(project_name, task_type, status="failed", progress=0, 
                                  logs=self.tasks[project_name]["logs"] + f"\n❌ El proceso falló con código {process.returncode}")
            except Exception as e:
                self.set_task(project_name, task_type, status="failed", progress=0, 
                              logs=self.tasks[project_name]["logs"] + f"\n❌ Error al ejecutar proceso: {str(e)}")

        t = threading.Thread(target=worker, daemon=True)
        t.start()

task_manager = TaskManager()

# ──────────────────────────────────────────────────────────────────────────────
# MULTIPART FORM DATA PARSER
# ──────────────────────────────────────────────────────────────────────────────

def parse_multipart_data(rfile, headers):
    content_type = headers.get('Content-Type', '')
    if not content_type.startswith('multipart/form-data'):
        return {}, {}
    
    # Extraer boundary
    boundary_parts = content_type.split('boundary=')
    if len(boundary_parts) < 2:
        return {}, {}
    boundary = boundary_parts[1].strip().encode('utf-8')
    
    # Content-Length
    content_length = int(headers.get('Content-Length', 0))
    if content_length == 0:
        return {}, {}
        
    body = rfile.read(content_length)
    
    # Separar partes por el boundary
    full_boundary = b'--' + boundary
    parts = body.split(full_boundary)
    
    form_data = {}
    files = {}
    
    for part in parts:
        if not part or part == b'--\r\n' or part == b'--':
            continue
        # Limpiar saltos de línea iniciales/finales
        if part.startswith(b'\r\n'):
            part = part[2:]
        if part.endswith(b'\r\n'):
            part = part[:-2]
            
        # Separar headers del contenido
        subparts = part.split(b'\r\n\r\n', 1)
        if len(subparts) < 2:
            continue
        part_headers_bytes, part_content = subparts
        
        part_headers = part_headers_bytes.decode('utf-8', errors='ignore')
        
        disposition = ''
        name = ''
        filename = ''
        for line in part_headers.split('\r\n'):
            if line.lower().startswith('content-disposition:'):
                disposition = line
                # Extraer nombre y filename
                for segment in line.split(';'):
                    segment = segment.strip()
                    if segment.startswith('name='):
                        name = segment.split('=')[1].strip('"')
                    elif segment.startswith('filename='):
                        filename = segment.split('=')[1].strip('"')
                        
        if name:
            if filename:
                files[name] = {
                    'filename': filename,
                    'content': part_content
                }
            else:
                form_data[name] = part_content.decode('utf-8', errors='ignore')
                
    return form_data, files

# ──────────────────────────────────────────────────────────────────────────────
# HANDLER HTTP
# ──────────────────────────────────────────────────────────────────────────────

class KaraokeHTTPHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Deshabilitar logs estándar de consola para no contaminar
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status)

    def do_OPTIONS(self):
        # Soporte CORS para desarrollo
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path
        query = urllib.parse.parse_qs(url_parsed.query)

        # ── ENDPOINTS DE LA API ───────────────────────────────────────────────
        
        if path == '/api/projects':
            # Listar proyectos (carpetas que tengan config.json en el directorio)
            projects = []
            for item in WORKSPACE_DIR.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name != 'web_ui':
                    cfg_file = item / 'config.json'
                    if cfg_file.exists():
                        try:
                            cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
                            projects.append({
                                "name": item.name,
                                "title": cfg.get("title", item.name),
                                "artist": cfg.get("artist", "")
                            })
                        except Exception:
                            projects.append({
                                "name": item.name,
                                "title": item.name,
                                "artist": ""
                            })
            return self.send_json({"projects": projects})

        elif path == '/api/info':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta el parámetro 'project'")
            
            project_path = WORKSPACE_DIR / project_name
            if not project_path.exists() or not project_path.is_dir():
                return self.send_error_json("Proyecto no encontrado")
            
            # Cargar config
            cfg_file = project_path / 'config.json'
            config = {}
            if cfg_file.exists():
                try:
                    config = json.loads(cfg_file.read_text(encoding='utf-8'))
                except Exception as e:
                    return self.send_error_json(f"Error al leer config.json: {str(e)}")

            out_dir = project_path / 'output'
            
            # Comprobar estado de archivos
            audio_file = project_path / config.get('audio', 'audio.mp3')
            images_dir = project_path / config.get('images_folder', 'images')
            
            images_list = []
            if images_dir.exists():
                images_list = [p.name for p in images_dir.iterdir() if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}]
                images_list.sort()

            info = {
                "config": config,
                "status": {
                    "audio_exists": audio_file.exists() and audio_file.stat().st_size > 0,
                    "instrumental_exists": (project_path / "instrumental.mp3").exists() and (project_path / "instrumental.mp3").stat().st_size > 0,
                    "images_count": len(images_list),
                    "words_json_exists": (out_dir / 'words.json').exists(),
                    "words_srt_exists": (out_dir / 'words.srt').exists(),
                    "map_exists": (out_dir / 'map.json').exists(),
                    "video_exists": (out_dir / get_dynamic_output_name(config, project_name, preview=False)).exists(),
                    "preview_exists": (out_dir / get_dynamic_output_name(config, project_name, preview=True)).exists()
                },
                "images": images_list
            }
            return self.send_json(info)

        elif path == '/api/images':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta el parámetro 'project'")
            
            project_path = WORKSPACE_DIR / project_name
            images_dir = project_path / 'images'
            if not images_dir.exists():
                return self.send_json({"images": []})
            
            exts = {'.png', '.jpg', '.jpeg', '.webp'}
            imgs = [p.name for p in images_dir.iterdir() if p.suffix.lower() in exts]
            imgs.sort()
            return self.send_json({"images": imgs})

        elif path == '/api/background_videos':
            base_dir = WORKSPACE_DIR / 'base_videos'
            loop_dir = WORKSPACE_DIR / 'loop_videos'
            
            video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
            
            base_list = []
            if base_dir.exists():
                base_list = [f"base_videos/{p.name}" for p in base_dir.iterdir() if p.suffix.lower() in video_exts]
                base_list.sort()
                
            loop_list = []
            if loop_dir.exists():
                loop_list = [f"loop_videos/{p.name}" for p in loop_dir.iterdir() if p.suffix.lower() in video_exts]
                loop_list.sort()
                
            return self.send_json({
                "base_videos": base_list,
                "loop_videos": loop_list
            })

        # Endpoint para listar las imágenes pre-cargadas de base_images/
        elif path == '/api/base_images':
            base_dir = WORKSPACE_DIR / 'base_images'
            img_exts = {'.png', '.jpg', '.jpeg', '.webp'}
            
            images = []
            collections = set()
            
            if base_dir.exists():
                for p in sorted(base_dir.iterdir()):
                    if p.suffix.lower() not in img_exts:
                        continue
                    # Detectar colección a partir del prefijo del nombre
                    # Ej: "Ciudad-Roja-1.png" -> "Ciudad Roja"
                    # Ej: "Karaoke_neon_1.png" -> "Karaoke Neon"
                    stem = p.stem  # nombre sin extensión
                    # Quitar número final (ej: -1, _1, _2, etc.)
                    import re
                    base_name = re.sub(r'[-_]\d+$', '', stem)
                    # Convertir separadores a espacios y capitalizar cada palabra
                    collection = ' '.join(
                        word.capitalize()
                        for word in re.split(r'[-_]', base_name)
                        if word
                    )
                    collections.add(collection)
                    images.append({
                        "filename": p.name,
                        "path": f"base_images/{p.name}",
                        "collection": collection
                    })
            
            return self.send_json({
                "images": images,
                "collections": sorted(collections)
            })

        # Endpoint para servir archivos de imagen de base_images/ (para miniaturas)
        elif path == '/api/base_image_file':
            filename = query.get('filename', [''])[0]
            if not filename:
                return self.send_error_json("Falta el parámetro 'filename'")
            
            # Prevenir path traversal — solo nombre de archivo, no rutas
            if '/' in filename or '\\' in filename or '..' in filename:
                return self.send_error_json("Nombre de archivo no válido", 403)
            
            filepath = (WORKSPACE_DIR / 'base_images' / filename).resolve()
            
            # Verificar que esté dentro de base_images/
            try:
                filepath.relative_to((WORKSPACE_DIR / 'base_images').resolve())
            except ValueError:
                return self.send_error_json("Acceso no autorizado", 403)
            
            if not filepath.exists() or filepath.is_dir():
                return self.send_error_json("Imagen no encontrada", 404)
            
            self.send_response(200)
            mime, _ = mimetypes.guess_type(str(filepath))
            self.send_header('Content-Type', mime or 'image/png')
            self.send_header('Cache-Control', 'max-age=3600')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
            return

        elif path == '/api/video_file':
            filepath_str = query.get('path', [''])[0]
            if not filepath_str:
                return self.send_error_json("Falta el parámetro 'path'")
            
            # Normalizar la ruta y verificar seguridad
            resolved_path = (WORKSPACE_DIR / filepath_str).resolve()
            
            # Verificar que la ruta resuelta esté dentro de WORKSPACE_DIR
            try:
                resolved_path.relative_to(WORKSPACE_DIR)
            except ValueError:
                return self.send_error_json("Acceso no autorizado", 403)
                
            # Adicionalmente, verificar que pertenezca a base_videos o loop_videos
            parts = resolved_path.relative_to(WORKSPACE_DIR).parts
            if not parts or parts[0] not in ('base_videos', 'loop_videos'):
                return self.send_error_json("Acceso no autorizado", 403)
                
            if not resolved_path.exists() or resolved_path.is_dir():
                return self.send_error_json("Archivo no encontrado", 404)
                
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', str(resolved_path.stat().st_size))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(resolved_path, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    self.wfile.write(data)
            return

        elif path == '/api/map':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta el parámetro 'project'")
            
            map_file = WORKSPACE_DIR / project_name / 'output' / 'map.json'
            if not map_file.exists():
                return self.send_error_json("El mapa no ha sido generado aún. Corre la transcripción primero.")
            
            try:
                map_data = json.loads(map_file.read_text(encoding='utf-8'))
                return self.send_json(map_data)
            except Exception as e:
                return self.send_error_json(f"Error al leer map.json: {str(e)}")

        elif path == '/api/words':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta el parámetro 'project'")
            
            words_file = WORKSPACE_DIR / project_name / 'output' / 'words.json'
            if not words_file.exists():
                return self.send_error_json("La transcripción no existe aún.")
            
            try:
                words_data = json.loads(words_file.read_text(encoding='utf-8'))
                return self.send_json(words_data)
            except Exception as e:
                return self.send_error_json(f"Error al leer words.json: {str(e)}")

        elif path == '/api/status':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta el parámetro 'project'")
            
            return self.send_json(task_manager.get_status(project_name))

        # Endpoint para servir archivos de imagen de un proyecto (para miniaturas)
        elif path == '/api/image_file':
            project_name = query.get('project', [''])[0]
            filename = query.get('file', [''])[0]
            if not project_name or not filename:
                return self.send_error_json("Falta 'project' o 'file'")
            
            filepath = WORKSPACE_DIR / project_name / 'images' / filename
            if not filepath.exists() or filepath.is_dir():
                return self.send_error_json("Imagen no encontrada", 404)
            
            self.send_response(200)
            mime, _ = mimetypes.guess_type(str(filepath))
            self.send_header('Content-Type', mime or 'image/png')
            self.send_header('Cache-Control', 'max-age=3600')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
            return

        # Endpoint para servir el video final o preview
        elif path == '/api/video':
            project_name = query.get('project', [''])[0]
            preview = query.get('preview', ['false'])[0] == 'true'
            is_download = query.get('download', ['false'])[0] == 'true'
            if not project_name:
                return self.send_error_json("Falta 'project'")
            
            project_path = WORKSPACE_DIR / project_name
            cfg_file = project_path / 'config.json'
            if not cfg_file.exists():
                return self.send_error_json("Proyecto no válido")
                
            cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
            out_name = get_dynamic_output_name(cfg, project_name, preview=preview)
                
            filepath = project_path / 'output' / out_name
            if not filepath.exists():
                return self.send_error_json("Video no encontrado", 404)
            
            # Servir con soporte parcial de rango (si lo requiere el navegador)
            # Para simplificar, servimos el archivo completo
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', str(filepath.stat().st_size))
            self.send_header('Access-Control-Allow-Origin', '*')
            
            if is_download:
                self.send_header('Content-Disposition', f'attachment; filename="{out_name}"')
                
            self.end_headers()
            with open(filepath, 'rb') as f:
                # Escribir en bloques de 64KB para evitar sobrecarga de memoria
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    self.wfile.write(data)
            return

        elif path == '/api/download_video':
            project_name = query.get('project', [''])[0]
            preview = query.get('preview', ['false'])[0] == 'true'
            if not project_name:
                return self.send_error_json("Falta 'project'")
            
            project_path = WORKSPACE_DIR / project_name
            cfg_file = project_path / 'config.json'
            if not cfg_file.exists():
                return self.send_error_json("Proyecto no válido")
                
            cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
            out_name = get_dynamic_output_name(cfg, project_name, preview=preview)
                
            filepath = project_path / 'output' / out_name
            if not filepath.exists():
                return self.send_error_json("Video no encontrado", 404)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(filepath.stat().st_size))
            self.send_header('Content-Disposition', f'attachment; filename="{out_name}"')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(filepath, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    self.wfile.write(data)
            return

        # Endpoint para listar fuentes disponibles del sistema
        elif path == '/api/fonts':
            # Solo devolvemos algunas de las fuentes de FONT_PATHS que realmente existen
            from karaoke_assembler import FONT_PATHS
            available = []
            for p in FONT_PATHS:
                if Path(p).exists():
                    available.append({
                        "name": Path(p).stem,
                        "path": p
                    })
            # Agregar también cualquier archivo .ttf en la raíz o subcarpetas del proyecto
            for ttf in WORKSPACE_DIR.glob('**/*.ttf'):
                if '.venv' not in ttf.parts:
                    available.append({
                        "name": f"[Proyecto] {ttf.name}",
                        "path": str(ttf.resolve())
                    })
            return self.send_json({"fonts": available})

        # Endpoint para servir el archivo de fuente binario (.ttf/.otf) al cliente
        elif path == '/api/font_file':
            font_path_str = query.get('path', [''])[0]
            if not font_path_str:
                return self.send_error_json("Falta el parámetro 'path'")
            
            filepath = Path(font_path_str)
            if not filepath.exists() or filepath.is_dir() or filepath.suffix.lower() not in {'.ttf', '.otf'}:
                return self.send_error_json("Archivo de fuente no válido o no encontrado", 404)
            
            self.send_response(200)
            self.send_header('Content-Type', 'font/ttf')
            self.send_header('Content-Length', str(filepath.stat().st_size))
            self.send_header('Cache-Control', 'max-age=3600')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
            return

        # ── SERVIR INTERFAZ WEB (STATIC FILES) ────────────────────────────────
        
        # Redirigir la raíz a /index.html
        if path == '/':
            path = '/index.html'

        # Resolver ruta del archivo estático
        file_path = WEB_UI_DIR / path.lstrip('/')
        # Prevenir path traversal
        try:
            file_path.relative_to(WEB_UI_DIR)
        except ValueError:
            return self.send_error_json("Acceso no autorizado", 403)

        if file_path.exists() and file_path.is_file():
            self.send_response(200)
            mime_type, _ = mimetypes.guess_type(str(file_path))
            self.send_header('Content-Type', mime_type or 'text/plain')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path
        query = urllib.parse.parse_qs(url_parsed.query)

        # ── CREACIÓN DE PROYECTO (MULTIPART) ──────────────────────────────────
        if path == '/api/init':
            form, files = parse_multipart_data(self.rfile, self.headers)
            
            name = form.get('name', '').strip()
            if not name:
                return self.send_error_json("El nombre del proyecto es obligatorio")
            
            # Sanitizar nombre
            name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
            if not name:
                return self.send_error_json("El nombre del proyecto contiene caracteres no válidos")

            project_path = WORKSPACE_DIR / name
            is_new = not project_path.exists()

            # Crear directorios
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / 'images').mkdir(exist_ok=True)
            (project_path / 'output').mkdir(exist_ok=True)

            # Manejar el audio
            audio_field = files.get('audio')
            audio_filename = "audio.mp3"
            original_audio_name = ""
            
            if not is_new:
                # Si el proyecto ya existe, recuperar el nombre del archivo de audio de la configuración previa
                cfg_file = project_path / 'config.json'
                if cfg_file.exists():
                    try:
                        old_cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
                        audio_filename = old_cfg.get('audio', 'audio.mp3')
                        original_audio_name = old_cfg.get('original_audio_name', '')
                    except Exception:
                        pass

            if audio_field and audio_field['content']:
                # Guardar el archivo subido si se proporciona uno nuevo
                orig_filename = audio_field['filename']
                original_audio_name = orig_filename
                ext = Path(orig_filename).suffix.lower() or '.mp3'
                audio_filename = f"audio{ext}"
                with open(project_path / audio_filename, 'wb') as f:
                    f.write(audio_field['content'])
            elif is_new:
                # Solo si el proyecto es nuevo creamos un archivo de audio vacío si no se subió nada
                (project_path / 'audio.mp3').touch()

            # Configuración
            cfg = {
                "_nota": "Edita este archivo para personalizar el proyecto.",
                "title": form.get('title', name),
                "artist": form.get('artist', ''),
                "audio": audio_filename,
                "original_audio_name": original_audio_name,
                "language": form.get('lang', 'es'),
                "whisper_model": form.get('whisper_model', 'medium'),
                "mode": form.get('mode', 'karaoke'),
                "style": form.get('style', 'minimal'),
                "resolution": form.get('resolution', '1920x1080'),
                "font": form.get('font') or None,
                "font_size": int(form.get('font_size', 72)),
                "images_folder": "images",
                "output_name": "karaoke.mp4",
                "show_title": form.get('show_title') == 'true',
                "gap_threshold": float(form.get('gap_threshold', 1.2))
            }
            # Computar output_name dinámicamente y guardarlo
            cfg['output_name'] = get_dynamic_output_name(cfg, name, preview=False, mode=cfg['mode'])
            
            (project_path / 'config.json').write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8'
            )

            # Generar README
            readme = f"# {cfg['title']} — Proyecto Karaoke\nCreado: {Path(project_path).name}\n"
            (project_path / 'README.txt').write_text(readme, encoding='utf-8')

            return self.send_json({"success": True, "project": name})

        # ── CONFIGURACIÓN (JSON) ──────────────────────────────────────────────
        elif path == '/api/config':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            project_name = data.get('project')
            new_config = data.get('config')
            
            if not project_name or not new_config:
                return self.send_error_json("Parámetros incorrectos")
                
            cfg_file = WORKSPACE_DIR / project_name / 'config.json'
            if not cfg_file.exists():
                return self.send_error_json("Proyecto no encontrado")
                
            try:
                # Mantener nota
                old_cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
                new_config['_nota'] = old_cfg.get('_nota', '')
                new_config['output_name'] = get_dynamic_output_name(new_config, project_name, preview=False)
                cfg_file.write_text(json.dumps(new_config, ensure_ascii=False, indent=2), encoding='utf-8')
                return self.send_json({"success": True})
            except Exception as e:
                return self.send_error_json(f"Error al guardar config: {str(e)}")

        # ── SUBIR IMAGEN (MULTIPART) ──────────────────────────────────────────
        elif path == '/api/upload_image':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta 'project'")
                
            form, files = parse_multipart_data(self.rfile, self.headers)
            img_field = files.get('image')
            
            if not img_field or not img_field['content']:
                return self.send_error_json("No se envió ninguna imagen")
                
            filename = img_field['filename']
            # Asegurar extensión válida
            ext = Path(filename).suffix.lower()
            if ext not in {'.png', '.jpg', '.jpeg', '.webp'}:
                return self.send_error_json("Formato de imagen no soportado (debe ser PNG, JPG, JPEG o WEBP)")
                
            # Limpiar nombre
            clean_name = Path(filename).stem
            clean_name = "".join(c for c in clean_name if c.isalnum() or c in ('_', '-')) + ext
            
            images_dir = WORKSPACE_DIR / project_name / 'images'
            images_dir.mkdir(exist_ok=True)
            
            dest = images_dir / clean_name
            with open(dest, 'wb') as f:
                f.write(img_field['content'])
                
            return self.send_json({"success": True, "filename": clean_name})

        # ── SUBIR VIDEO (MULTIPART) ───────────────────────────────────────────
        elif path == '/api/upload_video':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta 'project'")
                
            form, files = parse_multipart_data(self.rfile, self.headers)
            video_field = files.get('video')
            
            if not video_field or not video_field['content']:
                return self.send_error_json("No se envió ningún video")
                
            filename = video_field['filename']
            # Asegurar extensión válida
            ext = Path(filename).suffix.lower()
            if ext not in {'.mp4', '.mov', '.avi', '.mkv', '.webm'}:
                return self.send_error_json("Formato de video no soportado (debe ser MP4, MOV, AVI, MKV o WEBM)")
                
            # Limpiar nombre
            clean_name = Path(filename).stem
            clean_name = "".join(c for c in clean_name if c.isalnum() or c in ('_', '-')) + ext
            
            loop_videos_dir = WORKSPACE_DIR / 'loop_videos'
            loop_videos_dir.mkdir(exist_ok=True)
            
            dest = loop_videos_dir / clean_name
            with open(dest, 'wb') as f:
                f.write(video_field['content'])
                
            return self.send_json({"success": True, "filename": f"loop_videos/{clean_name}"})

        # ── ELIMINAR IMAGEN ───────────────────────────────────────────────────
        elif path == '/api/delete_image':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            project_name = data.get('project')
            filename = data.get('file')
            
            if not project_name or not filename:
                return self.send_error_json("Parámetros incorrectos")
                
            project_path = WORKSPACE_DIR / project_name
            img_file = project_path / 'images' / filename
            if img_file.exists() and img_file.is_file():
                try:
                    img_file.unlink()
                    return self.send_json({"success": True})
                except Exception as e:
                    return self.send_error_json(f"Error al eliminar imagen: {str(e)}")
            else:
                return self.send_error_json("Imagen no encontrada")

        # ── COPIAR IMAGEN DE BIBLIOTECA BASE AL PROYECTO ──────────────────────
        elif path == '/api/copy_base_image':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            project_name = data.get('project')
            filename = data.get('filename')
            
            if not project_name or not filename:
                return self.send_error_json("Parámetros incorrectos")
            
            # Prevenir path traversal
            if '/' in filename or '\\' in filename or '..' in filename:
                return self.send_error_json("Nombre de archivo no válido", 403)
            
            src = (WORKSPACE_DIR / 'base_images' / filename).resolve()
            
            # Verificar seguridad
            try:
                src.relative_to((WORKSPACE_DIR / 'base_images').resolve())
            except ValueError:
                return self.send_error_json("Acceso no autorizado", 403)
            
            if not src.exists() or src.is_dir():
                return self.send_error_json("Imagen base no encontrada", 404)
            
            images_dir = WORKSPACE_DIR / project_name / 'images'
            images_dir.mkdir(exist_ok=True)
            dest = images_dir / filename
            
            # Copiar solo si no existe ya (idempotente)
            if not dest.exists():
                shutil.copy2(src, dest)
            
            return self.send_json({"ok": True, "filename": filename})

        # ── GUARDAR MAPA (JSON) ───────────────────────────────────────────────
        elif path == '/api/map':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            project_name = data.get('project')
            map_data = data.get('map')
            
            if not project_name or not map_data:
                return self.send_error_json("Parámetros incorrectos")
                
            map_file = WORKSPACE_DIR / project_name / 'output' / 'map.json'
            try:
                map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding='utf-8')
                return self.send_json({"success": True})
            except Exception as e:
                return self.send_error_json(f"Error al guardar el mapa: {str(e)}")

        # ── GUARDAR LETRAS Y PALABRAS EDITADAS (JSON + SRT) ───────────────────────
        elif path == '/api/save_words':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            project_name = data.get('project')
            segments = data.get('segments')
            
            if not project_name or segments is None:
                return self.send_error_json("Parámetros incorrectos")
                
            project_path = WORKSPACE_DIR / project_name
            out_dir = project_path / 'output'
            words_json = out_dir / 'words.json'
            words_srt = out_dir / 'words.srt'
            
            try:
                # Cargar el JSON original para conservar campos como idioma, etc.
                old_data = {}
                if words_json.exists():
                    old_data = json.loads(words_json.read_text(encoding='utf-8'))
                
                # Reconstruir listado plano de palabras (words_flat)
                words_flat = []
                for seg in segments:
                    seg_id = int(seg.get('id', 0))
                    seg_text = seg.get('text', '').strip()
                    
                    for w in seg.get('words', []):
                        words_flat.append({
                            "word": w.get('word', '').strip(),
                            "start": round(float(w.get('start', 0.0)), 3),
                            "end": round(float(w.get('end', 0.0)), 3),
                            "duration_ms": int(round((float(w.get('end', 0.0)) - float(w.get('start', 0.0))) * 1000)),
                            "confidence": round(float(w.get('confidence', 1.0)), 3),
                            "segment_id": seg_id,
                            "line_text": seg_text
                        })
                
                # Formatear timestamps en segmentos para visualización
                def fmt_display(sec):
                    m = int(sec // 60)
                    s = sec % 60
                    return f"{m:02d}:{s:05.2f}"
                
                for seg in segments:
                    seg['start_fmt'] = fmt_display(seg.get('start', 0.0))
                    seg['end_fmt'] = fmt_display(seg.get('end', 0.0))
                    seg['word_count'] = len(seg.get('words', []))
                    # Limpiar campo line_text de cada palabra
                    for w in seg.get('words', []):
                        if 'line_text' in w:
                            del w['line_text']
                
                new_data = {
                    "language": old_data.get('language', 'es'),
                    "total_words": len(words_flat),
                    "total_segments": len(segments),
                    "words_flat": words_flat,
                    "segments": segments
                }
                
                # Guardar words.json
                words_json.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding='utf-8')
                
                # Generar words.srt
                def fmt_srt(sec: float) -> str:
                    total_ms = int(round(sec * 1000))
                    ms = total_ms % 1000
                    total_s = total_ms // 1000
                    s = total_s % 60
                    m = (total_s // 60) % 60
                    h = total_s // 3600
                    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                
                entries = []
                for i, w in enumerate(words_flat, 1):
                    entries.append(
                        f"{i}\n"
                        f"{fmt_srt(w['start'])} --> {fmt_srt(w['end'])}\n"
                        f"{w['word']}\n"
                    )
                words_srt.write_text("\n".join(entries), encoding="utf-8")
                
                return self.send_json({"success": True})
            except Exception as e:
                return self.send_error_json(f"Error al guardar letras: {str(e)}")

        # ── EJECUTAR SEPARADOR ────────────────────────────────────────────────
        elif path == '/api/run_separator':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta 'project'")
                
            project_path = WORKSPACE_DIR / project_name
            cfg_file = project_path / 'config.json'
            if not cfg_file.exists():
                return self.send_error_json("Proyecto no encontrado")
                
            cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
            audio_path = project_path / cfg.get('audio', 'audio.mp3')
            
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                return self.send_error_json("El archivo de audio no existe o está vacío. Por favor sube un archivo de audio válido en el Paso 1.")
            
            # Limpiar pistas anteriores si existen
            instrumental_file = project_path / 'instrumental.mp3'
            vocals_file = project_path / 'vocals.mp3'
            if instrumental_file.exists():
                try: instrumental_file.unlink()
                except Exception: pass
            if vocals_file.exists():
                try: vocals_file.unlink()
                except Exception: pass
                
            # Comando: python.exe karaoke_separator.py <audio_path> <project_path>
            cmd = [
                str(VENV_PYTHON),
                str(WORKSPACE_DIR / 'karaoke_separator.py'),
                str(audio_path),
                str(project_path)
            ]
            
            # Ejecutar tarea asíncrona de tipo 'separator'
            task_manager.run_command_async(project_name, cmd, 'separator')
            return self.send_json({"success": True})

        # ── EJECUTAR WHISPER ──────────────────────────────────────────────────
        elif path == '/api/run_whisper':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta 'project'")
                
            project_path = WORKSPACE_DIR / project_name
            cfg_file = project_path / 'config.json'
            if not cfg_file.exists():
                return self.send_error_json("Proyecto no encontrado")
                
            cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
            
            use_vocals = query.get('use_vocals', ['false'])[0] == 'true'
            cfg['transcribe_from_vocals'] = use_vocals
            try:
                cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception as e:
                print(f"[WARNING] No se pudo guardar config.json al correr whisper: {e}")
            
            # Obtener duración aproximada del MP3 para estimar el porcentaje (usando ffprobe si está disponible)
            audio_path = project_path / cfg.get('audio', 'audio.mp3')
            if use_vocals:
                vocals_path = project_path / 'vocals.mp3'
                if not vocals_path.exists() or vocals_path.stat().st_size == 0:
                    return self.send_error_json("No se encontró el archivo de voz limpia (vocals.mp3) o está vacío. Por favor realiza la separación de audio primero.")
                audio_path = vocals_path
            else:
                if not audio_path.exists() or audio_path.stat().st_size == 0:
                    return self.send_error_json("El archivo de audio no existe o está vacío. Por favor sube un archivo de audio válido en el Paso 1.")
                    
            total_duration = 200.0 # fallback por defecto (3:20 mins)
            try:
                probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)]
                res = subprocess.run(probe_cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    total_duration = float(res.stdout.strip())
            except Exception:
                pass
            
            # Borrar palabras previas para asegurar la recreación
            words_json = project_path / 'output' / 'words.json'
            words_srt = project_path / 'output' / 'words.srt'
            map_json = project_path / 'output' / 'map.json'
            if words_json.exists(): words_json.unlink()
            if words_srt.exists(): words_srt.unlink()
            
            # Comando: python.exe karaoke_timing.py <audio> --model <model> --language <lang> --output <output>
            cmd = [
                str(VENV_PYTHON),
                str(WORKSPACE_DIR / 'karaoke_timing.py'),
                str(audio_path),
                '--model', cfg.get('whisper_model', 'medium'),
                '--language', cfg.get('language', 'es'),
                '--output', str(project_path / 'output')
            ]
            
            # Ejecutar de fondo
            task_manager.run_command_async(project_name, cmd, 'whisper', total_duration)
            
            # Iniciar un hilo monitor para que renombre el archivo generado cuando termine Whisper y genere el primer map.json
            def monitor_post_whisper():
                # Esperar a que termine la tarea
                import time
                while True:
                    time.sleep(1)
                    status = task_manager.get_status(project_name)
                    if status["status"] == "success":
                        # Whisper de por sí genera '<audio_stem>_words.json'
                        # Renombrarlo a words.json y words.srt
                        stem = Path(audio_path).stem
                        gen_json = project_path / 'output' / f"{stem}_words.json"
                        gen_srt = project_path / 'output' / f"{stem}_words.srt"
                        
                        target_json = project_path / 'output' / "words.json"
                        target_srt = project_path / 'output' / "words.srt"
                        
                        if gen_json.exists() and not target_json.exists():
                            gen_json.rename(target_json)
                        if gen_srt.exists() and not target_srt.exists():
                            gen_srt.rename(target_srt)
                            
                        # Ahora generar mapa automático si no existe
                        if not map_json.exists():
                            # python karaoke_assembler.py --generate-map --images <dir> --srt <srt> --audio <audio> --json <json>
                            gen_map_cmd = [
                                str(VENV_PYTHON),
                                str(WORKSPACE_DIR / 'karaoke_assembler.py'),
                                '--generate-map',
                                '--images', str(project_path / 'images'),
                                '--srt', str(target_srt),
                                '--audio', str(audio_path),
                                '--json', str(target_json)
                            ]
                            
                            # Ejecutar temporalmente y mover karaoke_map.json a output/map.json
                            task_manager.append_log(project_name, "\n⚙️ Generando mapa automático de imágenes (map.json) en base a silencios...\n")
                            env = os.environ.copy()
                            env["PYTHONIOENCODING"] = "utf-8"
                            env["PYTHONUTF8"] = "1"
                            subprocess.run(gen_map_cmd, cwd=str(WORKSPACE_DIR), env=env)
                            temp_map = WORKSPACE_DIR / 'karaoke_map.json'
                            if temp_map.exists():
                                shutil.move(str(temp_map), str(map_json))
                                task_manager.append_log(project_name, "✅ Mapa map.json generado exitosamente en output/map.json.\n")
                        break
                    elif status["status"] in ("failed", "idle"):
                        break

            threading.Thread(target=monitor_post_whisper, daemon=True).start()

            return self.send_json({"success": True})

        # ── EJECUTAR ASSEMBLER (RÉNDER) ───────────────────────────────────────
        elif path == '/api/run_assembler':
            project_name = query.get('project', [''])[0]
            if not project_name:
                return self.send_error_json("Falta 'project'")
                
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            preview = data.get('preview', False)
            resolution = data.get('resolution', '1920x1080')
            font_size = data.get('font_size', 72)
            style = data.get('style', 'minimal')
            
            project_path = WORKSPACE_DIR / project_name
            cfg_file = project_path / 'config.json'
            if not cfg_file.exists():
                return self.send_error_json("Proyecto no encontrado")
                
            cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
            mode = data.get('mode', cfg.get('mode', 'karaoke'))
            
            # Persistir las opciones de renderizado elegidas por el usuario en config.json
            cfg['mode'] = mode
            cfg['style'] = style
            cfg['resolution'] = resolution
            cfg['font_size'] = font_size
            cfg['output_name'] = get_dynamic_output_name(cfg, project_name, preview=False, mode=mode)
            try:
                cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception as e:
                print(f"[WARNING] No se pudo guardar config.json al renderizar: {e}")
                
            audio_path = project_path / cfg.get('audio', 'audio.mp3')
            if mode == 'karaoke':
                instrumental_path = project_path / 'instrumental.mp3'
                if instrumental_path.exists():
                    audio_path = instrumental_path
                    
            words_srt = project_path / 'output' / 'words.srt'
            words_json = project_path / 'output' / 'words.json'
            map_json = project_path / 'output' / 'map.json'
            
            out_name = get_dynamic_output_name(cfg, project_name, preview=preview, mode=mode)
            output_mp4 = project_path / 'output' / out_name
            
            if output_mp4.exists():
                try:
                    output_mp4.unlink() # Eliminar si existía antes
                except Exception:
                    pass
            
            # Comando: python.exe karaoke_assembler.py ...
            cmd = [
                str(VENV_PYTHON),
                str(WORKSPACE_DIR / 'karaoke_assembler.py'),
                '--images', str(project_path / 'images'),
                '--srt', str(words_srt),
                '--audio', str(audio_path),
                '--output', str(output_mp4),
                '--mode', mode,
                '--style', style,
                '--resolution', resolution,
                '--font-size', str(font_size),
                '--map', str(map_json),
                '--config', str(cfg_file)
            ]
            
            if words_json.exists():
                cmd += ['--json', str(words_json)]
                
            if cfg.get('font'):
                cmd += ['--font', str(cfg['font'])]
                
            if cfg.get('show_title') and cfg.get('title'):
                cmd += ['--title', cfg['title']]

            if cfg.get('background_type') == 'video':
                cmd += ['--background-type', 'video']
                if cfg.get('video_backgrounds'):
                    cmd += ['--video-bg', ','.join(cfg.get('video_backgrounds'))]
                
            if preview:
                cmd.append('--preview')
                
            task_manager.run_command_async(project_name, cmd, 'assembler')
            return self.send_json({"success": True})

        else:
            return self.send_error_json("Endpoint no encontrado", 404)

# ──────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ──────────────────────────────────────────────────────────────────────────────

def run_server(port=8080):
    # Asegurar que la carpeta web_ui existe
    if not WEB_UI_DIR.exists():
        print(f"[WARNING] Carpeta {WEB_UI_DIR} no encontrada. Asegurate de crear los archivos del frontend.")
        
    server_address = ('', port)
    httpd = HTTPServer(server_address, KaraokeHTTPHandler)
    
    print(f"\n{'='*72}")
    print(f" [OK] Servidor activo en: http://localhost:{port}")
    print(f"    Directorio de trabajo: {WORKSPACE_DIR}")
    print(f"    Python ejecutable venv: {VENV_PYTHON}")
    print(f" Presiona CTRL+C para detener el servidor")
    print(f"{'='*72}\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] Deteniendo servidor...")
        httpd.server_close()
        print("[OK] Servidor detenido.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Inicia el servidor web local para Karaoke Maker")
    parser.add_argument('--port', type=int, default=8080, help="Puerto del servidor (default: 8080)")
    args = parser.parse_args()
    
    run_server(port=args.port)
