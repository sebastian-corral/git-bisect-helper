# git-autobisect developer tasks. Install targets come in a later task.

# Use the tools from a local virtualenv when one exists.
ifneq ($(wildcard .venv/bin),)
export PATH := $(CURDIR)/.venv/bin:$(PATH)
endif

RUFF ?= ruff
SHELLCHECK ?= shellcheck
PYTEST ?= pytest
BATS ?= bats

SHELL_SOURCES := bin/git-autobisect $(wildcard tests/e2e/*.bats)

.PHONY: lint test

lint:
	$(RUFF) check .
	$(RUFF) format --check .
	$(SHELLCHECK) $(SHELL_SOURCES)

test:
	$(PYTEST)
	$(BATS) tests/e2e
