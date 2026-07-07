from __future__ import annotations

import os
from typing import Any

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
    pod_metrics = _best_effort(lambda: _parse_top_pods(kubectl.top_pods()), {})
    pvc_usage = _best_effort(lambda: _collect_pvc_usage(kubectl), {})
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
        pod_metrics=pod_metrics,
        pvc_usage=pvc_usage,
        cpu_threshold_percent=_env_float("CPU_ALERT_THRESHOLD_PERCENT", 80.0),
        pvc_threshold_percent=_env_float("PVC_ALERT_THRESHOLD_PERCENT", 80.0),
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


def _parse_top_pods(output: str) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        pod_name, cpu, memory = parts[:3]
        metrics[pod_name] = {
            "cpu": cpu,
            "cpu_millicores": _cpu_to_millicores(cpu),
            "memory": memory,
        }
    return metrics


def _collect_pvc_usage(kubectl: Kubectl) -> dict[str, dict[str, Any]]:
    pvc_usage: dict[str, dict[str, Any]] = {}
    nodes = kubectl.get_nodes()
    for node in nodes.get("items", []):
        node_name = node.get("metadata", {}).get("name")
        if not node_name:
            continue
        stats = kubectl.get_raw(f"/api/v1/nodes/{node_name}/proxy/stats/summary")
        _merge_pvc_stats(kubectl.namespace, stats, pvc_usage)
    return pvc_usage


def _merge_pvc_stats(namespace: str, stats: dict[str, Any], pvc_usage: dict[str, dict[str, Any]]) -> None:
    for pod in stats.get("pods", []):
        pod_ref = pod.get("podRef", {})
        if pod_ref.get("namespace") != namespace:
            continue
        pod_name = pod_ref.get("name", "")
        for volume in pod.get("volume", []):
            pvc_ref = volume.get("pvcRef")
            if not pvc_ref or pvc_ref.get("namespace") != namespace:
                continue
            pvc_name = pvc_ref.get("name")
            used_bytes = volume.get("usedBytes")
            capacity_bytes = volume.get("capacityBytes")
            if not pvc_name or not capacity_bytes:
                continue

            current = pvc_usage.setdefault(
                pvc_name,
                {"used_bytes": 0, "capacity_bytes": capacity_bytes, "usage_percent": 0.0, "pods": []},
            )
            current["used_bytes"] = max(int(current["used_bytes"]), int(used_bytes or 0))
            current["capacity_bytes"] = max(int(current["capacity_bytes"]), int(capacity_bytes))
            if pod_name and pod_name not in current["pods"]:
                current["pods"].append(pod_name)
            current["usage_percent"] = current["used_bytes"] / current["capacity_bytes"] * 100


def _cpu_to_millicores(value: str) -> float:
    text = value.strip()
    try:
        if text.endswith("m"):
            return float(text[:-1])
        if text.endswith("n"):
            return float(text[:-1]) / 1_000_000
        if text.endswith("u"):
            return float(text[:-1]) / 1_000
        return float(text) * 1000
    except ValueError:
        return 0.0


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
