# Development Workflow

## Workflow Overview

1. Changes are prepared on WSL
2. Tested by using ```pytest -q```
3. Commit and push to GitHub
4. On Rasperry Pi sources are only pulled from Git and deployed
5. Ideally, no manual changes are performed on the Pi
6. Secure defaults, hardening and reviewed / new tests is part of integrating new services

## on WSL

- git commit handling in Visual Studio or explicitely ...
  - ```git status```
  - ```git add ...```
  - ```git commit -m <>```
  - Note: GitHub commit comprises tests via a pre-commit hook
- ```pytest -q``` executes all tests on WSL in the (.venv), i.e. it includes
  - ```make precommit``` conscious and explicit, with pytest -m precommit -rs reasons for skipped tests are shown
  - ```make doctor```  check on pre-requirements
  - GitHub pre-commit checks as defined in .pre-commit-config.yaml
- fix issues if needed and start from top

~~~text
Note: A virtual environment is used on WSL and automatically called by the make phases.
The repro local Python Virtual Environment '(.venv)' is used as well for local development.
The following commancds manually activate and deactive it:
    - to activate '(.venv)': ```source .venv/bin/activate```
    - to deactive in '(.venv)': ```deactivate```
~~~

## CI

CI mirrors the local precommit workflow to ensure parity between
developer machines and automated checks. The test phases on WSL automatically lunch the virtual environment (.venv)

- ```make precommit```
- ```make doctor```
- in (.venv) on WSL optionally: ```pre-commit run --all-files``` to run GitHub pre-commit checks in virtual environment (.venv)
- the partially to Git-Hub pre-commit hook redundant lint tests can optionally be executed with ```make lint```

## on PI after deploy

- ```cd ~/iac/raspberry-pi-homelab```
- ```git pull```
- ```make doctor```
- ```sudo ./deploy.sh```    #Execute deploy with sudo:
  - The deploy scribed automatically launches the post deploy tests
  - Options for different modes
    - First deploy / after volume migration: Set permissions in safe manner: ```sudo RUN_INIT_PERMISSIONS=always ./deploy.sh```
    - Fast deploy without pull: ```sudo PULL_IMAGES=0 ./deploy.sh```
    - Deploy without tests (only in case of emergency): ```sudo RUN_TESTS=0 ./deploy.sh```

- Status/analysis of issues on deploy.sh failing:
  - Container status:
    - ```cd ~/iac/raspberry-pi-homelab```
    - ```docker compose -f monitoring/compose/docker-compose.yml ps -all```
  - Logs:
    - ```docker compose -f monitoring/compose/docker-compose.yml logs --tail=200```
      and if too many, on individual services:
      - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color grafana```
      - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color prometheus```
      - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color alertmanager```
  - Clean start of entire stack:
    - ```docker compose -f monitoring/compose/docker-compose.yml up -d --force-recreate```
- Rollback (git revert) on deploy failure:

  - Note: Reverting commits that include data migrations may require manual validation of volumes.

  - ~~~bash
    cd ~/iac/raspberry-pi-homelab
    git log --oneline --max-count=10
    ~~~

    - ```git revert <commit-sha>```
    - ```git pull --rebase```
    - ```sudo ./deploy.sh```
- Quick sanity check with postdeploy tests is always posible: ```make postdeploy```

## Operational Guardrails (Do Not Violate)

- No manual changes on the Raspberry Pi (except git pull + sudo ./deploy.sh)
- No secrets committed to Git (use /etc/.../.env)
- init-permissions.sh must not be run manually on the Pi

## Failure Handling Philosophy

- Failing fast is preferred over partial deploys
- Deployments are expected to be repeatable and idempotent
- Git history is the source of truth for rollback and recovery
