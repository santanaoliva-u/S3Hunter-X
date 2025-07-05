import re
import os
from typing import List, Dict
from config import settings
import logging

logger = logging.getLogger('S3Hunter-X')

class Analyzer:
    def __init__(self, patterns_file: str):
        """Inicializa el analizador con patrones de riesgo."""
        self.patterns = []
        try:
            with open(patterns_file, 'r', encoding='utf-8') as f:
                self.patterns = [line.strip() for line in f if line.strip()]
            logger.info(f"Cargados {len(self.patterns)} patrones desde {patterns_file}")
        except FileNotFoundError:
            logger.error(f"No se encontró el archivo de patrones: {patterns_file}")
            self.patterns = []
        except Exception as e:
            logger.error(f"Error al cargar patrones: {e}")
            self.patterns = []

    def analyze_files(self, bucket: str, files: List[Dict]) -> List[Dict]:
        """Analiza archivos de un bucket S3 y asigna niveles de riesgo."""
        results = []
        for file in files:
            filename = file.get('Key', '')
            if not filename:
                continue
            risk = 'LOW'
            if any(re.search(pattern, filename, re.IGNORECASE) for pattern in self.patterns):
                risk = 'HIGH'
            results.append({
                'bucket': bucket,
                'filename': filename,
                'risk': risk
            })
            logger.debug(f"Analizado {filename} en {bucket}: Riesgo {risk}")
        return results

    def analyze_content(self, file_path: str) -> str:
        """Analiza el contenido de un archivo descargado para detectar patrones sensibles."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for pattern in self.patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        logger.debug(f"Patrón sensible encontrado en {file_path}: {pattern}")
                        return 'HIGH'
            return 'LOW'
        except Exception as e:
            logger.error(f"Error al analizar contenido de {file_path}: {e}")
            return 'UNKNOWN'