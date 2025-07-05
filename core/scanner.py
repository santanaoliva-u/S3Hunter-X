import aiohttp
import xmltodict
import asyncio
import logging
import random
from typing import List, Tuple, Dict, Optional
from config import settings
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger('S3Hunter-X')

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=5, max=120))
async def check_bucket_async(bucket: str, session: aiohttp.ClientSession, region: str = 'us-east-1') -> Tuple[str, Optional[Dict]]:
    """Verifica si un bucket S3 es público, privado o no existe."""
    url = f"https://{bucket}.s3.{region}.amazonaws.com"
    headers = {'User-Agent': random.choice(settings.SETTINGS['user_agents'])}
    try:
        async with session.get(url, headers=headers, timeout=settings.SETTINGS['request_timeout']) as response:
            if response.status == 200:
                content = await response.text()
                try:
                    xml_data = xmltodict.parse(content)
                    region = response.headers.get('x-amz-bucket-region', region)
                    logger.info(f"Bucket {bucket} es público en región {region}: HTTP 200")
                    return bucket, {'status': 'PUBLIC', 'data': xml_data, 'region': region}
                except xmltodict.expat.ExpatError:
                    logger.info(f"Bucket {bucket} es público pero no contiene lista de archivos en región {region}")
                    return bucket, {'status': 'PUBLIC', 'data': None, 'region': region}
            elif response.status == 403:
                logger.info(f"Bucket {bucket} no es público: HTTP 403 (privado) en región {region}")
                return bucket, {'status': 'PRIVATE', 'data': None, 'region': region}
            elif response.status == 404:
                logger.debug(f"Bucket {bucket} no existe: HTTP 404 en región {region}")
                return bucket, {'status': 'NOT_FOUND', 'data': None, 'region': region}
            elif response.status == 429:
                logger.warning(f"Límite de tasa alcanzado para {bucket}, esperando...")
                raise aiohttp.ClientError("Rate limit")
            else:
                logger.warning(f"Bucket {bucket} retornó estado inesperado: HTTP {response.status} en región {region}")
                return bucket, {'status': f'UNKNOWN_{response.status}', 'data': None, 'region': region}
    except aiohttp.ClientSSLError as e:
        logger.error(f"Error SSL al verificar {bucket} en región {region}: {e}")
        return bucket, None
    except aiohttp.ClientError as e:
        logger.error(f"Error al verificar {bucket} en región {region}: {e}")
        return bucket, None

async def scan_buckets_async(buckets: List[str], max_workers: int, session: aiohttp.ClientSession) -> List[Tuple[str, Optional[Dict]]]:
    """Escanea una lista de buckets de manera asíncrona en múltiples regiones."""
    semaphore = asyncio.Semaphore(max_workers)
    async def check_bucket_with_semaphore(bucket: str, region: str) -> Tuple[str, Optional[Dict]]:
        async with semaphore:
            return await check_bucket_async(bucket, session, region)
    
    tasks = [check_bucket_with_semaphore(bucket, region) for bucket in buckets for region in settings.SETTINGS['s3_regions']]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    results_dict = {}
    for result in results:
        if isinstance(result, tuple) and result[1] is not None:
            bucket, data = result
            current_region = data.get('region', 'unknown')
            if bucket not in results_dict or (data['status'] == 'PUBLIC' and results_dict[bucket]['region'] != current_region):
                results_dict[bucket] = data
    return list(results_dict.items())