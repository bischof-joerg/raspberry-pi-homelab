# Testing as crucial part of the development process

SHELL := /bin/bash

.PHONY: help venv venv-clean precommit lint postdeploy test doctor ruff ruff-fix format

help:
	@echo "Targets:"
	@echo "  make venv        Create/update local venv (WSL only)"
	@echo "  make precommit   Run pre-commit checks"
	@echo "  make lint        Run redundant sanity checks (subset of precommit)"
	@echo "  make ruff        Run ruff lint checks"
	@echo "  make ruff-fix    Run ruff lint checks with autofix"
	@echo "  make format      Run ruff formatter"
	@echo "  make postdeploy  Run post-deploy checks (Pi)"
	@echo "  make test        Run all tests"
	@echo "  make doctor      Check tooling/config for this repo (WSL/Pi)"

# --- Platform detection ------------------------------------------------------

IS_PI  := $(shell grep -qi raspberry /proc/device-tree/model 2>/dev/null && echo yes || echo no)
IS_WSL := $(shell grep -qi microsoft /proc/version 2>/dev/null && echo yes || echo no)

# venv should be used automatically ONLY on WSL (per your requirement), not on the Pi.
USE_VENV := $(IS_WSL)

# --- Python tooling ----------------------------------------------------------

VENV_DIR := .venv

ifeq ($(USE_VENV),yes)
PY      := $(VENV_DIR)/bin/python
PIP     := $(VENV_DIR)/bin/pip
PYTEST  := $(PY) -m pytest
YAMLLINT:= $(VENV_DIR)/bin/yamllint
RUFF    := $(VENV_DIR)/bin/ruff
else
PY      := python3
PIP     := python3 -m pip
PYTEST  := python3 -m pytest
YAMLLINT:= yamllint
RUFF    := ruff
endif

PYTEST_STRICT = --strict-markers --maxfail=1
PYTEST_REPORT = -rA

# --- Repo paths --------------------------------------------------------------

COMPOSE_NEW := stacks/monitoring/compose/docker-compose.yml
COMPOSE_OLD := monitoring/compose/docker-compose.yml

VMAGENT_CFG := stacks/monitoring/vmagent/vmagent.yml
VMALERT_CFG := stacks/monitoring/vmalert/vmalert.yml
ALERTMANAGER_CFG := stacks/monitoring/alertmanager/alertmanager.yml
VM_CFG := stacks/monitoring/victoriametrics/victoriametrics.yml

# --- venv bootstrap ----------------------------------------------------------

venv:
ifeq ($(USE_VENV),yes)
	@set -euo pipefail; \
	if [ ! -d "$(VENV_DIR)" ]; then \
	  echo "[venv] creating $(VENV_DIR)"; \
	  python3 -m venv "$(VENV_DIR)"; \
	fi; \
	echo "[venv] upgrading pip"; \
	"$(VENV_DIR)/bin/python" -m pip install -U pip >/dev/null; \
	if [ -f requirements-dev.txt ]; then \
	  echo "[venv] installing requirements-dev.txt"; \
	  "$(VENV_DIR)/bin/pip" install -r requirements-dev.txt; \
	elif [ -f pyproject.toml ]; then \
	  echo "[venv] installing project (editable) with dev extras"; \
	  "$(VENV_DIR)/bin/pip" install -e ".[dev]"; \
	else \
	  echo "[venv] installing minimal deps (pytest, yamllint, ruff)"; \
	  "$(VENV_DIR)/bin/pip" install pytest yamllint ruff; \
	fi
else
	@echo "venv: SKIP (venv is only used on WSL by design)"
endif

venv-clean:
ifeq ($(USE_VENV),yes)
	@rm -rf "$(VENV_DIR)"
	@echo "Removed $(VENV_DIR)"
else
	@echo "venv-clean: SKIP (not on WSL)"
endif

# --- Ruff -------------------------------------------------------------------

ruff: $(if $(filter yes,$(USE_VENV)),venv,)
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing (install via venv/pyproject dev extras)"; exit 2)
	$(RUFF) check .

ruff-fix: $(if $(filter yes,$(USE_VENV)),venv,)
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing (install via venv/pyproject dev extras)"; exit 2)
	$(RUFF) check . --fix

format: $(if $(filter yes,$(USE_VENV)),venv,)
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing (install via venv/pyproject dev extras)"; exit 2)
	$(RUFF) format .

# --- Test targets ------------------------------------------------------------

precommit: $(if $(filter yes,$(USE_VENV)),venv,)
	# Ruff is fast and should be part of precommit
	@command -v $(RUFF) >/dev/null 2>&1 && $(RUFF) check . || echo "WARN: ruff missing (precommit will still run pytest suite)"
	@command -v $(RUFF) >/dev/null 2>&1 && $(RUFF) format --check . || true
	$(PYTEST) $(PYTEST_STRICT) $(PYTEST_REPORT) tests/precommit -m precommit

lint: $(if $(filter yes,$(USE_VENV)),venv,)
	# Lint is a stricter local gate: require ruff
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing (make venv installs it via .[dev])"; exit 2)
	$(RUFF) check .
	$(RUFF) format --check .
	$(PYTEST) $(PYTEST_STRICT) $(PYTEST_REPORT) tests/precommit -m lint

ifeq ($(IS_PI),yes)
postdeploy:
	./run-tests.sh $(PYTEST_STRICT) $(PYTEST_REPORT) tests/postdeploy -m postdeploy
else
postdeploy:
	@echo "postdeploy tests are intended to run on the Raspberry Pi"
	@exit 1
endif

test:
	./run-tests.sh $(PYTEST_STRICT) $(PYTEST_REPORT)

# --- Doctor -----------------------------------------------------------------

doctor: $(if $(filter yes,$(USE_VENV)),venv,)
	@echo "== Repo =="
	@git rev-parse --show-toplevel >/dev/null 2>&1 && echo "OK: inside git repo" || (echo "FAIL: not in git repo" && exit 2)
	@echo

	@echo "== Tools =="
	@command -v python3 >/dev/null 2>&1 && python3 --version || (echo "FAIL: python3 missing" && exit 2)
	@echo "Using PY=$(PY)"
	@$(PY) --version
	@$(PYTEST) --version >/dev/null 2>&1 && $(PYTEST) --version || echo "WARN: pytest missing (needed for tests)"
	@command -v $(YAMLLINT) >/dev/null 2>&1 && $(YAMLLINT) --version || echo "WARN: yamllint missing (precommit lint may skip/fail)"
	@command -v $(RUFF) >/dev/null 2>&1 && $(RUFF) --version || echo "WARN: ruff missing (ruff checks will fail/skip depending on target)"
	@command -v gitleaks >/dev/null 2>&1 && gitleaks version || echo "WARN: gitleaks missing (precommit secret scan may skip/fail)"
	@command -v curl >/dev/null 2>&1 && curl --version | head -n 1 || echo "WARN: curl missing (endpoint checks will skip)"
	@echo

	@echo "== Docker/Compose =="
	@command -v docker >/dev/null 2>&1 && docker --version || (echo "FAIL: docker missing" && exit 2)
	@docker compose version >/dev/null 2>&1 && docker compose version || echo "WARN: docker compose plugin not available here"
	@echo

	@echo "== Repo files =="
	@if [ -f "$(COMPOSE_NEW)" ]; then echo "OK: compose file present ($(COMPOSE_NEW))"; \
	elif [ -f "$(COMPOSE_OLD)" ]; then echo "OK: compose file present ($(COMPOSE_OLD))"; \
	else echo "FAIL: compose file missing"; exit 2; fi
	@test -f "$(VMAGENT_CFG)" && echo "OK: vmagent config present ($(VMAGENT_CFG))" || echo "WARN: vmagent config missing ($(VMAGENT_CFG))"
	@test -f "$(VMALERT_CFG)" && echo "OK: vmalert config present ($(VMALERT_CFG))" || echo "WARN: vmalert config missing ($(VMALERT_CFG))"
	@test -f "$(ALERTMANAGER_CFG)" && echo "OK: alertmanager config present ($(ALERTMANAGER_CFG))" || echo "WARN: alertmanager config missing ($(ALERTMANAGER_CFG))"
	@test -f "$(VM_CFG)" && echo "OK: victoriametrics config present ($(VM_CFG))" || echo "WARN: victoriametrics config missing ($(VM_CFG))"
	@test -x ./deploy.sh && echo "OK: deploy.sh executable" || echo "WARN: deploy.sh not executable (chmod +x deploy.sh)"
	@echo

	@echo "== Python deps sanity =="
	@$(PY) -c "import yaml, requests; print('OK: PyYAML + requests import')" >/dev/null 2>&1 || echo "WARN: missing PyYAML/requests (install via requirements-dev.txt / make venv)"
	@echo

	@echo "== Compose config validation (pytest) =="
	@$(PYTEST) -q --strict-markers -m precommit tests/precommit -k compose_config && echo "OK: compose config validation passed" || (echo "FAIL: compose config validation failed" && exit 2)
	@echo

	@echo "== Secrets (Pi only) =="
	@if grep -qi raspberry /proc/device-tree/model 2>/dev/null; then \
	  test -f /etc/raspberry-pi-homelab/monitoring.env && echo "OK: /etc/raspberry-pi-homelab/monitoring.env exists" || (echo "FAIL: monitoring.env missing" && exit 2); \
	  sudo test -r /etc/raspberry-pi-homelab/monitoring.env && echo "OK: monitoring.env readable by root" || (echo "FAIL: monitoring.env not readable by root" && exit 2); \
	else \
	  echo "SKIP: not on Raspberry Pi"; \
	fi
	@echo
