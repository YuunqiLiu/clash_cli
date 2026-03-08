.PHONY: install dev test test-unit test-integration test-build build download-mihomo clean install-mihomo build-clean

# ── Config ────────────────────────────────────────────────────
DOCKER_IMAGE   := ghcr.io/yuunqiliu/centos7-gcc14:latest
BUILD_TAG      := clash-cli-build
BUILD_DIR      := build
BINARY         := $(BUILD_DIR)/clash
MIHOMO_VERSION ?= v1.19.0

# ── Dev setup ─────────────────────────────────────────────────
install:
	pip install .

dev:
	pip install -e ".[dev]"

# ── Tests (source code) ───────────────────────────────────────
# Run only unit tests (no mihomo binary needed, fast)
test-unit:
	python -m pytest -v -m "not integration" --tb=short

# Run integration tests (requires mihomo in PATH or CLASH_MIHOMO_PATH)
test-integration:
	python -m pytest tests/integration/ -v -m integration --tb=short

# Run unit + integration tests
test: test-unit test-integration

# ── Build ─────────────────────────────────────────────────────
# Build single-file executable via PyInstaller in Docker.
# Downloads mihomo $(MIHOMO_VERSION) during the build.
# Output: build/clash  — then immediately runs test-build to verify.
build:
	@echo "============================================================"
	@echo "  Building clash (PyInstaller + Docker)"
	@echo "============================================================"
	mkdir -p $(BUILD_DIR)
	docker build \
		--network host \
		--build-arg MIHOMO_VERSION=$(MIHOMO_VERSION) \
		-f Dockerfile.build \
		-t $(BUILD_TAG) \
		.
	docker create --name clash-cli-extract $(BUILD_TAG) /bin/true
	docker cp clash-cli-extract:/src/dist/clash $(BINARY)
	docker rm clash-cli-extract
	@chmod +x $(BINARY)
	@echo ""
	@echo "  Built: $(BINARY)"
	@ls -lh $(BINARY)
	@echo ""
	@echo "  Running build verification..."
	$(MAKE) test-build

# ── Test built binary ─────────────────────────────────────────
# Verify the binary on bare CentOS 7 (minimal glibc 2.17 deps).
test-build: $(BINARY)
	@echo "============================================================"
	@echo "  Testing clash binary on bare CentOS 7"
	@echo "============================================================"
	docker run --rm \
		-v $(CURDIR)/$(BUILD_DIR):/build:ro \
		-v $(CURDIR)/scripts:/scripts:ro \
		$(DOCKER_IMAGE) \
		bash /scripts/test_build.sh /build/clash

# ── Local mihomo (for integration tests) ─────────────────────
install-mihomo:
	@echo "Downloading Mihomo $(MIHOMO_VERSION)..."
	wget -q "https://github.com/MetaCubeX/mihomo/releases/download/$(MIHOMO_VERSION)/mihomo-linux-amd64-$(MIHOMO_VERSION).gz" -O /tmp/mihomo.gz
	gunzip -f /tmp/mihomo.gz
	find /tmp -maxdepth 1 -name "mihomo*" -type f | head -1 | xargs -I{} mv {} $(HOME)/.local/bin/mihomo
	chmod +x $(HOME)/.local/bin/mihomo
	@echo "Installed to ~/.local/bin/mihomo"
	mihomo -v

# ── Misc ──────────────────────────────────────────────────────
clean:
	rm -rf $(BUILD_DIR) dist __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	docker rmi $(BUILD_TAG) 2>/dev/null || true

build-clean: clean build

