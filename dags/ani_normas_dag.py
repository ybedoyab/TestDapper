from datetime import timedelta

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
        df = run_extraction(num_pages=num_pages_to_scrape, verbose=verbose)
        print(f"Total de registros extraídos: {len(df)}")
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
        records = ti.xcom_pull(task_ids='extract') or []
        df = pd.DataFrame(records)
        df_valid, metrics = run_validation(df)
        print(f"Métricas de validación: {metrics}")
        return {
            'records': df_valid.to_dict(orient='records'),
            'metrics': metrics,
        }

    validate_task = PythonOperator(
        task_id='validate',
        python_callable=validate_callable,
    )

    def write_callable(ti):
        payload = ti.xcom_pull(task_ids='validate') or {}
        records = payload.get('records', [])
        df = pd.DataFrame(records)
        inserted, message = (0, 'No records to write') if df.empty else run_write(df, ENTITY_VALUE)
        print(f"Escritura: inserted={inserted} | {message}")
        return {
            'inserted': inserted,
            'message': message,
        }

    write_task = PythonOperator(
        task_id='write',
        python_callable=write_callable,
    )

    extract_task >> validate_task >> write_task


