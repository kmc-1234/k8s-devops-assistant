# GitOps Deployment With Helm And Argo CD

This project now includes a Helm chart at:

```text
charts/k8s-devops-assistant
```

Argo CD should deploy that chart from Git. The example Argo CD app is:

```text
argocd/applications/k8s-devops-assistant.yaml
```

## 1. Build And Push Image

Replace the repository with your real registry:

```bash
docker build -t kmc173/k8s-devops-assistan:0.2.0 .
docker push kmc173/k8s-devops-assistan:0.2.0
```

Then update:

```text
charts/k8s-devops-assistant/values-prod.yaml
```

Set:

```yaml
image:
  repository: kmc173/k8s-devops-assistan
  tag: "0.2.0"
```

## 2. Optional OpenAI Secret

If AI summaries are enabled, create the secret outside Git:

```bash
kubectl create namespace devops-assistant
kubectl -n devops-assistant create secret generic k8s-devops-assistant-openai \
  --from-literal=OPENAI_API_KEY="YOUR_KEY"
```

The chart references that secret through:

```yaml
openai:
  enabled: true
  existingSecret: k8s-devops-assistant-openai
  apiKeySecretKey: OPENAI_API_KEY
```

For GitOps production, prefer External Secrets, Sealed Secrets, or your cloud secret manager instead of committing raw API keys.

## 3. Test Helm Locally

Render the chart:

```bash
helm template k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --values charts/k8s-devops-assistant/values-prod.yaml
```

Install manually without Argo CD:

```bash
helm upgrade --install k8s-devops-assistant charts/k8s-devops-assistant \
  --namespace devops-assistant \
  --create-namespace \
  --values charts/k8s-devops-assistant/values-prod.yaml
```

## 4. Deploy With Argo CD

First confirm Argo CD is installed:

```bash
kubectl get crd applications.argoproj.io
```

If that fails, install Argo CD first using:

```text
argocd/bootstrap/README.md
```

Edit:

```text
argocd/applications/k8s-devops-assistant.yaml
```

Replace:

```yaml
repoURL: https://github.com/kmc-1234/k8s-devops-assistant.git
```

Then commit and push the repository.

Apply the Argo CD application:

```bash
kubectl apply -f argocd/applications/k8s-devops-assistant.yaml
```

Argo CD will create the `devops-assistant` namespace, render the Helm chart, and keep it synced.

## 5. Verify

```bash
kubectl -n devops-assistant get pods
kubectl -n devops-assistant get svc
kubectl -n devops-assistant port-forward svc/k8s-devops-assistant 8080:80
```

Test:

```bash
curl http://127.0.0.1:8080/healthz
curl "http://127.0.0.1:8080/diagnose?namespace=ingress-nginx"
```

Open the dashboard:

```text
http://127.0.0.1:8080/
```

## 6. RBAC Scope

By default the chart uses cluster-wide read-only RBAC so the assistant can troubleshoot namespaces across the cluster.

For namespace-only access:

```yaml
rbac:
  clusterWide: false
```

This limits the assistant to the namespace where it is installed.
