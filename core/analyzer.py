import os
import re
import logging
import json
import yaml
import csv
from typing import List, Dict, Optional

logger = logging.getLogger('S3Hunter-X')

class Analyzer:
    def __init__(self, patterns_file: str):
        """Inicializa el analizador con una lista de patrones."""
        self.patterns = self.load_patterns(patterns_file)
    
    def load_patterns(self, patterns_file: str) -> List[re.Pattern]:
        """Carga patrones desde un archivo."""
        patterns = []
        try:
            with open(patterns_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(re.compile(line, re.IGNORECASE))
            logger.info(f"Cargados {len(patterns)} patrones desde {patterns_file}")
            return patterns
        except FileNotFoundError:
            logger.error(f"No se encontró el archivo de patrones: {patterns_file}")
            return []
        except Exception as e:
            logger.error(f"Error al cargar patrones: {e}")
            return []
    
    def analyze_files(self, bucket: str, files: List[Dict]) -> List[Dict]:
        """Analiza archivos en un bucket y asigna nivel de riesgo."""
        analyzed_files = []
        for file in files:
            filename = file.get('Key', '')
            if not filename:
                continue
            risk = 'LOW'
            if any(pattern.search(filename.lower()) for pattern in self.patterns):
                risk = 'HIGH'
            analyzed_files.append({
                'bucket': bucket,
                'filename': filename,
                'risk': risk
            })
        return analyzed_files
    
    def analyze_content(self, file_path: str) -> str:
        """Analiza el contenido de un archivo descargado."""
        try:
            if os.path.getsize(file_path) == 0:
                return 'EMPTY'
            if file_path.endswith('.csv'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        content_str = ' '.join(row)
                        for pattern in self.patterns:
                            if pattern.search(content_str):
                                return 'HIGH'
                return 'LOW'
            if file_path.endswith('.env'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if '=' in line and any(pattern.search(line) for pattern in self.patterns):
                            return 'HIGH'
                return 'LOW'
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024 * 1024)  # Leer máximo 1MB
                for pattern in self.patterns:
                    if pattern.search(content):
                        return 'HIGH'
                try:
                    parsed = json.loads(content)
                    content_str = json.dumps(parsed, ensure_ascii=False)
                    for pattern in self.patterns:
                        if pattern.search(content_str):
                            return 'HIGH'
                except json.JSONDecodeError:
                    try:
                        parsed = yaml.safe_load(content)
                        content_str = yaml.dump(parsed, allow_unicode=True)
                        for pattern in self.patterns:
                            if pattern.search(content_str):
                                return 'HIGH'
                    except yaml.YAMLError:
                        pass
                return 'LOW'
        except UnicodeDecodeError:
            logger.warning(f"Archivo binario detectado: {file_path}")
            return 'UNKNOWN'
        except Exception as e:
            logger.error(f"Error al analizar contenido de {file_path}: {e}")
            return 'UNKNOWN'