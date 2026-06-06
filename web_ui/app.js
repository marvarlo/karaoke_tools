// VARIABLES DE ESTADO GLOBAL
let currentProject = "";
let currentStep = 1;
let projectConfig = null;
let projectStatus = null;
let projectImages = [];
let mapData = null;
let lyricsData = null;
let selectedStyle = "minimal";
let currentPaletteName = "default";
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
    setupSyncHandlers();
    updateFontPreview();
    setupPaletteHandlers();
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

    if (!fontSelect || !fontSizeInput || !previewBox) return;

    const selectedFont = fontSelect.value;
    const fontSize = fontSizeInput.value;
    let appliedFontFamily = selectedFont;

    // Aplicar estilos a la caja de previsualización
    // Si es una ruta (de font de sistema/proyecto), inyectamos la regla @font-face y usamos el nombre de la fuente
    if (selectedFont.includes('/') || selectedFont.includes('\\')) {
        const parts = selectedFont.split(/[/\\]/);
        const fontName = parts[parts.length - 1].replace(/\.[^/.]+$/, "");
        appliedFontFamily = fontName;
        
        let fontFaceId = `font-face-${fontName}`;
        if (!document.getElementById(fontFaceId)) {
            const style = document.createElement('style');
            style.id = fontFaceId;
            style.textContent = `
                @font-face {
                    font-family: "${fontName}";
                    src: url('/api/font_file?path=${encodeURIComponent(selectedFont)}');
                }
            `;
            document.head.appendChild(style);
        }
        previewBox.style.fontFamily = `"${fontName}", serif`;
    } else {
        previewBox.style.fontFamily = selectedFont;
    }

    // Cambiar tamaño de fuente principal (el del elemento active-prev)
    const activePrev = previewBox.querySelector('.active-prev');
    if (activePrev) {
        activePrev.style.fontSize = `${fontSize}px`;
    }

    // También aplicar al texto de las tarjetas de estilo en "Configuración del Estilo"
    const stylePreviewTexts = document.querySelectorAll('.style-card .preview-text');
    stylePreviewTexts.forEach(el => {
        if (selectedFont.includes('/') || selectedFont.includes('\\')) {
            el.style.fontFamily = `"${appliedFontFamily}", serif`;
        } else {
            el.style.fontFamily = selectedFont;
        }
    });

    // Guardar en config del proyecto si está cargado
    if (projectConfig && currentProject) {
        let isChanged = false;
        if (projectConfig.font !== selectedFont) {
            projectConfig.font = selectedFont;
            isChanged = true;
        }
        const parsedSize = parseInt(fontSize) || 72;
        if (projectConfig.font_size !== parsedSize) {
            projectConfig.font_size = parsedSize;
            isChanged = true;
        }

        if (isChanged) {
            fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: currentProject,
                    config: projectConfig
                })
            }).catch(e => console.error("Error al guardar fuente en config:", e));
            
            // Sincronizar el input de tamaño del Paso 5
            const renderFontSizeInput = document.getElementById('render-font-size');
            if (renderFontSizeInput && renderFontSizeInput.value !== fontSize) {
                renderFontSizeInput.value = fontSize;
            }
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// SELECCIÓN Y CARGA DE PROYECTO
// ──────────────────────────────────────────────────────────────────────────────
async function loadProjects(selectNewProject = "") {
    try {
        const res = await fetch('/api/projects');
        const data = await res.json();

        projectSelect.innerHTML = `
            <option value="" disabled selected>Selecciona o crea un proyecto...</option>
            <option value="__new_project__">+ Crear nuevo proyecto...</option>
        `;
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
    if (e.target.value === '__new_project__') {
        initNewProjectForm();
    } else {
        handleProjectChange(e.target.value);
    }
});

function initNewProjectForm() {
    currentProject = "";
    projectConfig = null;
    projectStatus = null;
    projectImages = [];
    mapData = null;
    lyricsData = null;

    // Habilitar y limpiar formulario
    const nameInput = document.getElementById('p-name');
    nameInput.value = "";
    nameInput.disabled = false;

    document.getElementById('p-title').value = "";
    document.getElementById('p-artist').value = "";
    document.getElementById('p-lang').value = "es";
    document.getElementById('p-mode').value = "karaoke";
    document.getElementById('p-whisper').value = "medium";

    // Resetear estilo
    selectStyle(document.querySelector('.style-card[data-style="minimal"]'));

    // Limpiar preview de audio
    document.getElementById('p-audio').value = "";
    document.getElementById('audio-upload-label').innerText = "Arrastra tu MP3 aquí o haz click para explorar";

    // Ocultar editor
    document.getElementById('lyrics-editor-card').style.display = 'none';

    // Deshabilitar pasos del wizard
    document.getElementById('node-2').classList.add('disabled');
    document.getElementById('node-3').classList.add('disabled');
    document.getElementById('node-4').classList.add('disabled');
    document.getElementById('node-5').classList.add('disabled');

    document.getElementById('step2-next').setAttribute('disabled', 'true');
    document.getElementById('step3-next').setAttribute('disabled', 'true');
    document.getElementById('step4-next').setAttribute('disabled', 'true');

    // Resetear video player
    updateVideoPlayer();
}

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

        // Estilo visual y paleta de colores
        currentPaletteName = projectConfig.selected_palette || "default";
        selectedStyle = projectConfig.style || "minimal";

        // Aplicar paleta en las tarjetas y botón
        applyPaletteUI(currentPaletteName);

        // Seleccionar el estilo activo
        const activeCard = document.querySelector(`.style-card[data-style="${selectedStyle}"]`);
        if (activeCard) {
            selectStyle(activeCard);
        }

        // Configuración de render en el paso 5 e inicialización de fuentes en el paso 1
        document.getElementById('render-mode').value = projectConfig.mode || "karaoke";
        document.getElementById('render-style').value = selectedStyle;
        
        const fSize = projectConfig.font_size || 72;
        document.getElementById('render-font-size').value = fSize;
        
        const fontSizePreview = document.getElementById('font-size-preview');
        if (fontSizePreview) {
            fontSizePreview.value = fSize;
        }
        
        const fontSelectPreview = document.getElementById('font-select-preview');
        if (fontSelectPreview) {
            fontSelectPreview.value = projectConfig.font || "georgia";
        }
        
        updateFontPreview();

        // Cargar miniaturas y mapa
        updateImagesGallery();

        // Inicializar tipo de fondo
        const bgType = projectConfig.background_type || "image";
        const radioImg = document.querySelector('input[name="bg-type"][value="image"]');
        const radioVid = document.querySelector('input[name="bg-type"][value="video"]');
        if (radioImg && radioVid) {
            radioImg.checked = (bgType === 'image');
            radioVid.checked = (bgType === 'video');
        }

        const imgSection = document.getElementById('bg-image-section');
        const vidSection = document.getElementById('bg-video-section');
        if (bgType === 'video') {
            if (imgSection) imgSection.style.display = 'none';
            if (vidSection) vidSection.style.display = 'block';
            updateBackgroundVideos();
        } else {
            if (imgSection) imgSection.style.display = 'block';
            if (vidSection) vidSection.style.display = 'none';
        }

        // Cargar editor de letras si ya está transcribido
        if (projectStatus.words_json_exists) {
            document.getElementById('lyrics-editor-card').style.display = 'block';
            loadLyricsEditor();
        } else {
            document.getElementById('lyrics-editor-card').style.display = 'none';
        }

        // Activar/desactivar pasos del Wizard según el progreso real del proyecto
        updateStepAccess();

        // Actualizar etiqueta del audio en Paso 1
        const audioUploadLabel = document.getElementById('audio-upload-label');
        if (projectStatus.audio_exists) {
            audioUploadLabel.innerText = `Audio cargado: ${projectConfig.audio || 'audio.mp3'}`;
        } else {
            audioUploadLabel.innerText = "Arrastra tu MP3 aquí o haz click para explorar";
        }

        // Actualizar UI del Separador
        const runSeparatorBtn = document.getElementById('run-separator-btn');
        const separatorStatusDesc = document.getElementById('separator-status-desc');
        if (runSeparatorBtn && separatorStatusDesc) {
            if (projectStatus.instrumental_exists) {
                runSeparatorBtn.innerText = "⚡ Re-separar Audio";
                separatorStatusDesc.innerHTML = "Pista instrumental lista 🎸<br><small style='color: var(--success);'>El modo Karaoke usará la instrumental aislada.</small>";
            } else {
                runSeparatorBtn.innerText = "⚡ Iniciar Separación de Audio";
                separatorStatusDesc.innerHTML = "Pista instrumental no disponible.<br><small style='color: var(--text-muted);'>Se usará el audio original con voces si compilas ahora.</small>";
            }
        }

        // Actualizar UI del Checkbox de Voz para Whisper
        const whisperUseVocals = document.getElementById('whisper-use-vocals');
        const whisperVocalsHint = document.getElementById('whisper-vocals-hint');
        if (whisperUseVocals && whisperVocalsHint) {
            if (projectStatus.instrumental_exists) {
                whisperUseVocals.disabled = false;
                if (projectConfig.transcribe_from_vocals !== undefined) {
                    whisperUseVocals.checked = projectConfig.transcribe_from_vocals;
                } else {
                    whisperUseVocals.checked = true; // Preseleccionar por defecto si existe vocals.mp3
                }
                whisperVocalsHint.innerText = "¡Pista de voz disponible! Recomendado para mayor precisión.";
                whisperVocalsHint.style.color = "var(--success)";
            } else {
                whisperUseVocals.disabled = true;
                whisperUseVocals.checked = false;
                whisperVocalsHint.innerText = "Mejora el timing al transcribir sin música de fondo. Requiere separar primero.";
                whisperVocalsHint.style.color = "var(--text-muted)";
            }
        }

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

    // Nodo 4 (Mapeo) requiere que words_srt existan. En modo video, también requiere que haya al menos 1 video en la secuencia.
    const node4 = document.getElementById('node-4');
    const isVideoMode = (projectConfig && projectConfig.background_type === 'video');
    const hasVideos = projectConfig && projectConfig.video_backgrounds && projectConfig.video_backgrounds.length > 0;

    if (projectStatus.words_srt_exists && (!isVideoMode || hasVideos)) {
        node4.classList.remove('disabled');
        document.getElementById('step3-next').removeAttribute('disabled');
    } else {
        node4.classList.add('disabled');
        document.getElementById('step3-next').setAttribute('disabled', 'true');
    }

    // Nodo 5 (Render)
    const node5 = document.getElementById('node-5');
    if (isVideoMode) {
        if (projectStatus.words_srt_exists && hasVideos) {
            node5.classList.remove('disabled');
            document.getElementById('step4-next').removeAttribute('disabled');
            loadMapEditor();
        } else {
            node5.classList.add('disabled');
            document.getElementById('step4-next').setAttribute('disabled', 'true');
        }
    } else {
        if (projectStatus.map_exists) {
            node5.classList.remove('disabled');
            document.getElementById('step4-next').removeAttribute('disabled');
            loadMapEditor();
        } else {
            node5.classList.add('disabled');
            document.getElementById('step4-next').setAttribute('disabled', 'true');
        }
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

    // Sincronizar con el selector del paso 5
    const renderStyleSelect = document.getElementById('render-style');
    if (renderStyleSelect) {
        renderStyleSelect.value = selectedStyle;
    }

    // Cambiar estilo de la previsualización de fuentes también
    const palette = colorPalettes[currentPaletteName].styles[selectedStyle];
    const previewBox = document.getElementById('lyric-preview-box');
    previewBox.style.background = palette.bg;

    const sungWord = previewBox.querySelector('.sung');
    const actWord = previewBox.querySelector('.active-word');
    const unsungWord = previewBox.querySelector('.unsung');

    if (sungWord) sungWord.style.color = palette.sung;
    if (actWord) actWord.style.color = palette.active;
    if (unsungWord) unsungWord.style.color = palette.unsung;

    // Guardar en config del proyecto si está cargado
    if (projectConfig && currentProject) {
        projectConfig.style = selectedStyle;
        projectConfig.custom_colors = palette.python;

        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: currentProject,
                config: projectConfig
            })
        }).catch(e => console.error("Error al guardar estilo en config:", e));
    }
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

    const font = document.getElementById('font-select-preview').value;
    const font_size = document.getElementById('font-size-preview').value;
    formData.append('font', font);
    formData.append('font_size', font_size);

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

    const useVocalsInput = document.getElementById('whisper-use-vocals');
    const useVocals = useVocalsInput ? useVocalsInput.checked : false;

    try {
        const res = await fetch(`/api/run_whisper?project=${currentProject}&use_vocals=${useVocals}`, { method: 'POST' });
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

async function startSeparator() {
    if (!currentProject) return;

    try {
        const res = await fetch(`/api/run_separator?project=${currentProject}`, { method: 'POST' });
        const data = await res.json();

        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast("Separador RoFormer iniciado en segundo plano...", "warning");
            const runSeparatorBtn = document.getElementById('run-separator-btn');
            if (runSeparatorBtn) runSeparatorBtn.disabled = true;
            pollStatus();
        }
    } catch (e) {
        showToast("Error al iniciar la separación de audio", "error");
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
            } else if (data.task === 'separator') {
                const sepConsole = document.getElementById('separator-console-output');
                const sepProgressFill = document.getElementById('separator-progress-fill');
                const sepProgressPct = document.getElementById('separator-progress-pct');
                const sepStatusText = document.getElementById('separator-status-text');

                if (sepStatusText && sepProgressPct && sepProgressFill && sepConsole) {
                    sepStatusText.innerText = `Estado: Separando (${data.status})`;
                    sepProgressPct.innerText = `${data.progress}%`;
                    sepProgressFill.style.width = `${data.progress}%`;
                    sepConsole.innerText = data.logs || "Ejecutando separación de audio...";
                    sepConsole.scrollTop = sepConsole.scrollHeight;
                }

                if (data.status === 'success') {
                    clearInterval(statusInterval);
                    showToast("¡Separación de audio completada con éxito!");
                    const runSeparatorBtn = document.getElementById('run-separator-btn');
                    if (runSeparatorBtn) runSeparatorBtn.disabled = false;
                    handleProjectChange(currentProject);
                } else if (data.status === 'failed') {
                    clearInterval(statusInterval);
                    showToast("La separación de audio falló. Revisa la consola.", "error");
                    const runSeparatorBtn = document.getElementById('run-separator-btn');
                    if (runSeparatorBtn) runSeparatorBtn.disabled = false;
                    handleProjectChange(currentProject);
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
            } else if (data.task === 'separator') {
                const runSeparatorBtn = document.getElementById('run-separator-btn');
                if (runSeparatorBtn) runSeparatorBtn.disabled = true;
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

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-image-btn';
        deleteBtn.innerHTML = '&times;';
        deleteBtn.title = 'Eliminar imagen';
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deleteProjectImage(imgName);
        };

        item.appendChild(img);
        item.appendChild(label);
        item.appendChild(deleteBtn);
        gallery.appendChild(item);
    });
}

async function deleteProjectImage(imgName) {
    if (!currentProject) return;
    
    if (!confirm(`¿Estás seguro de que deseas eliminar la imagen "${imgName}"?`)) {
        return;
    }
    
    try {
        const res = await fetch('/api/delete_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: currentProject,
                file: imgName
            })
        });
        const data = await res.json();
        
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast(`Imagen "${imgName}" eliminada correctamente.`);
            handleProjectChange(currentProject);
        }
    } catch (e) {
        showToast("Error al intentar eliminar la imagen", "error");
    }
}

// ── GESTIÓN DE VIDEOS DE FONDO (NUEVO) ─────────────────────────────────────────
function toggleBackgroundType(type) {
    if (!projectConfig) return;
    projectConfig.background_type = type;
    
    if (!projectConfig.video_backgrounds) {
        projectConfig.video_backgrounds = [];
    }

    saveConfigSilent();

    const imgSection = document.getElementById('bg-image-section');
    const vidSection = document.getElementById('bg-video-section');
    
    const radioImg = document.querySelector('input[name="bg-type"][value="image"]');
    const radioVid = document.querySelector('input[name="bg-type"][value="video"]');
    if (radioImg && radioVid) {
        radioImg.checked = (type === 'image');
        radioVid.checked = (type === 'video');
    }

    if (type === 'video') {
        if (imgSection) imgSection.style.display = 'none';
        if (vidSection) vidSection.style.display = 'block';
        updateBackgroundVideos();
    } else {
        if (imgSection) imgSection.style.display = 'block';
        if (vidSection) vidSection.style.display = 'none';
    }

    updateStepAccess();
}

async function handleVideosUpload(event) {
    const files = event.target.files;
    if (files.length === 0) return;

    showToast(`Subiendo video: ${files[0].name}...`, "warning");

    const file = files[0];
    const formData = new FormData();
    formData.append('video', file);

    try {
        const res = await fetch(`/api/upload_video?project=${currentProject}`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast("Video subido correctamente.");
            if (projectConfig) {
                if (!projectConfig.video_backgrounds) projectConfig.video_backgrounds = [];
                projectConfig.video_backgrounds.push(data.filename);
                await saveConfigSilent();
            }
            updateBackgroundVideos();
        }
    } catch (e) {
        showToast(`Error al subir el video ${file.name}`, "error");
    }
}

async function updateBackgroundVideos() {
    if (!currentProject) return;

    try {
        const res = await fetch(`/api/background_videos?project=${currentProject}`);
        const data = await res.json();

        // Renderizar base videos
        const baseList = document.getElementById('base-videos-list');
        if (baseList) {
            baseList.innerHTML = '';
            if (!data.base_videos || data.base_videos.length === 0) {
                baseList.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 0.85rem; padding: 10px;">No hay videos base disponibles.</div>';
            } else {
                data.base_videos.forEach(vPath => {
                    const filename = vPath.split('/').pop();
                    const card = createVideoCard(vPath, filename, 'base');
                    baseList.appendChild(card);
                });
            }
        }

        // Renderizar loop videos
        const loopList = document.getElementById('loop-videos-list');
        if (loopList) {
            loopList.innerHTML = '';
            if (!data.loop_videos || data.loop_videos.length === 0) {
                loopList.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 0.85rem; padding: 10px;">No hay videos de loop disponibles.</div>';
            } else {
                data.loop_videos.forEach(vPath => {
                    const filename = vPath.split('/').pop();
                    const card = createVideoCard(vPath, filename, 'loop');
                    loopList.appendChild(card);
                });
            }
        }

        updateVideoSequenceUI();
    } catch (e) {
        console.error("Error al cargar videos de fondo:", e);
    }
}

function createVideoCard(vPath, filename, type) {
    const card = document.createElement('div');
    card.className = 'video-item-card';

    const info = document.createElement('div');
    info.className = 'video-item-info';

    const name = document.createElement('span');
    name.className = 'video-item-name';
    name.innerText = filename;
    name.title = filename;

    const meta = document.createElement('div');
    meta.className = 'video-item-meta';

    const badge = document.createElement('span');
    badge.className = `badge-video-source badge-${type}`;
    badge.innerText = type === 'base' ? 'base' : 'loop';

    meta.appendChild(badge);
    info.appendChild(name);
    info.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'video-item-actions';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'glow-button secondary';
    prevBtn.style.padding = '4px 10px';
    prevBtn.style.fontSize = '0.75rem';
    prevBtn.innerText = '▶️';
    prevBtn.title = 'Previsualizar';
    prevBtn.onclick = (e) => {
        e.stopPropagation();
        playVideoPreview(vPath);
    };

    const addBtn = document.createElement('button');
    addBtn.className = 'glow-button success';
    addBtn.style.padding = '4px 10px';
    addBtn.style.fontSize = '0.75rem';
    addBtn.innerText = '➕ Añadir';
    addBtn.onclick = (e) => {
        e.stopPropagation();
        addVideoToSequence(vPath);
    };

    actions.appendChild(prevBtn);
    actions.appendChild(addBtn);
    card.appendChild(info);
    card.appendChild(actions);

    return card;
}

function addVideoToSequence(vPath) {
    if (!projectConfig) return;
    if (!projectConfig.video_backgrounds) {
        projectConfig.video_backgrounds = [];
    }
    projectConfig.video_backgrounds.push(vPath);
    saveConfigSilent().then(() => {
        updateVideoSequenceUI();
        updateStepAccess();
    });
}

function removeVideoFromSequence(index) {
    if (!projectConfig || !projectConfig.video_backgrounds) return;
    projectConfig.video_backgrounds.splice(index, 1);
    saveConfigSilent().then(() => {
        updateVideoSequenceUI();
        updateStepAccess();
    });
}

function updateVideoSequenceUI() {
    const seqContainer = document.getElementById('video-sequence-container');
    const seqCount = document.getElementById('video-sequence-count');
    
    if (!seqContainer) return;
    
    const sequence = projectConfig.video_backgrounds || [];
    if (seqCount) {
        seqCount.innerText = `${sequence.length} video${sequence.length === 1 ? '' : 's'}`;
    }

    if (sequence.length === 0) {
        seqContainer.innerHTML = '<div class="gallery-empty-message" style="width: 100%; text-align: center; color: var(--text-muted);">No has seleccionado videos para el bucle. Añade algunos de las listas de abajo.</div>';
        return;
    }

    seqContainer.innerHTML = '';
    sequence.forEach((vPath, idx) => {
        const filename = vPath.split('/').pop();
        const item = document.createElement('div');
        item.className = 'video-sequence-item';

        const indexIndicator = document.createElement('span');
        indexIndicator.className = 'video-sequence-index';
        indexIndicator.innerText = idx + 1;

        const nameSpan = document.createElement('span');
        nameSpan.innerText = filename;
        nameSpan.title = vPath;

        const removeBtn = document.createElement('span');
        removeBtn.className = 'video-sequence-remove';
        removeBtn.innerHTML = '&times;';
        removeBtn.title = 'Quitar de la secuencia';
        removeBtn.onclick = () => removeVideoFromSequence(idx);

        item.appendChild(indexIndicator);
        item.appendChild(nameSpan);
        item.appendChild(removeBtn);
        seqContainer.appendChild(item);
    });
}

function playVideoPreview(vPath) {
    const modal = document.getElementById('video-preview-modal');
    const player = document.getElementById('preview-video-player');
    const title = document.getElementById('video-preview-title');
    
    if (!modal || !player) return;

    const filename = vPath.split('/').pop();
    if (title) title.innerText = `Previsualizar: ${filename}`;

    player.src = `/api/video_file?path=${vPath}`;
    modal.style.display = 'flex';
    player.play().catch(err => console.log("Auto-play blocked or error: ", err));
}

function closeVideoPreview() {
    const modal = document.getElementById('video-preview-modal');
    const player = document.getElementById('preview-video-player');
    
    if (modal) modal.style.display = 'none';
    if (player) {
        player.pause();
        player.src = '';
    }
}

async function saveConfigSilent() {
    if (!currentProject || !projectConfig) return;
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: currentProject,
                config: projectConfig
            })
        });
    } catch (e) {
        console.error("Error al guardar configuración silenciosamente:", e);
    }
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
    const videoZone = document.getElementById('videos-dropzone');

    // Configurar zonas de arrastre
    [audioZone, imageZone, videoZone].forEach(zone => {
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
            extractMetadata(files[0]);
        }
    });

    // Manejar selección de audio manual (click)
    const audioInput = document.getElementById('p-audio');
    if (audioInput) {
        audioInput.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length > 0) {
                document.getElementById('audio-upload-label').innerText = `Seleccionado: ${files[0].name}`;
                extractMetadata(files[0]);
            }
        });
    }

    // Manejar drop de imágenes
    if (imageZone) {
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

    // Manejar drop de videos
    if (videoZone) {
        videoZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                const input = document.getElementById('p-videos');
                input.files = files;
                handleVideosUpload({ target: { files: files } });
            }
        });
    }

    // Manejar selección de video manual
    const videoInput = document.getElementById('p-videos');
    if (videoInput) {
        videoInput.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length > 0) {
                handleVideosUpload({ target: { files: files } });
            }
        });
    }
}


// ──────────────────────────────────────────────────────────────────────────────
// PASO 4: MAPEO VISUAL DE IMÁGENES (`map.json`)
// ──────────────────────────────────────────────────────────────────────────────
async function saveMapDataSilent() {
    if (!currentProject || !mapData) return;
    try {
        await fetch('/api/map', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: currentProject,
                map: mapData
            })
        });
    } catch (e) {
        console.error("Error in saveMapDataSilent:", e);
    }
}

async function loadMapEditor() {
    if (!currentProject) return;

    const container = document.getElementById('map-sections-list');
    if (projectConfig && projectConfig.background_type === 'video') {
        if (container) {
            container.innerHTML = `
                <div class="glass-panel" style="padding: 40px 20px; text-align: center; border: 1px dashed var(--border-color); border-radius: 12px; margin: 20px 0;">
                    <div style="font-size: 3rem; margin-bottom: 15px;">🎥</div>
                    <h3 style="color: var(--accent-gold); margin-bottom: 10px;">Modo Video de Fondo Activo</h3>
                    <p style="color: var(--text-muted); max-width: 500px; margin: 0 auto 25px auto; font-size: 0.95rem; line-height: 1.5;">
                        Has seleccionado video en bucle secuencial como fondo. Los videos se reproducirán de forma continua a lo largo de toda la canción, por lo que no es necesario mapear secciones a tiempos individuales.
                    </p>
                    <button class="glow-button primary" onclick="nextStep()" style="margin: 0 auto;">Ir al Paso 5: Ensamblar →</button>
                </div>
            `;
        }
        return;
    }

    try {
        const res = await fetch(`/api/map?project=${currentProject}`);
        if (!res.ok) return;

        mapData = await res.json();
        
        const numImages = projectImages.length;
        const segments = mapData.segments || [];
        const isSolidOnly = segments.length === 1 && (segments[0].image === 'solid' || segments[0].image === '');
        
        if (numImages > 0 && (segments.length !== numImages || isSolidOnly)) {
            const totalDuration = mapData.total_duration || 300.0;
            const step = totalDuration / numImages;
            mapData.segments = [];
            for (let i = 0; i < numImages; i++) {
                const start = parseFloat((i * step).toFixed(2));
                const end = parseFloat((i === numImages - 1 ? totalDuration : (i + 1) * step).toFixed(2));
                mapData.segments.push({
                    start: start,
                    end: end,
                    image: `images/${projectImages[i]}`,
                    _label: `Sección ${i + 1}`
                });
            }
            await saveMapDataSilent();
        } else if (numImages === 0 && (segments.length !== 1 || segments[0].image !== 'solid')) {
            const totalDuration = mapData.total_duration || 300.0;
            mapData.segments = [{
                start: 0.0,
                end: parseFloat(totalDuration.toFixed(2)),
                image: "solid",
                _label: "Fondo Sólido"
            }];
            await saveMapDataSilent();
        }

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

        if (projectImages.length > 0) {
            // Miniatura especial para Fondo Sólido
            const solidThumb = document.createElement('div');
            const isSolid = seg.image === 'solid' || !seg.image;
            solidThumb.className = `thumb-option ${isSolid ? 'selected' : ''}`;
            solidThumb.title = "Fondo Sólido (Color de la paleta)";
            
            const solidIcon = document.createElement('div');
            solidIcon.className = 'solid-color-thumb-preview';
            solidIcon.innerText = '🎨';
            solidThumb.appendChild(solidIcon);
            
            solidThumb.onclick = () => {
                thumbsGrid.querySelectorAll('.thumb-option').forEach(t => t.classList.remove('selected'));
                solidThumb.classList.add('selected');
                seg.image = 'solid';
                showToast(`Asignado Fondo Sólido a la Sección ${idx + 1}`);
            };
            thumbsGrid.appendChild(solidThumb);

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
        } else {
            const noImgMsg = document.createElement('div');
            noImgMsg.className = 'no-images-note';
            noImgMsg.innerText = 'Fondo sólido activo (se usará el color de la paleta seleccionada)';
            pickerDiv.appendChild(noImgMsg);
        }

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

async function resetMapDistribution() {
    if (!currentProject || !mapData) return;
    
    if (!confirm("¿Deseas restablecer y distribuir uniformemente los tiempos del mapa para las imágenes actuales?")) {
        return;
    }
    
    const numImages = projectImages.length;
    const totalDuration = mapData.total_duration || 300.0;
    
    if (numImages > 0) {
        const step = totalDuration / numImages;
        mapData.segments = [];
        for (let i = 0; i < numImages; i++) {
            const start = parseFloat((i * step).toFixed(2));
            const end = parseFloat((i === numImages - 1 ? totalDuration : (i + 1) * step).toFixed(2));
            mapData.segments.push({
                start: start,
                end: end,
                image: `images/${projectImages[i]}`,
                _label: `Sección ${i + 1}`
            });
        }
    } else {
        mapData.segments = [{
            start: 0.0,
            end: parseFloat(totalDuration.toFixed(2)),
            image: "solid",
            _label: "Fondo Sólido"
        }];
    }
    
    renderMapEditorRows();
    await saveMapData();
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

function setupSyncHandlers() {
    const pMode = document.getElementById('p-mode');
    const renderMode = document.getElementById('render-mode');
    if (pMode && renderMode) {
        pMode.addEventListener('change', (e) => {
            renderMode.value = e.target.value;
        });
        renderMode.addEventListener('change', (e) => {
            pMode.value = e.target.value;
        });
    }

    const renderStyle = document.getElementById('render-style');
    if (renderStyle) {
        renderStyle.addEventListener('change', (e) => {
            const styleCard = document.querySelector(`.style-card[data-style="${e.target.value}"]`);
            if (styleCard) {
                selectStyle(styleCard);
            }
        });
    }

    const renderFontSize = document.getElementById('render-font-size');
    const fontSizePreview = document.getElementById('font-size-preview');
    if (renderFontSize && fontSizePreview) {
        renderFontSize.addEventListener('input', (e) => {
            fontSizePreview.value = e.target.value;
            updateFontPreview();
        });
        fontSizePreview.addEventListener('input', (e) => {
            renderFontSize.value = e.target.value;
            updateFontPreview();
        });
    }
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

    const mode = document.getElementById('render-mode').value;
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
                style: style,
                mode: mode
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

function getCleanAudioName() {
    let name = (projectConfig && projectConfig.original_audio_name) || "";
    if (!name) {
        name = (projectConfig && projectConfig.title) || "";
    }
    if (!name) {
        name = currentProject;
    }

    // Quitar extensión
    if (name.includes('.')) {
        name = name.substring(0, name.lastIndexOf('.'));
    }

    // Normalizar y reemplazar espacios/acentos
    name = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    name = name.replace(/\s+/g, '-');
    let cleanName = name.replace(/[^a-zA-Z0-9_-]/g, '');
    while (cleanName.includes('--')) {
        cleanName = cleanName.replace('--', '-');
    }
    return cleanName.replace(/^-+|-+$/g, '');
}

function getDynamicOutputName(isPreview) {
    const cleanAudio = getCleanAudioName();
    const mode = (projectConfig && projectConfig.mode) || "karaoke";
    const suffix = mode === "lyrics" ? "Lyrics" : "karaoke";
    return isPreview ? `${cleanAudio}-${suffix}-preview.mp4` : `${cleanAudio}-${suffix}.mp4`;
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

        // Usar la ruta dedicada de descarga para saltarse la caché del reproductor y forzar Save As
        downloadBtn.href = `/api/download_video?project=${currentProject}&preview=${isPreview}&t=${Date.now()}`;

        const downloadFilename = getDynamicOutputName(isPreview);
        downloadBtn.setAttribute('download', downloadFilename);

        downloadBtn.innerText = isPreview ? '📥 Descargar Vista Previa (30s)' : '📥 Descargar Video Completo';
    } else {
        player.src = '';
        player.style.display = 'none';
        placeholder.style.display = 'flex';
        actionsBox.style.display = 'none';
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// EDITOR DE LETRAS Y TIMINGS (PASO 2)
// ──────────────────────────────────────────────────────────────────────────────
async function loadLyricsEditor() {
    if (!currentProject) return;
    try {
        const res = await fetch(`/api/words?project=${currentProject}`);
        if (!res.ok) return;
        lyricsData = await res.json();
        renderLyricsEditor();
    } catch (e) {
        console.error("Error al cargar words.json:", e);
        showToast("Error al cargar la letra del proyecto", "error");
    }
}

function renderLyricsEditor() {
    const container = document.getElementById('lyrics-editor-list');
    container.innerHTML = '';

    if (!lyricsData || !lyricsData.segments || lyricsData.segments.length === 0) {
        container.innerHTML = '<div class="gallery-empty-message">No hay letra disponible para editar.</div>';
        return;
    }

    lyricsData.segments.forEach((seg, segIdx) => {
        const segBox = document.createElement('div');
        segBox.className = 'segment-editor-box';
        segBox.dataset.index = segIdx;

        // Header del segmento
        const header = document.createElement('div');
        header.className = 'segment-editor-header';

        const title = document.createElement('h4');
        const startTime = seg.start !== undefined ? parseFloat(seg.start).toFixed(2) : '0.00';
        const endTime = seg.end !== undefined ? parseFloat(seg.end).toFixed(2) : '0.00';
        title.innerText = `Segmento ${segIdx + 1} (${startTime}s - ${endTime}s)`;

        const deleteSegBtn = document.createElement('button');
        deleteSegBtn.className = 'delete-segment-btn';
        deleteSegBtn.innerText = '🗑️ Eliminar';
        deleteSegBtn.onclick = () => deleteSegment(segIdx);

        header.appendChild(title);
        header.appendChild(deleteSegBtn);

        // Contenedor de palabras
        const wordsContainer = document.createElement('div');
        wordsContainer.className = 'words-edit-container';

        // Renderizar palabras
        const wordsList = seg.words || [];
        wordsList.forEach((w, wIdx) => {
            const wordCard = document.createElement('div');
            wordCard.className = 'word-edit-card';

            // Botón eliminar palabra
            const delWordBtn = document.createElement('span');
            delWordBtn.className = 'word-delete-btn';
            delWordBtn.innerHTML = '&times;';
            delWordBtn.onclick = () => deleteWord(segIdx, wIdx);

            // Input texto de palabra
            const wordInput = document.createElement('input');
            wordInput.type = 'text';
            wordInput.className = 'word-text';
            wordInput.value = w.word;
            wordInput.placeholder = 'Palabra';
            wordInput.oninput = (e) => {
                w.word = e.target.value;
                updateSegmentFullText(segIdx);
            };

            // Contenedor de tiempos
            const timesDiv = document.createElement('div');
            timesDiv.className = 'word-edit-times';

            // Input start
            const startDiv = document.createElement('div');
            startDiv.className = 'timing-field-mini';
            startDiv.innerHTML = `<label>Ini</label>`;
            const startInput = document.createElement('input');
            startInput.type = 'number';
            startInput.step = '0.01';
            startInput.value = w.start;
            startInput.oninput = (e) => {
                w.start = parseFloat(e.target.value) || 0.0;
                updateSegmentTimesFromWords(segIdx);
            };
            startDiv.appendChild(startInput);

            // Input end
            const endDiv = document.createElement('div');
            endDiv.className = 'timing-field-mini';
            endDiv.innerHTML = `<label>Fin</label>`;
            const endInput = document.createElement('input');
            endInput.type = 'number';
            endInput.step = '0.01';
            endInput.value = w.end;
            endInput.oninput = (e) => {
                w.end = parseFloat(e.target.value) || 0.0;
                updateSegmentTimesFromWords(segIdx);
            };
            endDiv.appendChild(endInput);

            timesDiv.appendChild(startDiv);
            timesDiv.appendChild(endDiv);

            wordCard.appendChild(delWordBtn);
            wordCard.appendChild(wordInput);
            wordCard.appendChild(timesDiv);

            wordsContainer.appendChild(wordCard);
        });

        // Botón añadir palabra
        const addWordBtn = document.createElement('button');
        addWordBtn.className = 'add-word-btn-mini';
        addWordBtn.innerHTML = '➕ Añadir';
        addWordBtn.onclick = () => addWordToSegment(segIdx);

        wordsContainer.appendChild(addWordBtn);

        segBox.appendChild(header);
        segBox.appendChild(wordsContainer);

        container.appendChild(segBox);
    });
}

function updateSegmentFullText(segIdx) {
    const seg = lyricsData.segments[segIdx];
    if (!seg) return;
    seg.text = (seg.words || []).map(w => w.word).join(' ');
}

function updateSegmentTimesFromWords(segIdx) {
    const seg = lyricsData.segments[segIdx];
    if (!seg || !seg.words || seg.words.length === 0) return;

    // El inicio del segmento es el inicio de su primera palabra
    seg.start = seg.words[0].start;
    // El fin del segmento es el fin de su última palabra
    seg.end = seg.words[seg.words.length - 1].end;

    // Actualizar visualmente el título del segmento en el DOM
    const segBox = document.querySelector(`.segment-editor-box[data-index="${segIdx}"]`);
    if (segBox) {
        const title = segBox.querySelector('.segment-editor-header h4');
        if (title) {
            title.innerText = `Segmento ${segIdx + 1} (${seg.start.toFixed(2)}s - ${seg.end.toFixed(2)}s)`;
        }
    }
}

function deleteSegment(segIdx) {
    if (!lyricsData || !lyricsData.segments) return;
    if (confirm(`¿Estás seguro de que deseas eliminar por completo el segmento ${segIdx + 1}?`)) {
        lyricsData.segments.splice(segIdx, 1);
        // Re-indexar los IDs de segmentos para que sean continuos
        lyricsData.segments.forEach((seg, idx) => {
            seg.id = idx;
        });
        renderLyricsEditor();
    }
}

function deleteWord(segIdx, wIdx) {
    if (!lyricsData || !lyricsData.segments[segIdx]) return;
    const seg = lyricsData.segments[segIdx];
    seg.words.splice(wIdx, 1);

    // Actualizar texto y tiempos del segmento
    updateSegmentFullText(segIdx);
    updateSegmentTimesFromWords(segIdx);

    renderLyricsEditor();
}

function addWordToSegment(segIdx) {
    if (!lyricsData || !lyricsData.segments[segIdx]) return;
    const seg = lyricsData.segments[segIdx];
    if (!seg.words) seg.words = [];

    // Determinar tiempos razonables por defecto para la nueva palabra
    let newStart = 0.0;
    let newEnd = 1.0;
    if (seg.words.length > 0) {
        const lastWord = seg.words[seg.words.length - 1];
        newStart = lastWord.end;
        newEnd = lastWord.end + 0.5; // +500ms
    } else {
        newStart = seg.start || 0.0;
        newEnd = (seg.start || 0.0) + 1.0;
    }

    seg.words.push({
        word: "Nueva",
        start: parseFloat(newStart.toFixed(3)),
        end: parseFloat(newEnd.toFixed(3)),
        confidence: 1.0
    });

    updateSegmentFullText(segIdx);
    updateSegmentTimesFromWords(segIdx);

    renderLyricsEditor();
}

async function saveLyricsData() {
    if (!currentProject || !lyricsData) return;

    try {
        showToast("Guardando cambios de letras...", "warning");
        const res = await fetch('/api/save_words', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project: currentProject,
                segments: lyricsData.segments
            })
        });
        const data = await res.json();

        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast("¡Letras y timings guardados correctamente!");
            // Recargar info del proyecto
            handleProjectChange(currentProject);
        }
    } catch (e) {
        showToast("Error al guardar letras", "error");
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// PARSEO DE METADATOS ID3v1/ID3v2 DE AUDIO (MP3)
// ──────────────────────────────────────────────────────────────────────────────
function extractMetadata(file) {
    const reader = new FileReader();

    // Leer los primeros 128 KB para ID3v2
    reader.onload = function (e) {
        const buffer = e.target.result;
        const view = new DataView(buffer);

        let title = "";
        let artist = "";

        try {
            // Verificar firma ID3v2 "ID3"
            if (view.byteLength >= 10 &&
                view.getUint8(0) === 0x49 &&
                view.getUint8(1) === 0x44 &&
                view.getUint8(2) === 0x33) {

                const versionMajor = view.getUint8(3);
                const sizeBytes = [view.getUint8(6), view.getUint8(7), view.getUint8(8), view.getUint8(9)];
                const id3Size = (sizeBytes[0] << 21) | (sizeBytes[1] << 14) | (sizeBytes[2] << 7) | sizeBytes[3];

                let offset = 10;
                const limit = Math.min(id3Size + 10, view.byteLength);

                // Si es ID3v2.2
                if (versionMajor === 2) {
                    while (offset < limit - 6) {
                        let frameId = "";
                        for (let i = 0; i < 3; i++) {
                            const charCode = view.getUint8(offset + i);
                            if (charCode >= 32 && charCode <= 126) {
                                frameId += String.fromCharCode(charCode);
                            }
                        }
                        if (frameId.length < 3 || frameId === "000") break;

                        // Tamaño de frame en v2.2 es de 3 bytes
                        const frameSize = (view.getUint8(offset + 3) << 16) | (view.getUint8(offset + 4) << 8) | view.getUint8(offset + 5);
                        if (frameSize <= 0 || offset + 6 + frameSize > limit) break;

                        if (frameId === "TT2" || frameId === "TP1") {
                            const encoding = view.getUint8(offset + 6);
                            const rawContent = new Uint8Array(buffer, offset + 7, frameSize - 1);

                            let text = "";
                            try {
                                let decoderName = "iso-8859-1";
                                if (encoding === 1) decoderName = "utf-16";
                                const decoder = new TextDecoder(decoderName);
                                text = decoder.decode(rawContent).replace(/\0/g, '').trim();
                            } catch (err) {
                                console.error("Error al decodificar texto metadata v2.2:", err);
                            }

                            if (frameId === "TT2") title = text;
                            if (frameId === "TP1") artist = text;
                        }
                        offset += 6 + frameSize;
                    }
                } else {
                    // ID3v2.3 o v2.4
                    while (offset < limit - 10) {
                        let frameId = "";
                        for (let i = 0; i < 4; i++) {
                            const charCode = view.getUint8(offset + i);
                            if (charCode >= 32 && charCode <= 126) {
                                frameId += String.fromCharCode(charCode);
                            }
                        }

                        if (frameId.length < 4 || frameId === "0000") break;

                        let frameSize = 0;
                        if (versionMajor === 4) {
                            // En v2.4 el tamaño del frame es synchsafe (7 bits por byte)
                            const fsBytes = [view.getUint8(offset + 4), view.getUint8(offset + 5), view.getUint8(offset + 6), view.getUint8(offset + 7)];
                            frameSize = (fsBytes[0] << 21) | (fsBytes[1] << 14) | (fsBytes[2] << 7) | fsBytes[3];
                        } else {
                            // En v2.3 es un entero de 32 bits estándar
                            frameSize = view.getUint32(offset + 4);
                        }

                        if (frameSize <= 0 || offset + 10 + frameSize > limit) break;

                        if (frameId === "TIT2" || frameId === "TPE1") {
                            const encoding = view.getUint8(offset + 10);
                            const rawContent = new Uint8Array(buffer, offset + 11, frameSize - 1);

                            let text = "";
                            try {
                                let decoderName = "iso-8859-1";
                                if (encoding === 1) {
                                    decoderName = "utf-16";
                                } else if (encoding === 2) {
                                    decoderName = "utf-16be";
                                } else if (encoding === 3) {
                                    decoderName = "utf-8";
                                }
                                const decoder = new TextDecoder(decoderName);
                                text = decoder.decode(rawContent).replace(/\0/g, '').trim();
                            } catch (err) {
                                console.error("Error al decodificar texto metadata:", err);
                            }

                            if (frameId === "TIT2") title = text;
                            if (frameId === "TPE1") artist = text;
                        }

                        offset += 10 + frameSize;
                    }
                }
            }
        } catch (err) {
            console.error("Error parsing ID3v2 tags:", err);
        }

        // Fallback a ID3v1 si no se detectó por ID3v2
        if (!title && !artist) {
            try {
                const lastReader = new FileReader();
                lastReader.onload = function (le) {
                    try {
                        const lastBuffer = le.target.result;
                        const lastView = new DataView(lastBuffer);
                        if (lastView.byteLength === 128 &&
                            lastView.getUint8(0) === 0x54 &&
                            lastView.getUint8(1) === 0x41 &&
                            lastView.getUint8(2) === 0x47) {

                            const decoder = new TextDecoder("iso-8859-1");
                            const titleBytes = new Uint8Array(lastBuffer, 3, 30);
                            const artistBytes = new Uint8Array(lastBuffer, 33, 30);

                            title = decoder.decode(titleBytes).replace(/\0/g, '').trim();
                            artist = decoder.decode(artistBytes).replace(/\0/g, '').trim();

                            applyMetadata(title, artist, file.name);
                        } else {
                            applyMetadata("", "", file.name);
                        }
                    } catch (err1) {
                        console.error("Error parsing ID3v1 tags inside onload:", err1);
                        applyMetadata("", "", file.name);
                    }
                };
                const slice = file.slice(Math.max(0, file.size - 128));
                lastReader.readAsArrayBuffer(slice);
            } catch (err2) {
                console.error("Error slicing or reading for ID3v1:", err2);
                applyMetadata("", "", file.name);
            }
        } else {
            applyMetadata(title, artist, file.name);
        }
    };

    try {
        const headerSlice = file.slice(0, Math.min(128 * 1024, file.size));
        reader.readAsArrayBuffer(headerSlice);
    } catch (err) {
        console.error("Error reading file header for ID3v2:", err);
        applyMetadata("", "", file.name);
    }
}

function applyMetadata(title, artist, filename) {
    const nameInput = document.getElementById('p-name');
    const titleInput = document.getElementById('p-title');
    const artistInput = document.getElementById('p-artist');

    if (title) {
        titleInput.value = title;
        let folderName = title.toLowerCase()
            .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9\s_-]/g, "")
            .replace(/\s+/g, "_");
        nameInput.value = folderName;
    } else {
        const base = filename.replace(/\.[^/.]+$/, "")
            .toLowerCase()
            .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9\s_-]/g, "")
            .replace(/\s+/g, "_");
        nameInput.value = base;
        titleInput.value = filename.replace(/\.[^/.]+$/, "");
    }

    if (artist) {
        artistInput.value = artist;
    } else {
        artistInput.value = "";
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// PALETAS DE COLORES DINÁMICAS (NUEVO)
// ──────────────────────────────────────────────────────────────────────────────

// DATABASE DE PALETAS DE COLORES
const colorPalettes = {
    "default": {
        "name": "Default",
        "headerBg": "linear-gradient(135deg, #1f2937 0%, #111827 100%)",
        "image": "https://images.unsplash.com/photo-1520523839897-bd0b52f945a0?q=80&w=400",
        "colors": ["#C8903A", "#F4EFE6", "#464646", "#00FFB4", "#AFAFFF", "#111111"],
        "styles": {
            "minimal": { active: '#C8903A', sung: '#F4EFE6', unsung: '#464646', bg: 'linear-gradient(135deg, #111 0%, #222 100%)', python: { active: [200,144,58], sung: [244,239,230], unsung: [70,70,70], adj: [45,42,38], bg: 0.68, overlay: 110, bg_color: [15,15,15] } },
            "dark": { active: '#FFCD5A', sung: '#D7D7C3', unsung: '#373737', bg: 'linear-gradient(135deg, #050505 0%, #151515 100%)', python: { active: [255,205,90], sung: [215,215,195], unsung: [55,55,55], adj: [28,28,28], bg: 0.48, overlay: 165, bg_color: [10,10,10] } },
            "neon": { active: '#00FFB4', sung: '#AFAFFF', unsung: '#414141', bg: 'linear-gradient(135deg, #000 0%, #080a10 100%)', python: { active: [0,255,180], sung: [175,175,255], unsung: [65,65,65], adj: [30,30,30], bg: 0.35, overlay: 185, bg_color: [5,5,10] } },
            "vintage": { active: '#FFD77D', sung: '#F0DAB6', unsung: '#5f553e', bg: 'linear-gradient(135deg, #2a221a 0%, #3d3428 100%)', python: { active: [255,215,125], sung: [240,218,182], unsung: [95,85,62], adj: [55,50,38], bg: 0.65, overlay: 125, bg_color: [30,24,18] } }
        }
    },
    "blues": {
        "name": "Blues",
        "headerBg": "linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%)",
        "image": "https://images.unsplash.com/photo-1518609878373-06d740f60d8b?q=80&w=400",
        "colors": ["#CBEBF6", "#3FA9F5", "#1B75BC", "#114D80", "#1E2A5C", "#0A0E29"],
        "styles": {
            "minimal": { active: '#00D2FF', sung: '#FFFFFF', unsung: '#4A5F70', bg: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)', python: { active: [0,210,255], sung: [255,255,255], unsung: [74,95,112], adj: [30,40,50], bg: 0.65, overlay: 110, bg_color: [10,15,25] } },
            "dark": { active: '#3B82F6', sung: '#93C5FD', unsung: '#1E3A8A', bg: 'linear-gradient(135deg, #020617 0%, #0F172A 100%)', python: { active: [59,130,246], sung: [147,197,253], unsung: [30,58,138], adj: [10,20,40], bg: 0.45, overlay: 165, bg_color: [2,5,15] } },
            "neon": { active: '#00F2FE', sung: '#4FACFE', unsung: '#1E293B', bg: 'linear-gradient(135deg, #0B132B 0%, #1C2541 100%)', python: { active: [0,242,254], sung: [79,172,254], unsung: [30,41,59], adj: [15,20,35], bg: 0.35, overlay: 185, bg_color: [5,10,20] } },
            "vintage": { active: '#60A5FA', sung: '#DBEAFE', unsung: '#3B82F6', bg: 'linear-gradient(135deg, #172554 0%, #1e3a8a 100%)', python: { active: [96,165,250], sung: [219,234,254], unsung: [59,130,246], adj: [40,50,80], bg: 0.60, overlay: 125, bg_color: [15,25,45] } }
        }
    },
    "passion": {
        "name": "Passion",
        "headerBg": "linear-gradient(135deg, #7c2d12 0%, #dc2626 100%)",
        "image": "https://images.unsplash.com/photo-1518156677180-95a2893f3e9f?q=80&w=400",
        "colors": ["#ff7e40", "#ea580c", "#dc2626", "#991b1b", "#450a0a", "#0c0a09"],
        "styles": {
            "minimal": { active: '#F97316', sung: '#FFF7ED', unsung: '#7C2D12', bg: 'linear-gradient(135deg, #1C1917 0%, #292524 100%)', python: { active: [249,115,22], sung: [255,247,237], unsung: [124,45,18], adj: [60,30,20], bg: 0.65, overlay: 110, bg_color: [20,15,15] } },
            "dark": { active: '#EF4444', sung: '#FEE2E2', unsung: '#450A0A', bg: 'linear-gradient(135deg, #0C0A09 0%, #1C1917 100%)', python: { active: [239,68,68], sung: [254,226,226], unsung: [69,10,10], adj: [30,10,10], bg: 0.45, overlay: 165, bg_color: [10,5,5] } },
            "neon": { active: '#FF0055', sung: '#FFAA00', unsung: '#500000', bg: 'linear-gradient(135deg, #0A0003 0%, #1A0008 100%)', python: { active: [255,0,85], sung: [255,170,0], unsung: [80,0,0], adj: [35,0,5], bg: 0.35, overlay: 185, bg_color: [15,0,5] } },
            "vintage": { active: '#EA580C', sung: '#FFEDD5', unsung: '#7C2D12', bg: 'linear-gradient(135deg, #451a03 0%, #7c2d12 100%)', python: { active: [234,88,12], sung: [255,237,213], unsung: [124,45,18], adj: [80,30,20], bg: 0.60, overlay: 125, bg_color: [35,15,10] } }
        }
    },
    "memory": {
        "name": "Memory",
        "headerBg": "linear-gradient(135deg, #1e1b4b 0%, #4c1d95 100%)",
        "image": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?q=80&w=400",
        "colors": ["#eef2ff", "#ffedd5", "#fed7aa", "#c7d2fe", "#b45309", "#1e1b4b"],
        "styles": {
            "minimal": { active: '#A78BFA', sung: '#F5F3FF', unsung: '#4C1D95', bg: 'linear-gradient(135deg, #18181B 0%, #27272A 100%)', python: { active: [167,139,250], sung: [245,243,255], unsung: [76,29,149], adj: [40,20,60], bg: 0.65, overlay: 110, bg_color: [15,15,20] } },
            "dark": { active: '#C084FC', sung: '#E9D5FF', unsung: '#581C87', bg: 'linear-gradient(135deg, #090514 0%, #181124 100%)', python: { active: [192,132,252], sung: [233,213,255], unsung: [88,28,135], adj: [30,10,50], bg: 0.45, overlay: 165, bg_color: [5,3,10] } },
            "neon": { active: '#D8B4FE', sung: '#F3E8FF', unsung: '#581C87', bg: 'linear-gradient(135deg, #120E1E 0%, #1A122C 100%)', python: { active: [216,180,254], sung: [243,232,255], unsung: [88,28,135], adj: [40,20,60], bg: 0.35, overlay: 185, bg_color: [10,8,15] } },
            "vintage": { active: '#F472B6', sung: '#FCE7F3', unsung: '#9D174D', bg: 'linear-gradient(135deg, #4a044e 0%, #701a75 100%)', python: { active: [244,114,182], sung: [252,231,243], unsung: [157,23,77], adj: [80,20,60], bg: 0.60, overlay: 125, bg_color: [35,5,30] } }
        }
    },
    "acid": {
        "name": "Acid",
        "headerBg": "linear-gradient(135deg, #1e293b 0%, #10b981 100%)",
        "image": "https://images.unsplash.com/photo-1541701494587-cb58502866ab?q=80&w=400",
        "colors": ["#a3e635", "#06b6d4", "#3b82f6", "#22c55e", "#ec4899", "#311042"],
        "styles": {
            "minimal": { active: '#39FF14', sung: '#FFFFFF', unsung: '#1F4D12', bg: 'linear-gradient(135deg, #050A02 0%, #0E1A04 100%)', python: { active: [57,255,20], sung: [255,255,255], unsung: [31,77,18], adj: [10,30,5], bg: 0.65, overlay: 110, bg_color: [5,10,2] } },
            "dark": { active: '#CCFF00', sung: '#E2E2E2', unsung: '#3A4400', bg: 'linear-gradient(135deg, #0D1000 0%, #1D2200 100%)', python: { active: [204,255,0], sung: [226,226,226], unsung: [58,68,0], adj: [20,25,0], bg: 0.45, overlay: 165, bg_color: [10,12,0] } },
            "neon": { active: '#00FF00', sung: '#FF00FF', unsung: '#330033', bg: 'linear-gradient(135deg, #000000 0%, #0D0D0D 100%)', python: { active: [0,255,0], sung: [255,0,255], unsung: [51,0,51], adj: [10,0,10], bg: 0.35, overlay: 185, bg_color: [0,0,0] } },
            "vintage": { active: '#8B5CF6', sung: '#DDD6FE', unsung: '#4C1D95', bg: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)', python: { active: [139,92,246], sung: [221,214,254], unsung: [76,29,149], adj: [30,10,70], bg: 0.60, overlay: 125, bg_color: [15,12,25] } }
        }
    },
    "macaron": {
        "name": "Macaron",
        "headerBg": "linear-gradient(135deg, #fbcfe8 0%, #ccfbf1 100%)",
        "image": "https://images.unsplash.com/photo-1569864358642-9d1684040f43?q=80&w=400",
        "colors": ["#fbcfe8", "#fde047", "#a7f3d0", "#fed7aa", "#bfdbfe", "#f472b6"],
        "styles": {
            "minimal": { active: '#FFB7B2', sung: '#FFFFFC', unsung: '#E8AEB7', bg: 'linear-gradient(135deg, #1C1921 0%, #2A2730 100%)', python: { active: [255,183,178], sung: [255,255,252], unsung: [232,174,183], adj: [50,40,50], bg: 0.65, overlay: 110, bg_color: [20,18,22] } },
            "dark": { active: '#FFD166', sung: '#F7FFF7', unsung: '#06D6A0', bg: 'linear-gradient(135deg, #070F15 0%, #122030 100%)', python: { active: [255,209,102], sung: [247,255,247], unsung: [6,214,160], adj: [5,30,40], bg: 0.45, overlay: 165, bg_color: [5,10,15] } },
            "neon": { active: '#F72585', sung: '#4CC9F0', unsung: '#3F37C9', bg: 'linear-gradient(135deg, #10002B 0%, #240046 100%)', python: { active: [247,37,133], sung: [76,201,240], unsung: [63,55,201], adj: [20,10,50], bg: 0.35, overlay: 185, bg_color: [12,0,20] } },
            "vintage": { active: '#E9C46A', sung: '#F4A261', unsung: '#264653', bg: 'linear-gradient(135deg, #2E3D44 0%, #1D262B 100%)', python: { active: [233,196,106], sung: [244,162,97], unsung: [38,70,83], adj: [40,50,60], bg: 0.60, overlay: 125, bg_color: [25,30,35] } }
        }
    }
};

function setupPaletteHandlers() {
    const openBtn = document.getElementById('open-palette-btn');
    const closeBtn = document.getElementById('close-palette-modal');
    const modal = document.getElementById('palette-modal');
    
    if (openBtn) {
        openBtn.addEventListener('click', () => {
            renderPaletteCards();
            modal.style.display = 'flex';
        });
    }
    
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }
    
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }
}

function applyPaletteUI(pKey) {
    if (!colorPalettes[pKey]) pKey = "default";
    currentPaletteName = pKey;
    
    const stylesData = colorPalettes[pKey].styles;
    document.querySelectorAll('.style-card').forEach(card => {
        const styleName = card.dataset.style;
        const cfg = stylesData[styleName];
        if (!cfg) return;
        
        const preview = card.querySelector('.style-preview');
        if (preview) {
            preview.style.background = cfg.bg;
            preview.style.borderColor = cfg.active;
            
            const pText = preview.querySelector('.preview-text');
            if (pText) {
                pText.style.color = cfg.sung;
                const actSpan = pText.querySelector('span');
                if (actSpan) {
                    actSpan.style.color = cfg.active;
                }
            }
        }
        
        const labelSpan = card.querySelector('span');
        if (labelSpan) {
            const styleCap = styleName.charAt(0).toUpperCase() + styleName.slice(1);
            labelSpan.innerText = `${styleCap} (${colorPalettes[pKey].name})`;
        }
    });
    
    const openBtn = document.getElementById('open-palette-btn');
    if (openBtn) {
        const primaryColor = colorPalettes[pKey].colors[0];
        openBtn.style.color = primaryColor;
        openBtn.style.borderColor = primaryColor;
        openBtn.style.boxShadow = `0 0 10px ${primaryColor}40`;
    }
}

function renderPaletteCards() {
    const grid = document.getElementById('palette-list-grid');
    if (!grid) return;
    
    grid.innerHTML = '';
    
    // Cargar dinámicamente las paletas recomendadas
    Object.keys(colorPalettes).forEach(pKey => {
        const pal = colorPalettes[pKey];
        const isSelected = currentPaletteName === pKey;
        
        const card = document.createElement('div');
        card.className = `palette-card ${isSelected ? 'selected' : ''}`;
        card.onclick = () => selectPalette(pKey);
        
        if (isSelected) {
            const primaryColor = pal.colors[0];
            card.style.borderColor = primaryColor;
            card.style.boxShadow = `0 0 15px ${primaryColor}60`;
        }
        
        // Cabecera visual (imagen con fallback de gradiente)
        const vHeader = document.createElement('div');
        vHeader.className = 'palette-visual-header';
        if (pal.image) {
            vHeader.style.background = `url('${pal.image}') center/cover no-repeat, ${pal.headerBg}`;
        } else {
            vHeader.style.background = pal.headerBg;
        }
        
        // Franja de colores
        const colorStrip = document.createElement('div');
        colorStrip.className = 'palette-color-strip';
        
        pal.colors.forEach(col => {
            const block = document.createElement('div');
            block.className = 'palette-color-block';
            block.style.backgroundColor = col;
            colorStrip.appendChild(block);
        });
        
        // Nombre superpuesto
        const nameOverlay = document.createElement('div');
        nameOverlay.className = 'palette-name-overlay';
        nameOverlay.innerText = pal.name;
        colorStrip.appendChild(nameOverlay);
        
        card.appendChild(vHeader);
        card.appendChild(colorStrip);
        grid.appendChild(card);
    });
}

async function selectPalette(pKey) {
    if (!colorPalettes[pKey]) return;
    
    currentPaletteName = pKey;
    showToast(`Paleta de colores cambiada a: ${colorPalettes[pKey].name}`);
    
    // Cerrar modal
    const modal = document.getElementById('palette-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    
    // Aplicar a la interfaz
    applyPaletteUI(pKey);
    
    // Re-seleccionar el estilo activo para pintar la previsualización del centro/reproductor
    const activeCard = document.querySelector(`.style-card[data-style="${selectedStyle}"]`);
    if (activeCard) {
        selectStyle(activeCard);
    }
    
    // Guardar en config del proyecto
    if (projectConfig && currentProject) {
        projectConfig.selected_palette = pKey;
        projectConfig.style = selectedStyle;
        projectConfig.custom_colors = colorPalettes[pKey].styles[selectedStyle].python;
        
        try {
            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: currentProject,
                    config: projectConfig
                })
            });
        } catch (e) {
            console.error("Error al guardar paleta en config:", e);
        }
    }
}
