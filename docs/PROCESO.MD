### Plan de implementación por commits

 - Paso 1 — chore: init repo estructura airflow y carpetas base (dags, src, config, logs, plugins)
   - Crear carpetas base del proyecto:
     - `dags/`: almacenará el DAG de Airflow.
     - `src/`: contendrá módulos `extraccion.py`, `validacion.py`, `escritura.py`, `db.py`.
     - `config/`: reglas de validación (`validation_rules.yaml`) y DDL opcional (`schema.sql`).
     - `logs/` y `plugins/`: usados por Airflow.
   - Verificar que en `docker-compose.yml`:
     - Se montan los volúmenes `./dags`, `./src`, `./config`, `./logs`, `./plugins`.
     - `PYTHONPATH` incluye `/opt/airflow/src` para importar módulos desde el DAG.
   - No mover ni modificar lógica aún; solo la estructura para el refactor posterior.

 - Paso 2 — chore: agregar .gitignore y plantilla de .env.example (sin secretos)
   - `.gitignore` incluirá: `__pycache__/`, `.venv/`, `.env`, `logs/`, `*.pyc`, `.ipynb_checkpoints/`, `.DS_Store`, `plugins/__pycache__/`, `dags/__pycache__/`.
   - `.env.example` contendrá placeholders no sensibles (p. ej. `AIRFLOW_UID=50000`, `AIRFLOW_GID=50000`).
   - Nota operativa: el compose ya define `AIRFLOW__CORE__SQL_ALCHEMY_CONN`, evitaremos secretos en VCS.

 - Paso 3 — refactor: extraer lógica de scraping a src/extraccion.py (sin cambios de reglas)
   - Mover a `src/extraccion.py` funciones existentes en `lambda.py`:
     - `clean_quotes`, `get_rtype_id`, `is_valid_created_at`, `normalize_datetime`.
     - Extracción granular por fila: `extract_title_and_link`, `extract_summary`, `extract_creation_date`.
     - Paginación y scraping: `scrape_page(page_num, verbose=False)`.
   - Añadir `run_extraction(num_pages: int)` que itera páginas 0..N-1, acumula y devuelve `pandas.DataFrame` con columnas:
     - `created_at, update_at, is_active, title, gtype, entity, external_link, rtype_id, summary, classification_id`.
   - Requisitos clave: no alterar heurísticas ni reglas de omisión (longitud, enlace, fechas, etc.).

 - Paso 4 — refactor: mover DatabaseManager e inserción a src/escritura.py (sin secretos AWS)
   - Trasladar `DatabaseManager` y `insert_new_records` desde `lambda.py` a `src/escritura.py`.
   - Mantener la idempotencia con `unique_key = title|created_at|external_link`.
   - Conservar inserción en `regulations` y luego en `regulations_component` (con `components_id = 7`).
   - Exponer `run_write(df)` que:
     - Conecta a la BD.
     - Normaliza tipos y `NaN`→`NULL`.
     - Ejecuta inserción en bloque y retorna métricas (insertados y mensaje).

 - Paso 5 — refactor: reemplazar Secrets Manager por conexión vía env/AIRFLOW__CORE__SQL_ALCHEMY_CONN
   - Eliminar `boto3` y `get_secret()` del flujo.
   - Implementar una utilidad para leer/parsing de `AIRFLOW__CORE__SQL_ALCHEMY_CONN` y extraer:
     - `dbname, user, password, host, port` compatibles con `psycopg2`.
   - Si no existiera la env, permitir fallback a variables `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

 - Paso 6 — feat: crear src/db.py con parseo de URI y creación de tablas si no existen
   - Funciones propuestas:
     - `parse_sqlalchemy_uri(uri: str) -> Dict[str, Any]`.
     - `create_tables_if_not_exists(conn)` que ejecute DDL para las tablas destino.
   - DDL sugerido (si se usa creación en código o `config/schema.sql`):
     - Tabla `regulations`:
       - `id SERIAL PRIMARY KEY`
       - `created_at TIMESTAMP NULL`, `update_at TIMESTAMP NULL`, `is_active BOOLEAN`
       - `title VARCHAR(255)`, `gtype VARCHAR(50)`, `entity VARCHAR(255)`
       - `external_link TEXT`, `rtype_id INTEGER`, `summary TEXT`, `classification_id INTEGER`
     - Tabla `regulations_component`:
       - `id SERIAL PRIMARY KEY`, `regulations_id INTEGER REFERENCES regulations(id)`, `components_id INTEGER`
   - No agregar `UNIQUE` que altere comportamiento; la idempotencia se respeta en la app.

 - Paso 7 — feat: agregar config/validation_rules.yaml con tipos/regex/obligatoriedad
   - Estructura por campo con `type`, `required`, `regex` (opcional), `coerce` (opcional):
```yaml
title:
  type: string
  required: true
  regex: "^.{1,65}$"
external_link:
  type: url
  required: true
created_at:
  type: date
  required: true
entity:
  type: string
  required: true
summary:
  type: string
  required: false
rtype_id:
  type: integer
  required: false
classification_id:
  type: integer
  required: false
gtype:
  type: string
  required: false
is_active:
  type: boolean
  required: false
update_at:
  type: date
  required: false
```
   - Regla de negocio: si un campo no cumple, ese campo → `NULL`; si el campo es `required`, descartar la fila.

 - Paso 8 — feat: implementar validador en src/validacion.py (nullificación de campos, descarte de filas obligatorias)
   - Implementar `run_validation(df, rules)`:
     - Validar por columna según `type` (string/date/boolean/integer/url), aplicar `regex` si existe.
     - Campos inválidos → `None`.
     - Filas con algún `required` inválido → descartar.
   - Métricas de salida:
     - `total_input_rows`, `total_valid_rows`, `total_dropped_rows`.
     - `invalid_by_field`: conteo por campo invalidado.
   - Retornar `(df_validado, metrics)` para logging en DAG.

 - Paso 9 — feat: DAG Airflow ani_normas con tareas Extracción → Validación → Escritura
   - Archivo: `dags/ani_normas_dag.py` con tres `PythonOperator` en secuencia:
     - `extract_task`: ejecuta `run_extraction(num_pages)`; publica resultado (usar XCom con DF→JSON o parquet temporal en `/opt/airflow/logs/tmp/`).
     - `validate_task`: carga reglas de `config/validation_rules.yaml`, ejecuta `run_validation`, publica `df_validado` y métricas.
     - `write_task`: ejecuta `run_write(df_validado)`.
   - Configuración inicial del DAG:
     - `schedule_interval=None` (ejecución manual) y `catchup=False`.
     - `start_date` razonable (p. ej., `days_ago(1)`).
   - Variables/params:
     - `num_pages_to_scrape` como Param o Variable de Airflow con default (p. ej., 3 o 9).
   - Nota: no se implementa pre-chequeo de “contenido nuevo” en el DAG; se ejecuta siempre la extracción y se confía en la idempotencia durante la escritura.

 - Paso 10 — feat: logs métricas por etapa (extraídos, descartados por validación, insertados)
   - `extract_task`: loggear páginas procesadas y `len(df_extraido)`.
   - `validate_task`: loggear `metrics` (por campo y total de filas descartadas) y `len(df_validado)`.
   - `write_task`: loggear filas insertadas en `regulations` y `regulations_component`, y mensaje de resumen.

 - Paso 11 — docs: agregar README con pasos para levantar entorno y ejecutar el DAG
   - Índice breve: requisitos, levantar entorno, credenciales, ejecución del DAG, troubleshooting.
   - Comandos principales (vía Makefile): `make start`, abrir UI en `http://localhost:8080` (admin/admin).
   - Mencionar dónde editar `config/validation_rules.yaml` y cómo cambiar `num_pages_to_scrape`.
   - Indicar que el destino de escritura es la BD Postgres del compose.

 - Paso 12 — chore: agregar config/schema.sql (DDL exportado/alternativo a creación en código)
   - Incluir DDL equivalente al creado por `create_tables_if_not_exists` para referencia:
```sql
CREATE TABLE IF NOT EXISTS regulations (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMP NULL,
  update_at TIMESTAMP NULL,
  is_active BOOLEAN,
  title VARCHAR(255),
  gtype VARCHAR(50),
  entity VARCHAR(255),
  external_link TEXT,
  rtype_id INTEGER,
  summary TEXT,
  classification_id INTEGER
);

CREATE TABLE IF NOT EXISTS regulations_component (
  id SERIAL PRIMARY KEY,
  regulations_id INTEGER REFERENCES regulations(id),
  components_id INTEGER
);
```

 - Paso 13 — chore: limpiar dependencias no usadas (boto3), asegurar requirements en Dockerfile
   - Eliminar `boto3` y `botocore` del código y de `requirements.txt` si existieran.
   - Verificar `requirements.txt`: `requests`, `beautifulsoup4`, `pandas`, `numpy==1.24.3`, `psycopg2-binary==2.9.10`.
   - Confirmar `Dockerfile` instala `requirements.txt` como usuario `airflow`.

 - Paso 14 — chore: pruebas manuales locales documentadas y checklist de criterios de evaluación
   - Pruebas sugeridas:
     - Correr `make start`, crear usuario admin (si no existe) y validar UI.
     - Ejecutar el DAG manualmente con `num_pages_to_scrape` bajo (p. ej., 2-3) y revisar logs.
     - Ejecutar nuevamente para verificar idempotencia (sin nuevos insertados).
     - Modificar temporalmente una regla de validación para forzar descartes y confirmar métricas.
   - Checklist:
     - Correctitud: scraping sin cambios; validación respeta reglas; DAG escribe en DB de Airflow.
     - Diseño: etapas separadas; reglas en archivo; conexión por env.
     - Operabilidad: repo entendible; README suficiente.
     - Calidad: manejo simple de errores; logs útiles.
     - Idempotencia: no duplica registros.

 - Paso 15 — chore: limpieza del repositorio (legacy y dependencias)
   - Mover `lambda.py` a la carpeta `legacy/`.
   - Eliminar importaciones/paquetes no usados (p. ej., `boto3`, `botocore`) de código y `requirements.txt`.
   - Revisar `README.md` para reflejar el flujo final con Airflow.

 - Paso 16 - fix: cambio de nombre de configs a config para estandarizacion
   - Cambiar el nombre de la carpeta `configs/` a `config/`

 - Paso 17: fix: variables de entorno centralizadas