# raspberry-pi-homelab
Raspberry PI HomeLab Repro

# commit and update workflow
## on WSL
- ```make precommit```     # concious and explicit, with pytest -m precommit -rs reasons for skipped tests are shown
- fix issues if needed and start from top
- git commit handling
    - ```git status```
    - ```git add ...```
    - ```git commit -m <>```

## CI
- ```make precommit```

## on PI after deploy
- ```cd ~/iac/raspberry-pi-homelab```
- ```git pull```
- Execute deploy with sudo: ```sudo ./deploy.sh```
    - Options for different modes
        - First deploy / after volume migration: Set permissions in safe manner: ```sudo RUN_INIT_PERMISSIONS=always ./deploy.sh```
        - Fast deploy without pull: ```sudo PULL_IMAGES=0 ./deploy.sh```
        - Deploy without tests (only in case of emergency): ```sudo RUN_TESTS=0 ./deploy.sh```

- Status/analysis of issues on deploy.sh failing:
    - Container status:
        - ```cd ~/iac/raspberry-pi-homelab```
        - ```docker compose -f monitoring/compose/docker-compose.yml ps```
    - Logs:
        - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color grafana```
        - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color prometheus```
        - ```docker compose -f monitoring/compose/docker-compose.yml logs -n 200 --no-color alertmanager```
    - Clean start of entire stack:
        - ```docker compose -f monitoring/compose/docker-compose.yml up -d --force-recreate```

## Don't do any longer to keep things stable
- no manual changes “live” on Pi (except to ```git pull``` + ```sudo ./deploy.sh```)
- no secrets in repo (instead approach to store them in /etc/.../secrets.env)
- init-permissions.sh not to execute on PI (recursive chown may last long dependent on amount of data) → execution is done by deploy.sh per default if needed.