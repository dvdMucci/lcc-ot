#!/usr/bin/env python3
"""
Script de prueba para verificar que Whisper esté funcionando correctamente
"""

import os
import sys
import logging
import whisper

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_whisper():
    """Prueba la funcionalidad básica de Whisper"""
    try:
        logger.info("Iniciando prueba de Whisper...")
        
        # Verificar si hay archivos de audio para probar
        audio_dir = "worklog_audios"
        if not os.path.exists(audio_dir):
            logger.error(f"Directorio {audio_dir} no existe")
            return False
        
        audio_files = [f for f in os.listdir(audio_dir) if f.endswith('.ogg')]
        if not audio_files:
            logger.error(f"No hay archivos de audio .ogg en {audio_dir}")
            return False
        
        logger.info(f"Encontrados {len(audio_files)} archivos de audio")
        
        # Cargar modelo Whisper
        logger.info("Cargando modelo Whisper 'small'...")
        model = whisper.load_model("small")
        logger.info("Modelo Whisper cargado exitosamente")
        
        # Probar con el primer archivo de audio
        test_audio = os.path.join(audio_dir, audio_files[0])
        logger.info(f"Probando transcripción con: {test_audio}")
        
        # Transcribir
        result = model.transcribe(test_audio, language="es", fp16=False)
        text = result.get('text', '').strip()
        
        if text:
            logger.info(f"Transcripción exitosa: {text[:100]}...")
            return True
        else:
            logger.warning("Transcripción no produjo texto")
            return False
            
    except Exception as e:
        logger.error(f"Error en prueba de Whisper: {e}")
        return False

if __name__ == "__main__":
    success = test_whisper()
    if success:
        print("✅ Prueba de Whisper exitosa")
        sys.exit(0)
    else:
        print("❌ Prueba de Whisper falló")
        sys.exit(1)
