import aiohttp
import os
import re
import time
from typing import Tuple, Optional
from config import settings
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger('S3Hunter-X')

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=5, max=120))
async def download_file(bucket: str, filename: str, analyzer: 'Analyzer', region: str) -> Tuple[Optional[str], Optional[str]]:
    """Descarga un archivo desde un bucket S3 y analiza su contenido."""
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{filename}"
    download_dir = 'data/downloads'
    os.makedirs(download_dir, exist_ok=True)
    base, ext = os.path.splitext(filename.replace('/', '_'))
    local_path = os.path.join(download_dir, f"{bucket}_{base}{ext}")
    if os.path.exists(local_path):
        local_path = os.path.join(download_dir, f"{bucket}_{base}_{int(time.time())}{ext}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=settings.SETTINGS['request_timeout']) as response:
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    max_size_bytes = settings.SETTINGS['max_file_size_mb'] * 1024 * 1024
                    downloaded_bytes = 0
                    with open(local_path, 'wb' if 'text' not in content_type else 'w', encoding='utf-8' if 'text' in content_type else None) as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            downloaded_bytes += len(chunk)
                            if downloaded_bytes > max_size_bytes:
                                logger.warning(f"Archivo {url} excede el tamaño máximo ({settings.SETTINGS['max_file_size_mb']} MB)")
                                return None, None
                            f.write(chunk.decode('utf-8', errors='ignore') if 'text' in content_type else chunk)
                    content_risk = analyzer.analyze_content(local_path)
                    logger.info(f"Archivo descargado: {local_path}, Riesgo: {content_risk}")
                    return local_path, content_risk
                else:
                    logger.error(f"Error al descargar {url}: Status {response.status}")
                    return None, None
    except Exception as e:
        logger.error(f"Error al descargar {url}: {e}")
        return None, None

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=5, max=120))
async def send_telegram_notification(message: str, token: str, chat_id: str) -> bool:
    """Envía una notificación a Telegram."""
    if not token or not chat_id:
        logger.error("Falta telegram_token o telegram_chat_id")
        return False
    if not re.match(r'^bot\d+:[A-Za-z0-9_-]+$', token):
        logger.error("Formato de telegram_token inválido")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status == 200:
                    logger.info("Notificación de Telegram enviada exitosamente")
                    return True
                elif response.status == 429:
                    logger.warning("Límite de tasa de Telegram alcanzado, esperando...")
                    raise aiohttp.ClientError("Rate limit")
                else:
                    logger.error(f"Error al enviar notificación de Telegram: Status {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Error al enviar notificación de Telegram: {e}")
        return False