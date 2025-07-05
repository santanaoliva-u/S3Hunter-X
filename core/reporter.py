import sqlite3
import json
import gzip
import csv
import os
from config import settings
import logging
from typing import List

logger = logging.getLogger('S3Hunter-X')

def escape_markdown(text: str) -> str:
    """Escapa caracteres especiales para Markdown."""
    return text.replace('_', '\\_').replace('*', '\\*').replace('#', '\\#') if text else 'N/A'

def generate_report(formats: List[str] = ['md', 'json', 'csv'], output_prefix: str = 'results') -> None:
    """Genera reportes en los formatos especificados."""
    try:
        with sqlite3.connect(settings.SETTINGS['database'], check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute("SELECT bucket, filename, risk, content_risk, url, region FROM results WHERE risk = 'HIGH' OR content_risk = 'HIGH'")
            high_risk_results = c.fetchall()
            c.execute("SELECT bucket, status, region, timestamp FROM scanned_buckets")
            all_buckets = c.fetchall()
        
        if 'md' in formats:
            md_content = "# S3Hunter-X Report\n\n"
            md_content += "## Buckets Públicos de Alto Riesgo\n\n"
            if high_risk_results:
                for bucket, filename, risk, content_risk, url, region in high_risk_results:
                    md_content += f"- **Bucket**: {escape_markdown(bucket)}\n"
                    md_content += f"  - **Archivo**: {escape_markdown(filename)}\n"
                    md_content += f"  - **URL**: {escape_markdown(url)}\n"
                    md_content += f"  - **Región**: {escape_markdown(region)}\n"
                    md_content += f"  - **Riesgo**: {escape_markdown(risk)}\n"
                    md_content += f"  - **Riesgo de Contenido**: {escape_markdown(content_risk)}\n\n"
            else:
                md_content += "No se encontraron buckets públicos de alto riesgo.\n\n"
            
            md_content += "## Resumen de Buckets Escaneados\n\n"
            md_content += "| Bucket | Estado | Región | Timestamp |\n"
            md_content += "|--------|--------|--------|-----------|\n"
            for bucket, status, region, timestamp in all_buckets:
                md_content += f"| {escape_markdown(bucket)} | {escape_markdown(status)} | {escape_markdown(region)} | {escape_markdown(timestamp)} |\n"
            
            with open(f'{output_prefix}.md', 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"Reporte Markdown generado: {output_prefix}.md")
        
        if 'json' in formats:
            json_data = {
                'high_risk': [
                    {
                        'bucket': bucket,
                        'filename': filename or 'N/A',
                        'url': url or 'N/A',
                        'region': region or 'N/A',
                        'risk': risk or 'N/A',
                        'content_risk': content_risk or 'N/A'
                    } for bucket, filename, risk, content_risk, url, region in high_risk_results
                ],
                'all_buckets': [
                    {
                        'bucket': bucket,
                        'status': status or 'N/A',
                        'region': region or 'N/A',
                        'timestamp': timestamp or 'N/A'
                    } for bucket, status, region, timestamp in all_buckets
                ]
            }
            with open(f'{output_prefix}.json', 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            with gzip.open(f'{output_prefix}.json.gz', 'wt', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Reportes JSON generados: {output_prefix}.json, {output_prefix}.json.gz")
        
        if 'csv' in formats:
            with open(f'{output_prefix}.csv', 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Bucket', 'Filename', 'URL', 'Region', 'Risk', 'Content Risk'])
                for bucket, filename, risk, content_risk, url, region in high_risk_results:
                    writer.writerow([bucket, filename or 'N/A', url or 'N/A', region or 'N/A', risk or 'N/A', content_risk or 'N/A'])
            logger.info(f"Reporte CSV generado: {output_prefix}.csv")
    
    except Exception as e:
        logger.error(f"Error al generar reportes: {e}")
        raise