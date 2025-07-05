import os
import sys
import asyncio
import sqlite3
import logging
import argparse
import re
import time
from datetime import datetime
from tabulate import tabulate
from tenacity import retry, stop_after_attempt, wait_exponential
import aiohttp
import signal
from typing import List
from config import settings
from core.utils import load_module, is_authorized_domain
from core.analyzer import Analyzer
from core.downloader import send_telegram_notification
from core.logger import setup_logger

def parse_args() -> argparse.Namespace:
    """Parsea los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(description='S3Hunter-X: Herramienta para buscar buckets S3 públicos')
    parser.add_argument('--target-domain', type=str, required=True, help='Dominio objetivo para generar nombres de buckets')
    parser.add_argument('--buckets-file', type=str, default='data/buckets.txt', help='Archivo con lista de buckets')
    parser.add_argument('--wordlist', type=str, default=None, help='Archivo de wordlist para fuzzing')
    parser.add_argument('--subdomains', type=str, default=None, help='Archivo con subdominios')
    parser.add_argument('--max-buckets', type=int, default=10000, help='Máximo número de buckets a generar')
    parser.add_argument('--batch-size', type=int, default=1000, help='Tamaño del lote para escaneo')
    parser.add_argument('--delay', type=float, default=1.0, help='Retraso entre lotes (segundos)')
    parser.add_argument('--max-workers', type=int, default=20, help='Número máximo de workers concurrentes')
    parser.add_argument('--max-file-size', type=int, default=50, help='Tamaño máximo de archivo a descargar (MB)')
    parser.add_argument('--output', type=str, default='results', help='Prefijo para archivos de salida')
    parser.add_argument('--report-formats', nargs='+', default=['md', 'json', 'csv'], help='Formatos de reporte')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO', help='Nivel de logging')
    parser.add_argument('--telegram-token', type=str, default=os.getenv('TELEGRAM_TOKEN'), help='Token de Telegram')
    parser.add_argument('--telegram-chat-id', type=str, default=os.getenv('TELEGRAM_CHAT_ID'), help='Chat ID de Telegram')
    parser.add_argument('--purge-db', action='store_true', help='Purgar la base de datos antes de iniciar')
    parser.add_argument('--verbose', action='store_true', help='Mostrar información detallada')
    
    args = parser.parse_args()
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$', args.target_domain):
        parser.error("El dominio objetivo no es válido")
    if args.max_buckets <= 0:
        parser.error("max-buckets debe ser mayor que 0")
    if args.batch_size <= 0:
        parser.error("batch-size debe ser mayor que 0")
    if args.max_workers <= 0:
        parser.error("max-workers debe ser mayor que 0")
    return args

def init_db(db_path: str) -> None:
    """Inicializa la base de datos con índices optimizados y verifica las columnas 'url' y 'region'."""
    try:
        with sqlite3.connect(db_path, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('''CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bucket TEXT NOT NULL,
                filename TEXT,
                risk TEXT,
                content_risk TEXT,
                url TEXT,
                source TEXT,
                region TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bucket, filename)
            )''')
            c.execute("PRAGMA table_info(results)")
            columns = [col[1] for col in c.fetchall()]
            if 'url' not in columns:
                c.execute("ALTER TABLE results ADD COLUMN url TEXT")
                logging.getLogger('S3Hunter-X').info("Columna 'url' añadida a la tabla 'results'")
            if 'region' not in columns:
                c.execute("ALTER TABLE results ADD COLUMN region TEXT")
                logging.getLogger('S3Hunter-X').info("Columna 'region' añadida a la tabla 'results'")
            c.execute('''CREATE TABLE IF NOT EXISTS scanned_buckets (
                bucket TEXT PRIMARY KEY,
                status TEXT,
                region TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_bucket ON results (bucket)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_risk ON results (risk)')
            conn.commit()
        logging.getLogger('S3Hunter-X').info("Base de datos inicializada con WAL y índices")
    except sqlite3.Error as e:
        logging.getLogger('S3Hunter-X').error(f"Error al inicializar base de datos: {e}")
        raise

async def cleanup(session: aiohttp.ClientSession = None, db_conn: sqlite3.Connection = None):
    """Cierra recursos abiertos (sesión HTTP y conexión a la base de datos)."""
    logger = logging.getLogger('S3Hunter-X')
    if session and not session.closed:
        await session.close()
        logger.info("Sesión HTTP cerrada")
    if db_conn:
        db_conn.close()
        logger.info("Conexión a la base de datos cerrada")

def handle_shutdown(loop, session, db_conn):
    """Maneja la señal de interrupción (SIGINT)."""
    logger = logging.getLogger('S3Hunter-X')
    logger.info("Interrupción detectada (Ctrl+C), cerrando recursos...")
    tasks = [task for task in asyncio.all_tasks(loop) if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    loop.run_until_complete(loop.create_task(cleanup(session, db_conn)))
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
    logger.info("Programa terminado limpiamente")
    sys.exit(0)

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=60))
async def main() -> None:
    """Punto de entrada de S3Hunter-X."""
    print("""
    AVISO LEGAL: S3Hunter-X está diseñado para uso ético en programas de Bug Bounty o auditorías autorizadas.
    El uso no autorizado para escanear o explotar buckets S3 sin permiso es ilegal y no está respaldado.
    """)
    
    args = parse_args()
    logger = setup_logger(log_level=args.log_level)
    
    telegram_enabled = False
    if args.telegram_token and args.telegram_chat_id:
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', args.telegram_token):
            logger.warning(f"Formato de telegram_token inválido: {args.telegram_token}. Notificaciones de Telegram deshabilitadas")
        elif not re.match(r'^-?\d+$', args.telegram_chat_id):
            logger.warning(f"Formato de telegram_chat_id inválido: {args.telegram_chat_id}. Notificaciones de Telegram deshabilitadas")
        else:
            telegram_enabled = True
            logger.info("Configuración de Telegram validada")
            # Enviar notificación de prueba
            logger.debug("Enviando notificación de prueba a Telegram")
            await send_telegram_notification(
                "🚀 S3Hunter-X iniciado para el dominio: " + args.target_domain,
                args.telegram_token,
                args.telegram_chat_id
            )
    else:
        logger.info("Notificaciones de Telegram no configuradas")
    
    settings.SETTINGS.update({
        'buckets_file': args.buckets_file,
        'max_workers': min(args.max_workers, 100),
        'max_file_size_mb': args.max_file_size,
        'telegram_token': args.telegram_token if telegram_enabled else '',
        'telegram_chat_id': args.telegram_chat_id if telegram_enabled else '',
        'request_timeout': 10,
        's3_regions': ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']
    })
    
    session = None
    db_conn = None
    try:
        if args.purge_db and os.path.exists(settings.SETTINGS['database']):
            os.remove(settings.SETTINGS['database'])
            logger.info("Base de datos purgada")
        
        init_db(settings.SETTINGS['database'])
        bucket_generator = load_module('core.bucket_generator')
        scanner = load_module('core.scanner')
        analyzer = Analyzer(settings.SETTINGS['patterns_file'])
        downloader = load_module('core.downloader')
        reporter = load_module('core.reporter')
        
        if not all([bucket_generator, scanner, analyzer, downloader, reporter]):
            logger.error("No se pudieron cargar todos los módulos necesarios")
            sys.exit(1)
        
        buckets_list: List[str] = []
        success = bucket_generator.generate_buckets_file(
            target_domain=args.target_domain,
            output_file=args.buckets_file,
            max_buckets=args.max_buckets,
            wordlist_file=args.wordlist,
            subdomains_file=args.subdomains
        )
        if not success:
            logger.error("No se pudo generar buckets.txt")
            sys.exit(1)
        
        with open(args.buckets_file, 'r', encoding='utf-8') as f:
            buckets_list = [line.strip() for line in f if line.strip()]
        if not buckets_list:
            logger.error(f"El archivo {args.buckets_file} está vacío")
            sys.exit(1)
        
        buckets_list = [b for b in buckets_list if is_authorized_domain(b, [args.target_domain] + settings.SETTINGS['authorized_domains'])]
        if not buckets_list:
            logger.error("No hay buckets autorizados para escanear")
            sys.exit(1)
        logger.info(f"Filtrados {len(buckets_list)} buckets autorizados")
        
        loop = asyncio.get_running_loop()
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=args.max_workers))
        db_conn = sqlite3.connect(settings.SETTINGS['database'], check_same_thread=False)
        signal.signal(signal.SIGINT, lambda s, f: handle_shutdown(loop, session, db_conn))
        
        try:
            for i in range(0, len(buckets_list), args.batch_size):
                batch = buckets_list[i:i + args.batch_size]
                logger.info(f"Escaneando lote {i+1} a {min(i+args.batch_size, len(buckets_list))} de {len(buckets_list)}")
                
                results = await scanner.scan_buckets_async(batch, args.max_workers, session)
                c = db_conn.cursor()
                public_buckets_found = 0
                for bucket, data in results:
                    if data and data['status'] == 'PUBLIC':
                        public_buckets_found += 1
                        c.execute(
                            "INSERT OR REPLACE INTO scanned_buckets (bucket, status, region, timestamp) VALUES (?, ?, ?, ?)",
                            (bucket, data['status'], data.get('region', 'unknown'), datetime.now())
                        )
                        if 'data' in data and data['data']:
                            files = data['data'].get('Contents', [])
                            if not isinstance(files, list):
                                files = [files]
                            analyzed_files = analyzer.analyze_files(bucket, files)
                            results_data = [
                                (file['bucket'], file['filename'], file['risk'], 'S3Hunter-X', 
                                 f"https://{bucket}.s3.{data.get('region', 'us-east-1')}.amazonaws.com/{file['filename']}", 
                                 data.get('region', 'unknown'))
                                for file in analyzed_files
                            ]
                            c.executemany(
                                "INSERT OR REPLACE INTO results (bucket, filename, risk, source, url, region) VALUES (?, ?, ?, ?, ?, ?)",
                                results_data
                            )
                            for file in analyzed_files:
                                if file['risk'] == 'HIGH' and telegram_enabled:
                                    logger.debug(f"Intentando descargar archivo {file['filename']} de bucket {bucket} para análisis")
                                    local_path, content_risk = await downloader.download_file(
                                        file['bucket'], file['filename'], analyzer, data.get('region', 'us-east-1')
                                    )
                                    if local_path:
                                        c.execute(
                                            "UPDATE results SET content_risk = ? WHERE bucket = ? AND filename = ?",
                                            (content_risk, file['bucket'], file['filename'])
                                        )
                                        logger.debug(f"Enviando notificación de Telegram para {bucket}/{file['filename']}")
                                        await send_telegram_notification(
                                            f"🚨 Bucket público de alto riesgo encontrado: https://{bucket}.s3.{data.get('region', 'us-east-1')}.amazonaws.com/{file['filename']} (Riesgo: {content_risk})",
                                            args.telegram_token,
                                            args.telegram_chat_id
                                        )
                        db_conn.commit()
                    logger.debug(f"Procesado bucket {bucket}: {data.get('status', 'UNKNOWN')}")
                logger.info(f"Lote {i//args.batch_size+1} completado. Buckets públicos encontrados: {public_buckets_found}")
                
                try:
                    reporter.generate_report(formats=args.report_formats, output_prefix=f"{args.output}_batch_{i//args.batch_size+1}")
                except Exception as e:
                    logger.error(f"Fallo al generar reporte para lote {i//args.batch_size+1}: {e}")
                
                if i + args.batch_size < len(buckets_list):
                    logger.info(f"Esperando {args.delay} segundos antes del siguiente lote...")
                    await asyncio.sleep(args.delay)
            
            try:
                reporter.generate_report(formats=args.report_formats, output_prefix=args.output)
            except Exception as e:
                logger.error(f"Fallo al generar reporte final: {e}")
            
            if args.verbose:
                c = db_conn.cursor()
                c.execute("SELECT bucket, status, region, timestamp FROM scanned_buckets")
                table = [[r[0], r[1], r[2], r[3]] for r in c.fetchall()]
                print("\nResumen de buckets escaneados:")
                print(tabulate(table, headers=["Bucket", "Estado", "Región", "Timestamp"], tablefmt="grid"))
            
            logger.info(f"¡Proceso completado! Revisa los reportes en {args.output}.*")
            if public_buckets_found == 0:
                logger.warning("No se encontraron buckets públicos. Considera usar un dominio diferente o aumentar el número de buckets generados.")
        
        except asyncio.CancelledError:
            logger.info("Tareas canceladas debido a interrupción")
            raise
        
    except Exception as e:
        logger.error(f"Error inesperado: {type(e).__name__} - {e}")
        raise
    finally:
        await cleanup(session, db_conn)

if __name__ == '__main__':
    asyncio.run(main())