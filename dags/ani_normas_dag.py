from airflow import DAG
from airflow.models.param import Param
from airflow.utils.dates import days_ago
from airflow.operators.python import PythonOperator

import pandas as pd

from src.extraccion import run_extraction, ENTITY_VALUE
from src.validacion import run_validation
from src.escritura import run_write


default_args = {
    'owner': 'airflow',
    'retries': 0,
}


with DAG(
    dag_id='ani_normas_pipeline',
    description='Extracción → Validación → Escritura para ANI',
    default_args=default_args,
    start_date=days_ago(1),
    schedule_interval=None,
    catchup=False,
    params={
        'num_pages_to_scrape': Param(3, type='integer', minimum=1, maximum=25),
        'verbose': Param(False, type='boolean'),
    },
) as dag:

    def extract_callable(ti, num_pages_to_scrape: int, verbose: bool):
        print("\n=== ETAPA: EXTRACCIÓN ===")
        print(f"Parámetros → num_pages_to_scrape={num_pages_to_scrape}, verbose={verbose}")
        df = run_extraction(num_pages=num_pages_to_scrape, verbose=verbose)
        print(f"Total de registros extraídos: {len(df)}")
        print("=== FIN EXTRACCIÓN ===\n")
        return df.to_dict(orient='records')

    extract_task = PythonOperator(
        task_id='extract',
        python_callable=extract_callable,
        op_kwargs={
            'num_pages_to_scrape': '{{ params.num_pages_to_scrape }}',
            'verbose': '{{ params.verbose }}',
        },
    )

    def validate_callable(ti):
        print("\n=== ETAPA: VALIDACIÓN ===")
        records = ti.xcom_pull(task_ids='extract') or []
        df = pd.DataFrame(records)
        df_valid, metrics = run_validation(df)
        print("Resumen de validación →")
        print(f"  - total_input_rows: {metrics.get('total_input_rows')}")
        print(f"  - total_valid_rows: {metrics.get('total_valid_rows')}")
        print(f"  - total_dropped_rows: {metrics.get('total_dropped_rows')}")
        invalid_by_field = metrics.get('invalid_by_field', {})
        if invalid_by_field:
            print("  - invalid_by_field:")
            for k, v in invalid_by_field.items():
                print(f"    * {k}: {v}")
        print("=== FIN VALIDACIÓN ===\n")
        return {
            'records': df_valid.to_dict(orient='records'),
            'metrics': metrics,
        }

    validate_task = PythonOperator(
        task_id='validate',
        python_callable=validate_callable,
    )

    def write_callable(ti):
        print("\n=== ETAPA: ESCRITURA ===")
        payload = ti.xcom_pull(task_ids='validate') or {}
        records = payload.get('records', [])
        df = pd.DataFrame(records)
        inserted, message = (0, 'No records to write') if df.empty else run_write(df, ENTITY_VALUE)
        print(f"Escritura → inserted={inserted}")
        print(f"Mensaje: {message}")
        print("=== FIN ESCRITURA ===\n")
        return {
            'inserted': inserted,
            'message': message,
        }

    write_task = PythonOperator(
        task_id='write',
        python_callable=write_callable,
    )

    extract_task >> validate_task >> write_task


