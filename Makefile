.PHONY: reset-airflow init-airflow up-airflow down-airflow start create-tables install-deps load-env view-data view-regulations view-components db-connect export-csv

load-env:
	@echo "Loading environment variables..."
	@if [ -f .env ]; then \
		export $$(cat .env | xargs); \
		echo "Environment variables loaded from .env"; \
	else \
		echo "Warning: .env file not found, using default values"; \
	fi

install-deps:
	@echo "Installing Docker and Docker Compose..."
	sudo apt-get update
	sudo apt-get install -y docker.io
	@echo "Installing latest Docker Compose..."
	sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$$(uname -s)-$$(uname -m)" -o /usr/local/bin/docker-compose
	sudo chmod +x /usr/local/bin/docker-compose
	sudo usermod -aG docker $$USER
	@echo "Starting Docker daemon..."
	@sudo docker version > /dev/null 2>&1 || sudo dockerd > /dev/null 2>&1 &
	@echo "Docker installed and started successfully!"

down-airflow:
	docker-compose down --volumes

reset-airflow: down-airflow
	sudo chown -R $$(id -u):$$(id -g) logs dags plugins || true
	rm -rf logs/* plugins/*
	find dags -name "*.pyc" -delete 2>/dev/null || true
	find dags -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	mkdir -p logs dags plugins
	chmod 777 logs dags plugins

init-airflow:
	docker-compose run --rm webserver airflow db init
	@echo "#!/bin/bash" > /tmp/create_user.sh
	@echo "set -e" >> /tmp/create_user.sh
	@echo "sed -i 's/\r$$//' .env" >> /tmp/create_user.sh
	@echo "source .env" >> /tmp/create_user.sh
	@echo "docker-compose run --rm webserver airflow users create \\" >> /tmp/create_user.sh
	@echo "  --username \$$AIRFLOW_ADMIN_USERNAME --password \$$AIRFLOW_ADMIN_PASSWORD \\" >> /tmp/create_user.sh
	@echo "  --firstname \$$AIRFLOW_ADMIN_FIRSTNAME --lastname \$$AIRFLOW_ADMIN_LASTNAME \\" >> /tmp/create_user.sh
	@echo "  --role Admin --email \$$AIRFLOW_ADMIN_EMAIL" >> /tmp/create_user.sh
	@chmod +x /tmp/create_user.sh
	@bash /tmp/create_user.sh
	@rm /tmp/create_user.sh

create-tables:
	@if [ -f config/schema.sql ]; then \
		echo "Creating database tables..."; \
		docker-compose exec -T postgres psql -U airflow -d airflow < config/schema.sql; \
		echo "Tables created successfully!"; \
	else \
		echo "No schema.sql found, skipping table creation"; \
	fi

up-airflow:
	docker-compose up -d

start: install-deps reset-airflow init-airflow up-airflow create-tables
	@echo "Airflow started successfully!"
	@echo "Access UI at: http://localhost:8080"
	@sed -i 's/\r$$//' .env 2>/dev/null || true
	@export $$(cat .env | xargs) && echo "Login: $$AIRFLOW_ADMIN_USERNAME / $$AIRFLOW_ADMIN_PASSWORD"

db-connect:
	@echo "Connecting to PostgreSQL database..."
	docker-compose exec postgres psql -U airflow -d airflow

view-data:
	@echo "=== RESUMEN DE DATOS EN LA BASE DE DATOS ==="
	@echo "Total de regulaciones:"
	docker-compose exec -T postgres psql -U airflow -d airflow -c "SELECT COUNT(*) as total_regulations FROM regulations;"
	@echo ""
	@echo "Total de componentes:"
	docker-compose exec -T postgres psql -U airflow -d airflow -c "SELECT COUNT(*) as total_components FROM regulations_component;"
	@echo ""
	@echo "Regulaciones por entidad:"
	docker-compose exec -T postgres psql -U airflow -d airflow -c "SELECT entity, COUNT(*) as count FROM regulations GROUP BY entity ORDER BY count DESC;"

view-regulations:
	@echo "=== ÚLTIMAS 10 REGULACIONES ==="
	docker-compose exec -T postgres psql -U airflow -d airflow -c "SELECT id, title, entity, gtype, created_at FROM regulations ORDER BY created_at DESC LIMIT 10;"

view-components:
	@echo "=== COMPONENTES DE REGULACIONES ==="
	docker-compose exec -T postgres psql -U airflow -d airflow -c "SELECT rc.id, r.title, r.entity, rc.components_id FROM regulations_component rc JOIN regulations r ON rc.regulations_id = r.id ORDER BY rc.id DESC LIMIT 10;"

export-csv:
	@echo "=== EXPORTANDO DATOS A CSV ==="
	@mkdir -p exports
	@echo "Ejecutando script de exportación..."
	docker-compose exec -T webserver python /opt/airflow/scripts/export_to_csv.py --components
	@echo "Exportación completada! Revisa la carpeta exports/"
