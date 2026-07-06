from __future__ import annotations

from .ai import maybe_add_ai_summary
from .analyzer import analyze
from .kubectl import Kubectl, KubectlError
from .models import Diagnosis


def run_diagnosis(
    namespace: str,
    pod: str | None = None,
    deployment: str | None = None,
    include_ai: bool = False,
) -> Diagnosis:
    kubectl = Kubectl(namespace=namespace)
    pods = _load_pods(kubectl, pod)
    events = _best_effort(kubectl.get_events, {"items": []})
    logs = _collect_logs(kubectl, pods)
    deployment_status = None

    if deployment:
        deployment_status = _best_effort(lambda: kubectl.rollout_status(deployment), None)

    diagnosis = analyze(
        namespace=namespace,
        pods=pods,
        events=events,
        selected_pod=pod,
        deployment_status=deployment_status,
        logs=logs,
    )

    if include_ai:
        diagnosis = maybe_add_ai_summary(diagnosis)

    return diagnosis


def _load_pods(kubectl: Kubectl, pod: str | None) -> dict:
    if pod:
        item = kubectl.get_pod(pod)
        return {"items": [item]}
    return kubectl.get_pods()


def _collect_logs(kubectl: Kubectl, pods: dict) -> dict[str, str]:
    logs: dict[str, str] = {}
    for pod in pods.get("items", []):
        pod_name = pod.get("metadata", {}).get("name")
        if not pod_name:
            continue
        statuses = pod.get("status", {}).get("containerStatuses", [])
        for status in statuses:
            container = status.get("name")
            if not container:
                continue
            logs[f"{pod_name}/{container}/current"] = _best_effort(
                lambda pod_name=pod_name, container=container: kubectl.logs(pod_name, container),
                "",
            )
            if status.get("restartCount", 0) > 0:
                logs[f"{pod_name}/{container}/previous"] = _best_effort(
                    lambda pod_name=pod_name, container=container: kubectl.logs(pod_name, container, previous=True),
                    "",
                )
    return logs


def _best_effort(func, default):
    try:
        return func()
    except KubectlError:
        return default

