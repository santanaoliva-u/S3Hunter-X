import os
import re
import itertools
import random
import string
import dns.resolver
from typing import List, Set
from config import settings
import logging

logger = logging.getLogger('S3Hunter-X')

def resolve_subdomains(domain: str) -> List[str]:
    """Resuelve subdominios de un dominio usando DNS, filtrando solo los relacionados con S3."""
    subdomains = [domain.replace('.', '-').lower()]
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = resolver.resolve(domain, 'CNAME')
        for rdata in answers:
            target = rdata.target.to_text().rstrip('.')
            if target.endswith('.s3.amazonaws.com') or any(target.endswith(f'.s3.{region}.amazonaws.com') for region in settings.SETTINGS['s3_regions']):
                subdomains.append(domain.replace('.', '-').lower())
        logger.debug(f"CNAMEs encontrados para {domain}: {[rdata.target.to_text() for rdata in answers]}")
    except Exception as e:
        logger.debug(f"No se encontraron CNAMEs válidos para {domain}: {e}")
    return list(set(subdomains))

def load_wordlist(file_path: str) -> List[str]:
    """Carga una lista de palabras desde un archivo."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"No se encontró el archivo de palabras: {file_path}")
        return []
    except Exception as e:
        logger.error(f"Error al leer el archivo de palabras: {e}")
        return []

def generate_fuzzed_names(base_name: str, max_fuzz: int = 100) -> List[str]:
    """Genera variaciones fuzzed de un nombre base."""
    fuzzed = [base_name]
    for i in range(min(max_fuzz // 2, 50)):
        fuzzed.append(f"{base_name}-{i:03d}")
        fuzzed.append(f"{base_name}{i:03d}")
    for _ in range(min(max_fuzz // 2, 50)):
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        fuzzed.append(f"{base_name}-{random_suffix}")
    variations = ['v1', 'v2', 'v3', 'prod', 'dev', 'test', 'backup', 'old', 'new', 'temp', 'staging', 'qa', 'sandbox']
    for var in variations:
        fuzzed.append(f"{base_name}-{var}")
        fuzzed.append(f"{var}-{base_name}")
    return fuzzed

def generate_bucket_names(target_domain: str, wordlist_file: str = None, subdomains_file: str = None, max_buckets: int = None) -> List[str]:
    """Genera nombres de buckets con fuzzing avanzado."""
    prefixes = [
        'dev', 'prod', 'staging', 'backup', 'data', 'files', 'public', 'logs', 'test', 'api',
        'app', 'config', 'archive', 'static', 'media', 'assets', 'qa', 'sandbox', 'temp',
        'www', 'cdn', 'upload', 'download', 'secure', 'internal', 'external', 'devops',
        'storage', 'bucket', 's3', 'private', 'shared', 'legacy', 'demo', 'beta'
    ]
    suffixes = [
        'backup', 'data', 'files', 'logs', 'public', 'archive', 'config', 's3', 'storage',
        'bucket', 'prod', 'dev', 'test', 'staging', 'private', 'assets', 'media', 'temp',
        'v1', 'v2', 'old', 'new', 'qa', 'sandbox', 'internal', 'external', 'secure'
    ]
    
    if wordlist_file:
        extra_words = load_wordlist(wordlist_file)
        prefixes.extend(extra_words[:100])  # Aumentar para más combinaciones
        suffixes.extend(extra_words[:100])
    
    subdomains = resolve_subdomains(target_domain)
    if subdomains_file and os.path.exists(subdomains_file):
        with open(subdomains_file, 'r', encoding='utf-8') as f:
            subdomains.extend([line.strip().replace('.', '-').lower() for line in f if line.strip()])
    subdomains = list(set(subdomains))
    
    buckets: Set[str] = set()
    for domain_clean in subdomains:
        high_priority = [
            f"{domain_clean}",
            f"s3-{domain_clean}",
            f"{domain_clean}-s3",
            f"{domain_clean}-public",
            f"{domain_clean}-private",
            f"{domain_clean}-data",
            f"{domain_clean}-backup",
            f"{domain_clean}-prod",
            f"{domain_clean}-dev",
            f"{domain_clean}-test"
        ]
        buckets.update(high_priority)
        for prefix in prefixes:
            buckets.add(f"{prefix}-{domain_clean}")
        for suffix in suffixes:
            buckets.add(f"{domain_clean}-{suffix}")
        for prefix, suffix in itertools.product(prefixes, suffixes):
            buckets.add(f"{prefix}-{domain_clean}-{suffix}")
        for base_name in high_priority:
            buckets.update(generate_fuzzed_names(base_name, max_fuzz=100))
    
    valid_buckets = [b for b in buckets if is_valid_s3_bucket_name(b)]
    if max_buckets:
        valid_buckets = sorted(valid_buckets, key=lambda x: any(kw in x for kw in ['prod', 'backup', 'data', 'public', 's3', 'dev', 'test']), reverse=True)[:max_buckets]
    
    logger.info(f"Generados {len(valid_buckets)} nombres de buckets para {target_domain}")
    return valid_buckets

def is_valid_s3_bucket_name(bucket: str) -> bool:
    """Valida si un nombre de bucket cumple con las reglas de AWS S3."""
    if not (3 <= len(bucket) <= 63):
        return False
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', bucket):
        return False
    if '..' in bucket or '--' in bucket or bucket.startswith('.') or bucket.endswith('.'):
        return False
    return True

def generate_buckets_file(target_domain: str, output_file: str = 'data/buckets.txt', max_buckets: int = None, wordlist_file: str = None, subdomains_file: str = None) -> bool:
    """Genera un archivo buckets.txt con nombres de buckets."""
    if not target_domain:
        logger.error("Se requiere un dominio objetivo para generar buckets")
        return False
    
    buckets = generate_bucket_names(target_domain, wordlist_file, subdomains_file, max_buckets)
    authorized_domains = settings.SETTINGS.get('authorized_domains', [])
    if authorized_domains:
        authorized_domains_clean = [domain.replace('.', '-').lower() for domain in authorized_domains]
        buckets = [b for b in buckets if any(domain in b for domain in authorized_domains_clean)]
        logger.info(f"Filtrados {len(buckets)} buckets autorizados")
    
    if not buckets:
        logger.error("No se generaron buckets válidos para escanear")
        return False
    
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            for bucket in buckets:
                f.write(f"{bucket}\n")
        logger.info(f"Archivo {output_file} generado con {len(buckets)} buckets")
        return True
    except Exception as e:
        logger.error(f"Error al generar {output_file}: {e}")
        return False