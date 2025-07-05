import aiohttp
import asyncio
import xmltodict
from typing import List, Tuple, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from config import settings

logger = logging.getLogger('S3Hunter-X')

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=5, max=120))
async def check_bucket(session: aiohttp.ClientSession, bucket: str, region: str) -> Dict:
    """Verifica la accesibilidad de un bucket S3 en una región específica."""
    url = f"https://{bucket}.s3.{region}.amazonaws.com"
    try:
        async with session.get(url, timeout=settings.SETTINGS['request_timeout']) as response:
            if response.status == 200:
                content = await response.text()
                return {'status': 'PUBLIC', 'data': xmltodict.parse(content) if 'ListBucketResult' in content else None, 'region': region}
            elif response.status == 403:
                return {'status': 'PRIVATE', 'region': region}
            elif response.status == 404:
                return {'status': 'NOT_FOUND', 'region': region}
            elif response.status == 429:
                logger.warning(f"Rate limit alcanzado para {url}, reintentando...")
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=429,
                    message="Rate limit"
                )
            else:
                logger.debug(f"Estado inesperado para {url}: {response.status}")
                return {'status': 'UNKNOWN', 'region': region}
    except Exception as e:
        logger.debug(f"Error al verificar {url}: {e}")
        return {'status': 'ERROR', 'error': str(e), 'region': region}

async def scan_buckets_async(buckets: List[str], max_workers: int, session: aiohttp.ClientSession, grep_list: List[str] = None) -> List[Tuple[str, Dict]]:
    """Escanea una lista de buckets S3 de forma asíncrona."""
    results = []
    semaphore = asyncio.Semaphore(max_workers)
    cache = {}  # Caché en memoria para evitar reescaneos
    
    async def scan_with_semaphore(bucket: str) -> Tuple[str, Dict]:
        async with semaphore:
            if bucket in cache:
                logger.debug(f"Usando caché para {bucket}")
                return bucket, cache[bucket]
            
            result = {'status': 'UNKNOWN'}
            for region in settings.SETTINGS['s3_regions']:
                bucket_result = await check_bucket(session, bucket, region)
                if bucket_result['status'] == 'PUBLIC':
                    result = bucket_result
                    break
                elif bucket_result['status'] in ('PRIVATE', 'NOT_FOUND'):
                    result = bucket_result
                else:
                    result = bucket_result
            
            if result.get('data') and grep_list:
                contents = result['data'].get('ListBucketResult', {}).get('Contents', [])
                if not isinstance(contents, list):
                    contents = [contents]
                filtered_contents = []
                for item in contents:
                    key = item.get('Key', '')
                    if any(re.search(pattern, key, re.IGNORECASE) for pattern in grep_list):
                        filtered_contents.append(item)
                result['data']['Contents'] = filtered_contents
            
            cache[bucket] = result
            return bucket, result
    
    tasks = [scan_with_semaphore(bucket) for bucket in buckets]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for bucket, result in results:
        if isinstance(result, Exception):
            logger.error(f"Error al escanear {bucket}: {result}")
            results.append((bucket, {'status': 'ERROR', 'error': str(result)}))
    
    return [r for r in results if not isinstance(r[1], Exception)]