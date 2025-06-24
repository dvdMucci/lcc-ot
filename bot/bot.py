import time
import logging
import os
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('TestBot')

def main():
    """Función principal del bot"""
    logger.info("🤖 Bot iniciado correctamente")
    logger.info(f"📝 Variables de entorno disponibles: {len(os.environ)}")
    
    # Mostrar algunas variables de entorno importantes
    env_vars = ['HOSTNAME', 'USER', 'PATH', 'HOME']
    for var in env_vars:
        value = os.getenv(var, 'No definida')
        logger.info(f"🔧 {var}: {value}")
    
    counter = 0
    
    try:
        while True:
            counter += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            
            logger.info(f"✅ Bot ejecutándose - Ciclo #{counter} - Hora: {current_time}")
            
            # Simular algún trabajo
            if counter % 5 == 0:
                logger.info(f"🔄 Ejecutando tarea especial en ciclo #{counter}")
            
            if counter % 10 == 0:
                logger.info(f"📊 Estado del sistema: OK - Uptime: {counter * 30} segundos")
            
            # Esperar 30 segundos
            time.sleep(30)
            
    except KeyboardInterrupt:
        logger.info("⏹️  Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        raise
    finally:
        logger.info("🛑 Bot finalizado")

if __name__ == "__main__":
    main()