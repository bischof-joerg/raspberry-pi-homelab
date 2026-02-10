# Testing as crucial part of the development process

SHELL := /bin/bash
.DEFAULT_GOAL := help

# --- Platform detection ------------------------------------------------------

IS_PI  := $(shell grep -qi raspberry /proc/device-tree/model 2>/dev/null && echo yes || echo no)
IS_WSL := $(shell grep -qi microsoft /proc/version 2>/dev/null && echo yes || echo no)

# venv is intentionally WSL-only (Pi is deploy target)
USE_VENV := $(IS_WSL)

# --- Python tooling ----------------------------------------------------------

VENV_DIR := .venv

ifeq ($(USE_VENV),yes)
PY       := $(VENV_DIR)/bin/python
PIP      := $(VENV_DIR)/bin/pip
PYTEST   := $(PY) -m pytest
YAMLLINT := $(VENV_DIR)/bin/yamllint
RUFF     := $(VENV_DIR)/bin/ruff
else
PY       := python3
PIP      := python3 -m pip
PYTEST   := python3 -m pytest
YAMLLINT := yamllint
RUFF     := ruff
endif

# --- Pytest configuration ----------------------------------------------------

# Hard defaults (good hygiene + fast feedback)
PYTEST_STRICT ?= --strict-markers --maxfail=1
PYTEST_REPORT ?= -rA

# Arbitrary additional args without editing Makefile
# e.g. PYTEST_ARGS="-k expr -vv" make test
PYTEST_ARGS ?=

# Quiet mode toggle (0/1). If 1, adds -q.
PYTEST_QUIET ?= 0
ifeq ($(PYTEST_QUIET),1)
PYTEST_QUIET_FLAG := -q
else
PYTEST_QUIET_FLAG :=
endif

# Composite used by direct pytest invocations
PYTEST_BASE = $(PYTEST) $(PYTEST_QUIET_FLAG) $(PYTEST_STRICT) $(PYTEST_REPORT) $(PYTEST_ARGS)

# --- Repo paths (single source of truth) -------------------------------------

COMPOSE_FILE := stacks/monitoring/compose/docker-compose.yml

VMAGENT_CFG := stacks/monitoring/vmagent/vmagent.yml
VMALERT_CFG := stacks/monitoring/vmalert/vmalert.yml
VM_CFG      := stacks/monitoring/victoriametrics/victoriametrics.yml

# VictoriaLogs configuration (required)

# Alertmanager is generated -> repo contains template only
ALERTMANAGER_TMPL := stacks/monitoring/alertmanager/alertmanager.yml.tmpl

# Doctor behavior:
# - default: warn only if configs/templates are missing
# - strict: fail hard (exit 2)
VM_CONFIG_STRICT ?= 0

# Postdeploy behavior toggles used by tests
POSTDEPLOY_ON_TARGET ?= 0
VM_EXPECT_METRICS ?= 0
VM_EXPECT_JOBS ?= 0

# --- Phony targets -----------------------------------------------------------

.PHONY: help \
        venv venv-clean \
        precommit lint \
        ruff ruff-fix format \
        postdeploy postdeploy-endpoints postdeploy-vm \
        test \
        doctor doctor-strict \
        check check-all ci \
        _guard-wsl _guard-pi

# --- Help (authoritative; excludes internal _guard-* targets) ----------------

help: ## Show this help (auto-generated from target docstrings)
	@echo "Targets:"
	@awk 'BEGIN {FS=":.*## "}; \
	     /^[a-zA-Z0-9_.-]+:.*## / { \
	       if ($$1 !~ /^_guard-/) printf "  %-22s %s\n", $$1, $$2 \
	     } \
	    ' $(MAKEFILE_LIST)
	@echo
	@echo "Options (env vars):"
	@echo "  VM_CONFIG_STRICT=1        doctor fails if required configs/templates are missing (default: 0 = WARN)"
	@echo "  PYTEST_ARGS=\"...\"        append arbitrary pytest args (e.g. -k expr, -vv, -x, --lf)"
	@echo "  PYTEST_QUIET=1            add -q to pytest (default: 0)"
	@echo "  PYTEST_STRICT=\"...\"      override strict flags (default: --strict-markers --maxfail=1)"
	@echo "  PYTEST_REPORT=\"...\"      override reporting flags (default: -rA)"
	@echo
	@echo "Postdeploy test toggles (consumed by tests):"
	@echo "  POSTDEPLOY_ON_TARGET=1    mark tests as running on the Pi (default: 0)"
	@echo "  VM_EXPECT_METRICS=1       enable metric-existence expectations in VM query tests (default: 0)"
	@echo "  VM_EXPECT_JOBS=1          enable job-existence expectations in VM query tests (default: 0)"
	@echo
	@echo "Guardrails:"
	@echo "  - check/check-all/ci are WSL-only (fail fast on the Pi)."
	@echo "  - postdeploy targets are Pi-only (fail fast on non-Pi hosts)."
	@echo
	@echo "Alertmanager config:"
	@echo "  - Repo expects template: $(ALERTMANAGER_TMPL)"
	@echo "  - Rendered alertmanager.yml is runtime/postdeploy concern (generated on target)."

# --- Guards ------------------------------------------------------------------

_guard-wsl: ## Internal: fail if not running on WSL
	@set -euo pipefail; \
	if [ "$(IS_WSL)" != "yes" ]; then \
	  echo "FAIL: this target is WSL-only (run from WSL/CI workspace, not on the Pi)"; \
	  exit 2; \
	fi

_guard-pi: ## Internal: fail if not running on Raspberry Pi
	@set -euo pipefail; \
	if [ "$(IS_PI)" != "yes" ]; then \
	  echo "FAIL: this target is Pi-only (run on the Raspberry Pi deploy target)"; \
	  exit 2; \
	fi

# --- venv bootstrap ----------------------------------------------------------

venv: ## Create/update local venv (WSL only)
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
	@echo "venv: SKIP (WSL only by design)"
endif

venv-clean: ## Remove local venv (WSL only)
ifeq ($(USE_VENV),yes)
	@rm -rf "$(VENV_DIR)"
	@echo "Removed $(VENV_DIR)"
else
	@echo "venv-clean: SKIP (not on WSL)"
endif

# --- Ruff -------------------------------------------------------------------

ruff: _guard-wsl venv ## Run ruff lint checks (WSL/CI)
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing (make venv installs it)"; exit 2)
	$(RUFF) check .

ruff-fix: _guard-wsl venv ## Run ruff lint checks with autofix (WSL only)
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing (make venv installs it)"; exit 2)
	$(RUFF) check . --fix

format: _guard-wsl venv ## Run ruff formatter (WSL only)
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing (make venv installs it)"; exit 2)
	$(RUFF) format .

# --- Test targets ------------------------------------------------------------

precommit: _guard-wsl venv ## Run pre-commit test suite (pytest precommit marker)
	@command -v $(RUFF) >/dev/null 2>&1 && $(RUFF) check . || echo "WARN: ruff missing"
	@command -v $(RUFF) >/dev/null 2>&1 && $(RUFF) format --check . || true
	$(PYTEST_BASE) tests/precommit -m precommit

lint: _guard-wsl venv ## Run strict local lint gate (requires ruff)
	@command -v $(RUFF) >/dev/null 2>&1 || (echo "FAIL: ruff missing"; exit 2)
	$(RUFF) check .
	$(RUFF) format --check .
	$(PYTEST_BASE) tests/precommit -m lint

postdeploy: _guard-pi ## Run all post-deploy checks (Pi only) [supports POSTDEPLOY_ON_TARGET/VM_EXPECT_* + PYTEST_ARGS]
	@POSTDEPLOY_ON_TARGET=$(POSTDEPLOY_ON_TARGET) \
	  VM_EXPECT_METRICS=$(VM_EXPECT_METRICS) \
	  VM_EXPECT_JOBS=$(VM_EXPECT_JOBS) \
	  ./run-tests.sh $(PYTEST_QUIET_FLAG) $(PYTEST_STRICT) $(PYTEST_REPORT) $(PYTEST_ARGS) \
	    tests/postdeploy -m postdeploy

postdeploy-endpoints: _guard-pi ## Run only postdeploy endpoint tests (Pi only) [use PYTEST_ARGS for -k/-vv]
	@POSTDEPLOY_ON_TARGET=$(POSTDEPLOY_ON_TARGET) \
	  ./run-tests.sh $(PYTEST_QUIET_FLAG) $(PYTEST_STRICT) $(PYTEST_REPORT) $(PYTEST_ARGS) \
	    tests/postdeploy -m postdeploy -k endpoints

postdeploy-vm: _guard-pi ## Run only postdeploy VM query tests (Pi only) [set VM_EXPECT_METRICS=1 and/or VM_EXPECT_JOBS=1]
	@POSTDEPLOY_ON_TARGET=$(POSTDEPLOY_ON_TARGET) \
	  VM_EXPECT_METRICS=$(VM_EXPECT_METRICS) \
	  VM_EXPECT_JOBS=$(VM_EXPECT_JOBS) \
	  ./run-tests.sh $(PYTEST_QUIET_FLAG) $(PYTEST_STRICT) $(PYTEST_REPORT) $(PYTEST_ARGS) \
	    tests/postdeploy -m postdeploy -k "vm_query or vm_queries or victoriametrics or vmagent or vmalert"

test: _guard-wsl venv ## Run all tests via run-tests.sh (WSL-only) [supports PYTEST_ARGS]
	./run-tests.sh $(PYTEST_QUIET_FLAG) $(PYTEST_STRICT) $(PYTEST_REPORT) $(PYTEST_ARGS)

# --- Doctor -----------------------------------------------------------------

doctor: ## Check tooling/config for this repo (WSL/Pi) [VM_CONFIG_STRICT=1 makes missing configs/templates FAIL]
	@set -euo pipefail; \
	echo "== Repo =="; \
	git rev-parse --show-toplevel >/dev/null 2>&1 && echo "OK: inside git repo" || (echo "FAIL: not in git repo" && exit 2); \
	echo; \
	\
	echo "== Tools =="; \
	command -v python3 >/dev/null 2>&1 && python3 --version || (echo "FAIL: python3 missing" && exit 2); \
	echo "Using PY=$(PY)"; \
	$(PY) --version; \
	$(PYTEST) --version >/dev/null 2>&1 && $(PYTEST) --version || echo "WARN: pytest missing"; \
	command -v $(YAMLLINT) >/dev/null 2>&1 && $(YAMLLINT) --version || echo "WARN: yamllint missing"; \
	command -v $(RUFF) >/dev/null 2>&1 && $(RUFF) --version || echo "WARN: ruff missing"; \
	command -v gitleaks >/dev/null 2>&1 && gitleaks version || echo "WARN: gitleaks missing"; \
	command -v curl >/dev/null 2>&1 && curl --version | head -n 1 || echo "WARN: curl missing"; \
	echo; \
	\
	echo "== Docker/Compose =="; \
	command -v docker >/dev/null 2>&1 && docker --version || (echo "FAIL: docker missing" && exit 2); \
	docker compose version >/dev/null 2>&1 && docker compose version || echo "WARN: docker compose plugin not available"; \
	echo; \
	\
	echo "== Repo files =="; \
	test -f "$(COMPOSE_FILE)" && echo "OK: compose file present ($(COMPOSE_FILE))" || (echo "FAIL: compose file missing ($(COMPOSE_FILE))" && exit 2); \
	echo "VM_CONFIG_STRICT=$(VM_CONFIG_STRICT) (0=warn, 1=fail)"; \
	check_req(){ \
	  p="$$1"; label="$$2"; kind="$$3"; \
	  if [ -f "$$p" ]; then echo "OK: $$label $$kind present ($$p)"; \
	  else \
	    if [ "$(VM_CONFIG_STRICT)" = "1" ]; then \
	      echo "FAIL: $$label $$kind missing ($$p)"; \
	      exit 2; \
	    else \
	      echo "WARN: $$label $$kind missing ($$p)"; \
	    fi; \
	  fi; \
	}; \
	check_req "$(VMAGENT_CFG)" "vmagent" "config"; \
	check_req "$(VMALERT_CFG)" "vmalert" "config"; \
	check_req "$(VM_CFG)" "victoriametrics" "config"; \
	check_req "$(ALERTMANAGER_TMPL)" "alertmanager" "template"; \
	test -x ./deploy.sh && echo "OK: deploy.sh executable" || echo "WARN: deploy.sh not executable"; \
	echo; \
	\
	echo "== Python deps sanity =="; \
	$(PY) -c "import yaml, requests; print('OK: PyYAML + requests import')" >/dev/null 2>&1 || echo "WARN: missing PyYAML/requests"; \
	echo; \
	\
	echo "== Compose config validation (pytest) =="; \
	$(PYTEST) -q --strict-markers -m precommit tests/precommit -k compose_config \
	  && echo "OK: compose config validation passed" \
	  || (echo "FAIL: compose config validation failed" && exit 2); \
	echo; \
	\
	echo "== Secrets (Pi only) =="; \
	if [ "$(IS_PI)" = "yes" ]; then \
	  test -f /etc/raspberry-pi-homelab/monitoring.env \
	    && echo "OK: monitoring.env exists" \
	    || (echo "FAIL: monitoring.env missing" && exit 2); \
	  sudo test -r /etc/raspberry-pi-homelab/monitoring.env \
	    && echo "OK: monitoring.env readable by root" \
	    || (echo "FAIL: monitoring.env not readable by root" && exit 2); \
	else \
	  echo "SKIP: not on Raspberry Pi"; \
	fi; \
	echo

doctor-strict: ## Doctor in strict mode (equivalent to VM_CONFIG_STRICT=1 make doctor)
	@VM_CONFIG_STRICT=1 $(MAKE) doctor

# --- Aggregators (WSL-only) --------------------------------------------------

check: _guard-wsl venv ## Run local quality gate (WSL-only): doctor + ruff + precommit
	@set -euo pipefail; \
	$(MAKE) doctor; \
	$(MAKE) ruff; \
	$(MAKE) precommit; \
	echo "OK: check passed"

check-all: _guard-wsl venv ## Run full local gate (WSL-only): check + test
	@set -euo pipefail; \
	$(MAKE) check; \
	$(MAKE) test; \
	echo "OK: check-all passed"

ci: _guard-wsl venv ## Run CI gate (WSL-only): doctor-strict + ruff + lint + test (quiet)
	@set -euo pipefail; \
	$(MAKE) PYTEST_QUIET=1 VM_CONFIG_STRICT=1 doctor; \
	$(MAKE) PYTEST_QUIET=1 ruff; \
	$(MAKE) PYTEST_QUIET=1 lint; \
	$(MAKE) PYTEST_QUIET=1 test; \
	echo "OK: ci passed"
