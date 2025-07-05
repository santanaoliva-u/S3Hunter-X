import os
import sqlite3
import json
import csv
from datetime import datetime
from typing import List
import logging
from config import settings

logger = logging.getLogger('S3Hunter-X')

def generate_report(formats: List[str], output_prefix: str) -> None:
    """Genera reportes en los formatos especificados."""
    try:
        with sqlite3.connect(settings.SETTINGS['database'], check_same_thread=False) as conn:
            c = conn.cursor()
            # Verificar si las columnas existen
            c.execute("PRAGMA table_info(results)")
            columns = [col[1] for col in c.fetchall()]
            select_columns = ['bucket', 'filename', 'risk', 'content_risk']
            if 'url' in columns:
                select_columns.append('url')
            if 'region' in columns:
                select_columns.append('region')
            else:
                select_columns.append("'unknown' AS region")
            select_columns.append('timestamp')
            query = f"SELECT {', '.join(select_columns)} FROM results WHERE risk IS NOT NULL"
            
            c.execute(query)
            results = c.fetchall()
            if not results:
                logger.info(f"No hay resultados para generar reportes en {output_prefix}")
                return
            
            os.makedirs(os.path.dirname(output_prefix), exist_ok=True)
            
            if 'md' in formats:
                md_content = "# S3Hunter-X Report\n\n"
                md_content += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                md_content += "| Bucket | Filename | Risk | Content Risk | {'URL' if 'url' in columns else ''} | {'Region' if 'region' in columns else 'Region'} | Timestamp |\n"
                md_content += "|--------|----------|------|--------------|{'---' if 'url' in columns else ''}|{'---' if 'region' in columns else '---'}|-----------|\n"
                for row in results:
                    row = list(row)
                    if 'url' not in columns:
                        row.insert(4, '')
                    if 'region' not in columns:
                        row[5] = 'unknown'
                    md_content += f"| {row[0]} | {row[1] or ''} | {row[2] or ''} | {row[3] or ''} | {row[4] or ''} | {row[5] or 'unknown'} | {row[6]} |\n"
                with open(f"{output_prefix}.md", 'w', encoding='utf-8') as f:
                    f.write(md_content)
                logger.info(f"Reporte Markdown generado: {output_prefix}.md")
            
            if 'json' in formats:
                json_data = []
                for row in results:
                    row_dict = {
                        'bucket': row[0],
                        'filename': row[1],
                        'risk': row[2],
                        'content_risk': row[3],
                        'url': row[4] if 'url' in columns else '',
                        'region': row[5] if 'region' in columns else 'unknown',
                        'timestamp': row[6]
                    }
                    json_data.append(row_dict)
                with open(f"{output_prefix}.json", 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Reporte JSON generado: {output_prefix}.json")
            
            if 'csv' in formats:
                with open(f"{output_prefix}.csv", 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    headers = ['Bucket', 'Filename', 'Risk', 'Content Risk', 'URL' if 'url' in columns else '', 'Region', 'Timestamp']
                    if not 'url' in columns:
                        headers[4] = ''
                    writer.writerow([h for h in headers if h])
                    for row in results:
                        row = list(row)
                        if 'url' not in columns:
                            row.insert(4, '')
                        if 'region' not in columns:
                            row[5] = 'unknown'
                        writer.writerow(row)
                logger.info(f"Reporte CSV generado: {output_prefix}.csv")
    
    except sqlite3.Error as e:
        logger.error(f"Error al generar reportes: {e}")
        raise