# Homelab

Production-grade Kubernetes infrastructure, fully declarative and GitOps-managed. This repository defines the complete state of a heterogeneous bare-metal cluster running real workloads.

## Stack

- **OS**: Talos Linux
- **Orchestration**: Kubernetes (mixed-arch nodes)
- **GitOps**: ArgoCD with auto-sync
- **IaC**: OpenTofu (Cloudflare DNS, external resources)
- **Networking**: Traefik ingress, Tailscale mesh, MetalLB, Cloudflared tunnels, External-DNS
- **Storage**: NFS with dynamic provisioning
- **Secrets**: SOPS + Age encryption (committed to git, decrypted in-cluster)
- **Database**: PostgreSQL (CloudNativePG operator), MariaDB
- **TLS**: cert-manager with Let's Encrypt
- **Monitoring**: Grafana Cloud (k8s-monitoring stack)
- **DNS**: AdGuard Home

## How It Works

Every change flows through git. Push to `main` and ArgoCD automatically reconciles cluster state. No manual `kubectl apply`, no drift.

```
git push -> ArgoCD detects change -> cluster converges
```

## Repository Structure

```
kubernetes/
  bootstrap/          # Talos node configs, ArgoCD bootstrap
  argocd/apps/
    infrastructure/   # cert-manager, MetalLB, NFS provisioner, etc.
    network/          # Traefik, Cloudflared, External-DNS, AdGuard
    monitoring/       # Grafana Cloud integration
    workloads/        # Application deployments
terraform/            # Cloudflare DNS and external resources
.taskfiles/           # Automation tasks (sops, kubernetes, argo)
```

## Workloads

Photo management, personal websites, game servers, book management, and more -- all running on hardware in the closet.
