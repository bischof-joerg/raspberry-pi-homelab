# Testing as crucial part of the development process

# Define commands for different test phases
.PHONY: help precommit postdeploy test

help:
	@echo "Targets:"
	@echo "  make precommit   Run pre-commit checks"
	@echo "  make postdeploy  Run post-deploy checks (Pi)"
	@echo "  make test        Run all tests"

IS_PI := $(shell grep -qi raspberry /proc/device-tree/model 2>/dev/null && echo yes || echo no)

PYTEST_STRICT = --strict-markers --maxfail=1
PYTEST_REPORT = -rA 
# If slowest tests shall be identified, uncomment the following line and comment the above line
#PYTEST_REPORT = -rA --durations=5

precommit:
	pytest $(PYTEST_STRICT) $(PYTEST_REPORT) tests/precommit -m precommit

postdeploy:
	ifeq ($(IS_PI),yes)
		./run-tests.sh tests/postdeploy -m postdeploy
	else
		@echo "postdeploy tests are intended to run on the Raspberry Pi"
		@exit 1
	endif

test:
	./run-tests.sh

