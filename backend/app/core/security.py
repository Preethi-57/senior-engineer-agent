import re

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]{20,}"),
]

def redact_secrets(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda m: "[REDACTED]", text)
    return text
