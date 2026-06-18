# 🎤 Karaoke Tools & Wizard Suite

Una suite completa de herramientas locales en Python y una interfaz web moderna en 5 pasos para crear videos líricos o de karaoke sincronizados de alta calidad profesional, a partir de archivos de audio, letras y fondos personalizados (imágenes o videos).

---

## 🚀 Características Principales

### 1. Transcripción y Sincronización Súper Precisa (Whisper)
- **Timing a Nivel de Palabra:** Sincronización automática de palabras con precisión de milisegundos mediante modelos Whisper.
- **Editor de Letra Interactivo:** Permite corregir ortografía, eliminar alucinaciones y reajustar marcas de tiempo directamente desde la UI antes del renderizado.

### 2. Ensamblado Eficiente por Estados (FFmpeg)
- **Render Eficiente:** En lugar de generar miles de fotogramas redundantes (por ejemplo, a 30 fps), el motor detecta los cambios de estado lírico (palabra activa, siguiente línea) generando únicamente los frames necesarios (~300 por canción), los cuales son compuestos instantáneamente sobre el fondo usando FFmpeg.
- **Soporte de Relaciones de Aspecto:** Horizontal (16:9) para YouTube, Vertical (9:16) para TikTok/Reels, y resoluciones avanzadas como 4K.
- **Estilos y Paletas de Colores:** Múltiples temas predefinidos (Minimal, Dark, Neon, Vintage), carga de fuentes `.ttf` o `.otf` locales, personalización de tamaños de fuente con autoajuste de wrapping a dos filas y reducción dinámica de tamaño en líneas largas.

### 3. Modos de Fondo Flexibles (Excluyentes)
- **🖼️ Imágenes por Secciones (Timeline):** Permite cargar entre 1 y 12 imágenes del proyecto y distribuirlas cronológicamente por pausas musicales silenciosas. Modificable interactivamente a través de un editor de línea de tiempo visual.
- **🎥 Videos de Fondo en Bucle Secuencial:** Permite encadenar múltiples videos base (de la carpeta `./base_videos` o `./loop_videos`) y videos personalizados subidos por el usuario. La secuencia se escala, recorta y repite secuencialmente de forma automática silenciando su audio para servir de fondo dinámico.
- **🎨 Fondos Sólidos:** Soporte para renderizar con un color sólido extraído automáticamente de la paleta del estilo visual seleccionado si no se cargan fondos.

### 4. Separador de Audio Vocal/Instrumental (Extra)
- **Alta Calidad de Aislamiento:** Script independiente (`karaoke_separator.py`) que utiliza la biblioteca `audio-separator` y el modelo RoFormer (`model_bs_roformer_ep_317_sdr_12.9755.ckpt`) para extraer pistas vocales e instrumentales limpias a partir de cualquier archivo de música.

---

## 📁 Estructura del Proyecto

```text
karaoke_tools/
├── install/                      # Scripts de instalación
│   ├── install.sh                #   Linux / macOS / Git Bash
│   ├── install.bat               #   CMD de Windows
│   └── install.ps1               #   PowerShell de Windows
├── projects/                     # Proyectos de canciones (generado en runtime)
│   └── <NombreProyecto>/         #   Una carpeta por canción
│       ├── config.json           #     Configuración del proyecto
│       ├── audio.mp3             #     Archivo de audio subido
│       ├── vocals.mp3            #     Pista vocal (opcional, generada por el separador)
│       ├── instrumental.mp3      #     Pista instrumental (opcional, generada por el separador)
│       ├── images/               #     Imágenes de fondo del proyecto
│       └── output/               #     Archivos generados
│           ├── words.json        #       Transcripción completa
│           ├── words.srt         #       Subtítulos por palabra
│           ├── map.json          #       Mapa de imágenes por sección de tiempo
│           └── *.mp4             #       Video(s) renderizado(s)
├── base_images/                  # Imágenes de ejemplo incluidas en el repositorio
├── base_videos/                  # Videos de fondo predeterminados cortos (5s)
├── loop_videos/                  # Videos de fondo en bucle y subidas del usuario
├── web_ui/                       # Frontend del Wizard interactivo
│   ├── index.html                #   Interfaz estructurada en 5 pasos
│   ├── style.css                 #   Estilos con efectos de cristal y gradientes
│   └── app.js                    #   Lógica del cliente y control del backend
├── /venv/                        # Entorno virtual de Python
├── karaoke_web_server.py         # Servidor HTTP local con APIs REST
├── karaoke_assembler.py          # Motor de renderizado y composición de video
├── karaoke_timing.py             # Transcripción Whisper por palabras
├── karaoke_separator.py          # Separación vocal/instrumental con RoFormer
├── karaoke_maker.py              # Orquestador CLI (init/build/preview/info/clean)
├── requirements.txt              # Dependencias del pipeline principal (Python 3.10–3.12)
├── requirements.3.14.txt         # Incluye audio-separator para Python 3.13+
├── .gitignore
└── README.md
```

---

## 🛠️ Requisitos e Instalación

### Prerrequisitos
1. **Python 3.10+**
2. **FFmpeg** instalado y disponible en las variables de entorno (`PATH`) del sistema.
   - En Windows, descarga de [ffmpeg.org](https://ffmpeg.org/download.html) y agrega la carpeta `/bin` a tu variable PATH.

### Instalación de dependencias

#### Python 3.10–3.12

```bash
# Linux / macOS / Git Bash
source .venv/bin/activate
pip install -r requirements.txt

# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### Python 3.13+

```bash
# Linux / macOS / Git Bash
source .venv/bin/activate
pip install -r requirements.3.14.txt

# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.3.14.txt
```

> `requirements.txt` contiene solo las dependencias del pipeline principal (sin audio-separator). `requirements.3.14.txt` incluye audio-separator y todas sus dependencias, con los paquetes necesarios para Python 3.14+ (`audioop-lts`, `onnx2torch-py313`).

#### Separador de audio (opcional, Python 3.10–3.12)

`audio-separator` **no está incluido en `requirements.txt`** porque tiene una dependencia transitiva (`diffq-fixed`) que falla al compilar en Windows. Los scripts de instalación (`install.sh`, `install.bat`, `install.ps1`) lo manejan automáticamente, pero también puedes instalarlo manualmente:

```bash
# Linux / macOS / Git Bash
pip install beartype einops julius ml_collections numpy \
    onnx2torch pydub pyyaml requests resampy \
    rotary-embedding-torch samplerate scipy six soundfile torch tqdm
pip install audio-separator --no-deps
```

```powershell
# Windows PowerShell
pip install beartype einops julius ml_collections numpy `
    onnx2torch pydub pyyaml requests resampy `
    rotary-embedding-torch samplerate scipy six soundfile torch tqdm
pip install audio-separator --no-deps
```

> **¿Por qué `--no-deps`?** `diffq-fixed==0.2.4` es la única dependencia declarada que falla: intenta compilar extensiones Cython desde fuente pero su paquete no incluye el archivo `bitpack.pyx`. Instalando las demás dependencias manualmente y usando `--no-deps` se evita el problema por completo.

---

## 💻 Guía de Uso

### 1. Iniciar el Wizard Web (Recomendado)
El método más sencillo y visual es ejecutar el servidor web local:

```powershell
python karaoke_web_server.py --port 8080
```
Abre tu navegador e ingresa a: **[http://localhost:8080](http://localhost:8080)**

#### El Flujo de Trabajo en 5 Pasos:
1. **Paso 1 (Configuración):** Crea un nuevo proyecto, sube tu archivo MP3/WAV y rellena el título, artista, tipografía y estilo visual de letras.
2. **Paso 2 (Transcripción):** Ejecuta la transcripción local con Whisper. Una vez finalizada, utiliza el editor interactivo para ajustar letras o tiempos por palabra si es necesario.
3. **Paso 3 (Fondos):** Selecciona el tipo de fondo:
   - **Imágenes:** Arrastra varias imágenes y el sistema las distribuirá en orden.
   - **Video en Bucle:** Arrastra un video personalizado o selecciona entre los videos base y loops preexistentes para crear una secuencia de reproducción.
4. **Paso 4 (Mapeo):**
   - En modo Imagen, distribuye las imágenes en la línea de tiempo.
   - En modo Video, este paso se salta automáticamente con una pantalla informativa.
5. **Paso 5 (Renderizado):** Elige formato horizontal (YouTube), vertical (Reels/TikTok) o 4K y compila una preview rápida de 30 segundos o el video completo. Podrás verlo en el reproductor integrado y descargarlo con un nombre dinámico sanitizado (ej: `Artista-Titulo-karaoke.mp4`).

---

### 2. Uso por Línea de Comandos (CLI)

#### Transcripción:
```powershell
python karaoke_timing.py path/to/audio.mp3 --model medium --language es --output path/to/output_dir
```

#### Ensamblado clásico con imágenes:
```powershell
python karaoke_assembler.py --images path/to/images --srt output/words.srt --audio path/to/audio.mp3 --map output/map.json --output video.mp4 --mode karaoke --style neon --font C:/Windows/Fonts/georgia.ttf
```

#### Ensamblado con videos de fondo en bucle:
```powershell
python karaoke_assembler.py --images path/to/images --srt output/words.srt --audio path/to/audio.mp3 --output video.mp4 --background-type video --video-bg "base_videos/musical_note_1.mp4,loop_videos/video_2.mp4" --mode lyrics --font C:/Windows/Fonts/georgia.ttf
```

#### Separación de Voz e Instrumental:
```powershell
python karaoke_audio_separator.py
```
*(Asegúrate de editar la ruta de entrada en el archivo para que apunte a tu canción).*
