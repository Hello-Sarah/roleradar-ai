.PHONY: install run-api run-dashboard test lint format docker-up
install:
	pip install -e '.[dev]'
run-api:
	uvicorn app.main:app --reload
run-dashboard:
	streamlit run app/dashboard/streamlit_app.py
test:
	pytest
lint:
	ruff check .
format:
	ruff format .
docker-up:
	docker compose up --build

