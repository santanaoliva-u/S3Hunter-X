import logging
from logging.handlers import RotatingFileHandler
import os
import sys

def setup_logger(log_level: str = 'INFO') -> logging.Logger:
    """Configura el logger con rotación de archivos y salida en consola."""
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 's3hunterx.log')
    
    logger = logging.getLogger('S3Hunter-X')
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Limpiar manejadores existentes para evitar duplicados
    logger.handlers.clear()
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(
        '%(levelname)s:%(name)s:%(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"Logger configurado con nivel {log_level}")
    return logger