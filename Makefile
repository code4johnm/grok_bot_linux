VERSION := $(shell tr -d '[:space:]' < VERSION)

.PHONY: help install uninstall deps docker-packages package docker-build docker-run check

help:
	@echo "Targets:"
	@echo "  make install           Install app + runtime packages"
	@echo "  make uninstall         Remove installed app files"
	@echo "  make deps              Install GTK/Electron/VA-API packages"
	@echo "  make docker-packages   Install Docker Engine + Compose"
	@echo "  make package           Build dist/grok_bot_linux-$(VERSION)-linux-x64.tar.gz"
	@echo "  make docker-build      Build the GUI container image"
	@echo "  make docker-run        Run Grok Bot in Docker (needs X11)"
	@echo "  make check             Syntax-check scripts"

install:
	./install.sh

uninstall:
	./uninstall.sh

deps:
	./scripts/install-deps.sh

docker-packages:
	./scripts/install-docker.sh

package:
	./scripts/build-package.sh

docker-build:
	docker compose -f docker/docker-compose.yml build

docker-run:
	xhost +local:docker >/dev/null 2>&1 || true
	docker compose -f docker/docker-compose.yml up --build

check:
	bash -n install.sh uninstall.sh launch.sh
	bash -n scripts/*.sh docker/entrypoint.sh
	docker compose -f docker/docker-compose.yml config >/dev/null
