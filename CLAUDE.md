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
*Last updated: 2025-12-29*
