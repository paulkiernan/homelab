# Le Paulynomial Homelab

## Publishing arm64 images

This cluster runs on the arm64 instruction set. Some of the deployments in it
do not provide cross-built docker images for the arm64 arch so we use QEMU to
emulate it at build time and push the image to [my public GitHub Container
Registry](https://github.com/paulkiernan?tab=packages).

### Setup

First, we need to add arm64 as an available build target from an x86 host using
buildx. We can verify that arm64 targets are missing via:

```console
# Verify that no arm64 local build env exists
$ docker buildx ls
NAME/NODE DRIVER/ENDPOINT STATUS  PLATFORMS
default * docker
  default default         running linux/amd64, linux/386

# Start the buildx qemu environment
$ docker \
  run \
    --rm \
    --privileged \
    tonistiigi/binfmt:qemu-v6.0.0 \
        --install arm64

# Verify that new build environments have been added
$ docker buildx ls
NAME/NODE DRIVER/ENDPOINT STATUS  PLATFORMS
default * docker
  default default         running linux/amd64, linux/386, linux/arm64
```

Next, we'll need to authorize docker to push container images to my registry:
[docs](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

```bash
export CR_PAT=SECRET_SECRET
echo $CR_PAT | docker login ghcr.io -u paulkiernan --password-stdin
```

Finally, we can build the images.

#### Cloudflared (Argo Tunnel)

```bash
docker \
  buildx \
    build \
      --platform linux/arm64 \
      -t ghcr.io/paulkiernan/valheim-server-docker:main-arm64 \
      --push \
      .
```

#### Valheim Server

```bash
docker \
  buildx \
    build \
      --progress plain \
      --platform linux/arm64 \
      -t ghcr.io/paulkiernan/valheim-server-docker:main-arm64 \
      --push \
      .
```

### Cleanup

We can uninstall QEMU:

```bash
docker \
  run \
    --privileged \
    --rm \
    tonistiigi/binfmt \
      --uninstall qemu-aarch64
```

## Declarative Configuration & Security

This repository follows a strict **declarative configuration** model. All cluster state, including infrastructure and application configuration, must be defined as code within this repository.

### Principles
1.  **GitOps**: All changes should be committed to git and applied via ArgoCD (or similar controllers). Avoid manual `kubectl apply` unless strictly necessary for bootstrapping or debugging.
2.  **Secret Management**: Sensitive values (API keys, passwords, etc.) must **NEVER** be committed in plain text. Use **SOPS** (Secrets OPerationS) with Age encryption to encrypt secrets before committing them.
    *   Files containing secrets should be suffixed with `.sops.yaml`.
    *   Use `task sops:encrypt` (if available) or `sops -e -i <file>` to encrypt.
3.  **Portability**: The configuration should be portable across machines, relying on the repository as the single source of truth.

### Tailscale Access
To access the cluster via Tailscale, use the provided task:
```bash
task tailscale:update-kubeconfig
```
This configures your local `kubeconfig` to use the Tailscale-exposed API endpoint.
