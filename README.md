# TestDapper — Refactor + Validación + DAG en Airflow

**Prueba técnica**: Refactorizar Lambda para ejecutar Extracción → Validación → Escritura en Airflow.

## Estructura del proyecto
```
TestDapper/
├── dags/ani_normas_dag.py          # DAG de Airflow
├── src/
│   ├── extraccion.py               # Módulo de scraping
│   ├── validacion.py               # Módulo de validación
│   └── escritura.py                # Módulo de persistencia
├── config/
│   ├── validation_rules.yaml       # Reglas de validación
│   └── schema.sql                  # DDL de tablas
├── docker-compose.yml              # Servicios
├── Makefile                        # Comandos
└── .env.example                    # Variables de entorno
```

## Instalación y Configuración

```bash
# 1. Clonar repositorio
git clone https://github.com/ybedoyab/TestDapper
cd TestDapper

# 2. Configurar variables de entorno
cp .env.example .env

# 3. Levantar entorno
make start
```

**Acceso a Airflow**: `http://localhost:8080` (admin/admin)

## Comandos Principales

### Gestión del entorno
- `make start` - Inicia todo el entorno
- `make down-airflow` - Detiene servicios

### Visualización de datos
- `make view-data` - Resumen de la BD
- `make view-regulations` - Últimas regulaciones
- `make view-components` - Componentes
- `make db-connect` - Conexión directa a PostgreSQL

### Exportación
- `make export-csv` - Exporta a CSV

## Ejecución del Pipeline

1. Abrir Airflow UI: `http://localhost:8080`
2. Buscar DAG `ani_normas_pipeline`
3. Ejecutar con botón play ▶️

**Parámetros configurables:**
- `num_pages_to_scrape`: Páginas a scrapear (default: 3)
- `verbose`: Logs detallados (default: false)

## Documentación Adicional

- **[Guía Visual](docs/MUESTRA.MD)** - Paso a paso con capturas de pantalla
- **[Proceso de Implementación](docs/PROCESO.MD)** - Detalles técnicos del desarrollo

## Contacto

**Yulian Bedoya** - ysbedoya0@gmail.com