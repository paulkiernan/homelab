# ArgoCD GitOps Structure

This directory contains all ArgoCD Applications managed via GitOps.

## Initial Bootstrap

ArgoCD must be bootstrapped once manually. After that, it manages itself.

```bash
# 1. Bootstrap ArgoCD (one-time)
task argocd:bootstrap

# 2. Deploy root app-of-apps (one-time)
kubectl apply -f kubernetes/argocd/root.yaml
```

After bootstrap, ArgoCD manages its own configuration via `apps/infrastructure/argocd/`.

## Directory Structure

```
argocd/
├── root.yaml              # App-of-apps (discovers all applications)
└── apps/
    ├── infrastructure/    # Core cluster services
    ├── monitoring/        # Observability stack
    └── workloads/         # User applications
```

## Adding New Applications

1. Create directory: `apps/<category>/<app-name>/`
2. Add `application.yaml` with ArgoCD Application CRD
3. Add manifests (or Helm values if using charts)
4. Commit and push - ArgoCD auto-syncs via root app

## Self-Management

ArgoCD manages itself through `apps/infrastructure/argocd/`. Changes to ArgoCD configuration are applied via GitOps after initial bootstrap.
