# CHANGELOG — Karaoke Tools & Wizard Suite

Registro cronológico de todos los cambios, características nuevas y correcciones de bugs implementados durante el desarrollo del proyecto.

---

## [v2.1.0] — Filtros, Creador de Paletas y Reubicación de Whisper

---

### 🆕 Funcionalidad 1 — Reubicación de Modelo Whisper (Paso 1 → Paso 2)

**Archivos:** `web_ui/index.html`, `web_ui/app.js`, `karaoke_web_server.py`

- **Interfaz Reubicada:** Se trasladó el combobox del selector de "Modelo Whisper" desde el formulario inicial del Paso 1 al panel de sincronización con Whisper del Paso 2.
- **Sincronización Dinámica:** Al iniciar la transcripción, la interfaz envía el modelo seleccionado al endpoint `/api/run_whisper` vía parámetro query, el cual actualiza el valor de `whisper_model` en el archivo `config.json` del proyecto y ejecuta Whisper con la precisión escogida de forma inmediata.

---

### 🆕 Funcionalidad 2 — Creador de Paletas de Colores Personalizadas

**Archivos:** `web_ui/index.html`, `web_ui/style.css`, `web_ui/app.js`

- **Editor en Tiempo Real:** Interfaz integrada "+ New Palette" que abre un modal con strips de color adaptativos de 3 a 12 colores.
- **Acciones Hover & Popover:** Los strips de color admiten acciones en hover (editar ✏️, eliminar 🗑️). La edición despliega un popover `#color-edit-popover` posicionado debajo de la acción, con selector de color nativo y campo de texto hexadecimal sincronizados bidireccionalmente.
- **Generación de Estilos Unificados:** Parser `generateStylesFromColors()` que toma la paleta hexadecimal y la mapea a las propiedades de diseño CSS del Wizard (`minimal`, `dark`, `neon`, `vintage`), así como sus contrapartes RGB correspondientes en Python para el renderizador backend.
- **Persistencia Local y Backend:** Pestaña "My Palettes" que lee y escribe de `localStorage`, con botón interactivo de eliminación. Al seleccionar la paleta, se inyecta en el diseño actual y se guarda en el archivo `config.json` del proyecto activo.

---

### 🆕 Funcionalidad 3 — Filtros de Video y Colecciones (Paso 3)

**Archivos:** `web_ui/app.js`, `web_ui/index.html`, `web_ui/style.css`

- **Agrupamiento por Subdirectorio:** Se implementó una lógica similar a la de imágenes para escanear las carpetas `base_videos` y `loop_videos` mapeándolas a colecciones por subcarpeta.
- **Búsqueda y Filtros:** Se incorporaron selectores de colección y barras de búsqueda rápida en tiempo real para simplificar la navegación sobre los videos disponibles.

---

### 🆕 Funcionalidad 4 — Validación de Medios en el Paso 3

**Archivos:** `web_ui/app.js`

- **Validación Dinámica:** Modificación en la función `updateStepAccess()` para habilitar o deshabilitar el botón "Siguiente Paso" (`#step3-next`) según el tipo de fondo activo: requiere al menos una imagen en la galería para el modo Imagen, o al menos un video en la secuencia para el modo Video.

---

### 🐛 Corrección — Capas y Visualización de Paletas de Colores

**Archivos:** `web_ui/index.html`

- **Ajuste de Superposición (z-index):** Se incrementó el `z-index` de `#create-palette-modal` a `2100` (originalmente `1050`) para que se muestre correctamente sobre el modal de selección `#palette-modal` (que tiene `z-index: 2000`). Esto permite al usuario editar colores y nombrar la paleta sin tener que cerrar el selector de fondo.
- **Visualización en "My Palettes" (Grid):** Se corrigió un problema de visualización donde las paletas personalizadas se veían como líneas verticales colapsadas. Esto sucedía porque el contenedor `#my-palettes-view` usaba un contenedor flex sin anchos explícitos para las tarjetas. Se cambió el contenedor al estilo CSS de clase `.palette-list-grid` (grid de columnas adaptativas con un mínimo de 220px) para que las tarjetas de usuario se representen de forma idéntica a las recomendadas.
- **Edición de Paletas Guardadas:** Se incorporó el botón de edición (✏️) que se revela al pasar el cursor sobre cada tarjeta de paleta en "My Palettes". Este abre el creador en modo edición (`openCreatePaletteModal(pKey)`), cargando los colores y el nombre originales para que el usuario pueda modificarlos y guardarlos.
- **Eliminación Segura (Sin Confirmación Nativa):** Se implementó un flujo de confirmación de doble clic sobre el botón de borrado (×). El primer clic cambia el botón a un ícono de advertencia animado (⚠️) y el segundo clic confirma la eliminación de la paleta. Si no se pulsa de nuevo en 3 segundos, se cancela y se revierte al estado original, previniendo borrados involuntarios y bloqueos del navegador.
- **Reordenamiento de Dropzone (Paso 3):** Se reubicó la caja de carga de archivos (dropzone) de imágenes al principio de la sección de fondos de imagen en el Paso 3. Esto evita tener que desplazarse hasta el final de la página para subir imágenes propias del proyecto.

---

## [v2.0.1] — Corrección de Transcripción Whisper en Proyectos Vacíos

---

### 🐛 Corrección — Error en Whisper con Audio de 0 bytes

**Archivos:** `karaoke_web_server.py`, `karaoke_timing.py`

- **Problema:** Al crear un proyecto sin subir un audio en el Paso 1, el servidor creaba un archivo `audio.mp3` de 0 bytes (vacío). Al intentar iniciar la transcripción con Whisper en el Paso 2, la librería fallaba internamente cuando `ffmpeg` intentaba procesar el archivo vacío, lanzando un error del sistema `CalledProcessError` y `RuntimeError: Failed to load audio`. La interfaz reportaba erróneamente que el audio estaba cargado y habilitaba el paso de transcripción.
- **Solución:**
  - Se modificó la comprobación de estado en el backend (`/api/info`) para verificar que el archivo de audio no solo exista, sino que tenga un tamaño mayor a 0 bytes (`audio_exists` y `instrumental_exists` ahora validan `size > 0`).
  - Se agregaron validaciones explícitas en los endpoints `/api/run_whisper` y `/api/run_separator` del servidor web para retornar un error HTTP 400 descriptivo si el audio (o `vocals.mp3`) está vacío.
  - Se añadió la misma validación de tamaño de archivo (> 0 bytes) en el script CLI `karaoke_timing.py`.
  - Ahora, si el proyecto tiene un audio de 0 bytes, el Paso 2 permanece correctamente deshabilitado en el Wizard y el usuario recibe indicaciones claras para subir un archivo válido en el Paso 1.

---

## [v2.0] — Sesión de Desarrollo Completa

---

### 🆕 Funcionalidad 1 — Interfaz Web Wizard de 5 Pasos (Base)

**Archivos:** `karaoke_web_server.py` (nuevo), `web_ui/index.html` (nuevo), `web_ui/style.css` (nuevo), `web_ui/app.js` (nuevo)

#### Backend (`karaoke_web_server.py`)
- Servidor HTTP local implementado con la librería estándar de Python (`http.server`) sin dependencias externas.
- Gestión asíncrona de subprocesos en hilos separados: la ejecución de **Whisper** y **FFmpeg** no bloquea la interfaz.
- Parser robusto de formularios `multipart/form-data` para subida de archivos de audio e imágenes.
- Endpoints REST implementados:
  - `GET /api/projects` — Lista proyectos disponibles.
  - `POST /api/init` — Crea o actualiza un proyecto (audio + config).
  - `GET /api/info` — Estado completo de un proyecto (archivos existentes, configuración).
  - `GET /api/images`, `GET /api/image_file` — Listado y servicio de imágenes del proyecto.
  - `POST /api/upload_image`, `POST /api/delete_image` — Subida y eliminación de imágenes.
  - `GET /api/map`, `POST /api/map` — Lectura y guardado de `map.json`.
  - `GET /api/words`, `POST /api/save_words` — Lectura y guardado de `words.json` con regeneración de `words.srt`.
  - `GET /api/status` — Estado en tiempo real de la tarea en segundo plano.
  - `POST /api/run_whisper` — Inicia la transcripción Whisper en background.
  - `POST /api/run_assembler` — Inicia el ensamblado FFmpeg en background.
  - `GET /api/video`, `GET /api/download_video` — Servicio del video generado con soporte de descarga.
  - `GET /api/fonts`, `GET /api/font_file` — Listado y servicio de fuentes `.ttf`/`.otf` del sistema y del proyecto.

#### Frontend
- Diseño premium **dark-mode** con glassmorphism (`backdrop-filter: blur()`), gradientes animados y orbes luminosos.
- Google Fonts integradas: **Outfit** (UI), **Cormorant Garamond** (letras de karaoke), **Fira Code** (consola).
- Indicador de progreso del Wizard (5 nodos) con estados: `active`, `completed`, `disabled`.
- Paso 1 — Formulario de creación/edición de proyecto con autofill de metadatos ID3 del archivo MP3.
- Paso 2 — Consola de logs de Whisper en tiempo real con barra de progreso animada.
- Paso 3 — Zona de drag & drop para imágenes con galería de miniaturas.
- Paso 4 — Editor de mapa de imágenes con selectores visuales de fondo por sección.
- Paso 5 — Opciones de render, progress bar de FFmpeg y reproductor HTML5 integrado.

#### Correcciones de Bugs en esta Fase
- **`UnicodeEncodeError` en Windows (CP1252):** `karaoke_assembler.py` y `karaoke_timing.py` reconfiguran `sys.stdout`/`sys.stderr` a UTF-8 al inicio del script para evitar fallos al imprimir emojis en terminales Windows.
- **`FileNotFoundError` al mapear fondos:** El assembler busca imágenes por nombre de archivo dentro del directorio `--images` si no encuentra la ruta relativa exacta del mapa.
- **Corrección de coloreado en modo Lyrics con wrapping:** Cuando una línea larga se divide en dos filas, ambas filas se marcan correctamente como activas (`act = -3`).

---

### 🆕 Funcionalidad 2 — Mejoras de UX en la Interfaz

**Archivos:** `web_ui/app.js`, `web_ui/index.html`, `web_ui/style.css`, `karaoke_assembler.py`

- **Autofill de Metadatos de Audio:** Al arrastrar un MP3, se extraen automáticamente título y artista de las etiquetas ID3v1, ID3v2.2, ID3v2.3 e ID3v2.4 (con soporte correcto de enteros synchsafe de 7-bits). Fallback a nombre de archivo sanitizado.
- **Visualización del Audio Cargado:** Al cargar un proyecto existente, el área de drag & drop muestra `🎵 Audio cargado: [nombre_archivo]`.
- **Opción "Crear nuevo proyecto":** El selector de proyectos incluye la opción `+ Crear nuevo proyecto...`, que limpia y resetea el formulario del Paso 1 sin recargar el navegador.
- **Selector de Modo en Tiempo de Render (Paso 5):** El usuario puede elegir "Karaoke" o "Lyrics" directamente antes de renderizar, sin necesidad de recrear el proyecto.
- **Sincronización Bidireccional Paso 1 ↔ Paso 5:**
  - Cambiar el **Modo de Video** en Paso 1 actualiza Paso 5 y viceversa.
  - Cambiar el **Estilo** en Paso 1 (tarjetas visuales) actualiza Paso 5 y al contrario.
- **Persistencia de Opciones de Render:** Al renderizar, el servidor persiste `mode`, `style`, `resolution` y `font_size` de vuelta a `config.json`.
- **Previsualización de Fuentes:** Panel en Paso 1 para ver en vivo cómo se renderizan las letras ajustando tipografía y tamaño.
- **Soporte de Relaciones de Aspecto:** Horizontal (16:9 / YouTube), Vertical (9:16 / TikTok/Reels) y 4K (3840×2160) en el Paso 5 con escalado automático de fuentes.
- **Paletas de Colores:** Modal de selección de paletas en el Paso 1 con varias combinaciones predefinidas. La paleta se aplica al estilo seleccionado y se persiste en `config.json`.

---

### 🆕 Funcionalidad 3 — Videos de Fondo en Bucle Secuencial

**Archivos:** `karaoke_web_server.py`, `karaoke_assembler.py`, `web_ui/index.html`, `web_ui/style.css`, `web_ui/app.js`

#### Backend
- `GET /api/background_videos` — Lista videos de `./base_videos/` y `./loop_videos/` con rutas relativas. Solo devuelve videos de estas dos carpetas.
- `GET /api/video_file` — Sirve archivos de video de forma segura (validación anti path-traversal, solo `base_videos/` y `loop_videos/`).
- `POST /api/upload_video` — Sube y guarda videos personalizados del usuario directamente en `./loop_videos/`.
- `/api/run_assembler` — Acepta los parámetros `--background-type video` y `--video-bg` cuando el modo es video de fondo.

#### Assembler (`karaoke_assembler.py`)
- Nuevas opciones de CLI: `--background-type` y `--video-bg`.
- En modo video de fondo, los frames se generan con canal **RGBA** transparente (32-bits PNG).
- Pipeline FFmpeg de composición de video de fondo:
  - Escala, centra y recorta cada video de la secuencia a la resolución objetivo con `setsar=1`.
  - Concatena la secuencia en un `temp_sequence.mp4`.
  - Calcula las repeticiones necesarias usando `ffprobe` para cubrir la duración total de la canción.
  - Aplica `stream_loop` + filtro `overlay=0:0:shortest=1` para componer letras transparentes sobre el fondo en loop.

#### Frontend — Paso 3 (nueva sección de Video en Bucle)
- Selector de tipo de fondo con radio buttons: `🖼️ Imágenes por Secciones` vs `🎥 Video en Bucle`. Son excluyentes.
- Sección de video con:
  - Lista horizontal de secuencia seleccionada (se reproducirán en orden).
  - Dropzone de subida de video personalizado.
  - Grids de selección: **Videos Base** (carpeta `base_videos/`) y **Videos Loop** (carpeta `loop_videos/`).
- Modal de previsualización de video con reproductor HTML5 autoplay/loop.
- Nuevos estilos: tarjetas `.video-item-card`, badges `.badge-base`/`.badge-loop`, items de secuencia con índices numéricos.
- En el **Paso 4**, si el modo es video, se detecta automáticamente y se muestra un banner informativo saltando el mapeador de imágenes.

---

### 🆕 Funcionalidad 4 — Separador de Audio por IA (Vocal/Instrumental)

**Archivos:** `karaoke_separator.py` (nuevo), `karaoke_web_server.py`, `web_ui/index.html`, `web_ui/style.css`, `web_ui/app.js`

#### Script `karaoke_separator.py`
- Nuevo script independiente que usa la biblioteca `audio-separator`.
- Modelo RoFormer `model_bs_roformer_ep_317_sdr_12.9755.ckpt` para separación de alta calidad.
- Guarda los resultados como `instrumental.mp3` y `vocals.mp3` en la raíz del proyecto.

#### Backend (`karaoke_web_server.py`)
- `POST /api/run_separator` — Inicia la separación de audio en background.
- `GET /api/info` — Ahora incluye `instrumental_exists` en el status del proyecto.
- `run_command_async` — Extendido para soportar la tarea `'separator'` y parsear progreso de `tqdm`.
- `/api/run_assembler` — En modo **Karaoke** con `instrumental.mp3` existente, reemplaza automáticamente el audio de entrada por la pista instrumental aislada.

#### Frontend — Paso 2 (nuevo layout de dos columnas)
- El Paso 2 se reorganiza en layout de **dos columnas** (`step-grid-2col`):
  - Columna izquierda: Transcripción Whisper.
  - Columna derecha: Separador de Audio por IA.
- Botón de acción "⚡ Iniciar Separación de Audio", barra de progreso y consola de logs dedicados.
- `handleProjectChange()` detecta si `instrumental.mp3` existe y actualiza el botón y descripción del separador en consecuencia.

---

### 🆕 Funcionalidad 5 — Transcripción Whisper con Vocales Aisladas

**Archivos:** `karaoke_web_server.py`, `web_ui/index.html`, `web_ui/app.js`

- `POST /api/run_whisper` — Nuevo parámetro `use_vocals=true`. Si está activo y existe `vocals.mp3`, Whisper procesa la pista de voz limpia en lugar del audio original.
- La preferencia `transcribe_from_vocals` se guarda en `config.json` para persistir la selección.
- En el Paso 2, se agrega un **checkbox** "Usar voz limpia aislada (vocals.mp3)" dentro de la columna de Whisper:
  - Se habilita automáticamente si `vocals.mp3` existe en el proyecto.
  - Muestra un hint en verde cuando está listo.
  - Su estado se sincroniza con `config.json` al cargar el proyecto.

---

### 🐛 Corrección — Botón "Siguiente Paso" desactivado tras transcripción con vocales

**Archivos:** `karaoke_web_server.py`

- **Problema:** Al transcribir con `vocals.mp3`, Whisper generaba `vocals_words.json` y `vocals_words.srt`. El hilo monitor (`monitor_post_whisper`) buscaba `<stem_audio_original>_words.json` (ej: `sombras_del_pasado_words.json`) en lugar de `vocals_words.json`, por lo que no los renombraba y el botón "Siguiente Paso" quedaba desactivado.
- **Solución:** Se cambió `stem = Path(cfg.get('audio', 'audio.mp3')).stem` a `stem = Path(audio_path).stem` en `monitor_post_whisper()`, usando dinámicamente el stem del archivo realmente transcribido.

---

### 🆕 Funcionalidad 6 — Editor de Letras: Adición Manual de Segmentos

**Archivos:** `web_ui/index.html`, `web_ui/app.js`, `web_ui/style.css`

- Nuevo botón **"➕ Agregar Sección"** en la cabecera del editor de letras (Paso 2).
- `addSegmentManually()`: Crea un nuevo segmento con valores por defecto (ubicado 1 segundo después del último segmento existente, con dos palabras de ejemplo `"Nueva"` y `"sección"`). Hace scroll automático hacia él.
- `saveLyricsData()` actualizado:
  - Ordena automáticamente todos los segmentos por `start` antes de guardar.
  - Re-indexa secuencialmente los `id` de segmentos y los `segment_id` de palabras de `0` a `N-1`.
  - Garantiza que `words.json` y `words.srt` generados queden siempre ordenados y válidos.

---

### 🐛 Corrección — Botón "Eliminar" de segmentos no funcionaba

**Archivos:** `web_ui/app.js`, `web_ui/style.css`

- **Problema:** El botón "Eliminar" segmentos usaba `window.confirm()` nativo, que puede bloquearse silenciosamente en WebViews o ciertos entornos de desarrollo.
- **Solución:** Se sustituyó por una **confirmación interactiva en línea de doble clic**:
  - Primera pulsación: El botón adquiere clase `.confirm-delete` (color rojo de advertencia), muestra "⚠️ ¿Confirmar?".
  - Segunda pulsación: El segmento se elimina en memoria y la UI se re-indexa.
- Nuevos estilos en `style.css` para `.delete-segment-btn.confirm-delete` y su estado `:hover`.

---

### 🆕 Funcionalidad 7 — Biblioteca de Imágenes Base en Paso 3

**Archivos:** `karaoke_web_server.py`, `web_ui/index.html`, `web_ui/app.js`, `web_ui/style.css`

#### Backend (`karaoke_web_server.py`)
- `GET /api/base_images` — Escanea `./base_images/`, detecta la colección de cada imagen por prefijo de nombre (ej: `"Ciudad-Roja-1.png"` → colección `"Ciudad Roja"`), y devuelve el listado completo con las colecciones disponibles agrupadas. Actualmente expone **28 imágenes** en **11 colecciones**.
- `GET /api/base_image_file?filename=X` — Sirve imágenes de `./base_images/` de forma segura con validación anti path-traversal y caché `max-age=3600`.
- `POST /api/copy_base_image` — Copia una imagen de `./base_images/<filename>` al directorio `images/` del proyecto activo. Operación idempotente (si ya existe, no la duplica).

#### Frontend — Paso 3 (reorganización de sección de Imágenes)
La sección `#bg-image-section` se reorganizó en **tres zonas verticales**:

1. **Imágenes del Proyecto** (arriba) — Galería de miniaturas de las imágenes ya en el proyecto. Badge contador dinámico (`X imágenes`).
2. **Biblioteca de Imágenes Base** (centro) — Nueva sección `#base-images-section`:
   - Cabecera con filtro de colección (`<select>`) y campo de búsqueda en tiempo real.
   - Grid responsivo de tarjetas (`minmax(150px, 1fr)`) con:
     - Miniatura con `aspect-ratio: 16/9` y carga diferida (`loading="lazy"`).
     - Badge de colección (esquina superior izquierda).
     - Overlay con botón "➕ Agregar" (visible en hover).
     - Estado visual `.already-added` (borde neon + overlay "✅ Ya en proyecto") para imágenes ya en el proyecto.
3. **Subir imagen propia** (abajo) — Dropzone de subida personal, separado con línea divisoria sutil.

#### Nuevas Funciones JS
| Función | Descripción |
|---|---|
| `loadBaseImages()` | Carga la biblioteca, rellena el filtro de colecciones y renderiza el grid. |
| `renderBaseImagesGrid(images)` | Renderiza el array de imágenes filtrado en el grid DOM. |
| `createBaseImageCard(imgObj)` | Crea una tarjeta con miniatura, badge, overlay y nombre. |
| `copyBaseImageToProject(filename)` | Llama a `POST /api/copy_base_image` y refresca la galería del proyecto. |
| `filterBaseImages()` | Filtra el grid en tiempo real por colección y/o texto de búsqueda (sin petición al servidor). |
| `refreshBaseImagesAddedState()` | Actualiza el estado visual "ya agregada" en todas las tarjetas sin recargar. |

#### Cambios en Funciones Existentes
- `updateImagesGallery()` — Actualiza el nuevo badge contador y llama a `refreshBaseImagesAddedState()` al terminar.
- `toggleBackgroundType('image')` — Llama a `loadBaseImages()` al activar el modo de imagen.
- `handleProjectChange()` — Llama a `loadBaseImages()` automáticamente si el tipo de fondo es `image`.

---

## 📁 Archivos del Proyecto Modificados / Nuevos en Esta Sesión

| Archivo | Tipo de Cambio |
|---|---|
| `karaoke_web_server.py` | Modificado — +7 endpoints, gestión de tareas background |
| `karaoke_assembler.py` | Modificado — Soporte video bg, wrapping fixes, Unicode |
| `karaoke_timing.py` | Modificado — Fix Unicode Windows |
| `karaoke_separator.py` | **Nuevo** — Separación vocal/instrumental con RoFormer |
| `web_ui/index.html` | Modificado — Wizard 5 pasos, video bg, editor, biblioteca base |
| `web_ui/style.css` | Modificado — Estilos glassmorphism, video, editor, biblioteca |
| `web_ui/app.js` | Modificado — Toda la lógica de cliente del Wizard |
| `base_images/` | **Nuevo directorio** — 28 imágenes en 11 colecciones temáticas |
| `base_videos/` | **Nuevo directorio** — Videos base cortos (~5s) para fondos |
| `loop_videos/` | **Nuevo directorio** — Videos de loop y subidas del usuario |
| `README.md` | **Nuevo** — Documentación completa del proyecto |
| `CHANGELOG.md` | **Nuevo** — Este archivo |
