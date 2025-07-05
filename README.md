
# S3Hunter-X

![S3Hunter-X Logo](src/img/portada.jpg) 

**S3Hunter-X** es una herramienta avanzada diseñada para buscar y analizar buckets S3 públicos de Amazon Web Services (AWS) de manera ética, enfocada en programas de bug bounty y auditorías de seguridad autorizadas. Escanea dominios objetivo, genera nombres de buckets relevantes, analiza archivos sensibles y genera reportes detallados para identificar posibles vulnerabilidades en configuraciones de buckets S3.

⚠️ **AVISO LEGAL**: S3Hunter-X debe usarse únicamente en dominios autorizados (por ejemplo, programas de bug bounty o auditorías con permiso explícito). El uso no autorizado para escanear o explotar buckets S3 es ilegal y no está respaldado.

## Características

- **Generación Inteligente de Buckets**: Crea nombres de buckets basados en el dominio objetivo, subdominios, prefijos/sufijos comunes y fuzzing avanzado.
- **Escaneo Multi-Región**: Verifica buckets en múltiples regiones de AWS (us-east-1, us-west-2, eu-west-1, etc.) usando HTTP puro.
- **Análisis de Archivos**: Detecta datos sensibles en nombres y contenidos de archivos (JSON, YAML, texto) usando patrones predefinidos.
- **Notificaciones de Telegram**: Envía alertas en tiempo real para hallazgos de alto riesgo.
- **Reportes Detallados**: Genera reportes en Markdown, JSON y CSV con URLs completas, regiones y niveles de riesgo.
- **Autónomo y Ligero**: No depende de herramientas externas como `awscli` o `s3scanner`.
- **Robusto y Ético**: Incluye validación de dominios autorizados y manejo exhaustivo de errores.

## Requisitos

- Python 3.8+
- Dependencias (ver `requirements.txt`):
  - `aiohttp==3.8.4`
  - `tenacity==8.2.2`
  - `xmltodict==0.13.0`
  - `tabulate==0.9.0`
  - `python-dotenv==1.0.0`
  - `pyyaml==6.0`
  - `dnspython==2.3.0`

## Instalación

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/santanaoliva-u/S3Hunter-X.git && cd S3Hunter-X
   ```

2. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar variables de entorno** (opcional, para notificaciones de Telegram):
   Crea un archivo `.env` en el directorio raíz:
   ```env
   TELEGRAM_TOKEN=bot123456:ABC-DEF1234ghIkl-zyx57w2v1u123ew11
   TELEGRAM_CHAT_ID=123456789
   ```

4. **Crear el archivo de patrones**:
   Asegúrate de que `data/grep_words.txt` exista con patrones para detectar datos sensibles (ejemplo):
   ```
   api_key
   secret
   password
   credential
   ```

## Uso

Ejecuta S3Hunter-X con el dominio objetivo y las opciones deseadas:

```bash
python main.py --target-domain example.com --wordlist data/wordlist.txt --subdomains data/subdomains.txt --max-buckets 10000 --batch-size 1000 --max-workers 20 --verbose
```

### Opciones

| Argumento            | Descripción                                      | Predeterminado         |
|---------------------|--------------------------------------------------|------------------------|
| `--target-domain`   | Dominio objetivo (obligatorio)                   | -                      |
| `--buckets-file`    | Archivo de salida para nombres de buckets        | `data/buckets.txt`     |
| `--wordlist`        | Archivo de wordlist para fuzzing                | None                   |
| `--subdomains`      | Archivo con subdominios                         | None                   |
| `--max-buckets`     | Máximo número de buckets a generar              | 10000                  |
| `--batch-size`      | Tamaño del lote para escaneo                    | 1000                   |
| `--delay`           | Retraso entre lotes (segundos)                  | 1.0                    |
| `--max-workers`     | Número máximo de workers concurrentes           | 20                     |
| `--max-file-size`   | Tamaño máximo de archivo a descargar (MB)       | 50                     |
| `--output`          | Prefijo para archivos de salida                 | `results`              |
| `--report-formats`  | Formatos de reporte (md, json, csv)             | `md json csv`          |
| `--log-level`       | Nivel de logging (DEBUG, INFO, WARNING, ERROR)  | `INFO`                 |
| `--telegram-token`  | Token de Telegram para notificaciones           | `TELEGRAM_TOKEN` (env) |
| `--telegram-chat-id`| Chat ID de Telegram                            | `TELEGRAM_CHAT_ID` (env) |
| `--purge-db`        | Purgar la base de datos antes de iniciar        | False                  |
| `--verbose`         | Mostrar información detallada                   | False                  |

## Salida

- **Reportes**: Generados en `results.md`, `results.json`, `results.csv`, `results.json.gz`.
- **Archivos Descargados**: Guardados en `data/downloads/`.
- **Logs**: Registrados en `logs/s3hunterx.log`.

## Ejemplo

```bash
python main.py --target-domain uber.com --max-buckets 5000 --batch-size 500 --verbose
```

Esto genera nombres de buckets, escanea buckets públicos, analiza archivos sensibles y produce reportes detallados.

## Estructura del Proyecto

```
S3Hunter-X/
├── main.py
├── core/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── bucket PRODUCTION.py
│   ├── downloader.py
│   ├── reporter.py
│   ├── scanner.py
│   ├── utils.py
├── config/
│   ├── settings.py
├── data/
│   ├── buckets.txt
│   ├── grep_words.txt
│   ├── results.db
│   ├── downloads/
├── logs/
│   ├── s3hunterx.log
├── requirements.txt
├── README.md
```

## Advertencias Éticas

- **Uso Autorizado**: Solo utiliza S3Hunter-X en dominios incluidos en programas de bug bounty o con permiso explícito del propietario.
- **Cumplimiento Legal**: Escanear buckets S3 sin autorización es ilegal y puede tener consecuencias legales.
- **Configuración Segura**: Asegúrate de configurar `authorized_domains` en `config/settings.py` para limitar los escaneos a dominios permitidos.

## Contribuir

¡Contribuciones son bienvenidas! Por favor, sigue estos pasos:

1. Haz un fork del repositorio.
2. Crea una rama para tu cambio (`git checkout -b feature/nueva-funcionalidad`).
3. Realiza tus cambios y haz commit (`git commit -m "Agrega nueva funcionalidad"`).
4. Envía un pull request.

## Licencia

[MIT License](LICENSE)

## Contacto

Para preguntas o sugerencias, abre un issue en este repositorio o contacta a [santanaoliva-u](https://github.com/santanaoliva-u).


---



---

**S3Hunter-X**: ¡Caza buckets públicos de forma ética y eficiente!
```
# Prologo :

> Todo el conocimiento que aquí se expresa no proviene de mí, sino de Dios.  
> No he hecho nada por mi propia cuenta: lo bueno es Su obra, y lo malo es mi error.  
>  
>  
> Este proyecto está dedicado a Él. A Dios sea toda la gloria.