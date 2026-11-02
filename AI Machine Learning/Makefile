PY ?= python

.PHONY: native bench install test test-fast lint format pipeline fast serve mlflow docker

install:
	$(PY) -m pip install torch --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -e ".[dev,native]"
	$(PY) scripts/build_native.py --if-present

native:
	$(PY) scripts/build_native.py

bench:
	$(PY) scripts/benchmark_native.py

test:
	$(PY) -m pytest

test-fast:
	$(PY) -m pytest -m "not slow"

lint:
	ruff check src tests
	ruff format --check src tests

format:
	ruff format src tests
	ruff check --fix src tests

pipeline:
	churn-ml pipeline

fast:
	churn-ml -c fast pipeline

serve:
	churn-ml serve

mlflow:
	mlflow ui --backend-store-uri sqlite:///artifacts/mlflow.db

docker:
	docker compose build
