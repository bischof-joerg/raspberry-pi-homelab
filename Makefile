# Testing as crucial part of the development process

# Define commands for different test phases
.PHONY: help precommit postdeploy test doctor

help:
	@echo "Targets:"
	@echo "  make precommit   Run pre-commit checks"
	@echo "  make postdeploy  Run post-deploy checks (Pi)"
	@echo "  make test        Run all tests"
	@echo "  make doctor      Check tooling/secrets for this repo (WSL/Pi)"


IS_PI := $(shell grep -qi raspberry /proc/device-tree/model 2>/dev/null && echo yes || echo no)

PYTEST_STRICT = --strict-markers --maxfail=1
PYTEST_REPORT = -rA 
# If slowest tests shall be identified, uncomment the following line and comment the above line
#PYTEST_REPORT = -rA --durations=5

precommit:
	pytest $(PYTEST_STRICT) $(PYTEST_REPORT) tests/precommit -m precommit

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

doctor:
	@echo "== Repo =="
	@git rev-parse --show-toplevel >/dev/null 2>&1 && echo "OK: inside git repo" || (echo "FAIL: not in git repo" && exit 2)
	@echo

	@echo "== Tools =="
	@command -v python3 >/dev/null 2>&1 && python3 --version || (echo "FAIL: python3 missing" && exit 2)
	@command -v pytest >/dev/null 2>&1 && pytest --version || echo "WARN: pytest missing (needed for tests)"
	@command -v yamllint >/dev/null 2>&1 && yamllint --version || echo "WARN: yamllint missing (precommit lint may skip/fail)"
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

	@echo "== Secrets (Pi only) =="
	@if grep -qi raspberry /proc/device-tree/model 2>/dev/null; then \
	  test -f /etc/raspberry-pi-homelab/secrets.env && echo "OK: secrets file exists" || (echo "FAIL: /etc/raspberry-pi-homelab/secrets.env missing" && exit 2); \
	  sudo test -r /etc/raspberry-pi-homelab/secrets.env && echo "OK: secrets readable by root" || (echo "FAIL: secrets not readable by root" && exit 2); \
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

