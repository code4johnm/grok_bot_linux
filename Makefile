VERSION := $(shell tr -d '[:space:]' < VERSION)

.PHONY: help install uninstall deps docker-packages package docker-build docker-run check update check-update ubuntu-install rocky-install kali-install cli deb rpm

help:
	@echo "Targets:"
	@echo "  make install           User-local app + runtime packages"
	@echo "  make ubuntu-install    Ubuntu LTS helper (user-local; Debian/Mint ok)"
	@echo "  make rocky-install     Rocky Linux helper (user-local; RHEL/Alma ok)"
	@echo "  make kali-install      Kali Linux helper (user-local)"
	@echo "  make cli               Official Grok CLI (\$HOME/.grok/bin)"
	@echo "  make uninstall         Remove installed app files"
	@echo "  make update            Update wrapper, Grok Bot, and runtime packages"
	@echo "  make check-update      Show available updates"
	@echo "  make deps              Install GTK/Electron/VA-API packages"
	@echo "  make docker-packages   Install Docker Engine + Compose"
	@echo "  make package           Build dist/grok_bot_linux-$(VERSION)-linux-x64.tar.gz"
	@echo "  make deb               Build dist/grok-bot_$(VERSION)_amd64.deb"
	@echo "  make rpm               Build dist/grok-bot-$(VERSION)-*.rpm"
	@echo "  make docker-build      Build the GUI container image"
	@echo "  make docker-run        Run Grok Bot in Docker (needs X11)"
	@echo "  make check             Syntax-check scripts"

install:
	./install.sh --user

ubuntu-install:
	./scripts/install-ubuntu.sh --user --with-cli

rocky-install:
	./scripts/install-rocky.sh --user --with-cli

kali-install:
	./scripts/install-kali.sh --user --with-cli

cli:
	./scripts/install-cli.sh

uninstall:
	./uninstall.sh

update:
	./scripts/update.sh

check-update:
	./scripts/update.sh --check

deps:
	./scripts/install-deps.sh

docker-packages:
	./scripts/install-docker.sh

package:
	./scripts/build-package.sh

deb:
	./scripts/build-deb.sh

rpm:
	./scripts/build-rpm.sh

docker-build:
	docker compose -f docker/docker-compose.yml build

docker-run:
	xhost +local:docker >/dev/null 2>&1 || true
	docker compose -f docker/docker-compose.yml up --build

check:
	bash -n install.sh uninstall.sh launch.sh
	bash -n scripts/*.sh docker/entrypoint.sh
	docker compose -f docker/docker-compose.yml config >/dev/null
