# Testing as crucial part of the development process

SHELL := /bin/bash
.DEFAULT_GOAL := help

# --- Platform detection ------------------------------------------------------

IS_PI  := $(shell grep -qi raspberry /proc/device-tree/model 2>/dev/null && echo yes || echo no)
IS_WSL := $(shell grep -qi microsoft /proc/version 2>/dev/null && echo yes || echo no)
IS_CI := $(shell test -n "$$GITHUB_ACTIONS" && echo yes || echo no)

# venv is intentionally only in WSL and GitHub (Pi is deploy target)
USE_VENV := $(if $(filter yes,$(IS_WSL) $(IS_CI)),yes,no)

# --- Python tooling ----------------------------------------------------------

VENV_DIR := .venv

ifeq ($(USE_VENV),yes)
PY       := $(VENV_DIR)/bin/python
PIP      := $(VENV_DIR)/bin/pip
PYTEST   := $(PY) -m pytest
YAMLLINT := $(VENV_DIR)/bin/yamllint
RUFF     := $(VENV_DIR)/bin/ruff
PRE_COMMIT := $(VENV_DIR)/bin/pre-commit
else
PY       := python3
PIP      := python3 -m pip
PYTEST   := python3 -m pytest
YAMLLINT := yamllint
RUFF     := ruff
PRE_COMMIT := pre-commit
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

# Alertmanager is generated -> repo contains template only
ALERTMANAGER_TMPL := stacks/monitoring/alertmanager/alertmanager.yml.tmpl

# --- Strictness knobs --------------------------------------------------------

# If 1, doctor fails when a required config/template file is missing
VM_CONFIG_STRICT ?= 0

# Postdeploy behavior toggles used by tests
POSTDEPLOY_ON_TARGET ?= 0
VM_EXPECT_METRICS ?= 0
VM_EXPECT_JOBS ?= 0

# --- Phony targets -----------------------------------------------------------

.PHONY: help \
        venv venv-clean \
        hooks precommit \
        ruff ruff-fix format \
        postdeploy postdeploy-endpoints postdeploy-vm \
        test tests \
        doctor doctor-strict \
        check ci-doctor ci-precommit ci-tests ci \
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
	@echo "  - check/ci and ci-* targets are WSL-only (fail fast on the Pi)."
	@echo "  - postdeploy targets are Pi-only (fail fast on non-Pi hosts)."
	@echo
	@echo "Alertmanager config:"
	@echo "  - Repo expects template: $(ALERTMANAGER_TMPL)"
	@echo "  - Rendered alertmanager.yml is runtime/postdeploy concern (generated on target)."

# --- Guards ------------------------------------------------------------------

_guard-wsl: ## Internal: fail if not running on WSL
	@set -euo pipefail; \
	if [ "$(IS_PI)" = "yes" ]; then \
	  echo "FAIL: this target is dev/CI-only (must not run on the Raspberry Pi)"; \
	  exit 2; \
	fi; \
	if [ "$(IS_WSL)" != "yes" ] && [ "$(IS_CI)" != "yes" ]; then \
	  echo "FAIL: this target is WSL/CI-only (run from WSL or GitHub Actions)"; \
	  exit 2; \
	fi

_guard-pi: ## Internal: fail if not running on Raspberry Pi
	@set -euo pipefail; \
	if [ "$(IS_PI)" != "yes" ]; then \
	  echo "FAIL: this target is Pi-only (run on the Raspberry Pi deploy target)"; \
	  exit 2; \
	fi

# --- Virtualenv --------------------------------------------------------------

venv: ## Create local venv and install dev requirements (WSL only)
ifeq ($(USE_VENV),yes)
	@set -euo pipefail; \
	if [ ! -x "$(VENV_DIR)/bin/python" ]; then \
	  echo "[venv] creating $(VENV_DIR)"; \
	  python3 -m venv "$(VENV_DIR)"; \
	fi; \
	echo "[venv] upgrading pip"; \
	"$(VENV_DIR)/bin/pip" install -U pip >/dev/null; \
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

hooks: _guard-wsl venv ## Run pre-commit hooks only (all files)
	@command -v $(PRE_COMMIT) >/dev/null 2>&1 || { \
	  echo "ERROR: pre-commit not found."; \
	  echo "HINT: run: make venv && $(PIP) install -r requirements-dev.txt"; \
	  exit 2; \
	}
	@$(PRE_COMMIT) run --all-files --show-diff-on-failure

precommit: _guard-wsl venv ## Run pre-commit hooks + python precommit tests (WSL/CI)
	@echo "== pre-commit hooks =="
	@$(MAKE) hooks
	@echo
	@echo "== pytest (tests/precommit, marker=precommit) =="
	$(PYTEST_BASE) tests/precommit -m precommit

# Unit/integration test suite (WSL/CI) explicitly excludes Pi-only postdeploy tests.
# This keeps CI deterministic and fast, while postdeploy remains a separate on-target gate.
test: _guard-wsl venv ## Run unit/integration tests (excludes tests/postdeploy + tests/precommit)
	./run-tests.sh $(PYTEST_QUIET_FLAG) $(PYTEST_STRICT) $(PYTEST_REPORT) $(PYTEST_ARGS) \
	  tests -m "not postdeploy" --ignore=tests/postdeploy --ignore=tests/precommit

tests: test ## Alias for `make test` (useful for CI job naming)

postdeploy: _guard-pi ## Run all post-deploy checks (Pi only)
	@POSTDEPLOY_ON_TARGET=1 \
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
	command -v $(PRE_COMMIT) >/dev/null 2>&1 && $(PRE_COMMIT) --version || echo "WARN: pre-commit missing"; \
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
	echo

doctor-strict: ## Doctor in strict mode (equivalent to VM_CONFIG_STRICT=1 make doctor)
	@VM_CONFIG_STRICT=1 $(MAKE) doctor

# --- Aggregators (WSL-only) --------------------------------------------------

check: _guard-wsl venv ## Run local quality gate (WSL-only): doctor + precommit + tests
	@set -euo pipefail; \
	$(MAKE) doctor; \
	$(MAKE) precommit; \
	$(MAKE) test; \
	echo "OK: check passed"

# CI job-friendly targets (separate GitHub Actions jobs can call these)
ci-doctor: _guard-wsl venv ## CI job: doctor in strict mode (quiet)
	@$(MAKE) PYTEST_QUIET=1 VM_CONFIG_STRICT=1 doctor

ci-precommit: _guard-wsl venv ## CI job: precommit hooks + tests/precommit (quiet)
	@$(MAKE) PYTEST_QUIET=1 precommit

ci-tests: _guard-wsl venv ## CI job: unit/integration tests (quiet)
	@$(MAKE) PYTEST_QUIET=1 test

ci: _guard-wsl venv ## Run full CI gate (WSL-only): ci-doctor + ci-precommit + ci-tests
	@set -euo pipefail; \
	$(MAKE) ci-doctor; \
	$(MAKE) ci-precommit; \
	$(MAKE) ci-tests; \
	echo "OK: ci passed"
