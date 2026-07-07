from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


class KubectlError(RuntimeError):
    pass


@dataclass
class Kubectl:
    namespace: str
    timeout_seconds: int = 20

    def _run(self, args: list[str]) -> str:
        if not args:
            raise KubectlError("No kubectl arguments provided")

        allowed_verbs = {"get", "describe", "logs", "top", "rollout"}
        if args[0] not in allowed_verbs:
            raise KubectlError(f"Blocked non-read-only kubectl command: {' '.join(args)}")

        command = ["kubectl", *args]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise KubectlError("kubectl is not installed or not available on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise KubectlError(f"kubectl timed out: {' '.join(command)}") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise KubectlError(f"kubectl failed: {' '.join(command)}\n{message}")
        return completed.stdout

    def get_json(self, resource: str, name: str | None = None) -> dict[str, Any]:
        target = resource if name is None else f"{resource}/{name}"
        output = self._run(["get", target, "-n", self.namespace, "-o", "json"])
        return json.loads(output)

    def get_cluster_json(self, resource: str, name: str | None = None) -> dict[str, Any]:
        target = resource if name is None else f"{resource}/{name}"
        output = self._run(["get", target, "-o", "json"])
        return json.loads(output)

    def get_raw(self, path: str) -> dict[str, Any]:
        output = self._run(["get", "--raw", path])
        return json.loads(output)

    def get_pods(self) -> dict[str, Any]:
        return self.get_json("pods")

    def get_pod(self, pod: str) -> dict[str, Any]:
        return self.get_json("pod", pod)

    def get_events(self) -> dict[str, Any]:
        return self.get_json("events")

    def get_nodes(self) -> dict[str, Any]:
        return self.get_cluster_json("nodes")

    def top_pods(self) -> str:
        return self._run(["top", "pod", "-n", self.namespace, "--no-headers"])

    def describe_pod(self, pod: str) -> str:
        return self._run(["describe", "pod", pod, "-n", self.namespace])

    def logs(self, pod: str, container: str | None = None, previous: bool = False) -> str:
        args = ["logs", pod, "-n", self.namespace, "--tail=200"]
        if container:
            args.extend(["-c", container])
        if previous:
            args.append("--previous")
        return self._run(args)

    def rollout_status(self, deployment: str) -> str:
        return self._run(["rollout", "status", f"deployment/{deployment}", "-n", self.namespace])
