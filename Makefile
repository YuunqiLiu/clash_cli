.PHONY: install dev test test-unit test-integration lint clean build install-mihomo

install:
	pip install .

dev:
	pip install -e ".[dev]"

# Run only unit tests (no mihomo binary needed)
test-unit:
	python -m pytest -v -m "not integration" --tb=short

# Run integration tests (requires mihomo in PATH or CLASH_MIHOMO_PATH)
test-integration:
	python -m pytest tests/integration/ -v -m integration --tb=short

# Run everything
test: test-unit test-integration

# Download mihomo binary for local integration testing
MIHOMO_VERSION ?= v1.19.0
install-mihomo:
	@echo "Downloading Mihomo $(MIHOMO_VERSION)..."
	wget -q "https://github.com/MetaCubeX/mihomo/releases/download/$(MIHOMO_VERSION)/mihomo-linux-amd64-$(MIHOMO_VERSION).gz" -O /tmp/mihomo.gz
	gunzip -f /tmp/mihomo.gz
	chmod +x /tmp/mihomo-linux-amd64-$(MIHOMO_VERSION) 2>/dev/null || chmod +x /tmp/mihomo
	@# Rename uniformly
	mv /tmp/mihomo-linux-amd64-$(MIHOMO_VERSION) /tmp/mihomo 2>/dev/null || true
	mv /tmp/mihomo $(HOME)/.local/bin/mihomo
	@echo "Installed to ~/.local/bin/mihomo"
	mihomo -v

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build:
	python -m build
