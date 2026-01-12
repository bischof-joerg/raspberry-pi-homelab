# raspberry-pi-homelab
Raspberry PI HomeLab Repro


Um die Dateiverzeichzeichnisse auf dem Host anzulegen und korrekte Ownership zu setzen:
- nach git pull auf ~/src/raspberry-pi-homelab
- im compose verzeichnis ./init-permissions.sh aufrufen
    - einmalig Exec-Bit setzen (klein, aber praktisch): chmod +x init-permissions.sh

# commit and update workflow
## on WSL
make precommit     # concious and explicit
<potentially fix issues>
git add ...
git commit

## CI:
make precommit

## on PI after deploy:
cd ~/iac/raspberry-pi-homelab
git pull
docker compose -f monitoring/compose/docker-compose.yml pull
docker compose -f monitoring/compose/docker-compose.yml up -d
make postdeploy
<analyze whether there are issues>

