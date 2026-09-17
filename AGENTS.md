# Repository Context for Codex

## Purpose
This repository is a personal "homelab" setup that serves multiple objectives:
- **Declarative Infrastructure**: All infrastructure and services are managed declaratively via GitHub
- **Public Portfolio**: Publicly accessible as a reference/portfolio resource (e.g., for hiring managers, collaborators, or the community)
- **Personal Services**: Hosts essential services needed for personal life

## Architecture
- **Heterogeneous Kubernetes Cluster**: The homelab runs on a Kubernetes cluster with mixed hardware/nodes
- **GitOps**: Managed via ArgoCD with automatic synchronization
- **Key Infrastructure**:
  - **Ingress**: Traefik with Tailscale integration
  - **Networking**: MetalLB (LoadBalancer), Cloudflared, External-DNS
  - **Storage**: NFS subdir external provisioner
  - **Database**: PostgreSQL (CloudNativePG operator)
  - **Security**: cert-manager, SOPS operator for secrets
  - **Monitoring**: Grafana Cloud integration
  - **DNS**: AdGuard Home

## Services Hosted
- **Immich**: Photo management and backup server
- **Personal websites**: disconnect, paulynomial-index, chrisabel, gibson, taqueria-bonjour
- **Dashboard**: Hajimari
- **Games**: Minecraft server

## Development Workflow

### Taskfile Commands

**IMPORTANT: This repository uses [Taskfile](https://taskfile.dev) for common operations.**

Always check for and use existing Taskfile commands instead of running raw commands. You can view available commands with:

```bash
task --list
```

#### Common Tasks

**SOPS/Secrets:**
- `task sops:encrypt` - Encrypt all unencrypted SOPS files in the repository
- `task sops:re-encrypt` - Re-encrypt all SOPS files (useful after key rotation)

**Kubernetes:**
- `task kubernetes:resources` - List common cluster resources (useful for debugging)
- `task kubernetes:kubeconform` - Validate all Kubernetes manifests

**ArgoCD:**
- `task argo:bootstrap` - Bootstrap ArgoCD and deploy the root app-of-apps

#### Measurement Operations

The public-data futures measurement workload (`kubernetes/argocd/apps/workloads/market-measurement`) has its own task namespace, `measurement:` (`.taskfiles/measurement`). It captures public Coinbase US futures data and runs hypothetical paper analysis only: no venue credentials, no order path, and no task here authorizes live trading — live capital stays $0.

**Read-only tasks** (`render`, `diff`, `status`, `spool-node`, `logs`, `metrics`, `config-check`, `pull-secret-check`, `preflight`) inspect or render state; they write nothing to the cluster, the repository or a remote host.

**Tasks that change things:**
- `measurement:images` rewrites image tags in the kustomization (repository file).
- `measurement:pull-secret` and `measurement:ghcr-pull-secret` write SOPS-encrypted Secret files and list them in the kustomization (repository files).
- `measurement:report-run` and `measurement:pull-run` create one-off Jobs in the cluster.
- `measurement:alerts-apply` creates or updates Grafana Cloud alert rules.
- `measurement:vm-install` installs the recorder onto the capture VM over SSH.

**Images and the private pull Secret (needed before any pod can run):**
- Image tags must be a release published by `.github/workflows/measurement-images.yml` in `paulkiernan/diff-logic-cells` (manual `workflow_dispatch`), then pinned with `task measurement:images VERSION=vX.Y.Z`.
- The images are private and stay private; the namespace needs the SOPS-encrypted GHCR Secret made by `task measurement:ghcr-pull-secret` (`GHCR_USER` plus a `read:packages` token, read from the environment and never logged). If it is missing, pods sit in `ImagePullBackOff` by design — there is no anonymous fallback and no plaintext Secret in git.

**Read-only diagnostics:**
- `task measurement:render` renders the manifests offline; `task measurement:diff` shows what ArgoCD would change.
- `task measurement:status` lists pods, CronJobs, PVCs and the ArgoCD app; `task measurement:spool-node` names the node whose disk bounds the local capture spool.
- `task measurement:logs SERVICE=market-recorder|market-archive|pull|report` follows workload logs or lists the pull/report Jobs.
- `task measurement:metrics` port-forwards the recorder and prints `/healthz`, `/readyz` and `/metrics`.
- `task measurement:config-check` compares the deployed study config with `config/futures-study.json` from the source repo (set `MSR_SOURCE_DIR` if it is not at `$HOME/workspace/github.com/paulkiernan/diff-logic-cells`); `task measurement:preflight` combines render, the pull-Secret check and ArgoCD/pod state.

**Secret generators (encrypted output only; commit the encrypted file, never key material):**
- `task measurement:pull-secret` needs `SSH_PULL_KEY_FILE`, `SSH_PULL_KNOWN_HOSTS_FILE` and `SSH_PULL_REMOTE=user@host`; it writes SOPS-encrypted `ssh-pull-secret.sops.yaml` and lists it in the kustomization. No remote path is stored: the capture host's forced command already roots rrsync at the spool, so the pull Job asks for `/`. `task measurement:pull-secret-check` verifies the synced Secret has every required key.
- `task measurement:ghcr-pull-secret` writes the encrypted dockerconfigjson pull Secret described above.

**Capture VM (cloud host):**
- Provisioning is not a Taskfile task yet: after AWS credentials exist, run OpenTofu in `terraform/market-measurement` (`tofu init`, `tofu plan`, `tofu apply`; state is local and uncommitted). Resolve blueprint, bundle and availability zone with `aws lightsail get-*` first. The approved plan is the ~$7/month Lightsail class (2 vCPU / 1 GB / 40 GB SSD / 2 TB transfer), and that budget is documentation only — no AWS Budget, quota or IAM policy enforces it.
- `task measurement:vm-install` then ships the binary and systemd units over SSH in one checksummed payload. It requires `MSR_VM_TARGET`, `MSR_VM_SITE` and `MSR_VM_BINARY` — a real locally built Linux binary, whose ELF architecture the wrapper verifies — plus a pinned host key: `MSR_VM_KNOWN_HOSTS` (preferred) or `MSR_VM_FINGERPRINT`; `MSR_VM_TOFU=1` is the last resort. `MSR_VM_PULL_KEY` authorizes the read-only rsync pull key on the host. The approved instance is deployed: Lightsail `market-measurement` in `us-east-1a` (`micro_3_0`, the ~$7/month class, static IPv4 `107.21.239.171`, site `aws-us-east-1`); OpenTofu state and its backups stay local and git-ignored under `terraform/market-measurement/` — losing that state loses ownership of a running, data-bearing instance. `user_data` is create-only bootstrap: it runs at creation, and `lifecycle.ignore_changes = [user_data]` keeps a later launch-script edit from proposing a replacement of a host that holds the only copy of its spool. Corrections therefore change what future instances boot with, and existing hosts are updated by re-running the script over SSH or through the phase-2 `vm-install` path.
- The SSH-pull CronJob is active (since 2026-09-17), and its initial bootstrap requirement is kept here because every new capture host repeats it: before `suspend: false` may be committed, (1) the host keys must be trusted from the authenticated provider API — for Lightsail the AWS-managed `lightsail-connect` CIDR alias has to be allowed on TCP 22 temporarily so `get-instance-access-details` witnesses them, then removed again; an unauthenticated keyscan or TOFU is not acceptable — (2) the read-only rrsync key must be authorized on the host, (3) the SOPS `ssh-pull-secret.sops.yaml` must be committed and synced by ArgoCD, and (4) one `task measurement:pull-run` Job must have verified the sealed chunks on the NAS. A missing Secret or an unreachable VM keeps failing the pull Job visibly; suspension was a pending state, never a substitute for a working transport.
- Telemetry is on by default: with Alloy enabled, `MSR_VM_GRAFANA_ENV` (a local 0600 file holding `GRAFANA_CLOUD_PROM_URL`, `GRAFANA_CLOUD_PROM_USER` and `GRAFANA_CLOUD_TOKEN`) is mandatory, and the run fails if Alloy does not become active. An active unit proves local agent readiness only — it does not prove remote ingestion and says nothing about alert rules. On 2026-09-17 the Grafana Cloud tenant was over its active-series limit and every remote-write push was rejected with HTTP 429, so an active Alloy can still mean no metrics in Grafana; check the Alloy log for `Failed to send batch` before claiming telemetry works. `MSR_VM_ALLOY=0` opts out deliberately; `DRY_RUN=1` prints the plan and changes nothing.

**One-off jobs and alerts:**
- `task measurement:report-run` and `task measurement:pull-run` create one-off Jobs from the report and SSH-pull CronJobs and tail their logs; the pull path never writes to or deletes anything on the capture host.
- `task measurement:alerts-apply` writes the Grafana Cloud alert rules (Grafana evaluates them; there is no in-cluster Prometheus). `GRAFANA_URL` and `GRAFANA_TOKEN` plus folder/datasource UIDs are required; `DRY_RUN=1` prints the payload without sending it.

**Operational notes:**
- Deploy by committing and pushing to `main`; ArgoCD auto-syncs (prune + selfHeal) within a few minutes. No measurement task applies manifests — do not `kubectl apply` them.
- The measurement ConfigMap's `sites:` currently lists `homelab aws-us-east-1`, one output directory per site. Add another capture host's site id only once that host is producing sealed chunks, and never merge sites into one report run.
- Raw capture is never deleted automatically: the node-local spool is the real disk bound, sealed chunks may be pruned only after verification on the NAS archive, and the archive's source copy stays intact. The measurement PVCs carry `Prune=false,Delete=false` so a sync cannot drop them.

#### Adding New Tasks

**When performing regular operations, consider adding them to the appropriate Taskfile:**

1. Identify the category (sops, kubernetes, argo, etc.)
2. Add the task to `.taskfiles/<category>/Taskfile.yaml`
3. Follow the existing pattern with proper descriptions and preconditions
4. Document the new task in this file

Example task structure:
```yaml
my-task:
  desc: Description of what this task does
  cmds:
    - echo "Command to run"
  preconditions:
    - msg: Error message if precondition fails
      sh: test -f required-file
```

### CRITICAL: Testing Pattern for Cluster Changes
When making changes to cluster configurations, **always follow this workflow**:

1. **Code & Commit**: Make changes to YAML manifests and commit to repository
2. **Push to GitHub**: Push commits to the `main` branch
3. **Wait for ArgoCD**: Allow 1-3 minutes for ArgoCD to detect changes (automatic polling)
4. **ArgoCD Auto-Sync**: ArgoCD will automatically synchronize the changes (auto-sync enabled)
5. **Verify Deployment**: Check the results using kubectl commands

### Verification Commands
After ArgoCD syncs, use these commands to verify deployments:

```bash
# Check ArgoCD application sync status
kubectl get applications -n argocd

# Check pod status in the relevant namespace
kubectl get pods -n <namespace>

# View pod logs for debugging
kubectl logs <pod-name> -n <namespace>

# Get detailed resource information
kubectl describe <resource-type> <resource-name> -n <namespace>
```

### Important Notes
- **Do NOT manually apply manifests** with `kubectl apply` - let ArgoCD handle deployments
- **Observe, don't force-sync**: ArgoCD auto-sync is enabled; just monitor the status
- **Changes must be committed first**: Never test uncommitted changes directly on the cluster

## Secrets Management

**CRITICAL: All secrets in this Kubernetes cluster MUST use SOPS encryption.**

### SOPS Secret Pattern

This cluster uses the [SOPS Operator](https://github.com/isindir/sops-secrets-operator) to manage encrypted secrets. All sensitive data must be encrypted using SOPS before being committed to the repository.

#### Creating a New Secret

1. **Create a SopsSecret manifest** (not a plain Kubernetes Secret):

```yaml
apiVersion: isindir.github.com/v1alpha3
kind: SopsSecret
metadata:
  name: my-app-secret
  namespace: my-namespace
spec:
  secretTemplates:
    - name: my-app-secret
      stringData:
        username: my-username
        password: my-secure-password
```

2. **Encrypt the file using SOPS**:
   ```bash
   # Encrypt all unencrypted SOPS files
   task sops:encrypt

   # Or manually encrypt a specific file
   sops --encrypt --in-place path/to/secret.sops.yaml
   ```
   - The repository is configured with AGE encryption keys in `.sops.yaml`
   - SOPS will automatically encrypt the `stringData` field values
   - The SOPS operator in the cluster will decrypt these at runtime

3. **Reference the secret** in your deployments like a normal Kubernetes secret:

```yaml
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: my-app-secret
        key: password
```

#### Examples
- Database credentials: `kubernetes/argocd/apps/workloads/immich/manifests/db-credentials.secret.sops.yaml`
- MariaDB secrets: `kubernetes/argocd/apps/workloads/booklore/manifests/mariadb-secret.sops.yaml`

#### Never Commit Plain Secrets
- ❌ Do NOT use `kind: Secret` with plain text values
- ✅ Always use `kind: SopsSecret` with encrypted values
- The SOPS operator automatically creates the corresponding Kubernetes Secret from the SopsSecret

## Repository Structure
```
kubernetes/
├── bootstrap/argocd/          # ArgoCD bootstrap configs
│   └── root-applicationset.yaml  # Root ApplicationSet for app-of-apps pattern
└── argocd/apps/               # Application manifests
    ├── infrastructure/        # Core infrastructure services
    ├── workloads/            # Application workloads
    ├── network/              # Networking components
    └── monitoring/           # Observability stack
```

## Philosophy
This repository demonstrates infrastructure-as-code practices, GitOps workflows, and practical Kubernetes administration in a real-world personal computing environment. The entire homelab state is version-controlled, making it reproducible, auditable, and a living portfolio of DevOps/SRE capabilities.

---
*Last updated: 2026-09-17*