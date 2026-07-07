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
- `helm`
- Docker, if you build images locally
- Kubernetes access configured through your normal kubeconfig
- Optional: Argo CD for GitOps deployment

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

## End-To-End Installation

This section installs the assistant on a Kubernetes server and exposes the dashboard through a `NodePort`.

The examples use:

```text
GitHub repo: https://github.com/kmc-1234/k8s-devops-assistant.git
Docker image: kmc173/k8s-devops-assistan
Namespace: devops-assistant
Assistant NodePort: 30081
Argo CD namespace: argocd
```

### 1. Clone The Repository

```bash
git clone https://github.com/kmc-1234/k8s-devops-assistant.git
cd k8s-devops-assistant
```

If you are already inside the project directory, pull the latest changes:

```bash
git pull origin main
```

### 2. Verify Cluster Access

```bash
kubectl config current-context
kubectl get nodes -o wide
```

Expected:

```text
The current context should be your target server/cluster.
At least one node should show Ready.
```

### 3. Verify The Helm Chart

```bash
helm lint charts/k8s-devops-assistant
```

Render the production chart before installing:

```bash
helm template k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --values charts/k8s-devops-assistant/values-prod.yaml
```

The rendered service should show:

```yaml
type: NodePort
nodePort: 30081
```

The rendered deployment should show:

```yaml
image: kmc173/k8s-devops-assistan:main
```

### 4. Install With Helm

Install or upgrade the assistant:

```bash
helm upgrade --install k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --create-namespace \
  --values charts/k8s-devops-assistant/values-prod.yaml
```

If NodePort `30081` is already allocated, choose another free port in the Kubernetes NodePort range:

```bash
helm upgrade --install k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --create-namespace \
  --values charts/k8s-devops-assistant/values-prod.yaml \
  --set service.nodePort=30082
```

### 5. Check The Installation

```bash
kubectl -n devops-assistant rollout status deployment/k8s-devops-assistant --timeout=180s
kubectl -n devops-assistant get pods
kubectl -n devops-assistant get svc k8s-devops-assistant
```

Expected:

```text
Pods: 1/1 Running
Service: NodePort 80:30081/TCP
```

### 6. Open The Dashboard

Get the node IP:

```bash
kubectl get nodes -o wide
```

Open:

```text
http://<node-ip>:30081/
```

Example:

```text
http://10.90.6.117:30081/
```

Test the API:

```bash
curl http://<node-ip>:30081/healthz
curl "http://<node-ip>:30081/diagnose?namespace=devops-assistant"
```

Expected health response:

```json
{
  "status": "ok"
}
```

### 7. Open Firewall Ports

If the dashboard does not open from your browser, allow the NodePort on the server:

```bash
sudo ufw allow 30081/tcp
sudo ufw reload
sudo ufw status
```

If you expose Argo CD through NodePort too, also allow:

```bash
sudo ufw allow 30082/tcp
sudo ufw allow 30443/tcp
sudo ufw reload
```

### 8. Install Argo CD

Create the Argo CD namespace:

```bash
kubectl create namespace argocd
```

Install Argo CD:

```bash
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Wait for Argo CD:

```bash
kubectl -n argocd rollout status deployment/argocd-server --timeout=180s
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=180s
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=180s
```

Verify the Application CRD:

```bash
kubectl get crd applications.argoproj.io
```

### 9. Deploy With Argo CD GitOps

Apply the Argo CD application:

```bash
kubectl apply -f argocd/applications/k8s-devops-assistant.yaml
```

Check status:

```bash
kubectl -n argocd get application k8s-devops-assistant
kubectl -n argocd describe application k8s-devops-assistant
```

Expected:

```text
SYNC STATUS: Synced
HEALTH STATUS: Healthy
```

Argo CD will manage these resources:

```text
Deployment
Service
ServiceAccount
ClusterRole
ClusterRoleBinding
```

### 10. Expose Argo CD UI With NodePort

Patch the Argo CD server service:

```bash
kubectl -n argocd patch svc argocd-server \
  -p '{"spec":{"type":"NodePort","ports":[{"name":"http","port":80,"protocol":"TCP","targetPort":8080,"nodePort":30082},{"name":"https","port":443,"protocol":"TCP","targetPort":8080,"nodePort":30443}]}}'
```

Open:

```text
https://<node-ip>:30443/
```

Get the initial admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 --decode
```

Login:

```text
Username: admin
Password: <decoded-password>
```

In the Argo CD UI, open:

```text
k8s-devops-assistant
```

You should see the live GitOps resource tree.

### 11. Live GitOps Experience

To see GitOps working:

1. Edit:

```text
charts/k8s-devops-assistant/values-prod.yaml
```

2. Change:

```yaml
replicaCount: 2
```

to:

```yaml
replicaCount: 1
```

3. Commit and push:

```bash
git add charts/k8s-devops-assistant/values-prod.yaml
git commit -m "Scale assistant to one replica"
git push origin main
```

4. Watch Argo CD:

```bash
kubectl -n argocd get application k8s-devops-assistant
kubectl -n devops-assistant get pods
```

Argo CD will detect the Git change and sync the cluster to the new desired state.

### 12. CI/CD Setup

The GitHub Actions workflow is:

```text
.github/workflows/ci-cd.yml
```

It tests code, scans for issues, builds the Docker image, scans the image, and pushes to Docker Hub.

Add these GitHub repository secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

GitHub path:

```text
Repository -> Settings -> Secrets and variables -> Actions
```

Use a Docker Hub access token for `DOCKERHUB_TOKEN`.

On every push to `main`, the workflow publishes:

```text
kmc173/k8s-devops-assistan:latest
kmc173/k8s-devops-assistan:main
kmc173/k8s-devops-assistan:0.<github-run-number>.0
kmc173/k8s-devops-assistan:sha-<git-sha>
```

### 13. Troubleshooting

Check pods:

```bash
kubectl -n devops-assistant get pods
kubectl -n devops-assistant describe pod -l app.kubernetes.io/name=k8s-devops-assistant
```

Check logs:

```bash
kubectl -n devops-assistant logs deploy/k8s-devops-assistant
```

Check service:

```bash
kubectl -n devops-assistant get svc k8s-devops-assistant
```

Check events:

```bash
kubectl -n devops-assistant get events --sort-by=.lastTimestamp
```

If you see:

```text
ImagePullBackOff
```

verify the image and node architecture:

```bash
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.nodeInfo.architecture}{"\n"}{end}'
docker buildx imagetools inspect kmc173/k8s-devops-assistan:main
```

Use image tag `main` for this server because it is built by GitHub Actions for `linux/amd64`.

If you see:

```text
provided port is already allocated
```

find the service using the port:

```bash
kubectl get svc --all-namespaces
```

Then install with another NodePort:

```bash
helm upgrade --install k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --create-namespace \
  --values charts/k8s-devops-assistant/values-prod.yaml \
  --set service.nodePort=30082
```

If the browser cannot connect:

```bash
sudo ufw allow 30081/tcp
sudo ufw reload
```

For Minikube on macOS, direct node IP access may not work. Use:

```bash
minikube service k8s-devops-assistant -n devops-assistant --url
```

Keep that terminal open and use the printed localhost URL.

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
