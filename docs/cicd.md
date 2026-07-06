# CI/CD Pipeline

The GitHub Actions workflow is:

```text
.github/workflows/ci-cd.yml
```

It runs on:

- pull requests to `main`
- pushes to `main`
- Git tags like `v0.2.0`
- manual workflow dispatch

## What It Checks

Pull requests run:

- Python unit tests
- Python compile checks
- Ruff code checks
- Helm lint
- Helm template rendering
- Dockerfile lint with Hadolint
- Source filesystem security scan with Trivy

Pushes to `main` and release tags also:

- build the Docker image
- push it to Docker Hub
- generate SBOM/provenance metadata
- scan the pushed image with Trivy
- upload scan results to GitHub Security

## Docker Hub Repository

The image repository is:

```text
kmc173/k8s-devops-assistan
```

## Required GitHub Secrets

Create these in GitHub:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

Required secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

Use a Docker Hub access token for `DOCKERHUB_TOKEN`, not your Docker Hub password.

## Image Tag Strategy

On push to `main`, the workflow publishes:

```text
kmc173/k8s-devops-assistan:latest
kmc173/k8s-devops-assistan:main
kmc173/k8s-devops-assistan:0.<github-run-number>.0
kmc173/k8s-devops-assistan:sha-<git-sha>
```

Examples:

```text
GitHub run number 1 -> kmc173/k8s-devops-assistan:0.1.0
GitHub run number 2 -> kmc173/k8s-devops-assistan:0.2.0
GitHub run number 3 -> kmc173/k8s-devops-assistan:0.3.0
```

On a Git tag like `v0.3.0`, it also publishes:

```text
kmc173/k8s-devops-assistan:0.3.0
kmc173/k8s-devops-assistan:0.3
kmc173/k8s-devops-assistan:sha-<git-sha>
```

For Kubernetes production deployment, prefer pinning a version tag such as `0.3.0` in:

```text
charts/k8s-devops-assistant/values-prod.yaml
```

Avoid using `latest` for GitOps production deployments.

## Release Flow

For normal pushes, the Docker image tag is generated automatically as:

```text
0.<github-run-number>.0
```

For a controlled release, create a Git tag.

1. Update the image tag in:

```text
charts/k8s-devops-assistant/values-prod.yaml
```

2. Update chart version/appVersion in:

```text
charts/k8s-devops-assistant/Chart.yaml
```

3. Commit and push:

```bash
git add .
git commit -m "Release v0.3.0"
git push origin main
```

4. Create a Git tag:

```bash
git tag v0.3.0
git push origin v0.3.0
```

5. Argo CD will sync the chart from Git.
