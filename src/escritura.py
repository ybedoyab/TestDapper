import os
from typing import Tuple, List

import pandas as pd
import psycopg2


class DatabaseManager:
    def __init__(self) -> None:
        self.connection = None
        self.cursor = None

    def connect(self) -> bool:
        try:
            dbname = os.environ.get('DB_NAME', 'airflow')
            user = os.environ.get('DB_USER', 'airflow')
            password = os.environ.get('DB_PASSWORD', 'airflow')
            host = os.environ.get('DB_HOST', 'postgres')
            port = int(os.environ.get('DB_PORT', '5432'))

            self.connection = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
            )
            self.cursor = self.connection.cursor()
            return True
        except Exception as e:
            print(f"Database connection error: {e}")
            return False

    def close(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def execute_query(self, query: str, params=None):
        if not self.cursor:
            raise Exception("Database not connected")
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def bulk_insert(self, df: pd.DataFrame, table_name: str) -> int:
        if not self.connection or not self.cursor:
            raise Exception("Database not connected")
        try:
            df = df.astype(object).where(pd.notnull(df), None)
            columns_for_sql = ", ".join([f'"{col}"' for col in df.columns])
            placeholders = ", ".join(["%s"] * len(df.columns))
            insert_query = f"INSERT INTO {table_name} ({columns_for_sql}) VALUES ({placeholders})"
            records_to_insert = [tuple(x) for x in df.values]
            self.cursor.executemany(insert_query, records_to_insert)
            self.connection.commit()
            return len(df)
        except Exception as e:
            self.connection.rollback()
            raise Exception(f"Error inserting into {table_name}: {str(e)}")


def insert_regulations_component(db_manager: DatabaseManager, new_ids: List[int]) -> Tuple[int, str]:
    if not new_ids:
        return 0, "No new regulation IDs provided"
    try:
        id_rows = pd.DataFrame(new_ids, columns=['regulations_id'])
        id_rows['components_id'] = 7
        inserted_count = db_manager.bulk_insert(id_rows, 'regulations_component')
        return inserted_count, f"Successfully inserted {inserted_count} regulation components"
    except Exception as e:
        return 0, f"Error inserting regulation components: {str(e)}"


def insert_new_records(db_manager: DatabaseManager, df: pd.DataFrame, entity: str):
    regulations_table_name = 'regulations'
    try:
        query = (
            f"""
            SELECT title, created_at, entity, COALESCE(external_link, '') as external_link 
            FROM {regulations_table_name}
            WHERE entity = %s
            """
        )
        existing_records = db_manager.execute_query(query, (entity,))
        if not existing_records:
            db_df = pd.DataFrame(columns=['title', 'created_at', 'entity', 'external_link'])
        else:
            db_df = pd.DataFrame(existing_records, columns=['title', 'created_at', 'entity', 'external_link'])

        print(f"Registros existentes en BD para {entity}: {len(db_df)}")

        entity_df = df[df['entity'] == entity].copy()
        if entity_df.empty:
            return 0, f"No records found for entity {entity}"

        print(f"Registros a procesar para {entity}: {len(entity_df)}")

        if not db_df.empty:
            db_df['created_at'] = db_df['created_at'].astype(str)
            db_df['external_link'] = db_df['external_link'].fillna('').astype(str)
            db_df['title'] = db_df['title'].astype(str).str.strip()

        entity_df['created_at'] = entity_df['created_at'].astype(str)
        entity_df['external_link'] = entity_df['external_link'].fillna('').astype(str)
        entity_df['title'] = entity_df['title'].astype(str).str.strip()

        print("=== INICIANDO VALIDACIÓN DE DUPLICADOS OPTIMIZADA ===")
        if db_df.empty:
            new_records = entity_df.copy()
            duplicates_found = 0
            print("No hay registros existentes, todos son nuevos")
        else:
            entity_df['unique_key'] = (
                entity_df['title'] + '|' + entity_df['created_at'] + '|' + entity_df['external_link']
            )
            db_df['unique_key'] = (
                db_df['title'] + '|' + db_df['created_at'] + '|' + db_df['external_link']
            )
            existing_keys = set(db_df['unique_key'])
            entity_df['is_duplicate'] = entity_df['unique_key'].isin(existing_keys)
            new_records = entity_df[~entity_df['is_duplicate']].copy()
            duplicates_found = len(entity_df) - len(new_records)
            if duplicates_found > 0:
                print(f"Duplicados encontrados: {duplicates_found}")
                duplicate_records = entity_df[entity_df['is_duplicate']]
                print("Ejemplos de duplicados:")
                for _, row in duplicate_records.head(3).iterrows():
                    print(f"  - {row['title'][:50]}... | {row['created_at']}")

        print(f"Antes de remover duplicados internos: {len(new_records)}")
        new_records = new_records.drop_duplicates(
            subset=['title', 'created_at', 'external_link'], keep='first'
        )
        internal_duplicates = len(entity_df) - duplicates_found - len(new_records)
        if internal_duplicates > 0:
            print(f"Duplicados internos removidos: {internal_duplicates}")

        print(f"Después de remover duplicados internos: {len(new_records)}")
        print(f"=== DUPLICADOS IDENTIFICADOS: {duplicates_found + internal_duplicates} ===")

        if new_records.empty:
            return 0, f"No new records found for entity {entity} after duplicate validation"

        columns_to_drop = ['unique_key', 'is_duplicate']
        for col in columns_to_drop:
            if col in new_records.columns:
                new_records = new_records.drop(columns=[col])

        print(f"Registros finales a insertar: {len(new_records)}")

        try:
            print(f"=== INSERTANDO {len(new_records)} REGISTROS ===")
            total_rows_processed = db_manager.bulk_insert(new_records, regulations_table_name)
            if total_rows_processed == 0:
                return 0, f"No records were actually inserted for entity {entity}"
            print(f"Registros insertados exitosamente: {total_rows_processed}")
        except Exception as insert_error:
            print(f"Error en inserción: {insert_error}")
            if "duplicate" in str(insert_error).lower() or "unique" in str(insert_error).lower():
                print("Error de duplicados detectado - algunos registros ya existían")
                return 0, f"Some records for entity {entity} were duplicates and skipped"
            else:
                raise insert_error

        print("=== OBTENIENDO IDS DE REGISTROS INSERTADOS ===")
        new_ids_query = f"""
            SELECT id FROM {regulations_table_name}
            WHERE entity = %s 
            ORDER BY id DESC
            LIMIT %s
        """
        new_ids_result = db_manager.execute_query(new_ids_query, (entity, total_rows_processed))
        new_ids = [row[0] for row in new_ids_result]
        print(f"IDs obtenidos: {len(new_ids)}")

        inserted_count_comp = 0
        component_message = ""
        if new_ids:
            try:
                inserted_count_comp, component_message = insert_regulations_component(db_manager, new_ids)
                print(f"Componentes: {component_message}")
            except Exception as comp_error:
                print(f"Error insertando componentes: {comp_error}")
                component_message = f"Error inserting components: {str(comp_error)}"

        total_duplicates = duplicates_found + internal_duplicates
        stats = (
            f"Processed: {len(entity_df)} | "
            f"Existing: {len(db_df)} | "
            f"Duplicates skipped: {total_duplicates} | "
            f"New inserted: {total_rows_processed}"
        )
        message = f"Entity {entity}: {stats}. {component_message}"
        print("=== RESULTADO FINAL ===")
        print(message)
        print("=" * 50)
        return total_rows_processed, message

    except Exception as e:
        if hasattr(db_manager, 'connection') and db_manager.connection:
            db_manager.connection.rollback()
        error_msg = f"Error processing entity {entity}: {str(e)}"
        print(f"ERROR CRÍTICO: {error_msg}")
        import traceback
        print(traceback.format_exc())
        return 0, error_msg


def run_write(df: pd.DataFrame, entity: str) -> Tuple[int, str]:
    db_manager = DatabaseManager()
    if not db_manager.connect():
        return 0, 'Error de conexión a la base de datos'
    try:
        inserted_count, status_message = insert_new_records(db_manager, df, entity)
        return inserted_count, status_message
    finally:
        db_manager.close()


