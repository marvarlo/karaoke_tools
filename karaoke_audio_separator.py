from audio_separator.separator import Separator

# Inicializar el separador (selecciona el modelo)
separator = Separator()
# Modelo predeterminado: MDX-Net
separator.load_model(model_filename='model_bs_roformer_ep_317_sdr_12.9750.ckpt') # Modelo 2026 de alta calidad

# Separar
output_files = separator.separate('E:\\Users\\Marco\\Music\\Reencuentro\\Reencuentro.mp3')

print(f"Archivos generados: {output_files}")
# Resultado: instrumentals.wav, vocals.wav