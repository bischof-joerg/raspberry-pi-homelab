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
	@command -v yamllint >/dev/null 2>&1 && yamllint --version || echo "WARN: yamllint missing (precommit lint test may skip/fail)"
	@command -v gitleaks >/dev/null 2>&1 && gitleaks version || echo "WARN: gitleaks missing (precommit secret scan may skip/fail)"
	@echo

	@echo "== Docker/Compose =="
	@command -v docker >/dev/null 2>&1 && docker --version || (echo "FAIL: docker missing" && exit 2)
	@docker compose version >/dev/null 2>&1 && docker compose version || echo "WARN: docker compose plugin not available here"
	@echo

	@echo "== Repo files =="
	@test -f monitoring/compose/docker-compose.yml && echo "OK: compose file present" || (echo "FAIL: compose file missing" && exit 2)
	@test -x ./deploy.sh && echo "OK: deploy.sh executable" || echo "WARN: deploy.sh not executable (chmod +x deploy.sh)"
	@echo

	@echo "== Secrets (Pi only) =="
	@if grep -qi raspberry /proc/device-tree/model 2>/dev/null; then \
	  test -f /etc/raspberry-pi-homelab/secrets.env && echo "OK: secrets file exists" || (echo "FAIL: /etc/raspberry-pi-homelab/secrets.env missing" && exit 2); \
	  sudo test -r /etc/raspberry-pi-homelab/secrets.env && echo "OK: secrets readable by root" || (echo "FAIL: secrets not readable by root" && exit 2); \
	else \
	  echo "SKIP: not on Raspberry Pi"; \
	fi
