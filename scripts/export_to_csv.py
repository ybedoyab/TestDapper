# Script para exportar datos de la base de datos a CSV
import os
import sys
import argparse
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import psycopg2


def get_db_connection():
    try:
        uri = os.environ.get('AIRFLOW__CORE__SQL_ALCHEMY_CONN')
        if uri:
            parsed = urlparse(uri)
            dbname = parsed.path.lstrip('/') or 'airflow'
            user = parsed.username or 'airflow'
            password = parsed.password or 'airflow'
            host = parsed.hostname or 'postgres'
            port = parsed.port or 5432
        else:
            dbname = os.environ.get('POSTGRES_DB', 'airflow')
            user = os.environ.get('POSTGRES_USER', 'airflow')
            password = os.environ.get('POSTGRES_PASSWORD', 'airflow')
            host = os.environ.get('POSTGRES_HOST', 'postgres')
            port = int(os.environ.get('POSTGRES_PORT', '5432'))

        connection = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
        )
        return connection
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return None


def export_regulations_to_csv(output_file=None, limit=None):
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"/opt/airflow/exports/regulations_export_{timestamp}.csv"
    
    os.makedirs("/opt/airflow/exports", exist_ok=True)
    
    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión a la base de datos"
    
    try:
        query = """
        SELECT 
            r.id,
            r.title,
            r.entity,
            r.gtype,
            r.created_at,
            r.update_at,
            r.is_active,
            r.external_link,
            r.rtype_id,
            r.summary,
            r.classification_id,
            COUNT(rc.components_id) as component_count,
            STRING_AGG(rc.components_id::text, ', ') as component_ids
        FROM regulations r
        LEFT JOIN regulations_component rc ON r.id = rc.regulations_id
        GROUP BY r.id, r.title, r.entity, r.gtype, r.created_at, 
                 r.update_at, r.is_active, r.external_link, 
                 r.rtype_id, r.summary, r.classification_id
        ORDER BY r.created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        print(f"Ejecutando query de exportación...")
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("No se encontraron datos para exportar")
            return True, "No hay datos para exportar"
        
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['update_at'] = pd.to_datetime(df['update_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['summary'] = df['summary'].fillna('[Sin resumen]')
        df['external_link'] = df['external_link'].fillna('[Sin enlace]')
        
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"=== EXPORTACIÓN COMPLETADA ===")
        print(f"Archivo generado: {output_file}")
        print(f"Total de registros exportados: {len(df)}")
        print(f"Entidades encontradas: {df['entity'].nunique()}")
        print(f"Tipos de documentos: {df['gtype'].value_counts().to_dict()}")
        print(f"Rango de fechas: {df['created_at'].min()} a {df['created_at'].max()}")
        
        return True, f"Exportación exitosa: {len(df)} registros en {output_file}"
        
    except Exception as e:
        return False, f"Error durante la exportación: {str(e)}"
    finally:
        conn.close()


def export_components_to_csv(output_file=None, limit=None):
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"/opt/airflow/exports/components_export_{timestamp}.csv"
    
    os.makedirs("/opt/airflow/exports", exist_ok=True)
    
    conn = get_db_connection()
    if not conn:
        return False, "Error de conexión a la base de datos"
    
    try:
        query = """
        SELECT 
            rc.id as component_id,
            rc.regulations_id,
            rc.components_id,
            r.title as regulation_title,
            r.entity,
            r.created_at as regulation_date
        FROM regulations_component rc
        JOIN regulations r ON rc.regulations_id = r.id
        ORDER BY rc.id DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("No se encontraron componentes para exportar")
            return True, "No hay componentes para exportar"
        
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"=== EXPORTACIÓN DE COMPONENTES COMPLETADA ===")
        print(f"Archivo generado: {output_file}")
        print(f"Total de componentes exportados: {len(df)}")
        
        return True, f"Exportación de componentes exitosa: {len(df)} registros en {output_file}"
        
    except Exception as e:
        return False, f"Error durante la exportación de componentes: {str(e)}"
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Exportar datos de regulaciones a CSV')
    parser.add_argument('--output', '-o', help='Archivo de salida (por defecto: exports/regulations_export_TIMESTAMP.csv)')
    parser.add_argument('--limit', '-l', type=int, help='Límite de registros a exportar')
    parser.add_argument('--components', '-c', action='store_true', help='Exportar también componentes por separado')
    parser.add_argument('--only-components', action='store_true', help='Exportar solo componentes')
    
    args = parser.parse_args()
    
    print("=== SCRIPT DE EXPORTACIÓN A CSV ===")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if args.only_components:
        success, message = export_components_to_csv(args.output, args.limit)
    else:
        success, message = export_regulations_to_csv(args.output, args.limit)
        
        if success and args.components:
            print()
            comp_success, comp_message = export_components_to_csv(limit=args.limit)
            if not comp_success:
                print(f"Advertencia: {comp_message}")
    
    if success:
        print(f"\n✅ {message}")
        sys.exit(0)
    else:
        print(f"\n❌ {message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
