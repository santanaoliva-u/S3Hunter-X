import importlib
import logging
from typing import List, Optional

logger = logging.getLogger('S3Hunter-X')

def load_module(module_path: str) -> Optional[object]:
    """Carga un módulo dinámicamente."""
    try:
        module = importlib.import_module(module_path)
        return module
    except ImportError as e:
        logger.error(f"No se pudo cargar el módulo {module_path}: {e}")
        return None

def is_authorized_domain(bucket: str, authorized_domains: List[str]) -> bool:
    """Verifica si un bucket pertenece a un dominio autorizado."""
    if not authorized_domains:
        return True
    bucket_clean = bucket.lower()
    authorized_domains_clean = [domain.replace('.', '-').lower() for domain in authorized_domains]
    return any(domain in bucket_clean for domain in authorized_domains_clean)