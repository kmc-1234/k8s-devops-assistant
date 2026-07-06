# Kubernetes DevOps Assistant

Internal assistant for Kubernetes troubleshooting. It checks pod health, reads events and logs, detects common failure patterns, and recommends investigation or remediation commands.

The MVP is intentionally read-only. It does not apply fixes to the cluster.

## Features

- Detects common pod issues:
  - `CrashLoopBackOff`
  - `ImagePullBackOff`
  - `ErrImagePull`
  - `OOMKilled`
  - failed liveness/readiness probes
  - pending pods
  - scheduling failures
  - deployment rollout failures
- Collects Kubernetes context using safe `kubectl` commands.
- Produces a structured incident-style diagnosis.
- Runs as a CLI or a lightweight local HTTP API.
- Includes a React dashboard served by the same API.
- Optionally adds an AI summary when `OPENAI_API_KEY` is configured.

## Requirements

- Python 3.10+
- `kubectl`
- Kubernetes access configured through your normal kubeconfig

No Python dependencies are required for the MVP.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m k8s_assistant.cli --help
```

Diagnose a namespace:

```bash
python -m k8s_assistant.cli diagnose --namespace staging
```

Diagnose one pod:

```bash
python -m k8s_assistant.cli diagnose --namespace staging --pod payment-service-abc123
```

Diagnose a deployment rollout:

```bash
python -m k8s_assistant.cli diagnose --namespace staging --deployment payment-service
```

Start the local API:

```bash
python -m k8s_assistant.cli serve --host 127.0.0.1 --port 8080
```

Then call:

```bash
curl "http://127.0.0.1:8080/diagnose?namespace=staging"
```

Open the dashboard:

```text
http://127.0.0.1:8080/
```

## Optional AI Summary

Set an OpenAI API key to add an AI-generated operational summary on top of the deterministic analysis:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4.1-mini"
```

The assistant still works without an API key.

## Safety Model

The default command runner only allows read-only Kubernetes commands:

- `kubectl get`
- `kubectl describe`
- `kubectl logs`
- `kubectl top`
- `kubectl rollout status`

Commands like `apply`, `delete`, `scale`, `patch`, and `edit` are not executed by this assistant. They may appear only as recommended manual commands.

## Project Layout

```text
k8s_assistant/
  ai.py          Optional OpenAI summary integration
  analyzer.py    Kubernetes issue detection rules
  api.py         Small HTTP API using Python stdlib
  cli.py         CLI entry point
  kubectl.py     Safe kubectl wrapper
  models.py      Shared dataclasses
dashboard/
  index.html     React dashboard shell
  app.js         Dashboard application
  styles.css     Dashboard styles
tests/
  test_analyzer.py
manifests/
  deployment.yaml
  rbac-readonly.yaml
charts/
  k8s-devops-assistant/
argocd/
  applications/
```

## Helm Install

Render the chart:

```bash
helm template k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant
```

Install it:

```bash
helm upgrade --install k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --create-namespace
```

For production values, edit and use:

```bash
helm upgrade --install k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --create-namespace \
  --values charts/k8s-devops-assistant/values-prod.yaml
```

## Argo CD GitOps

Use the Argo CD application example:

```text
argocd/applications/k8s-devops-assistant.yaml
```

If your cluster says `no matches for kind "Application"`, install Argo CD first:

```text
argocd/bootstrap/README.md
```

Update `repoURL`, `targetRevision`, image repository, and image tag for your Git/registry setup, then apply:

```bash
kubectl apply -f argocd/applications/k8s-devops-assistant.yaml
```

Full instructions are in [docs/gitops-argocd.md](docs/gitops-argocd.md).

The production values expose the assistant as a `NodePort` on port `30080`:

```bash
kubectl -n devops-assistant get svc k8s-devops-assistant
```

Open:

```text
http://<node-ip>:30080/
```

## Production Setup Notes

For an internal deployment:

1. Run the assistant in a dedicated namespace.
2. Use the read-only RBAC in `manifests/rbac-readonly.yaml`.
3. Put it behind internal auth, such as SSO, VPN, or an internal gateway.
4. Store `OPENAI_API_KEY` in a Kubernetes secret if AI summaries are enabled.
5. Keep automated remediation disabled until approval flows and audit logging are in place.

## Test

```bash
python -m unittest discover -s tests
```
