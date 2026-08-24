PYTHON ?= python3
PREFIX ?= $(HOME)/.local
export PYTHONPATH := $(CURDIR)/src$(if $(PYTHONPATH),:$(PYTHONPATH))

.PHONY: all test install uninstall help

all:
	$(PYTHON) -m compileall -q src/grok_bot

help:
	@echo "Targets:"
	@echo "  make            Byte-compile the package (default)"
	@echo "  make test       Run offline pytest suite"
	@echo "  make install    Install to PREFIX (default ~/.local)"
	@echo "  make uninstall  Remove the installed files"

test:
	$(PYTHON) -m pytest -q

install:
	./install.sh --prefix "$(PREFIX)"

uninstall:
	./install.sh --prefix "$(PREFIX)" --uninstall
