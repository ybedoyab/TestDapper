## TestDapper — Refactor + Validación + DAG en Airflow

### Objetivo
Orquestar el flujo Extracción → Validación → Escritura en Airflow, reutilizando la lógica de scraping e idempotencia existentes y escribiendo en la base Postgres del docker-compose.

### Requisitos
- Docker y Docker Compose
- Make (opcional, puedes ejecutar los comandos docker-compose equivalentes)

### Estructura
- `dags/ani_normas_dag.py`: DAG con 3 tareas (extract → validate → write)
- `src/extraccion.py`: scraping (sin cambiar reglas de omisión actuales)
- `src/validacion.py`: validación por tipos/regex desde `configs/validation_rules.yaml`
- `src/escritura.py`: inserción con idempotencia en Postgres
- `src/db.py`: utilidades DB (parse URI y DDL si se requiere)
- `configs/validation_rules.yaml`: reglas de validación configurables
- `configs/schema.sql`: DDL opcional (referencia alternativa)

### Levantar Airflow
1) Construir e iniciar servicios
```bash
make start
# Equivalente manual:
# docker-compose down --volumes
# sudo chown -R $(id -u):$(id -g) logs dags plugins || true
# rm -rf logs/* dags/* plugins/* && mkdir -p logs dags plugins && chmod 777 logs dags plugins
# docker-compose run --rm webserver airflow db init | cat
# docker-compose run --rm webserver airflow users create \
#   --username admin --password admin --firstname Admin --lastname User \
#   --role Admin --email admin@example.com | cat
# docker-compose up -d
```

2) Acceso a la UI de Airflow
- URL: `http://localhost:8080`
- Usuario/clave: `admin` / `admin`

### Configuración
- BD de destino: la misma Postgres del compose (`postgres`), derivada de `AIRFLOW__CORE__SQL_ALCHEMY_CONN`.
- Reglas de validación: `configs/validation_rules.yaml`.
- Parámetros del DAG:
  - `num_pages_to_scrape` (default: 3)
  - `verbose` (default: false)

### Ejecución del DAG
1) En la UI, habilita `ani_normas_pipeline` y ejecuta `Trigger DAG`.
2) Observa logs por tarea: extracción, validación (métricas), escritura (insertados).

### Notas
- No se realiza pre-chequeo de “nuevo contenido”; se confía en la idempotencia durante la escritura para evitar duplicados.
- `lambda.py` se mantiene como referencia durante el refactor; no se usa en el DAG.

### Troubleshooting
- Si no se encuentra `PyYAML`, reconstruye la imagen: `docker-compose build --no-cache` y `docker-compose up -d`.
- Permisos en volúmenes: usar `AIRFLOW_UID` y `AIRFLOW_GID` en `.env` (ver `.env.example`).


