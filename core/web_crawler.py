import aiohttp
import asyncio
import re
from urllib.parse import urlparse
from typing import List, Optional
import logging

logger = logging.getLogger('S3Hunter-X')

async def gather_cloud_links(html: str, cloud_domains: Optional[List[str]] = None) -> List[str]:
    """
    Extrae URLs relacionadas con servicios en la nube desde contenido HTML.
    
    Args:
        html (str): Contenido HTML a analizar.
        cloud_domains (List[str], optional): Dominios de proveedores de nube.
    
    Returns:
        List[str]: Lista de URLs válidas relacionadas con la nube.
    """
    if not cloud_domains:
        cloud_domains = [
            r"amazonaws\.com",
            r"digitaloceanspaces\.com",
            r"windows\.net",
            r"storage\.googleapis\.com",
            r"aliyuncs\.com"
        ]
    
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, html)
    cloud_urls = [url for url in urls if any(re.search(domain, url, re.IGNORECASE) for domain in cloud_domains)]
    
    valid_urls = []
    async with aiohttp.ClientSession() as session:
        for url in set(cloud_urls):
            try:
                async with session.head(url, timeout=3) as response:
                    if response.status < 400:
                        valid_urls.append(url)
                        logger.info(f"Encontrada URL de nube válida: {url}")
            except Exception as e:
                logger.debug(f"URL inválida {url}: {e}")
    
    return valid_urls

async def spider_cloud_resources(start_url: str, depth: int = 5, workers: int = 2, cloud_domains: Optional[List[str]] = None) -> List[str]:
    """
    Rastrea un sitio web para descubrir URLs relacionadas con servicios en la nube.
    
    Args:
        start_url (str): URL inicial para el rastreo.
        depth (int): Profundidad máxima de rastreo.
        workers (int): Número de workers concurrentes.
        cloud_domains (List[str], optional): Dominios de proveedores de nube.
    
    Returns:
        List[str]: Lista de URLs relacionadas con la nube.
    """
    crawled_urls = set()
    cloud_urls = set()
    to_crawl = [start_url]
    target_domain = urlparse(start_url).netloc
    
    async with aiohttp.ClientSession() as session:
        while to_crawl:
            tasks = []
            for url in to_crawl[:workers]:
                if url in crawled_urls or urlparse(url).netloc != target_domain or url.count("/") > depth + 2:
                    continue
                tasks.append(crawl_page(session, url, cloud_domains))
                crawled_urls.add(url)
            
            to_crawl = to_crawl[workers:]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for new_urls in results:
                if isinstance(new_urls, list):
                    cloud_urls.update([url for url in new_urls if urlparse(url).netloc in cloud_domains])
                    to_crawl.extend([url for url in new_urls if url not in crawled_urls and urlparse(url).netloc == target_domain])
            
            logger.info(f"Rastreadas {len(crawled_urls)} URLs, encontradas {len(cloud_urls)} URLs de nube, {len(to_crawl)} URLs por rastrear")
    
    return list(cloud_urls)

async def crawl_page(session: aiohttp.ClientSession, url: str, cloud_domains: Optional[List[str]]) -> List[str]:
    """
    Rastrea una página individual y extrae URLs relacionadas con la nube.
    
    Args:
        session (aiohttp.ClientSession): Sesión HTTP.
        url (str): URL a rastrear.
        cloud_domains (List[str], optional): Dominios de proveedores de nube.
    
    Returns:
        List[str]: Lista de URLs encontradas.
    """
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                html = await response.text()
                return await gather_cloud_links(html, cloud_domains)
            return []
    except Exception as e:
        logger.error(f"Error al rastrear {url}: {e}")
        return []