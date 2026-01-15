# Grafana Dashboard Download & Update Workflow

This document describes the **workflow, scripts, and reasoning** behind downloading, updating, normalizing, and validating Grafana dashboards from Grafana.com (GNet) into this repository. The goal is a **repeatable, conflict-free, Git-driven workflow** that works reliably with **Grafana provisioning** and avoids UI-side drift.

---

## 1. Design Goals

The workflow is designed to ensure:

* **Idempotency**: Re-running scripts does not create noise or conflicts
* **Version awareness**: Dashboards are only downloaded when a newer revision exists
* **Provisioning safety**: Dashboards work with file-based provisioning
* **Datasource portability**: No hard-coded datasource UIDs or names
* **CI compatibility**: Dashboards pass JSON, lint, and compose checks
* **WSL-first workflow**: All changes are prepared and reviewed before deployment

---

## 2. Repository Structure (Relevant Parts)

```text
monitoring/
└── grafana/
    ├── dashboards/
    │   ├── docker/
    │   │   ├── docker-overview-21743.json
    │   │   ├── docker-engine-health-21040.json
    │   │   └── ...
    │   └── system/
    │       ├── node-exporter-full-1860.json
    │       ├── prometheus-metrics-management-19341.json
    │       └── ...
    └── provisioning/
        └── dashboards/
            └── dashboards.yml

scripts/
└── grafana/
    ├── download-gnet.sh
    ├── normalize-dashboard.py
    └── validate_dashboards.sh
```

---

## 3. High-Level Workflow

The complete workflow consists of **five deterministic phases**:

1. **Define dashboards to manage** (IDs, folders)
2. **Download dashboards from GNet** (only if newer)
3. **Normalize dashboards** (datasource, IDs, templating)
4. **Validate dashboards** (structural + semantic checks)
5. **Deploy via provisioning** (Grafana reads from filesystem)

Each phase is script-driven and Git-visible.

---

## 4. Dashboard Download

This step is fully automated and driven by scripts plus two small state/metadata files that live in the repository. Together, they ensure **idempotent, version-aware, GitOps-safe dashboard updates**.

### 4.1 Involved Files

#### `scripts/grafana/download-gnet.sh`

The main orchestration script responsible for:

* Querying Grafana.com (gnet) for dashboards by ID
* Detecting whether a newer revision exists
* Downloading dashboards only when necessary
* Writing raw dashboard JSONs into the correct folder

This script is **safe to run repeatedly** and produces no changes if no upstream updates exist.

---

#### `monitoring/grafana/dashboards/manifest.json`

The **authoritative manifest** describing which dashboards are managed by GitOps.

Example structure:

```json
{
  "docker": {
    "21743": "docker/docker-overview-21743.json",
    "193": "docker/docker-container-resource-usage-193.json",
    "21040": "docker/docker-engine-health-21040.json"
  },
  "system": {
    "1860": "system/node-exporter-full-1860.json",
    "9578": "system/alertmanager-9578.json",
    "19341": "system/prometheus-metrics-overview-19341.json"
  }
}
```

**Responsibilities:**

* Defines *which* dashboards are tracked
* Defines *where* they are stored (folder + filename)
* Acts as the single source of truth for downloads
* Prevents accidental dashboard sprawl or UI-only imports

Adding or removing dashboards is done **only** by editing this file.

---

#### `monitoring/grafana/dashboards/gnet-revisions.json`

A **state file** storing the last known Grafana.com revision for each dashboard.

Example:

```json
{
  "21743": 4,
  "193": 2,
  "21040": 1,
  "1860": 37
}
```

**Responsibilities:**

* Records the last downloaded `revision` from Grafana.com
* Enables change detection without diffing JSON payloads
* Makes downloads deterministic and reviewable

This file is:

* Updated automatically by `download-gnet.sh`
* Checked into Git intentionally
* Used to decide whether a download is required

If a dashboard revision on Grafana.com is unchanged, **no download occurs**.

---

### 4.2 Download Logic (Step-by-Step)

For each dashboard ID listed in `manifest.json`:

1. Query Grafana.com API for dashboard metadata
2. Read the current `revision` field
3. Compare revision against `gnet-revisions.json`
4. If revisions differ:

   * Download the dashboard JSON
   * Write it to the path defined in `manifest.json`
   * Update `gnet-revisions.json`
5. If revisions are equal:

   * Skip download
   * Leave working tree untouched

This guarantees:

* No unnecessary Git diffs
* No accidental overwrites
* Fully reproducible updates

---

### 4.3 Why Two Files Instead of One

| File                  | Purpose                                 |
| --------------------- | --------------------------------------- |
| `manifest.json`       | *Desired state* (what we want)          |
| `gnet-revisions.json` | *Observed state* (what we last fetched) |

This separation:

* Avoids embedding volatile state into configuration
* Makes reviews easy (`"revision changed from 3 → 4"`)
* Aligns with Infrastructure-as-Code best practices

---

### 4.4 Resulting Filesystem State

After a successful run:

```text
monitoring/grafana/dashboards/
├── manifest.json
├── gnet-revisions.json
├── docker/
│   ├── docker-overview-21743.json
│   ├── docker-engine-health-21040.json
│   └── docker-container-resource-usage-193.json
└── system/
    ├── node-exporter-full-1860.json
    ├── alertmanager-9578.json
    └── prometheus-metrics-overview-19341.json
```

Only files listed in the manifest exist here.

## 5. Dashboard Normalization (`normalize-dashboard.py`)

### Purpose

Downloaded dashboards are **not provisioning-safe by default**. The normalizer ensures:

* Datasources are portable
* Grafana-managed fields are removed
* IDs and UIDs do not conflict

### Key Transformations

#### Datasource Hardening

All Prometheus datasources are rewritten to:

```json
"datasource": {
  "type": "prometheus",
  "uid": "${DS_PROMETHEUS}"
}
```

This ensures compatibility with:

* Provisioned datasources
* Multiple Grafana instances
* CI validation

#### ID / UID Handling

The following fields are removed or reset:

* `id`
* `iteration`
* `version`

This prevents Grafana from treating dashboards as UI-owned.

#### Templating Normalization

* Removes datasource variables pointing to concrete UIDs
* Ensures templating queries reference `${DS_PROMETHEUS}`

---

## 6. Validation (`validate_dashboards.sh`)

### Purpose

Validation is **semantic**, not just JSON syntax.

The script ensures:

* All JSON files are valid
* No hard-coded Prometheus datasource UIDs exist
* Dashboards are safe for provisioning

### Why `jq`, Not `grep`

Datasource blocks typically span multiple lines:

```json
"datasource": {
  "type": "prometheus",
  "uid": "${DS_PROMETHEUS}"
}
```

Line-based tools (`grep`) produce false positives.

Instead, `jq` is used to:

* Traverse the full JSON AST
* Detect datasource objects structurally
* Flag only **real violations**

### Example Check

```bash
jq -r '
  .. | objects
  | select(has("datasource"))
  | .datasource
  | select(type=="object" and .type=="prometheus")
  | .uid // "MISSING_UID"
'
```

---

## 7. Grafana Provisioning Flow

Grafana is configured to read dashboards from disk:

```yaml
providers:
  - name: Docker
    folder: Docker
    options:
      path: /var/lib/grafana/dashboards/docker

  - name: System
    folder: System
    options:
      path: /var/lib/grafana/dashboards/system
```

### Implications

* Grafana UI **must not be used** to import dashboards
* Files on disk are the **single source of truth**
* Conflicts in the UI indicate drift, not errors

---

## 8. Recommended Day-to-Day Workflow

1. **Work in WSL**
2. Run:

   ```bash
   scripts/grafana/download-gnet.sh
   ```
3. Run:

   ```bash
   scripts/grafana/normalize-dashboard.py monitoring/grafana/dashboards
   ```
4. Validate:

   ```bash
   scripts/grafana/validate_dashboards.sh
   make precommit
   ```
5. Review Git diff
6. Commit and push
7. Pull on Raspberry Pi
8. Deploy via `deploy.sh`

---

## 9. Why This Works

This approach deliberately avoids:

* UI imports
* Manual patching
* Datasource name coupling

Instead, it embraces:

* GitOps principles
* Deterministic provisioning
* Reproducible environments

The result is a **stable monitoring stack** where dashboards can be updated confidently and repeatedly without regressions.

---

## 10. Future Extensions (Optional)

* Dashboard allowlist (`dashboards.yml`)
* Automated PRs for new GNet revisions
* JSON schema validation
* Dashboard golden tests (snapshot PromQL validation)

---

**End of document**
