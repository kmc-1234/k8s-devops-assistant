# Argo CD Bootstrap

Use this when the cluster does not have Argo CD installed yet.

If this command fails:

```bash
kubectl apply -f argocd/applications/k8s-devops-assistant.yaml
```

with:

```text
no matches for kind "Application" in version "argoproj.io/v1alpha1"
ensure CRDs are installed first
```

then the Argo CD CRDs are missing. Install Argo CD first.

## 1. Install Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

For production, pin a specific Argo CD release instead of using `stable`.

## 2. Wait For Argo CD

```bash
kubectl -n argocd rollout status deployment/argocd-server
kubectl -n argocd rollout status deployment/argocd-repo-server
kubectl -n argocd rollout status statefulset/argocd-application-controller
```

Verify the `Application` CRD exists:

```bash
kubectl get crd applications.argoproj.io
```

## 3. Update The Application Manifest

Edit:

```text
argocd/applications/k8s-devops-assistant.yaml
```

Replace:

```yaml
repoURL: https://github.com/kmc173/k8s-devops-assistan.git
targetRevision: main
```

with your real Git repository and branch.

## 4. Apply The Application

```bash
kubectl apply -f argocd/applications/k8s-devops-assistant.yaml
```

## 5. Check Sync

```bash
kubectl -n argocd get applications.argoproj.io
kubectl -n argocd describe application k8s-devops-assistant
kubectl -n devops-assistant get pods
```

## 6. Access Argo CD UI

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

Then open:

```text
https://127.0.0.1:8080
```

Get the initial admin password:

```bash
argocd admin initial-password -n argocd
```
