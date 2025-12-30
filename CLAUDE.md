# Repository Context for Claude

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
*Last updated: 2025-12-30*