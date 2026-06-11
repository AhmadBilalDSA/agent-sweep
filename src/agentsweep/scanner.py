from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    rule: str
    display: str
    value: str
    masked: str
    span: tuple[int, int]
    file: Path | None = None
    line: int | None = None
    keypath: list = field(default_factory=list)


RULES: list[tuple[str, str, re.Pattern]] = [
    ("aws-access-key", "AWS access key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws-session-token", "AWS session token",
        re.compile(r"\bASIA[0-9A-Z]{16}\b")),
    ("github-pat", "GitHub PAT",
        re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("github-oauth", "GitHub OAuth token",
        re.compile(r"\bgho_[A-Za-z0-9]{36}\b")),
    ("github-app", "GitHub App token",
        re.compile(r"\b(?:ghs|ghu)_[A-Za-z0-9]{36}\b")),
    ("github-fine-grained", "GitHub fine-grained PAT",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b")),
    ("stripe-live", "Stripe live secret key",
        re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{24,}\b")),
    ("stripe-test", "Stripe test secret key",
        re.compile(r"\b(?:sk|rk)_test_[A-Za-z0-9]{24,}\b")),
    ("openai", "OpenAI API key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b")),
    ("anthropic", "Anthropic API key",
        re.compile(r"\bsk-ant-(?:api|sid)[0-9]*-[A-Za-z0-9_-]{32,}\b")),
    ("google-api", "Google API key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack-bot", "Slack bot token",
        re.compile(r"\bxoxb-[A-Za-z0-9-]{10,}\b")),
    ("slack-user", "Slack user token",
        re.compile(r"\bxoxp-[A-Za-z0-9-]{10,}\b")),
    ("slack-webhook", "Slack webhook URL",
        re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+")),
    ("huggingface", "Hugging Face token",
        re.compile(r"\bhf_[A-Za-z0-9]{34}\b")),
    ("jwt", "JSON Web Token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("private-key-pem", "Private key (PEM block)",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
                   r"[\s\S]+?-----END (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----")),
    ("db-url-with-password", "Database URL with password",
        re.compile(r"\b(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp)://"
                   r"[^:/\s]+:[^@\s'\"]+@[^\s'\"/]+")),
    ("npm-token", "npm access token",
        re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("pypi-token", "PyPI upload token",
        re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}\b")),
    ("sendgrid", "SendGrid API key",
        re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b")),
    ("twilio", "Twilio API key",
        re.compile(r"\bSK[0-9a-fA-F]{32}\b")),
]


def mask(secret: str) -> str:
    if len(secret) <= 12:
        return secret[:3] + "*" * max(0, len(secret) - 3)
    return secret[:6] + "*" * 8 + secret[-4:]


def scan_text(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, display, pattern in RULES:
        for m in pattern.finditer(text):
            val = m.group(0)
            findings.append(Finding(
                rule=rule_id,
                display=display,
                value=val,
                masked=mask(val),
                span=(m.start(), m.end()),
            ))
    findings.sort(key=lambda f: f.span[0])
    return _dedupe_overlapping(findings)


def _dedupe_overlapping(findings: list[Finding]) -> list[Finding]:
    if not findings:
        return findings
    out = [findings[0]]
    for f in findings[1:]:
        last = out[-1]
        if f.span[0] < last.span[1]:
            if (f.span[1] - f.span[0]) > (last.span[1] - last.span[0]):
                out[-1] = f
            continue
        out.append(f)
    return out


ROTATION_GUIDANCE: dict[str, str] = {
    "aws-access-key": "Rotate: aws iam create-access-key, then aws iam delete-access-key --access-key-id <ID>",
    "aws-session-token": "Session tokens are short-lived; rotate the underlying IAM role/user credentials.",
    "github-pat": "Revoke: https://github.com/settings/tokens",
    "github-oauth": "Revoke: https://github.com/settings/applications",
    "github-app": "Rotate via your GitHub App's settings page.",
    "github-fine-grained": "Revoke: https://github.com/settings/tokens?type=beta",
    "stripe-live": "Roll: https://dashboard.stripe.com/apikeys",
    "stripe-test": "Roll: https://dashboard.stripe.com/test/apikeys",
    "openai": "Revoke: https://platform.openai.com/api-keys",
    "anthropic": "Revoke: https://console.anthropic.com/settings/keys",
    "google-api": "Rotate: https://console.cloud.google.com/apis/credentials",
    "slack-bot": "Rotate: https://api.slack.com/apps (OAuth & Permissions)",
    "slack-user": "Rotate: https://api.slack.com/apps (OAuth & Permissions)",
    "slack-webhook": "Regenerate the webhook in the Slack app that owns it.",
    "huggingface": "Revoke: https://huggingface.co/settings/tokens",
    "jwt": "Invalidate at the issuing service; short-lived tokens may expire naturally.",
    "private-key-pem": "Regenerate the key pair and rotate any authorized_keys / cert stores that reference it.",
    "db-url-with-password": "Change the database user's password and update connection strings.",
    "npm-token": "Revoke: https://www.npmjs.com/settings/~/tokens",
    "pypi-token": "Revoke: https://pypi.org/manage/account/token/",
    "sendgrid": "Rotate: https://app.sendgrid.com/settings/api_keys",
    "twilio": "Rotate: https://console.twilio.com/us1/account/keys-credentials/api-keys",
}
