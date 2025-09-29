from urllib.parse import urlparse
from typing import Dict, Any


def parse_sqlalchemy_uri(uri: str) -> Dict[str, Any]:
    p = urlparse(uri)
    return {
        'dbname': (p.path or '/airflow').lstrip('/') or 'airflow',
        'user': p.username or 'airflow',
        'password': p.password or 'airflow',
        'host': p.hostname or 'postgres',
        'port': int(p.port or 5432),
    }


def create_tables_if_not_exists(conn) -> None:
    ddl_regulations = (
        """
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
        """
    )
    ddl_regulations_component = (
        """
        CREATE TABLE IF NOT EXISTS regulations_component (
          id SERIAL PRIMARY KEY,
          regulations_id INTEGER REFERENCES regulations(id),
          components_id INTEGER
        );
        """
    )
    with conn.cursor() as cur:
        cur.execute(ddl_regulations)
        cur.execute(ddl_regulations_component)
    conn.commit()


