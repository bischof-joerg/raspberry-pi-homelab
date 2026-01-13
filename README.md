# raspberry-pi-homelab

Raspberry PI HomeLab Repro

# Secrets

- Runtime secrets don't reside in repo, but root-only under: /etc/raspberry-pi-homelab/secrets.env (Mode 600, Owner root)

# Commit and update workflow

- Changes are prepared on WSL, tested, committed and pushed to GitHub.
- On Rasperry PI sources are only pulled and deployed.
- Testing is done via well defined make phases - check Makefile

## on WSL

- ```make precommit```     # concious and explicit, with pytest -m precommit -rs reasons for skipped tests are shown
- fix issues if needed and start from top
- ```make doctor```     # check on pre-requirements
- git commit handling like ...
  - ```git status```
  - ```git add ...```
  - ```git commit -m <>```

## CI

- ```make precommit```

## on PI after deploy

- ```cd ~/iac/raspberry-pi-homelab```
- ```git pull```
- ```sudo chown -R admin:admin ~/iac/raspberry-pi-homelab```   #Clean up ownership in Repo (to avoid permission chaos)
- ```make doctor```
- ```sudo ./deploy.sh```    #Execute deploy with sudo:
  - Options for different modes
    - First deploy / after volume migration: Set permissions in safe manner: ```sudo RUN_INIT_PERMISSIONS=always ./deploy.sh```
    - Fast deploy without pull: ```sudo PULL_IMAGES=0 ./deploy.sh```
    - Deploy without tests (only in case of emergency): ```sudo RUN_TESTS=0 ./deploy.sh```

- Status/analysis of issues on deploy.sh failing:
  - Container status:
    - ```cd ~/iac/raspberry-pi-homelab```
    - ```docker compose -f monitoring/compose/docker-compose.yml ps -all```
  - Logs:
    - ```docker compose -f monitoring/compose/docker-compose.yml logs --tail=200``` <br>
      and if too many, on individual services:
      - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color grafana```
      - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color prometheus```
      - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color alertmanager```
  - Clean start of entire stack:
    - ```docker compose -f monitoring/compose/docker-compose.yml up -d --force-recreate```
- Rollback (git revert) on deploy failure:

  - ```bash
    cd ~/iac/raspberry-pi-homelab
    git log --oneline --max-count=10
    ```

    - ```git revert <commit-sha>```
    - ```git pull --rebase```
    - ```sudo ./deploy.sh```
- Quick sanity check with posdeploy tests is always posible: ```make postdeploy```

## Don't do these things to stay stable

- no manual changes “live” on Pi, except to ```git pull``` + ```sudo ./deploy.sh```)
- no secrets in repo (instead approach to store them in /etc/.../secrets.env)
- init-permissions.sh not to execute on PI (recursive chown may last long dependent on amount of data) → execution is done by deploy.sh per default if needed.
