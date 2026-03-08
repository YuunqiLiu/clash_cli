.PHONY: install dev test lint clean build

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	python -m pytest -v

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build:
	python -m build
