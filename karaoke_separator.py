import sys
import os
from pathlib import Path
from audio_separator.separator import Separator

def main():
    if len(sys.argv) < 3:
        print("Uso: python karaoke_separator.py <audio_path> <project_dir>")
        sys.exit(1)

    audio_path = Path(sys.argv[1]).resolve()
    project_dir = Path(sys.argv[2]).resolve()

    if not audio_path.exists():
        print(f"Error: El archivo de audio no existe: {audio_path}")
        sys.exit(1)

    project_dir.mkdir(parents=True, exist_ok=True)

    print(f"Separando audio: {audio_path}")
    print(f"Carpeta del proyecto: {project_dir}")

    # Definir directorio de modelos dentro de karaoke_tools para evitar escribir en /tmp
    workspace_dir = Path(__file__).parent.resolve()
    models_dir = workspace_dir / 'audio_separator_models'
    models_dir.mkdir(exist_ok=True)

    # Inicializar Separator
    separator = Separator(
        model_file_dir=str(models_dir),
        output_dir=str(project_dir),
        output_format='MP3',
        log_level=20  # INFO
    )

    # Cargar el modelo RoFormer de alta calidad
    model_name = 'model_bs_roformer_ep_317_sdr_12.9755.ckpt'
    print(f"Cargando modelo: {model_name}...")
    separator.load_model(model_name)

    # Separar pistas
    print("Iniciando separación de audio con RoFormer...")
    output_files = separator.separate(str(audio_path))
    print(f"Pistas generadas preliminares: {output_files}")

    # Identificar y renombrar instrumental y vocal
    instrumental_renamed = False
    vocals_renamed = False

    for file_name in output_files:
        full_path = project_dir / file_name
        if not full_path.exists():
            continue
            
        # El nombre suele contener "Instrumental" y "Vocals"
        if "(Instrumental)" in file_name or "Instrumental" in file_name:
            target_path = project_dir / "instrumental.mp3"
            if target_path.exists():
                target_path.unlink()
            full_path.rename(target_path)
            print(f"Instrumental guardada en: {target_path}")
            instrumental_renamed = True
        elif "(Vocals)" in file_name or "Vocals" in file_name:
            target_path = project_dir / "vocals.mp3"
            if target_path.exists():
                target_path.unlink()
            full_path.rename(target_path)
            print(f"Voz guardada en: {target_path}")
            vocals_renamed = True

    if not instrumental_renamed or not vocals_renamed:
        # Intento alternativo buscando por patrones de nombre si por alguna razón no coincidieron
        for item in project_dir.iterdir():
            if item.is_file() and item.suffix.lower() == '.mp3' and item.name not in ('audio.mp3', 'instrumental.mp3', 'vocals.mp3'):
                if 'instrumental' in item.name.lower():
                    target = project_dir / "instrumental.mp3"
                    if target.exists(): target.unlink()
                    item.rename(target)
                    print(f"Instrumental (alternativo) guardada en: {target}")
                    instrumental_renamed = True
                elif 'vocals' in item.name.lower() or 'vocal' in item.name.lower():
                    target = project_dir / "vocals.mp3"
                    if target.exists(): target.unlink()
                    item.rename(target)
                    print(f"Voz (alternativo) guardada en: {target}")
                    vocals_renamed = True

    if instrumental_renamed and vocals_renamed:
        print("Separación de audio completada con éxito. Archivos instrumental.mp3 y vocals.mp3 listos.")
    else:
        print("Advertencia: No se pudieron identificar todas las pistas.")

if __name__ == '__main__':
    main()
