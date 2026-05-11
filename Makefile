PYTHON ?= python
PIP ?= $(PYTHON) -m pip

.PHONY: install api web test lint format build-web

install:
	$(PIP) install -e .

api:
	$(PYTHON) -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd apps/web && npm install && npm run dev -- --host 0.0.0.0 --port 5173

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

build-web:
	cd apps/web && npm install && npm run build
