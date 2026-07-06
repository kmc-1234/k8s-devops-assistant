from __future__ import annotations

import argparse
import json
import sys

from .api import serve
from .runner import run_diagnosis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI-assisted Kubernetes troubleshooting")
    subparsers = parser.add_subparsers(dest="command", required=True)

    diagnose = subparsers.add_parser("diagnose", help="Diagnose Kubernetes workload health")
    diagnose.add_argument("--namespace", "-n", default="default")
    diagnose.add_argument("--pod")
    diagnose.add_argument("--deployment")
    diagnose.add_argument("--ai", action="store_true", help="Include optional OpenAI summary")
    diagnose.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    server = subparsers.add_parser("serve", help="Start local HTTP API")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)

    args = parser.parse_args(argv)

    if args.command == "serve":
        serve(args.host, args.port)
        return 0

    diagnosis = run_diagnosis(
        namespace=args.namespace,
        pod=args.pod,
        deployment=args.deployment,
        include_ai=args.ai,
    )
    if args.json:
        print(json.dumps(diagnosis.as_dict(), indent=2))
    else:
        _print_human(diagnosis.as_dict())
    return 0


def _print_human(payload: dict) -> None:
    print(f"Namespace: {payload['namespace']}")
    print(f"Summary: {payload['summary']}")
    if payload.get("ai_summary"):
        print("\nAI summary:")
        print(payload["ai_summary"])

    findings = payload.get("findings", [])
    if not findings:
        return

    print("\nFindings:")
    for index, finding in enumerate(findings, start=1):
        print(f"\n{index}. [{finding['severity']}] {finding['title']}")
        print(f"   Why: {finding['explanation']}")
        evidence = [item for item in finding.get("evidence", []) if item]
        if evidence:
            print("   Evidence:")
            for item in evidence:
                print(f"   - {item}")
        commands = finding.get("recommended_commands", [])
        if commands:
            print("   Recommended commands:")
            for command in commands:
                print(f"   - {command}")


if __name__ == "__main__":
    sys.exit(main())

