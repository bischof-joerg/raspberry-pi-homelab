#!/usr/bin/env bash
set -eu

sudo mkdir -p \
  /srv/data/monitoring/grafana \
  /srv/data/monitoring/prometheus \
  /srv/data/monitoring/alertmanager

# Prometheus läuft typischerweise als nobody/nogroup (65534) im prom/prometheus Image
echo "Prometheus/Alertmanager UID expected: 65534"
sudo chown -R 65534:65534 /srv/data/monitoring/prometheus

# Grafana im grafana/grafana Image nutzt meist UID 472
echo "Grafana UID expected: 472"
sudo chown -R 472:472 /srv/data/monitoring/grafana

# Alertmanager (prom/alertmanager) läuft häufig als nobody (65534) – je nach Image/Config
echo "Alertmanager UID expected: 65534"
sudo chown -R 65534:65534 /srv/data/monitoring/alertmanager

sudo chmod -R u+rwX,go-rwx /srv/data/monitoring

echo "Permissions initialized under /srv/data/monitoring"
