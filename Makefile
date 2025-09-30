.PHONY: reset-airflow init-airflow up-airflow down-airflow start create-tables

down-airflow:
	docker-compose down --volumes

reset-airflow: down-airflow
	sudo chown -R $$(id -u):$$(id -g) logs dags plugins || true
	rm -rf logs/* dags/* plugins/*
	mkdir -p logs dags plugins
	chmod 777 logs dags plugins

init-airflow:
	docker-compose run --rm webserver airflow db init
	docker-compose run --rm webserver \
	  airflow users create \
	    --username $${AIRFLOW_ADMIN_USERNAME} --password $${AIRFLOW_ADMIN_PASSWORD} \
	    --firstname $${AIRFLOW_ADMIN_FIRSTNAME} --lastname $${AIRFLOW_ADMIN_LASTNAME} \
	    --role $${AIRFLOW_ADMIN_ROLE} --email $${AIRFLOW_ADMIN_EMAIL}

create-tables:
	@echo "Creating database tables..."
	docker-compose exec -T postgres psql -U airflow -d airflow < config/schema.sql
	@echo "Tables created successfully!"

up-airflow:
	docker-compose up -d

start: reset-airflow init-airflow up-airflow create-tables
	@echo "Airflow started successfully!"
	@echo "Access UI at: http://localhost:8080"
	@echo "Login: $${AIRFLOW_ADMIN_USERNAME} / $${AIRFLOW_ADMIN_PASSWORD}"
