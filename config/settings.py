import os
import re
import requests
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

def validate_proxy(proxy: str) -> bool:
    """Valida si un proxy está funcional."""
    try:
        response = requests.get("https://httpbin.org/ip", proxies={"http": proxy, "https": proxy}, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Proxy {proxy} no funcional: {e}")
        return False

def validate_settings(settings: Dict) -> Dict:
    """Valida los valores de configuración."""
    errors = []
    if not isinstance(settings.get('max_workers', 0), int) or settings['max_workers'] <= 0:
        errors.append("max_workers debe ser un entero positivo")
    if not isinstance(settings.get('max_file_size_mb', 0), (int, float)) or settings['max_file_size_mb'] <= 0:
        errors.append("max_file_size_mb debe ser un número positivo")
    if not isinstance(settings.get('request_timeout', 0), (int, float)) or settings['request_timeout'] <= 0:
        errors.append("request_timeout debe ser un número positivo")
    if not os.path.exists(settings.get('patterns_file', '')):
        errors.append(f"No se encontró el archivo de patrones: {settings['patterns_file']}")
    if not settings.get('user_agents'):
        errors.append("La lista de user_agents no puede estar vacía")
    if not isinstance(settings.get('authorized_domains', []), list):
        errors.append("authorized_domains debe ser una lista")
    for domain in settings.get('authorized_domains', []):
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$', domain):
            errors.append(f"Dominio no válido en authorized_domains: {domain}")
    if not isinstance(settings.get('s3_regions', []), list) or not settings['s3_regions']:
        errors.append("s3_regions debe ser una lista no vacía")
    settings['proxies'] = [proxy for proxy in settings.get('proxies', []) if validate_proxy(proxy)]
    if settings.get('telegram_token') and not settings.get('telegram_chat_id'):
        errors.append("Se proporcionó telegram_token pero falta telegram_chat_id")
    if settings.get('telegram_chat_id') and not settings.get('telegram_token'):
        errors.append("Se proporcionó telegram_chat_id pero falta telegram_token")
    
    if errors:
        raise ValueError("\n".join(errors))
    return settings

DEFAULT_SETTINGS: Dict[str, any] = {
    'max_workers': 20,
    'max_file_size_mb': 50,
    'buckets_file': 'data/buckets.txt',
    'patterns_file': 'data/grep_words.txt',
    'database': 'data/results.db',
    'request_timeout': 10,
    's3_regions': ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1'],
    'proxies': [],
    'use_tor': False,
    'user_agents': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
    ],
    'telegram_token': os.getenv('TELEGRAM_TOKEN', ''),
    'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    'authorized_domains': ['walletbot.me', 'uber.com'],
    'log_level': 'INFO',
}

SETTINGS = validate_settings(DEFAULT_SETTINGS)