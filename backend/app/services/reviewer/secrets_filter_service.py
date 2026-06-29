from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings
import tempfile
import os
import re


# Regex patterns for token formats
COMMON_PATTERNS = [
    r'AIza[0-9A-Za-z\-_]{35}',                          
    r'AKIA[0-9A-Z]{16}',                                  
    r'gh[pousr]_[A-Za-z0-9]+',                        
    r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', 
    r'-----BEGIN PRIVATE KEY-----[\s\S]*?-----END PRIVATE KEY-----',
    r'Bearer\s+[A-Za-z0-9\-._~+/]+=*'
]


def scan_diff(diff_text):
    with tempfile.NamedTemporaryFile(mode="w",suffix=".txt",delete=False,encoding="utf-8") as f:
        f.write(diff_text)
        temp_path = f.name

    try:
        with default_settings():
            secrets = SecretsCollection()
            secrets.scan_file(temp_path)

            print("detect-secrets executed successfully")
            print("Files scanned:", secrets.files)

            return []

    finally:
        os.remove(temp_path)


def redact_text(text):
    MASK = "xxxx"

    # Database URLs
    text = re.sub(
        r'postgres(?:ql)?://[^:\s]+:[^@\s]+@[^"\']+',
        "postgres://"+MASK,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'mysql://[^:\s]+:[^@\s]+@[^"\']+',
        "mysql://"+MASK,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'mongodb(?:\+srv)?://[^:\s]+:[^@\s]+@[^"\']+',
        "mongodb://"+MASK,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'redis://[^:\s]+:[^@\s]+@[^"\']+',
        "redis://"+MASK,
        text,
        flags=re.IGNORECASE
    )

    # SQL Connection String
    text = re.sub(
        r'(?i)(connection_string\s*=\s*["\']).*?(["\'])',
        r'\1'+MASK+r'\2',
        text
    )

    # Generic sensitive variables
    variables = [
        "password",
        "db_password",
        "passwd",
        "pwd",
        "secret",
        "client_secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "connection_string"
    ]

    for var in variables:

        pattern = rf'(?i)({var}\s*=\s*["\'])(.*?)(["\'])'

        text = re.sub(
            pattern,
            rf'\1{MASK}\3',
            text
        )

    # JWT
    text = re.sub(
        r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
        MASK,
        text
    )

    # GitHub PAT
    text = re.sub(
        r'gh[pousr]_[A-Za-z0-9]+',
        MASK,
        text
    )

    # AWS Access Key
    text = re.sub(
        r'AKIA[0-9A-Z]{16}',
        MASK,
        text
    )

    # Google API Key
    text = re.sub(
        r'AIza[0-9A-Za-z\-_]{35}',
        MASK,
        text
    )

    # Bearer Token
    text = re.sub(
        r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',
        "Bearer "+MASK,
        text
    )

    # Private Keys
    text = re.sub(
        r'-----BEGIN[\s\S]*?PRIVATE KEY-----[\s\S]*?-----END[\s\S]*?PRIVATE KEY-----',
        "[MASKED_PRIVATE_KEY]",
        text
    )

    return text

def sanitize_files(files):

    sanitized = []

    for file in files:

        findings = scan_diff(file["diff"])

        masked_diff = redact_text(file["diff"])

        sanitized.append({
            "path": file["path"],
            "change_type": file["change_type"],
            "secret_findings": findings,
            "diff": masked_diff
        })

    return sanitized