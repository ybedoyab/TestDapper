## TestDapper — Refactor + Validación + DAG en Airflow

## 📑 Índice

- [Objetivo](#objetivo)
- [Características principales](#características-principales)
- [📋 Entregables Completados](#-entregables-completados)
- [Requisitos](#requisitos)
- [Estructura del proyecto](#estructura-del-proyecto)
- [🚀 Instalación y Configuración](#-instalación-y-configuración)
  - [1. Clonar el repositorio](#1-clonar-el-repositorio)
  - [2. Configuración inicial](#2-configuración-inicial)
  - [3. Levantar el entorno](#3-levantar-el-entorno)
  - [4. Acceso a la UI de Airflow](#4-acceso-a-la-ui-de-airflow)
- [📋 Comandos Principales](#-comandos-principales)
  - [Comandos de gestión del entorno](#comandos-de-gestión-del-entorno)
  - [Comandos de visualización de datos](#comandos-de-visualización-de-datos)
  - [Comandos de exportación](#comandos-de-exportación)
  - [Otros comandos útiles](#otros-comandos-útiles)
- [🎯 Ejecución del Pipeline](#-ejecución-del-pipeline)
  - [1. Ejecutar el DAG en Airflow](#1-ejecutar-el-dag-en-airflow)
  - [2. Parámetros configurables](#2-parámetros-configurables)
  - [3. Monitoreo y logs](#3-monitoreo-y-logs)
- [🔧 Configuración Avanzada](#-configuración-avanzada)
  - [Reglas de validación](#reglas-de-validación)
  - [Esquema de base de datos](#esquema-de-base-de-datos)
  - [Variables de entorno](#variables-de-entorno)
- [✅ Cumplimiento de Criterios de Evaluación](#-cumplimiento-de-criterios-de-evaluación)

---

### Objetivo
**Prueba técnica - Refactor + Validación + DAG en Airflow**

Refactorizar la Lambda provista para ejecutar el proceso con la secuencia: **Extracción → Validación → Escritura**, orquestado en Airflow. El sistema automatiza el scraping de normativas de la Agencia Nacional de Infraestructura (ANI), las valida según reglas configurables y las almacena en PostgreSQL con idempotencia.

**Cumplimiento de criterios de evaluación:**
- ✅ **Correctitud**: Lógica de scraping intacta, validación respeta reglas, DAG end-to-end funcional
- ✅ **Diseño**: Separación clara por etapas, configuración sin tocar código
- ✅ **Operabilidad**: Repositorio entendible, variables por entorno, README suficiente
- ✅ **Calidad**: Manejo de errores y logs útiles
- ✅ **Idempotencia**: No duplica registros

### Características principales
- ✅ **Pipeline completo**: Extracción → Validación → Escritura
- ✅ **29 regulaciones** extraídas y almacenadas exitosamente
- ✅ **Sistema de logs** detallado para debugging
- ✅ **Validación configurable** por archivos YAML
- ✅ **Exportación a CSV** de datos scrapeados
- ✅ **Comandos de visualización** de datos en BD
- ✅ **Idempotencia** para evitar duplicados
- ✅ **Configuración Docker** completa y estable

## 📋 Entregables Completados

### 1. Modularización ✅
- **`src/extraccion.py`**: Módulo de scraping (lógica intacta del código original)
- **`src/validacion.py`**: Módulo de validación por tipos/regex
- **`src/escritura.py`**: Módulo de persistencia con idempotencia

### 2. Validación ✅
- **`config/validation_rules.yaml`**: Reglas configurables (tipos, regex, obligatoriedad)
- **Lógica implementada**:
  - Campo inválido → se escribe como NULL
  - Campo obligatorio inválido → descarta fila completa
- **Métricas de validación**: totales extraídos, descartes por validación, filas insertadas

### 3. Airflow DAG ✅
- **`dags/ani_normas_dag.py`**: DAG con 3 tareas secuenciales
- **Base de datos**: PostgreSQL del docker-compose de Airflow
- **Acceso**: Variables de entorno (sin Secrets Manager)

### 4. Idempotencia ✅
- **Criterios mantenidos**: `title|created_at|external_link` como clave única
- **Lógica reutilizada**: Sin cambios en la lógica original de detección de duplicados

### 5. Documentación ✅
- **README completo**: Instalación, configuración, ejecución
- **Logs claros**: Totales extraídos, descartes por validación, filas insertadas
- **DDL incluido**: `config/schema.sql` para crear tablas si no existen


### Requisitos
- Docker y Docker Compose
- Make (opcional, puedes ejecutar los comandos docker-compose equivalentes)
- WSL (Windows Subsystem for Linux) si usas Windows

### Estructura del proyecto
```
TestDapper/
├── dags/
│   └── ani_normas_dag.py          # DAG principal de Airflow
├── src/
│   ├── __init__.py                # Paquete Python
│   ├── extraccion.py              # Lógica de scraping web
│   ├── validacion.py              # Validación de datos
│   └── escritura.py               # Inserción en BD con logs detallados
├── scripts/
│   └── export_to_csv.py           # Script de exportación a CSV
├── config/
│   ├── validation_rules.yaml      # Reglas de validación configurables
│   ├── schema.sql                 # DDL de tablas de BD
│   └── airflow.cfg                # Configuración de Airflow
├── exports/                       # Archivos CSV exportados (gitignored)
├── logs/                          # Logs de Airflow (gitignored)
├── plugins/                       # Plugins de Airflow
├── docker-compose.yml             # Configuración de servicios
├── Dockerfile                     # Imagen personalizada de Airflow
├── Makefile                       # Comandos de automatización
└── .env.example                   # Variables de entorno de ejemplo
```

## 🚀 Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/ybedoyab/TestDapper
cd TestDapper
```

### 2. Configuración inicial

**Crear archivo de variables de entorno y editar:**
```bash
cp .env.example .env
```

### 3. Levantar el entorno

**En Linux/macOS:**
```bash
make start
```

**En Windows (usando WSL):**
1. Abrir WSL (Windows Subsystem for Linux)
2. Navegar al directorio del proyecto: `cd ./TestDapper`
3. Ejecutar:
```bash
make start
```

**El comando `make start` automáticamente:**
- ✅ Instala Docker y Docker Compose (si no están instalados)
- ✅ Inicia el daemon de Docker
- ✅ Limpia el entorno anterior (logs, plugins, cache)
- ✅ Inicializa la base de datos de Airflow
- ✅ Crea el usuario administrador
- ✅ Levanta todos los servicios (PostgreSQL, Scheduler, Webserver)
- ✅ Crea las tablas necesarias (`regulations` y `regulations_component`)

### 4. Acceso a la UI de Airflow
- **URL**: `http://localhost:8080`
- **Usuario**: `admin` (configurado en `.env`)
- **Clave**: `admin` (configurado en `.env`)

## 📋 Comandos Principales

### Comandos de gestión del entorno

| Comando | Descripción |
|---------|-------------|
| `make start` | **Inicia todo el entorno** - Instala dependencias, configura BD, crea usuario admin y levanta servicios |
| `make down-airflow` | **Detiene todos los servicios** - Para parar el entorno completamente |

### Comandos de visualización de datos

| Comando | Descripción |
|---------|-------------|
| `make view-data` | **Resumen completo** - Muestra totales, entidades y estadísticas de la BD |
| `make view-regulations` | **Últimas regulaciones** - Muestra las 10 regulaciones más recientes |
| `make view-components` | **Componentes** - Muestra componentes de regulaciones con JOIN |
| `make db-connect` | **Conexión directa** - Abre sesión interactiva de PostgreSQL |

### Comandos de exportación

| Comando | Descripción |
|---------|-------------|
| `make export-csv` | **Exporta a CSV** - Genera archivos CSV con todos los datos scrapeados |

### Otros comandos útiles

| Comando | Descripción |
|---------|-------------|
| `make create-tables` | **Crea tablas** - Ejecuta DDL para crear tablas si no existen |
| `make reset-airflow` | **Limpia entorno** - Limpia logs y plugins (preserva DAGs) |

## 🎯 Ejecución del Pipeline

### 1. Ejecutar el DAG en Airflow
1. Abrir la UI de Airflow: `http://localhost:8080`
2. Buscar el DAG `ani_normas_pipeline`
3. Hacer clic en el botón de **play** (▶️) para ejecutar
4. Observar el progreso en la interfaz

### 2. Parámetros configurables
- **`num_pages_to_scrape`**: Número de páginas a scrapear (default: 3)
- **`verbose`**: Modo verbose para logs detallados (default: false)

### 3. Monitoreo y logs

**Logs que cumplen criterios de evaluación:**

#### Extracción
```
=== ETAPA: EXTRACCIÓN ===
Parámetros → num_pages_to_scrape=3, verbose=false
Total de registros extraídos: 30
=== FIN EXTRACCIÓN ===
```

#### Validación
```
=== ETAPA: VALIDACIÓN ===
Resumen de validación →
  - total_input_rows: 30
  - total_valid_rows: 29
  - total_dropped_rows: 1
  - invalid_by_field:
    * title: 1
=== FIN VALIDACIÓN ===
```

#### Escritura
```
=== ETAPA: ESCRITURA ===
=== EJEMPLOS DE DATOS A INSERTAR ===
  1. Título: Decreto 1430 de 2022 - Por el cual se establecen...
     Fecha: 2022-07-29 00:00:00
     Tipo: link
     Enlace: https://www.funcionpublica.gov.co/...
     Resumen: Este decreto establece disposiciones...

=== RESUMEN DE DATOS INSERTADOS ===
Total insertados: 29
Tipos de documentos encontrados:
  - link: 29
Entity Agencia Nacional de Infraestructura: Processed: 30 | Existing: 0 | Duplicates skipped: 1 | New inserted: 29. Successfully inserted 29 regulation components
=== FIN ESCRITURA ===
```

**Archivos generados:**
- `exports/regulations_export_YYYYMMDD_HHMMSS.csv` - Regulaciones principales
- `exports/components_export_YYYYMMDD_HHMMSS.csv` - Componentes y relaciones

### Estructura de datos
- **Tabla `regulations`**: 29 regulaciones de ANI (2021-2022)
- **Tabla `regulations_component`**: 29 componentes relacionados
- **Idempotencia**: Sistema evita duplicados automáticamente

## 🔧 Configuración Avanzada

### Reglas de validación
Editar `config/validation_rules.yaml` para modificar reglas de validación:
```yaml
title:
  type: string
  required: true
  regex: "^.{1,65}$"
# ... más reglas
```

### Esquema de base de datos
Ver `config/schema.sql` para la estructura completa de tablas.

### Variables de entorno
Configurar en `.env`:
- Credenciales de Airflow
- Configuración de PostgreSQL
- Parámetros de scraping

## ✅ Cumplimiento de Criterios de Evaluación

### Correctitud ✅
- **Lógica de scraping intacta**: No se modificaron reglas de omisión, criterios ni decisiones del código original
- **Validación respeta reglas**: Campo inválido → NULL, campo obligatorio inválido → descarta fila
- **DAG end-to-end funcional**: Extracción → Validación → Escritura ejecuta completamente
- **Escribe en DB de Airflow**: PostgreSQL del docker-compose como destino

### Diseño ✅
- **Separación clara por etapas**: 3 módulos independientes (`extraccion`, `validacion`, `escritura`)
- **Configuración sin tocar código**: Reglas en `config/validation_rules.yaml`
- **Modularización**: Código Lambda refactorizado en módulos reutilizables

### Operabilidad ✅
- **Repositorio entendible**: Estructura clara, documentación completa
- **Variables por entorno**: `.env` para configuración, sin secrets hardcodeados
- **README suficiente**: Instalación, configuración, ejecución sin tutoriales extensos

### Calidad ✅
- **Manejo de errores**: Try-catch en conexiones BD, validación de datos
- **Logs útiles**: Totales extraídos, descartes por validación, filas insertadas
- **Debugging**: Ejemplos de datos, métricas detalladas, comandos de visualización

### Idempotencia ✅
- **No duplica registros**: Criterios `title|created_at|external_link` como clave única
- **Lógica reutilizada**: Sistema de detección de duplicados del código original intacto
- **Validación en BD**: Verificación contra registros existentes antes de insertar