// VARIABLES DE ESTADO GLOBAL
let currentProject = "";
let currentStep = 1;
let projectConfig = null;
let projectStatus = null;
let projectImages = [];
let mapData = null;
let selectedStyle = "minimal";
let statusInterval = null;
let systemFonts = [];

// ELEMENTOS DOM COMUNES
const projectSelect = document.getElementById('project-select');
const toastElement = document.getElementById('toast');

// ──────────────────────────────────────────────────────────────────────────────
// INICIALIZACIÓN
// ──────────────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    loadFonts();
    setupDragAndDrop();
    setupAspectChangeHandler();
    updateFontPreview();
});

// MOSTRAR TOAST NOTIFICACIONES
function showToast(message, type = 'success') {
    toastElement.innerText = message;
    toastElement.className = `toast show ${type}`;
    setTimeout(() => {
        toastElement.classList.remove('show');
    }, 4000);
}

// CARGAR FUENTES DISPONIBLES
async function loadFonts() {
    try {
        const res = await fetch('/api/fonts');
        if (res.ok) {
            const data = await res.json();
            systemFonts = data.fonts;
            const previewSelect = document.getElementById('font-select-preview');
            
            // Vaciar select excepto las default
            previewSelect.innerHTML = `
                <option value="georgia" selected>Georgia</option>
                <option value="cambria">Cambria</option>
                <option value="times">Times New Roman</option>
            `;
            
            systemFonts.forEach(font => {
                const opt = document.createElement('option');
                opt.value = font.path;
                opt.innerText = font.name;
                previewSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.error("Error al cargar fuentes del backend:", e);
    }
}

// ACTUALIZAR PREVISUALIZACIÓN DE FUENTE EN VIVO (PETICIÓN DE USUARIO)
function updateFontPreview() {
    const fontSelect = document.getElementById('font-select-preview');
    const fontSizeInput = document.getElementById('font-size-preview');
    const previewBox = document.getElementById('lyric-preview-box');
    
    const selectedFont = fontSelect.value;
    const fontSize = fontSizeInput.value;
    
    // Aplicar estilos a la caja de previsualización
    // Si es una ruta (de font de sistema), usamos el nombre de la fuente o fallback serif
    if (selectedFont.includes('/') || selectedFont.includes('\\')) {
        // Extraer nombre del archivo sin extensión
        const parts = selectedFont.split(/[/\\]/);
        const fontName = parts[parts.length - 1].replace(/\.[^/.]+$/, "");
        // Creamos una regla @font-face temporal o simplemente aplicamos serif
        // En navegadores web locales no siempre podemos cargar archivos .ttf directamente de disco local
        // por políticas de seguridad, pero para previsualización, si es Georgia/Cambria/Times lo muestra perfecto.
        // Si es una fuente personalizada, usamos serif como fallback visual de tamaño.
        previewBox.style.fontFamily = `"${fontName}", serif`;
    } else {
        previewBox.style.fontFamily = selectedFont;
    }
    
    // Cambiar tamaño de fuente principal (el del elemento active-prev)
    const activePrev = previewBox.querySelector('.active-prev');
    if (activePrev) {
        activePrev.style.fontSize = `${fontSize}px`;
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// SELECCIÓN Y CARGA DE PROYECTO
// ──────────────────────────────────────────────────────────────────────────────
async function loadProjects(selectNewProject = "") {
    try {
        const res = await fetch('/api/projects');
        const data = await res.json();
        
        projectSelect.innerHTML = '<option value="" disabled selected>Selecciona o crea un proyecto...</option>';
        data.projects.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.name;
            opt.innerText = `${p.title} (${p.artist || 'Sin artista'})`;
            projectSelect.appendChild(opt);
        });

        if (selectNewProject) {
            projectSelect.value = selectNewProject;
            handleProjectChange(selectNewProject);
        } else if (currentProject) {
            projectSelect.value = currentProject;
        }
    } catch (e) {
        showToast("Error al cargar proyectos del backend", "error");
    }
}

projectSelect.addEventListener('change', (e) => {
    handleProjectChange(e.target.value);
});

async function handleProjectChange(projectName) {
    currentProject = projectName;
    clearInterval(statusInterval); // Detener cualquier polling previo
    
    try {
        const res = await fetch(`/api/info?project=${currentProject}`);
        const data = await res.json();
        
        projectConfig = data.config;
        projectStatus = data.status;
        projectImages = data.images;

        // Rellenar formulario del Paso 1 con la config actual
        document.getElementById('p-name').value = currentProject;
        document.getElementById('p-name').disabled = true; // No renombrar carpeta directo
        document.getElementById('p-title').value = projectConfig.title || "";
        document.getElementById('p-artist').value = projectConfig.artist || "";
        document.getElementById('p-lang').value = projectConfig.language || "es";
        document.getElementById('p-mode').value = projectConfig.mode || "karaoke";
        document.getElementById('p-whisper').value = projectConfig.whisper_model || "medium";
        
        // Estilo visual
        selectedStyle = projectConfig.style || "minimal";
        document.querySelectorAll('.style-card').forEach(card => {
            if (card.dataset.style === selectedStyle) {
                card.classList.add('active');
            } else {
                card.classList.remove('active');
            }
        });

        // Configuración de render en el paso 5
        document.getElementById('render-style').value = selectedStyle;
        document.getElementById('render-font-size').value = projectConfig.font_size || 72;
        
        // Cargar miniaturas y mapa
        updateImagesGallery();
        
        // Activar/desactivar pasos del Wizard según el progreso real del proyecto
        updateStepAccess();

        // Si hay una tarea ejecutándose actualmente en backend, reconectar al log/polling
        checkCurrentTaskRunning();

        // Si ya hay un video generado, cargar el player
        updateVideoPlayer();

        showToast(`Proyecto '${projectConfig.title}' cargado.`);
    } catch (e) {
        showToast("Error al obtener detalles del proyecto", "error");
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// HABILITAR NAVEGACIÓN ENTRE PASOS
// ──────────────────────────────────────────────────────────────────────────────
function updateStepAccess() {
    if (!currentProject) return;

    // Nodo 2 (Transcripción) requiere que exista el audio
    const node2 = document.getElementById('node-2');
    if (projectStatus.audio_exists) {
        node2.classList.remove('disabled');
    } else {
        node2.classList.add('disabled');
    }

    // Nodo 3 (Fondos) requiere que esté transcribiendo o ya tenga SRT
    const node3 = document.getElementById('node-3');
    if (projectStatus.words_srt_exists) {
        node3.classList.remove('disabled');
        document.getElementById('step2-next').removeAttribute('disabled');
    } else {
        node3.classList.add('disabled');
        document.getElementById('step2-next').setAttribute('disabled', 'true');
    }

    // Nodo 4 (Mapeo) requiere al menos 1 imagen y que words_srt existan
    const node4 = document.getElementById('node-4');
    if (projectStatus.words_srt_exists && projectStatus.images_count > 0) {
        node4.classList.remove('disabled');
        document.getElementById('step3-next').removeAttribute('disabled');
    } else {
        node4.classList.add('disabled');
        document.getElementById('step3-next').setAttribute('disabled', 'true');
    }

    // Nodo 5 (Render) requiere que el mapa (map.json) exista
    const node5 = document.getElementById('node-5');
    if (projectStatus.map_exists) {
        node5.classList.remove('disabled');
        document.getElementById('step4-next').removeAttribute('disabled');
        // Cargar mapa e inicializar el editor
        loadMapEditor();
    } else {
        node5.classList.add('disabled');
        document.getElementById('step4-next').setAttribute('disabled', 'true');
    }
}

function navigateToStep(stepNum) {
    // Verificar si el nodo correspondiente está deshabilitado
    const node = document.getElementById(`node-${stepNum}`);
    if (node.classList.contains('disabled')) {
        showToast("Primero debes completar el paso anterior.", "warning");
        return;
    }

    // Ocultar paso actual
    document.getElementById(`step-${currentStep}`).classList.remove('active-step');
    document.getElementById(`node-${currentStep}`).classList.remove('active');
    if (currentStep < stepNum) {
        document.getElementById(`node-${currentStep}`).classList.add('completed');
    }

    // Mostrar nuevo paso
    currentStep = stepNum;
    document.getElementById(`step-${currentStep}`).classList.add('active-step');
    document.getElementById(`node-${currentStep}`).classList.add('active');
    document.getElementById(`node-${currentStep}`).classList.remove('completed');
}

function nextStep() {
    if (currentStep < 5) navigateToStep(currentStep + 1);
}

function prevStep() {
    if (currentStep > 1) navigateToStep(currentStep - 1);
}

// ──────────────────────────────────────────────────────────────────────────────
// PASO 1: FORMULARIO DE INICIALIZACIÓN
// ──────────────────────────────────────────────────────────────────────────────
function selectStyle(element) {
    document.querySelectorAll('.style-card').forEach(card => card.classList.remove('active'));
    element.classList.add('active');
    selectedStyle = element.dataset.style;
    
    // Cambiar estilo de la previsualización de fuentes también
    const stylePalette = {
        'minimal': { active: '#C8903A', sung: '#F4EFE6', unsung: '#464646', bg: 'linear-gradient(135deg, #111 0%, #222 100%)' },
        'dark': { active: '#FFCD5A', sung: '#D7D7C3', unsung: '#373737', bg: 'linear-gradient(135deg, #050505 0%, #151515 100%)' },
        'neon': { active: '#00FFB4', sung: '#AFAFFF', unsung: '#414141', bg: 'linear-gradient(135deg, #000 0%, #080a10 100%)' },
        'vintage': { active: '#FFD77D', sung: '#F0DAB6', unsung: '#5f553e', bg: 'linear-gradient(135deg, #2a221a 0%, #3d3428 100%)' }
    };
    
    const palette = stylePalette[selectedStyle];
    const previewBox = document.getElementById('lyric-preview-box');
    previewBox.style.background = palette.bg;
    
    const sungWord = previewBox.querySelector('.sung');
    const actWord = previewBox.querySelector('.active-word');
    const unsungWord = previewBox.querySelector('.unsung');
    
    if (sungWord) sungWord.style.color = palette.sung;
    if (actWord) actWord.style.color = palette.active;
    if (unsungWord) unsungWord.style.color = palette.unsung;
}

async function handleInitProject(event) {
    event.preventDefault();
    
    const name = document.getElementById('p-name').value.trim();
    const title = document.getElementById('p-title').value.trim();
    const artist = document.getElementById('p-artist').value.trim();
    const audioInput = document.getElementById('p-audio');
    const lang = document.getElementById('p-lang').value;
    const mode = document.getElementById('p-mode').value;
    const whisper_model = document.getElementById('p-whisper').value;
    
    if (!name) return showToast("El nombre del proyecto es requerido", "error");
    
    const formData = new FormData();
    formData.append('name', name);
    formData.append('title', title);
    formData.append('artist', artist);
    formData.append('lang', lang);
    formData.append('mode', mode);
    formData.append('style', selectedStyle);
    formData.append('whisper_model', whisper_model);
    
    // Verificar si se seleccionó archivo de audio
    if (audioInput.files.length > 0) {
        formData.append('audio', audioInput.files[0]);
    }

    try {
        showToast("Inicializando proyecto...", "warning");
        const res = await fetch('/api/init', {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast("Proyecto inicializado correctamente!");
            await loadProjects(name);
            // Redirigir al Paso 2 automáticamente
            navigateToStep(2);
        }
    } catch (e) {
        showToast("Error en el servidor al inicializar proyecto", "error");
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// PASO 2: TRANSCRIPCIÓN CON WHISPER
// ──────────────────────────────────────────────────────────────────────────────
async function startWhisper() {
    if (!currentProject) return;
    
    try {
        const res = await fetch(`/api/run_whisper?project=${currentProject}`, { method: 'POST' });
        const data = await res.json();
        
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast("Whisper se ha iniciado en segundo plano...", "warning");
            document.getElementById('run-whisper-btn').disabled = true;
            pollStatus();
        }
    } catch (e) {
        showToast("Error al iniciar Whisper", "error");
    }
}

function pollStatus() {
    clearInterval(statusInterval);
    
    statusInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status?project=${currentProject}`);
            const data = await res.json();
            
            const consoleOutput = document.getElementById('whisper-console-output');
            const progressFill = document.getElementById('transcription-progress-fill');
            const progressPct = document.getElementById('transcription-progress-pct');
            const statusText = document.getElementById('transcription-status-text');
            
            // Si la tarea actual es del render FFmpeg, estamos en el paso 5.
            // Para Whisper, procesar aquí.
            if (data.task === 'whisper') {
                statusText.innerText = `Estado: Transcribiendo (${data.status})`;
                progressPct.innerText = `${data.progress}%`;
                progressFill.style.width = `${data.progress}%`;
                consoleOutput.innerText = data.logs || "Iniciando Whisper...";
                consoleOutput.scrollTop = consoleOutput.scrollHeight; // Autoscroll
                
                if (data.status === 'success') {
                    clearInterval(statusInterval);
                    showToast("¡Transcripción Whisper completada con éxito!");
                    document.getElementById('run-whisper-btn').disabled = false;
                    // Recargar datos del proyecto
                    handleProjectChange(currentProject);
                } else if (data.status === 'failed') {
                    clearInterval(statusInterval);
                    showToast("La transcripción de Whisper falló. Revisa la consola.", "error");
                    document.getElementById('run-whisper-btn').disabled = false;
                }
            } else if (data.task === 'assembler') {
                // Polling para renderizado del paso 5
                const renderConsole = document.getElementById('render-console-output');
                const renderProgressFill = document.getElementById('render-progress-fill');
                const renderProgressPct = document.getElementById('render-progress-pct');
                const renderStatusText = document.getElementById('render-status-text');
                
                renderStatusText.innerText = `Estado: Componiendo video (${data.status})`;
                renderProgressPct.innerText = `${data.progress}%`;
                renderProgressFill.style.width = `${data.progress}%`;
                renderConsole.innerText = data.logs || "Ejecutando render de video...";
                renderConsole.scrollTop = renderConsole.scrollHeight;
                
                if (data.status === 'success') {
                    clearInterval(statusInterval);
                    showToast("¡Ensamblaje del video completado!");
                    handleProjectChange(currentProject); // Recargar
                } else if (data.status === 'failed') {
                    clearInterval(statusInterval);
                    showToast("El ensamblaje falló. Revisa logs.", "error");
                }
            }
        } catch (e) {
            console.error("Error polling status:", e);
        }
    }, 1000);
}

async function checkCurrentTaskRunning() {
    try {
        const res = await fetch(`/api/status?project=${currentProject}`);
        const data = await res.json();
        
        if (data.status === 'running') {
            pollStatus();
            if (data.task === 'whisper') {
                document.getElementById('run-whisper-btn').disabled = true;
            }
        }
    } catch (e) {
        console.error(e);
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// PASO 3: SUBIDA Y GALERÍA DE FONDOS
// ──────────────────────────────────────────────────────────────────────────────
function updateImagesGallery() {
    const gallery = document.getElementById('images-gallery');
    const galleryCount = document.getElementById('gallery-count');
    galleryCount.innerText = projectImages.length;
    
    if (projectImages.length === 0) {
        gallery.innerHTML = '<div class="gallery-empty-message">Aún no has subido imágenes. ¡Arrastra archivos arriba!</div>';
        return;
    }
    
    gallery.innerHTML = '';
    projectImages.forEach(imgName => {
        const item = document.createElement('div');
        item.className = 'gallery-item';
        
        const img = document.createElement('img');
        img.src = `/api/image_file?project=${currentProject}&file=${imgName}`;
        img.alt = imgName;
        
        const label = document.createElement('div');
        label.className = 'gallery-item-name';
        label.innerText = imgName;
        
        item.appendChild(img);
        item.appendChild(label);
        gallery.appendChild(item);
    });
}

async function handleImagesUpload(event) {
    const files = event.target.files;
    if (files.length === 0) return;
    
    showToast(`Subiendo ${files.length} imágenes...`, "warning");
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('image', file);
        
        try {
            const res = await fetch(`/api/upload_image?project=${currentProject}`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.error) {
                showToast(data.error, "error");
            }
        } catch (e) {
            showToast(`Error al subir la imagen ${file.name}`, "error");
        }
    }
    
    showToast("Imágenes subidas correctamente.");
    // Recargar datos
    handleProjectChange(currentProject);
}

// DRAG & DROP HANDLERS
function setupDragAndDrop() {
    const audioZone = document.getElementById('audio-dropzone');
    const imageZone = document.getElementById('images-dropzone');
    
    // Configurar zonas de arrastre
    [audioZone, imageZone].forEach(zone => {
        if (!zone) return;
        ['dragenter', 'dragover'].forEach(eventName => {
            zone.addEventListener(eventName, (e) => {
                e.preventDefault();
                zone.classList.add('drag-over');
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            zone.addEventListener(eventName, (e) => {
                e.preventDefault();
                zone.classList.remove('drag-over');
            }, false);
        });
    });
    
    // Manejar drop de audio
    audioZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            document.getElementById('p-audio').files = files;
            document.getElementById('audio-upload-label').innerText = `Seleccionado: ${files[0].name}`;
        }
    });
    
    // Manejar drop de imágenes
    imageZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            const input = document.getElementById('p-images');
            input.files = files;
            // Forzar subida
            handleImagesUpload({ target: { files: files } });
        }
    });
}

// ──────────────────────────────────────────────────────────────────────────────
// PASO 4: MAPEO VISUAL DE IMÁGENES (`map.json`)
// ──────────────────────────────────────────────────────────────────────────────
async function loadMapEditor() {
    if (!currentProject) return;
    
    try {
        const res = await fetch(`/api/map?project=${currentProject}`);
        if (!res.ok) return;
        
        mapData = await res.json();
        renderMapEditorRows();
    } catch (e) {
        console.error("Error al cargar map.json:", e);
    }
}

function renderMapEditorRows() {
    const container = document.getElementById('map-sections-list');
    container.innerHTML = '';
    
    if (!mapData || !mapData.segments || mapData.segments.length === 0) {
        container.innerHTML = '<div class="gallery-empty-message">No hay segmentos en el mapa para editar.</div>';
        return;
    }
    
    mapData.segments.forEach((seg, idx) => {
        const row = document.createElement('div');
        row.className = 'map-segment-row';
        row.dataset.index = idx;
        
        // 1. Inputs de Tiempos
        const timingDiv = document.createElement('div');
        timingDiv.className = 'segment-timing';
        
        const startField = document.createElement('div');
        startField.className = 'timing-field';
        startField.innerHTML = `
            <label>Inicio (s)</label>
            <input type="number" step="0.01" class="glass-input start-time-input" value="${seg.start}" onchange="updateSegmentTime(${idx}, 'start', this.value)">
        `;
        
        const arrow = document.createElement('div');
        arrow.className = 'segment-connector-arrow';
        arrow.innerText = '→';
        
        const endField = document.createElement('div');
        endField.className = 'timing-field';
        endField.innerHTML = `
            <label>Fin (s)</label>
            <input type="number" step="0.01" class="glass-input end-time-input" value="${seg.end}" onchange="updateSegmentTime(${idx}, 'end', this.value)">
        `;
        
        timingDiv.appendChild(startField);
        timingDiv.appendChild(arrow);
        timingDiv.appendChild(endField);
        
        // 2. Previsualización del Texto
        const textDiv = document.createElement('div');
        textDiv.className = 'segment-lyric';
        
        // El assembler a veces pone _label, o el segment_id
        const labelText = seg._label || `Sección ${idx + 1}`;
        
        textDiv.innerHTML = `
            <div class="segment-lyric-title">${labelText}</div>
            <div class="segment-text" title="Líricas aproximadas">Asigna una imagen de fondo para esta sección de la canción...</div>
        `;
        
        // 3. Picker Visual de Miniaturas ( thumbnails )
        const pickerDiv = document.createElement('div');
        pickerDiv.className = 'segment-image-picker';
        
        const pickerLabel = document.createElement('div');
        pickerLabel.className = 'segment-image-label';
        pickerLabel.innerText = "Imagen asignada:";
        
        const thumbsGrid = document.createElement('div');
        thumbsGrid.className = 'thumbnail-picker-grid';
        
        // Renderizar una miniatura para cada imagen del proyecto
        projectImages.forEach(imgName => {
            const imgPath = `images/${imgName}`;
            const isSelected = seg.image === imgPath || seg.image === imgName;
            
            const thumb = document.createElement('div');
            thumb.className = `thumb-option ${isSelected ? 'selected' : ''}`;
            thumb.title = imgName;
            
            const thumbImg = document.createElement('img');
            thumbImg.src = `/api/image_file?project=${currentProject}&file=${imgName}`;
            
            thumb.appendChild(thumbImg);
            
            // Asignar evento click para seleccionar esta imagen
            thumb.onclick = () => {
                // Deseleccionar previas en esta fila
                thumbsGrid.querySelectorAll('.thumb-option').forEach(t => t.classList.remove('selected'));
                thumb.classList.add('selected');
                
                // Guardar selección
                seg.image = imgPath;
                showToast(`Asignada imagen '${imgName}' a la Sección ${idx + 1}`);
            };
            
            thumbsGrid.appendChild(thumb);
        });
        
        pickerDiv.appendChild(pickerLabel);
        pickerDiv.appendChild(thumbsGrid);
        
        row.appendChild(timingDiv);
        row.appendChild(textDiv);
        row.appendChild(pickerDiv);
        
        container.appendChild(row);
    });
}

function updateSegmentTime(idx, field, value) {
    if (mapData && mapData.segments[idx]) {
        mapData.segments[idx][field] = parseFloat(value);
    }
}

async function saveMapData() {
    if (!currentProject || !mapData) return;
    
    try {
        const res = await fetch('/api/map', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: currentProject,
                map: mapData
            })
        });
        const data = await res.json();
        
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast("¡Mapa map.json guardado correctamente!");
            // Recargar datos y actualizar acceso
            handleProjectChange(currentProject);
        }
    } catch (e) {
        showToast("Error al guardar el mapa", "error");
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// PASO 5: RENDERING Y EXPORTACIÓN (FFMPEG)
// ──────────────────────────────────────────────────────────────────────────────
function setupAspectChangeHandler() {
    const aspectSelect = document.getElementById('render-aspect');
    aspectSelect.addEventListener('change', handleAspectChange);
}

function handleAspectChange() {
    const aspectSelect = document.getElementById('render-aspect');
    const resGroup = document.getElementById('custom-res-group');
    const resInput = document.getElementById('render-resolution');
    
    const val = aspectSelect.value;
    if (val === '16:9') {
        resGroup.style.display = 'none';
        resInput.value = '1920x1080';
    } else if (val === '9:16') {
        resGroup.style.display = 'none';
        resInput.value = '1080x1920';
    } else if (val === '4K') {
        resGroup.style.display = 'none';
        resInput.value = '3840x2160';
    } else {
        resGroup.style.display = 'block';
    }
}

async function startRender(isPreview = false) {
    if (!currentProject) return;
    
    const resolution = document.getElementById('render-resolution').value;
    const font_size = document.getElementById('render-font-size').value;
    const style = document.getElementById('render-style').value;
    
    try {
        const res = await fetch(`/api/run_assembler?project=${currentProject}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                preview: isPreview,
                resolution: resolution,
                font_size: parseInt(font_size),
                style: style
            })
        });
        const data = await res.json();
        
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast(isPreview ? "Generando preview (30s)..." : "Renderizando video completo...", "warning");
            pollStatus();
        }
    } catch (e) {
        showToast("Error al iniciar el render", "error");
    }
}

function updateVideoPlayer() {
    const player = document.getElementById('output-video-player');
    const placeholder = document.getElementById('video-player-placeholder');
    const actionsBox = document.getElementById('video-actions-box');
    const downloadBtn = document.getElementById('download-video-btn');
    
    // Verificamos si existe el video (completo o preview)
    const hasVideo = projectStatus.video_exists || projectStatus.preview_exists;
    
    if (hasVideo) {
        // Preferir el video completo si existe, si no la preview
        const isPreview = !projectStatus.video_exists && projectStatus.preview_exists;
        const videoUrl = `/api/video?project=${currentProject}&preview=${isPreview}&t=${Date.now()}`;
        
        player.src = videoUrl;
        player.style.display = 'block';
        placeholder.style.display = 'none';
        
        actionsBox.style.display = 'block';
        downloadBtn.href = videoUrl;
        downloadBtn.innerText = isPreview ? '📥 Descargar Vista Previa (30s)' : '📥 Descargar Video Completo';
    } else {
        player.src = '';
        player.style.display = 'none';
        placeholder.style.display = 'flex';
        actionsBox.style.display = 'none';
    }
}
