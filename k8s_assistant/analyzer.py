from __future__ import annotations

from collections import Counter
from typing import Any

from .models import Diagnosis, Finding


BAD_WAITING_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "RunContainerError",
}


def analyze(
    namespace: str,
    pods: dict[str, Any],
    events: dict[str, Any] | None = None,
    selected_pod: str | None = None,
    deployment_status: str | None = None,
    logs: dict[str, str] | None = None,
) -> Diagnosis:
    diagnosis = Diagnosis(namespace=namespace)
    events = events or {"items": []}
    logs = logs or {}

    pod_items = pods.get("items", [])
    if selected_pod:
        pod_items = [pod for pod in pod_items if pod.get("metadata", {}).get("name") == selected_pod]

    if not pod_items:
        diagnosis.findings.append(
            Finding(
                severity="warning",
                title="No pods found",
                evidence=[f"namespace={namespace}", f"pod={selected_pod or '*'}"],
                explanation="No matching pods were returned by Kubernetes. Confirm the namespace and workload name.",
                recommended_commands=[
                    f"kubectl get pods -n {namespace}",
                    "kubectl config current-context",
                ],
            )
        )

    for pod in pod_items:
        _analyze_pod(namespace, pod, events, logs, diagnosis)

    if deployment_status:
        _analyze_deployment(namespace, deployment_status, diagnosis)

    if not diagnosis.findings:
        diagnosis.summary = "No obvious Kubernetes failure patterns were detected."
    else:
        counts = Counter(finding.severity for finding in diagnosis.findings)
        diagnosis.summary = (
            f"Detected {len(diagnosis.findings)} finding(s): "
            + ", ".join(f"{severity}={count}" for severity, count in sorted(counts.items()))
        )

    diagnosis.raw = {"pods": pods, "events": events, "logs": logs}
    return diagnosis


def _analyze_pod(
    namespace: str,
    pod: dict[str, Any],
    events: dict[str, Any],
    logs: dict[str, str],
    diagnosis: Diagnosis,
) -> None:
    metadata = pod.get("metadata", {})
    status = pod.get("status", {})
    spec = pod.get("spec", {})
    pod_name = metadata.get("name", "<unknown>")
    phase = status.get("phase", "Unknown")

    if phase == "Succeeded" or _is_completed_pod(status):
        return

    if phase == "Pending":
        event_messages = _event_messages_for_pod(events, pod_name)
        diagnosis.findings.append(
            Finding(
                severity="critical",
                title=f"Pod is pending: {pod_name}",
                evidence=[f"phase={phase}", *event_messages[:5]],
                explanation="The pod has not been scheduled or started. Common causes are insufficient CPU or memory, node selectors, taints, PVC binding, or image pull delays.",
                recommended_commands=[
                    f"kubectl describe pod {pod_name} -n {namespace}",
                    f"kubectl get events -n {namespace} --sort-by=.lastTimestamp",
                    "kubectl describe nodes",
                ],
            )
        )

    not_ready_conditions = [
        condition
        for condition in status.get("conditions", [])
        if condition.get("status") == "False" and condition.get("type") in {"Ready", "ContainersReady"}
    ]
    if not_ready_conditions:
        primary = next(
            (condition for condition in not_ready_conditions if condition.get("type") == "Ready"),
            not_ready_conditions[0],
        )
        diagnosis.findings.append(
            Finding(
                severity="warning",
                title=f"Pod is not ready: {pod_name}",
                evidence=[
                    "conditions="
                    + ",".join(condition.get("type", "unknown") for condition in not_ready_conditions),
                    f"reason={primary.get('reason', 'unknown')}",
                    primary.get("message", ""),
                ],
                explanation="The pod is running but not ready to receive traffic. Failed readiness probes or container startup problems are common causes.",
                recommended_commands=[
                    f"kubectl describe pod {pod_name} -n {namespace}",
                    f"kubectl logs {pod_name} -n {namespace} --tail=200",
                ],
            )
        )

    for container_status in status.get("containerStatuses", []):
        _analyze_container_status(namespace, pod_name, container_status, logs, diagnosis)

    for init_status in status.get("initContainerStatuses", []):
        _analyze_container_status(namespace, pod_name, init_status, logs, diagnosis, init_container=True)

    for container in spec.get("containers", []):
        resources = container.get("resources", {})
        if not resources.get("limits"):
            diagnosis.findings.append(
                Finding(
                    severity="info",
                    title=f"Container has no resource limits: {pod_name}/{container.get('name')}",
                    evidence=["resources.limits is empty"],
                    explanation="Missing limits can make failure behavior harder to predict and can affect cluster stability.",
                    recommended_commands=[
                        f"kubectl get deployment -n {namespace}",
                        f"kubectl describe pod {pod_name} -n {namespace}",
                    ],
                )
            )


def _is_completed_pod(status: dict[str, Any]) -> bool:
    reasons = [
        condition.get("reason")
        for condition in status.get("conditions", [])
        if condition.get("type") in {"Ready", "ContainersReady"}
    ]
    if reasons and all(reason == "PodCompleted" for reason in reasons):
        return True

    container_statuses = status.get("containerStatuses", [])
    if not container_statuses:
        return False
    return all(
        container.get("state", {}).get("terminated", {}).get("exitCode") == 0
        for container in container_statuses
    )


def _analyze_container_status(
    namespace: str,
    pod_name: str,
    container_status: dict[str, Any],
    logs: dict[str, str],
    diagnosis: Diagnosis,
    init_container: bool = False,
) -> None:
    container_name = container_status.get("name", "<unknown>")
    state = container_status.get("state", {})
    last_state = container_status.get("lastState", {})
    restart_count = container_status.get("restartCount", 0)
    label = "init container" if init_container else "container"

    waiting = state.get("waiting")
    if waiting:
        reason = waiting.get("reason", "Waiting")
        severity = "critical" if reason in BAD_WAITING_REASONS else "warning"
        commands = [
            f"kubectl describe pod {pod_name} -n {namespace}",
            f"kubectl logs {pod_name} -n {namespace} -c {container_name} --tail=200",
        ]
        if reason == "CrashLoopBackOff":
            commands.append(f"kubectl logs {pod_name} -n {namespace} -c {container_name} --previous --tail=200")
        diagnosis.findings.append(
            Finding(
                severity=severity,
                title=f"{label.title()} waiting: {pod_name}/{container_name} ({reason})",
                evidence=[
                    f"reason={reason}",
                    waiting.get("message", ""),
                    f"restart_count={restart_count}",
                    *_log_hints(logs, pod_name, container_name),
                ],
                explanation=_waiting_explanation(reason),
                recommended_commands=commands,
            )
        )

    terminated = last_state.get("terminated") or state.get("terminated")
    if terminated:
        reason = terminated.get("reason", "Terminated")
        if reason == "OOMKilled":
            diagnosis.findings.append(
                Finding(
                    severity="critical",
                    title=f"Container was OOMKilled: {pod_name}/{container_name}",
                    evidence=[
                        f"reason={reason}",
                        f"exit_code={terminated.get('exitCode')}",
                        f"restart_count={restart_count}",
                    ],
                    explanation="The container exceeded its memory limit or the node was under memory pressure.",
                    recommended_commands=[
                        f"kubectl top pod {pod_name} -n {namespace}",
                        f"kubectl describe pod {pod_name} -n {namespace}",
                        f"kubectl logs {pod_name} -n {namespace} -c {container_name} --previous --tail=200",
                    ],
                )
            )
        elif terminated.get("exitCode") not in (None, 0):
            diagnosis.findings.append(
                Finding(
                    severity="warning",
                    title=f"Container exited non-zero: {pod_name}/{container_name}",
                    evidence=[
                        f"reason={reason}",
                        f"exit_code={terminated.get('exitCode')}",
                        terminated.get("message", ""),
                    ],
                    explanation="The process inside the container exited with an error. Review previous logs and startup configuration.",
                    recommended_commands=[
                        f"kubectl logs {pod_name} -n {namespace} -c {container_name} --previous --tail=200",
                        f"kubectl describe pod {pod_name} -n {namespace}",
                    ],
                )
            )

    if restart_count and restart_count >= 3:
        diagnosis.findings.append(
            Finding(
                severity="warning",
                title=f"High restart count: {pod_name}/{container_name}",
                evidence=[f"restart_count={restart_count}"],
                explanation="Repeated restarts usually indicate application crashes, probe failures, or resource pressure.",
                recommended_commands=[
                    f"kubectl logs {pod_name} -n {namespace} -c {container_name} --previous --tail=200",
                    f"kubectl describe pod {pod_name} -n {namespace}",
                ],
            )
        )


def _analyze_deployment(namespace: str, deployment_status: str, diagnosis: Diagnosis) -> None:
    lowered = deployment_status.lower()
    if "successfully rolled out" not in lowered:
        diagnosis.findings.append(
            Finding(
                severity="critical",
                title="Deployment rollout is not healthy",
                evidence=[deployment_status.strip()],
                explanation="The deployment rollout has not completed. Check replica availability, pod events, and image or probe failures.",
                recommended_commands=[
                    f"kubectl get deployments -n {namespace}",
                    f"kubectl describe deployment -n {namespace}",
                    f"kubectl get rs,pods -n {namespace}",
                ],
            )
        )


def _event_messages_for_pod(events: dict[str, Any], pod_name: str) -> list[str]:
    messages = []
    for event in events.get("items", []):
        involved = event.get("involvedObject", {})
        if involved.get("name") == pod_name:
            reason = event.get("reason", "Event")
            message = event.get("message", "")
            messages.append(f"{reason}: {message}")
    return messages


def _waiting_explanation(reason: str) -> str:
    explanations = {
        "CrashLoopBackOff": "The container is repeatedly crashing after startup. Review previous logs, environment variables, config mounts, probes, and resource limits.",
        "ImagePullBackOff": "Kubernetes cannot pull the container image. Check image name, tag, registry credentials, and network access.",
        "ErrImagePull": "The first image pull attempt failed. Check registry access, image path, and image pull secrets.",
        "CreateContainerConfigError": "Kubernetes could not build the container configuration. Missing ConfigMaps, Secrets, or invalid env references are common causes.",
        "RunContainerError": "The runtime failed to start the container. Check command, args, mounts, security context, and node runtime events.",
    }
    return explanations.get(reason, "The container is waiting. Inspect pod events and container logs for the exact reason.")


def _log_hints(logs: dict[str, str], pod_name: str, container_name: str) -> list[str]:
    hints = []
    for suffix in ("current", "previous"):
        text = logs.get(f"{pod_name}/{container_name}/{suffix}", "")
        lowered = text.lower()
        if "permission denied" in lowered:
            hints.append(f"{suffix}_logs_hint=permission denied")
        if "connection refused" in lowered:
            hints.append(f"{suffix}_logs_hint=connection refused")
        if "no such file" in lowered:
            hints.append(f"{suffix}_logs_hint=no such file")
        if "out of memory" in lowered or "oom" in lowered:
            hints.append(f"{suffix}_logs_hint=out of memory")
    return hints[:5]
