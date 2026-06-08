# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
# pip install transformers accelerate bitsandbytes

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Comprobar si bitsandbytes está disponible para 8-bit
try:
    import bitsandbytes as bnb  # type: ignore
    _HAS_BNB = True
except Exception:
    _HAS_BNB = False

def _get_hf_auth_token():
    return (
        os.environ.get("HF_HUB_TOKEN")
        or os.environ.get("HUGGINGFACE_TOKEN")
        or os.environ.get("HF_TOKEN")
        
    )

def load_gemma_cpu_quantized(model_name="google/gemma-2b-it", local_dir="./GemmaIA"):
    """
    Carga el modelo Gemma en CPU con cuantización int8 para reducir uso de memoria.
    Descarga los archivos en `local_dir` (por defecto ./GemmaIA) y en ejecuciones
    posteriores intentará cargar desde esa carpeta.
    """
    try:
        print(f"Cargando modelo {model_name} en CPU con int8...")
        auth_token = _get_hf_auth_token()

        # Asegurar carpeta local
        local_dir = os.path.abspath(local_dir)
        os.makedirs(local_dir, exist_ok=True)

        # Detectar si ya hay archivos descargados en local_dir
        local_present = False
        try:
            local_present = len(os.listdir(local_dir)) > 0
        except Exception:
            local_present = False

        if local_present:
            print(f"Intentando cargar desde caché local: {local_dir}")
        else:
            print(f"No hay caché local en {local_dir}. Se intentará descargar allí si es posible.")

        # Construir argumentos comunes para transformers
        common_args = {"cache_dir": local_dir}
        # Pasar use_auth_token solo si vamos a acceder a repositorio remoto
        if auth_token and not local_present:
            common_args["use_auth_token"] = auth_token

        # Si hay archivos locales, usar la carpeta local como fuente directa
        pretrained_source = local_dir if local_present else model_name

        tokenizer = AutoTokenizer.from_pretrained(
            pretrained_source,
            local_files_only=local_present,
            **common_args
        )

        # Carga del modelo (usar cuantización 8-bit solo si bitsandbytes está instalado)
        if not _HAS_BNB:
            print("bitsandbytes no disponible: cargando sin cuantización 8-bit.")

        model_kwargs = {
            "device_map": "cpu",
            "low_cpu_mem_usage": True,
            "local_files_only": local_present,
        }

        model = AutoModelForCausalLM.from_pretrained(
            pretrained_source,
            **model_kwargs,
            **common_args
        )

        model.eval()
        return tokenizer, model
    except Exception as e:
        msg = str(e)
        if "gated repo" in msg.lower() or "restricted" in msg.lower() or "401" in msg:
            raise RuntimeError(
                "Error al cargar el modelo: el repositorio está restringido. "
                "Asegúrate de tener acceso a google/gemma-2b-it en Hugging Face y de definir HF_HUB_TOKEN."
            ) from e
        raise RuntimeError(f"Error al cargar el modelo: {e}") from e

def generate_text(prompt, tokenizer, model, max_tokens=100):
    """
    Genera texto usando el modelo Gemma en CPU.
    """
    try:
        inputs = tokenizer(prompt, return_tensors="pt").to("cpu")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )
        return tokenizer.decode(outputs[0], skip_special_tokens=True)
    except Exception as e:
        raise RuntimeError(f"Error al generar texto: {e}")

if __name__ == "__main__":
    try:
        # 1. Cargar modelo optimizado
        tokenizer, model = load_gemma_cpu_quantized()

        # 2. Prompt de ejemplo
        prompt = "Resume en una frase qué es la inteligencia artificial."

        # 3. Generar respuesta
        respuesta = generate_text(prompt, tokenizer, model)
        print("\n--- Respuesta del modelo ---")
        print(respuesta)

    except Exception as err:
        print(f"Fallo en la ejecución: {err}")
