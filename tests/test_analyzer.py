import unittest

from k8s_assistant.analyzer import analyze


class AnalyzerTest(unittest.TestCase):
    def test_detects_crash_loop(self):
        pods = {
            "items": [
                {
                    "metadata": {"name": "api-123"},
                    "spec": {"containers": [{"name": "api", "resources": {"limits": {"memory": "256Mi"}}}]},
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [
                            {
                                "name": "api",
                                "restartCount": 4,
                                "state": {"waiting": {"reason": "CrashLoopBackOff", "message": "back-off restarting failed container"}},
                                "lastState": {"terminated": {"reason": "Error", "exitCode": 1}},
                            }
                        ],
                    },
                }
            ]
        }

        diagnosis = analyze("staging", pods)

        titles = [finding.title for finding in diagnosis.findings]
        self.assertTrue(any("CrashLoopBackOff" in title for title in titles))
        self.assertTrue(any("High restart count" in title for title in titles))

    def test_detects_oom_killed(self):
        pods = {
            "items": [
                {
                    "metadata": {"name": "worker-123"},
                    "spec": {"containers": [{"name": "worker", "resources": {"limits": {"memory": "128Mi"}}}]},
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [
                            {
                                "name": "worker",
                                "restartCount": 1,
                                "state": {"running": {}},
                                "lastState": {"terminated": {"reason": "OOMKilled", "exitCode": 137}},
                            }
                        ],
                    },
                }
            ]
        }

        diagnosis = analyze("prod", pods)

        self.assertTrue(any("OOMKilled" in finding.title for finding in diagnosis.findings))

    def test_healthy_pod_has_no_findings(self):
        pods = {
            "items": [
                {
                    "metadata": {"name": "web-123"},
                    "spec": {"containers": [{"name": "web", "resources": {"limits": {"cpu": "500m", "memory": "256Mi"}}}]},
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "containerStatuses": [
                            {
                                "name": "web",
                                "restartCount": 0,
                                "state": {"running": {}},
                                "lastState": {},
                            }
                        ],
                    },
                }
            ]
        }

        diagnosis = analyze("default", pods)

        self.assertEqual([], diagnosis.findings)
        self.assertIn("No obvious", diagnosis.summary)

    def test_completed_job_pod_is_not_reported_as_not_ready(self):
        pods = {
            "items": [
                {
                    "metadata": {"name": "ingress-nginx-admission-create-dskqk"},
                    "spec": {"containers": [{"name": "create", "resources": {}}]},
                    "status": {
                        "phase": "Succeeded",
                        "conditions": [
                            {"type": "Ready", "status": "False", "reason": "PodCompleted"},
                            {"type": "ContainersReady", "status": "False", "reason": "PodCompleted"},
                        ],
                        "containerStatuses": [
                            {
                                "name": "create",
                                "restartCount": 0,
                                "state": {"terminated": {"reason": "Completed", "exitCode": 0}},
                                "lastState": {},
                            }
                        ],
                    },
                }
            ]
        }

        diagnosis = analyze("ingress-nginx", pods)

        self.assertEqual([], diagnosis.findings)

    def test_not_ready_conditions_are_deduplicated(self):
        pods = {
            "items": [
                {
                    "metadata": {"name": "api-123"},
                    "spec": {"containers": [{"name": "api", "resources": {"limits": {"memory": "256Mi"}}}]},
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {"type": "Ready", "status": "False", "reason": "ContainersNotReady"},
                            {"type": "ContainersReady", "status": "False", "reason": "ContainersNotReady"},
                        ],
                        "containerStatuses": [
                            {
                                "name": "api",
                                "restartCount": 0,
                                "state": {"running": {}},
                                "lastState": {},
                            }
                        ],
                    },
                }
            ]
        }

        diagnosis = analyze("staging", pods)

        not_ready = [finding for finding in diagnosis.findings if finding.title.startswith("Pod is not ready")]
        self.assertEqual(1, len(not_ready))

    def test_detects_high_cpu_usage(self):
        pods = {
            "items": [
                {
                    "metadata": {"name": "api-123"},
                    "spec": {
                        "containers": [
                            {
                                "name": "api",
                                "resources": {"limits": {"cpu": "500m", "memory": "256Mi"}},
                            }
                        ]
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "containerStatuses": [
                            {
                                "name": "api",
                                "restartCount": 0,
                                "state": {"running": {}},
                                "lastState": {},
                            }
                        ],
                    },
                }
            ]
        }

        diagnosis = analyze("prod", pods, pod_metrics={"api-123": {"cpu_millicores": 420}})

        self.assertTrue(any("CPU usage is high" in finding.title for finding in diagnosis.findings))

    def test_detects_high_pvc_usage(self):
        pods = {"items": []}
        pvc_usage = {
            "data-postgres-0": {
                "used_bytes": 90,
                "capacity_bytes": 100,
                "usage_percent": 90.0,
                "pods": ["postgres-0"],
            }
        }

        diagnosis = analyze("prod", pods, pvc_usage=pvc_usage)

        self.assertTrue(any("PVC usage is high" in finding.title for finding in diagnosis.findings))


if __name__ == "__main__":
    unittest.main()
