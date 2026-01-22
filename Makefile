# Testing as crucial part of the development process

SHELL := /bin/bash

.PHONY: help venv venv-clean precommit lint postdeploy test doctor

help:
	@echo "Targets:"
	@echo "  make venv        Create/update local venv (WSL only)"
	@echo "  make precommit   Run pre-commit checks"
	@echo "  make lint        Run redundant sanity checks (subset of precommit)"
	@echo "  make postdeploy  Run post-deploy checks (Pi)"
	@echo "  make test        Run all tests"
	@echo "  make doctor      Check tooling/secrets for this repo (WSL/Pi)"

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
else
PY      := python3
PIP     := python3 -m pip
PYTEST  := python3 -m pytest
YAMLLINT:= yamllint
endif

PYTEST_STRICT = --strict-markers --maxfail=1
PYTEST_REPORT = -rA
# If slowest tests shall be identified, uncomment the following line and comment the above line
#PYTEST_REPORT = -rA --durations=5

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
	  echo "[venv] installing project (editable)"; \
	  "$(VENV_DIR)/bin/pip" install -e .; \
	else \
	  echo "[venv] installing minimal deps (pytest, yamllint)"; \
	  "$(VENV_DIR)/bin/pip" install pytest yamllint; \
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

# --- Test targets ------------------------------------------------------------

precommit: $(if $(filter yes,$(USE_VENV)),venv,)
	$(PYTEST) $(PYTEST_STRICT) $(PYTEST_REPORT) tests/precommit -m precommit

# redundant sanity checks run by GitHub pre-commit hook
lint: $(if $(filter yes,$(USE_VENV)),venv,)
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
	@command -v gitleaks >/dev/null 2>&1 && gitleaks version || echo "WARN: gitleaks missing (precommit secret scan may skip/fail)"
	@command -v promtool >/dev/null 2>&1 && promtool --version || echo "WARN: promtool missing (Prometheus config check will skip)"
	@command -v curl >/dev/null 2>&1 && curl --version | head -n 1 || echo "WARN: curl missing (endpoint checks will skip)"
	@echo

	@echo "== Docker/Compose =="
	@command -v docker >/dev/null 2>&1 && docker --version || (echo "FAIL: docker missing" && exit 2)
	@docker compose version >/dev/null 2>&1 && docker compose version || echo "WARN: docker compose plugin not available here"
	@echo

	@echo "== Repo files =="
	@test -f monitoring/compose/docker-compose.yml && echo "OK: compose file present" || (echo "FAIL: compose file missing" && exit 2)
	@test -f monitoring/prometheus/prometheus.yml && echo "OK: prometheus.yml present" || (echo "FAIL: prometheus.yml missing" && exit 2)
	@test -x ./deploy.sh && echo "OK: deploy.sh executable" || echo "WARN: deploy.sh not executable (chmod +x deploy.sh)"
	@echo

	@echo "== docker compose config (hermetic) =="
	@if docker compose version >/dev/null 2>&1; then \
	  bash -euo pipefail -c '\
	    tmp="$$(mktemp -d)"; \
	    trap "rm -rf $$tmp" EXIT; \
	    \
	    compose_env="$$tmp/compose.env"; \
	    if [ -f monitoring/compose/env.example ]; then \
	      cp monitoring/compose/env.example "$$compose_env"; \
	    else \
	      : > "$$compose_env"; \
	    fi; \
	    printf "GRAFANA_ADMIN_USER=admin\nGRAFANA_ADMIN_PASSWORD=changeme\n" >> "$$compose_env"; \
	    \
	    # create isolated copy of repo (no secrets, no .git) \
	    if command -v rsync >/dev/null 2>&1; then \
	      rsync -a --delete --exclude ".git" ./ "$$tmp/repo/"; \
	    else \
	      mkdir -p "$$tmp/repo"; \
	      tar -cf - --exclude=.git . | tar -xf - -C "$$tmp/repo"; \
	    fi; \
	    \
	    mkdir -p "$$tmp/repo/monitoring/alertmanager" "$$tmp/repo/monitoring/grafana"; \
	    if [ -f monitoring/alertmanager/alertmanager.env.example ]; then \
	      cp monitoring/alertmanager/alertmanager.env.example "$$tmp/repo/monitoring/alertmanager/alertmanager.env"; \
	    else \
	      : > "$$tmp/repo/monitoring/alertmanager/alertmanager.env"; \
	    fi; \
	    if [ -f monitoring/grafana/grafana.env.example ]; then \
	      cp monitoring/grafana/grafana.env.example "$$tmp/repo/monitoring/grafana/grafana.env"; \
	    else \
	      : > "$$tmp/repo/monitoring/grafana/grafana.env"; \
	    fi; \
	    \
	    cd "$$tmp/repo"; \
	    docker compose --env-file "$$compose_env" -f monitoring/compose/docker-compose.yml config >/dev/null; \
	    echo "OK: compose config valid"; \
	  '; \
	else \
	  echo "SKIP: docker compose plugin not available"; \
	fi
	@echo

	@echo "== promtool check (if available) =="
	@if command -v promtool >/dev/null 2>&1; then \
	  echo "Running: promtool check config"; \
	  promtool check config monitoring/prometheus/prometheus.yml && echo "OK: promtool config valid" || (echo "FAIL: promtool config invalid" && exit 2); \
	  if test -d monitoring/prometheus/rules; then \
	    echo "Running: promtool check rules"; \
	    promtool check rules monitoring/prometheus/rules/*.yml && echo "OK: promtool rules valid" || (echo "FAIL: promtool rules invalid" && exit 2); \
	  else \
	    echo "SKIP: no rules directory"; \
	  fi \
	else \
	  echo "SKIP: promtool not installed"; \
	fi
	@echo

	@echo "== Secrets (.env on Pi only) =="
	@if grep -qi raspberry /proc/device-tree/model 2>/dev/null; then \
	  test -f /etc/raspberry-pi-homelab/.env && echo "OK: /etc/raspberry-pi-homelab/.env exists" || (echo "FAIL: /etc/raspberry-pi-homelab/.env missing" && exit 2); \
	  sudo test -r /etc/raspberry-pi-homelab/.env && echo "OK: .env readable by root" || (echo "FAIL: .env not readable by root" && exit 2); \
	else \
	  echo "SKIP: not on Raspberry Pi"; \
	fi
	@echo

	@echo "== Local endpoints (Pi only, if curl available) =="
	@if grep -qi raspberry /proc/device-tree/model 2>/dev/null && command -v curl >/dev/null 2>&1; then \
	  echo "Checking Prometheus ready..."; \
	  curl -fsS http://localhost:9090/-/ready >/dev/null && echo "OK: Prometheus ready" || (echo "FAIL: Prometheus not ready" && exit 2); \
	  echo "Checking Alertmanager ready..."; \
	  curl -fsS http://localhost:9093/-/ready >/dev/null && echo "OK: Alertmanager ready" || (echo "FAIL: Alertmanager not ready" && exit 2); \
	  echo "Checking Grafana health (unauthenticated)..."; \
	  curl -fsS http://localhost:3000/api/health >/dev/null && echo "OK: Grafana health endpoint reachable" || (echo "FAIL: Grafana health endpoint not reachable" && exit 2); \
	else \
	  echo "SKIP: not on Raspberry Pi or curl missing"; \
	fi
	@echo

	@echo "== Doctor tests (pytest -m doctor) =="
	@$(PYTEST) -q --strict-markers -m doctor tests/doctor && echo "OK: doctor tests passed" || (echo "FAIL: doctor tests failed" && exit 2)
