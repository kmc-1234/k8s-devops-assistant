from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

from .models import Diagnosis, Finding


def maybe_send_alert(diagnosis: Diagnosis) -> dict[str, object]:
    if not _env_bool("NOTIFICATIONS_ENABLED"):
        return {"enabled": False, "sent": False, "reason": "notifications disabled"}

    severities = _env_list("ALERT_SEVERITIES", "critical,warning")
    alert_findings = [finding for finding in diagnosis.findings if finding.severity in severities]
    if not alert_findings:
        return {"enabled": True, "sent": False, "reason": "no alert findings"}

    config = _smtp_config()
    missing = [key for key, value in config.items() if not value and key != "use_tls"]
    if missing:
        return {"enabled": True, "sent": False, "reason": "missing SMTP settings: " + ",".join(missing)}

    message = _build_message(diagnosis, alert_findings, config)
    context = ssl.create_default_context()
    with smtplib.SMTP(config["host"], int(config["port"]), timeout=20) as smtp:
        if config["use_tls"]:
            smtp.starttls(context=context)
        smtp.login(config["username"], config["password"])
        smtp.send_message(message)

    return {"enabled": True, "sent": True, "finding_count": len(alert_findings)}


def _smtp_config() -> dict[str, str | bool]:
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": os.getenv("SMTP_PORT", "587"),
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from": os.getenv("SMTP_FROM", ""),
        "to": os.getenv("ALERT_EMAIL_TO", ""),
        "use_tls": _env_bool("SMTP_STARTTLS", default=True),
    }


def _build_message(
    diagnosis: Diagnosis,
    findings: list[Finding],
    config: dict[str, str | bool],
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"Kubernetes alert: {diagnosis.namespace} - {len(findings)} finding(s)"
    message["From"] = str(config["from"])
    message["To"] = str(config["to"])
    message.set_content(_text_body(diagnosis, findings))
    return message


def _text_body(diagnosis: Diagnosis, findings: list[Finding]) -> str:
    lines = [
        f"Namespace: {diagnosis.namespace}",
        f"Summary: {diagnosis.summary}",
        "",
        "Findings:",
    ]
    for index, finding in enumerate(findings, start=1):
        lines.extend(
            [
                "",
                f"{index}. [{finding.severity}] {finding.title}",
                f"Explanation: {finding.explanation}",
                "Evidence:",
                *[f"- {item}" for item in finding.evidence if item],
                "Recommended commands:",
                *[f"- {command}" for command in finding.recommended_commands],
            ]
        )
    return "\n".join(lines)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> set[str]:
    value = os.getenv(name, default)
    return {item.strip().lower() for item in value.split(",") if item.strip()}
