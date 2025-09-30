# Proceso de Implementación - TestDapper

## Resumen del Proyecto
Este documento detalla el proceso completo de refactorización de una función Lambda a un pipeline de Airflow con las etapas: **Extracción → Validación → Escritura**.

---

## Pasos de Implementación

### Paso 1 — chore: init repo estructura airflow y carpetas base
**Objetivo:** Establecer la estructura base del proyecto Airflow.

**Acciones realizadas:**
- Se crearon las carpetas base del proyecto:
  - `dags/`: Almacena el DAG de Airflow
  - `src/`: Contiene módulos `extraccion.py`, `validacion.py`, `escritura.py`, `db.py`
  - `config/`: Reglas de validación (`validation_rules.yaml`) y DDL opcional (`schema.sql`)
  - `logs/` y `plugins/`: Usados por Airflow
- Se verificó que en `docker-compose.yml`:
  - Se montan los volúmenes `./dags`, `./src`, `./config`, `./logs`, `./plugins`
  - `PYTHONPATH` incluye `/opt/airflow/src` para importar módulos desde el DAG
- **Nota:** No se movió ni modificó lógica aún; solo se estableció la estructura para el refactor posterior

### Paso 2 — chore: agregar .gitignore y plantilla de .env.example
**Objetivo:** Configurar archivos de control de versiones y variables de entorno.

**Acciones realizadas:**
- Se creó `.gitignore` que incluye:
  - `__pycache__/`, `.venv/`, `.env`, `logs/`
  - `*.pyc`, `.ipynb_checkpoints/`, `.DS_Store`
  - `plugins/__pycache__/`, `dags/__pycache__/`
- Se creó `.env.example` con placeholders no sensibles:
  - `AIRFLOW_UID=50000`, `AIRFLOW_GID=50000`
- **Nota operativa:** El compose ya define `AIRFLOW__CORE__SQL_ALCHEMY_CONN`, se evitan secretos en VCS

### Paso 3 — refactor: extraer lógica de scraping a src/extraccion.py
**Objetivo:** Modularizar la lógica de scraping sin alterar las reglas existentes.

**Acciones realizadas:**
- Se movieron a `src/extraccion.py` las siguientes funciones de `lambda.py`:
  - `clean_quotes`, `get_rtype_id`, `is_valid_created_at`, `normalize_datetime`
  - Extracción granular por fila: `extract_title_and_link`, `extract_summary`, `extract_creation_date`
  - Paginación y scraping: `scrape_page(page_num, verbose=False)`
- Se añadió `run_extraction(num_pages: int)` que:
  - Itera páginas 0..N-1
  - Acumula resultados y devuelve `pandas.DataFrame` con columnas:
    - `created_at`, `update_at`, `is_active`, `title`, `gtype`, `entity`, `external_link`, `rtype_id`, `summary`, `classification_id`
- **Requisitos clave:** No se alteraron heurísticas ni reglas de omisión (longitud, enlace, fechas, etc.)

### Paso 4 — refactor: mover DatabaseManager e inserción a src/escritura.py
**Objetivo:** Modularizar la lógica de base de datos sin usar secretos de AWS.

**Acciones realizadas:**
- Se trasladaron `DatabaseManager` y `insert_new_records` desde `lambda.py` a `src/escritura.py`
- Se mantuvo la idempotencia con `unique_key = title|created_at|external_link`
- Se conservó la inserción en `regulations` y luego en `regulations_component` (con `components_id = 7`)
- Se expuso `run_write(df)` que:
  - Conecta a la base de datos
  - Normaliza tipos y convierte `NaN` → `NULL`
  - Ejecuta inserción en bloque y retorna métricas (insertados y mensaje)

### Paso 5 — refactor: reemplazar Secrets Manager por conexión vía env
**Objetivo:** Eliminar dependencias de AWS y usar variables de entorno de Airflow.

**Acciones realizadas:**
- Se eliminaron `boto3` y `get_secret()` del flujo
- Se implementó una utilidad para leer/parsing de `AIRFLOW__CORE__SQL_ALCHEMY_CONN` que extrae:
  - `dbname`, `user`, `password`, `host`, `port` compatibles con `psycopg2`
- Se permitió fallback a variables `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` si no existe la variable principal

### Paso 6 — feat: crear src/db.py con parseo de URI y creación de tablas
**Objetivo:** Crear utilidades de base de datos y DDL para las tablas.

**Acciones realizadas:**
- Se crearon las siguientes funciones:
  - `parse_sqlalchemy_uri(uri: str) -> Dict[str, Any]`
  - `create_tables_if_not_exists(conn)` que ejecuta DDL para las tablas destino
- Se definió DDL para las tablas (usado en código o `config/schema.sql`):
  - **Tabla `regulations`:**
       - `id SERIAL PRIMARY KEY`
       - `created_at TIMESTAMP NULL`, `update_at TIMESTAMP NULL`, `is_active BOOLEAN`
       - `title VARCHAR(255)`, `gtype VARCHAR(50)`, `entity VARCHAR(255)`
       - `external_link TEXT`, `rtype_id INTEGER`, `summary TEXT`, `classification_id INTEGER`
  - **Tabla `regulations_component`:**
       - `id SERIAL PRIMARY KEY`, `regulations_id INTEGER REFERENCES regulations(id)`, `components_id INTEGER`
- **Nota:** No se agregaron restricciones `UNIQUE` que alteren comportamiento; la idempotencia se respeta en la aplicación

### Paso 7 — feat: agregar config/validation_rules.yaml con tipos/regex/obligatoriedad
**Objetivo:** Crear reglas de validación configurables por archivo YAML.

**Acciones realizadas:**
- Se creó estructura por campo con `type`, `required`, `regex` (opcional), `coerce` (opcional):


created_at:
  type: date


- **Regla de negocio:** Si un campo no cumple, ese campo → `NULL`; si el campo es `required`, se descarta la fila

### Paso 8 — feat: implementar validador en src/validacion.py
**Objetivo:** Crear sistema de validación con nullificación de campos y descarte de filas obligatorias.

**Acciones realizadas:**
- Se implementó `run_validation(df, rules)` que:
  - Valida por columna según `type` (string/date/boolean/integer/url), aplica `regex` si existe
  - Campos inválidos → `None`
  - Filas con algún `required` inválido → se descartan
- Se definieron métricas de salida:
  - `total_input_rows`, `total_valid_rows`, `total_dropped_rows`
  - `invalid_by_field`: conteo por campo invalidado
- Se configuró para retornar `(df_validado, metrics)` para logging en DAG

### Paso 9 — feat: DAG Airflow ani_normas con tareas secuenciales
**Objetivo:** Crear el DAG principal de Airflow con las tres etapas del pipeline.

**Acciones realizadas:**
- Se creó archivo `dags/ani_normas_dag.py` con tres `PythonOperator` en secuencia:
  - `extract_task`: Ejecuta `run_extraction(num_pages)`; publica resultado (usando XCom con DF→JSON o parquet temporal en `/opt/airflow/logs/tmp/`)
  - `validate_task`: Carga reglas de `config/validation_rules.yaml`, ejecuta `run_validation`, publica `df_validado` y métricas
  - `write_task`: Ejecuta `run_write(df_validado)`
- Se configuró el DAG inicial:
  - `schedule_interval=None` (ejecución manual) y `catchup=False`
  - `start_date` razonable (ej. `days_ago(1)`)
- Se definieron variables/params:
  - `num_pages_to_scrape` como Param o Variable de Airflow con default (ej. 3 o 9)
- **Nota:** No se implementó pre-chequeo de "contenido nuevo" en el DAG; se ejecuta siempre la extracción y se confía en la idempotencia durante la escritura

### Paso 10 — feat: logs métricas por etapa
**Objetivo:** Implementar logging detallado de métricas para cada etapa del pipeline.

**Acciones realizadas:**
- `extract_task`: Se configuró logging de páginas procesadas y `len(df_extraido)`
- `validate_task`: Se configuró logging de `metrics` (por campo y total de filas descartadas) y `len(df_validado)`
- `write_task`: Se configuró logging de filas insertadas en `regulations` y `regulations_component`, y mensaje de resumen

### Paso 11 — docs: agregar README con pasos para levantar entorno
**Objetivo:** Crear documentación básica para uso del sistema.

**Acciones realizadas:**
- Se agregó índice breve: requisitos, levantar entorno, credenciales, ejecución del DAG, troubleshooting
- Se documentaron comandos principales (vía Makefile): `make start`, abrir UI en `http://localhost:8080` (admin/admin)
- Se mencionó dónde editar `config/validation_rules.yaml` y cómo cambiar `num_pages_to_scrape`
- Se indicó que el destino de escritura es la BD Postgres del compose

### Paso 12 — chore: agregar config/schema.sql
**Objetivo:** Crear archivo DDL de referencia para las tablas de la base de datos.

**Acciones realizadas:**
- Se incluyó DDL equivalente al creado por `create_tables_if_not_exists` para referencia:

### Paso 13 — chore: limpiar dependencias no usadas
**Objetivo:** Eliminar dependencias de AWS y asegurar requirements en Dockerfile.

**Acciones realizadas:**
- Se eliminaron `boto3` y `botocore` del código y de `requirements.txt` si existían
- Se verificó `requirements.txt`: `requests`, `beautifulsoup4`, `pandas`, `numpy==1.24.3`, `psycopg2-binary==2.9.10`
- Se confirmó que `Dockerfile` instala `requirements.txt` como usuario `airflow`

### Paso 14 — chore: pruebas manuales locales documentadas
**Objetivo:** Documentar pruebas manuales y checklist de criterios de evaluación.

**Acciones realizadas:**
- Se documentaron pruebas sugeridas:
  - Correr `make start`, crear usuario admin (si no existe) y validar UI
  - Ejecutar el DAG manualmente con `num_pages_to_scrape` bajo (ej. 2-3) y revisar logs
  - Ejecutar nuevamente para verificar idempotencia (sin nuevos insertados)
  - Modificar temporalmente una regla de validación para forzar descartes y confirmar métricas
- Se creó checklist de criterios:
  - **Correctitud:** Scraping sin cambios; validación respeta reglas; DAG escribe en DB de Airflow
  - **Diseño:** Etapas separadas; reglas en archivo; conexión por env
  - **Operabilidad:** Repo entendible; README suficiente
  - **Calidad:** Manejo simple de errores; logs útiles
  - **Idempotencia:** No duplica registros

### Paso 15 — chore: limpieza del repositorio
**Objetivo:** Limpiar archivos legacy y dependencias no utilizadas.

**Acciones realizadas:**
- Se movió `lambda.py` a la carpeta `legacy/`
- Se eliminaron importaciones/paquetes no usados (ej. `boto3`, `botocore`) de código y `requirements.txt`
- Se revisó `README.md` para reflejar el flujo final con Airflow

### Paso 16 — fix: cambio de nombre de configs a config
**Objetivo:** Estandarizar nombres de carpetas de configuración.

**Acciones realizadas:**
- Se cambió el nombre de la carpeta `configs/` a `config/`

### Paso 17 — fix: variables de entorno centralizadas
**Objetivo:** Centralizar configuración de variables de entorno.

**Acciones realizadas:**
- Se centralizaron las variables de entorno en archivo `.env`

### Paso 18 — fix: Makefile y docker-compose configurado
**Objetivo:** Configurar Makefile y docker-compose para seguir un flujo coherente.

**Acciones realizadas:**
- Se configuró Makefile y docker-compose para seguir un flujo coherente

### Paso 19 — fix: error de dependencia y CLI
**Objetivo:** Resolver problemas de instalación de dependencias en WSL.

**Problema identificado:** Error `make: pip: Permission denied` al intentar instalar dependencias directamente en WSL.

**Solución implementada:**
- Se modificó `Makefile` para instalar Docker y Docker Compose en lugar de dependencias Python directas
- Se agregó target `install-deps` que instala `docker.io` y `docker-compose`
- Se configuró inicio automático del daemon Docker con `sudo dockerd > /dev/null 2>&1 &`
- Se agregó `sleep 10` para permitir que el daemon inicie completamente

**Comandos agregados:**
```makefile
install-deps:
	sudo apt-get update
	sudo apt-get install -y docker.io
	sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
	sudo chmod +x /usr/local/bin/docker-compose
	sudo usermod -aG docker $USER
```

### Paso 20 — fix: pythonpath env error
**Objetivo:** Resolver error de módulo no encontrado en el DAG de Airflow.

**Problema identificado:** Error `ModuleNotFoundError: No module named 'src'` en el DAG de Airflow.

**Solución implementada:**
- Se agregó `PYTHONPATH: "/opt/airflow/src"` en `docker-compose.yml` para que Python encuentre el módulo `src`
- Se creó archivo `src/__init__.py` para hacer que `src` sea un paquete Python válido
- Se modificó el target `start` en `Makefile` para incluir `install-deps` como primer paso
- Se agregó manejo de variables de entorno desde `.env` en el proceso de creación de usuario de Airflow

**Archivos modificados:**
- `docker-compose.yml`: Agregado PYTHONPATH en environment
- `src/__init__.py`: Creado archivo vacío para paquete Python
- `Makefile`: Mejorado flujo de inicialización

### Paso 21 — feat: revisar los datos insertados y mejorado el debug
**Objetivo:** Implementar funcionalidades para revisar datos insertados y mejorar debugging.

**Funcionalidades implementadas:**
- Se agregaron logs detallados en `src/escritura.py` para mostrar ejemplos de datos antes de insertar
- Se implementó resumen estadístico después de la inserción (tipos de documentos, fechas, etc.)
- Se crearon comandos en `Makefile` para visualizar datos de la base de datos:
  - `make view-data`: Resumen completo con conteos y estadísticas
  - `make view-regulations`: Últimas 10 regulaciones insertadas
  - `make view-components`: Componentes de regulaciones con JOIN
  - `make db-connect`: Conexión directa a PostgreSQL

**Logs mejorados:**
```python
# Ejemplos de datos a insertar (máximo 10)
print("=== EJEMPLOS DE DATOS A INSERTAR ===")
# Resumen estadístico post-inserción
print("=== RESUMEN DE DATOS INSERTADOS ===")
```

### Paso 22 — feat: exportar información scrapeada a CSV
**Objetivo:** Crear script para exportar datos scrapeados a archivos CSV.

**Script creado:** `scripts/export_to_csv.py`
- Script independiente (NO es plugin de Airflow)
- Conecta a la BD usando las mismas credenciales que Airflow
- Exporta regulaciones con JOIN a componentes
- Incluye estadísticas y metadatos

**Funcionalidades del script:**
- Exportación principal: `python scripts/export_to_csv.py`
- Exportación con límite: `--limit 100`
- Solo componentes: `--only-components`
- Archivo personalizado: `--output mi_archivo.csv`
- Exportación completa: `--components` (incluye ambos archivos)

**Comando en Makefile:**
```makefile
export-csv:
	@mkdir -p exports
	@chmod 777 exports
	docker-compose exec -T webserver python /opt/airflow/scripts/export_to_csv.py --components
```

### Paso 23 — fix: carpeta de exports/ no estaba en docker
**Objetivo:** Resolver problema de sincronización de archivos CSV entre contenedor y sistema local.

**Problema identificado:** Los archivos CSV se creaban dentro del contenedor pero no se sincronizaban con el sistema de archivos local.

**Solución implementada:**
- Se agregó volumen `./exports:/opt/airflow/exports` en `docker-compose.yml`
- Se modificó script para usar rutas absolutas `/opt/airflow/exports/` dentro del contenedor
- Se agregó `exports/` al `.gitignore` para evitar subir archivos CSV al repositorio

**Archivos modificados:**
- `docker-compose.yml`: Agregado volumen para exports
- `scripts/export_to_csv.py`: Cambiadas rutas a absolutas
- `.gitignore`: Agregada carpeta exports

### Paso 24 — fix: permisos para la carpeta exports/
**Objetivo:** Resolver error de permisos al escribir archivos CSV.

**Problema identificado:** Error `Permission denied` al intentar escribir archivos CSV.

**Solución implementada:**
- Se agregó `chmod 777 exports` en el target `export-csv` del Makefile
- Se verificó que el volumen esté correctamente montado
- Se aseguró que el directorio se cree con permisos correctos antes de la exportación

**Comando final funcional:**
```bash
make export-csv
```

**Resultado:** Archivos CSV generados exitosamente en `exports/` con formato:
- `exports/regulations_export_YYYYMMDD_HHMMSS.csv`
- `exports/components_export_YYYYMMDD_HHMMSS.csv`

### Paso 25 — feat: documentación completa y limpieza final del proyecto
**Objetivo:** Completar documentación y limpiar el proyecto para evaluación técnica.

**Documentación implementada:**
- **`README.md`**: Documentación completa para prueba técnica con:
  - Índice navegable para acceso rápido
  - Guía de instalación y configuración paso a paso
  - Comandos principales organizados por categorías
  - Ejecución del pipeline con parámetros configurables
  - Configuración avanzada (reglas de validación, esquema BD, variables de entorno)
  - Troubleshooting detallado con soluciones
  - Cumplimiento explícito de criterios de evaluación
  - Ejemplos de logs esperados para cada etapa
- **`docs/PROCESO.MD`**: Documentación técnica detallada del proceso de implementación
- **`docs/MUESTRA.MD`**: Guía visual paso a paso con capturas de pantalla del proceso completo

**Limpieza del proyecto:**
- **Eliminada carpeta `plugins/`**: No se utilizaba en el proyecto, se removió para mantener el repositorio limpio
- **Actualizado `.gitignore`**: Incluye `exports/` y otros archivos temporales
- **Estructura final optimizada**:
---
