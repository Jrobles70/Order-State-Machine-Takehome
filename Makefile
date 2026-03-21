.PHONY: setup test run clean

setup:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest -v

run:
	.venv/bin/uvicorn app.main:app --reload

clean:
	rm -rf .venv .pytest_cache __pycache__ app/__pycache__ tests/__pycache__
