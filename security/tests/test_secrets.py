import ast
from pathlib import Path

from security.secrets import redact, scan_text

ROOT = Path(__file__).resolve().parents[2]

# built at runtime so no literal token sits in the repository
GITHUB_TOKEN = "ghp_" + "Zx81Kq0LmP3vT9sYw2Ru" + "Jc6Hn4Bd7Ea5Gf1Ii0Oo"
HF_TOKEN = "hf_" + "QeRtYuIoPaSdFgHjKlZxCvBnMqWeRtYuIo"


def rules(text):
    return {f.rule for f in scan_text(text)}


def test_demo_repo_settings_secrets_are_found():
    text = (ROOT / "demo_repo" / "tinyshop" / "settings.py").read_text()
    found = {(f.rule, f.line) for f in scan_text(text)}
    assert ("aws-access-key", 9) in found
    assert ("aws-secret-key", 10) in found
    assert ("generic-secret", 8) in found


def test_known_token_formats():
    assert "github-token" in rules(f'token = "{GITHUB_TOKEN}"')
    assert "huggingface-token" in rules(f"HF={HF_TOKEN}")
    key = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----"
    assert "private-key" in rules(key)


def test_ordinary_strings_are_not_secrets():
    code = (
        'COLOR = "ffffff"\n'
        'password_hint = "ask the manager"\n'
        'TOKEN_URL = "https://example.com/oauth/token"\n'
        'secret_key = os.environ["SECRET_KEY"]\n'
        'API_KEY = ""\n'
        "tokenizer='Qwen/Qwen2.5-Coder-1.5B-Instruct', tokens_per_second = 'fast-1234567890'\n"
    )
    assert scan_text(code) == []


def test_redaction_keeps_code_parseable_and_removes_values():
    text = (ROOT / "demo_repo" / "tinyshop" / "settings.py").read_text()
    clean = redact(text)
    ast.parse(clean)
    assert "AKIAIOSFODNN7EXAMPLE" not in clean
    assert "wJalrXUtnFEMI" not in clean
    assert "f3b1c9e07a5d4e2b8c6a9d0e1f2a3b4c" not in clean
    assert '"[REDACTED:aws-access-key]"' in clean
    assert "VAT_RATE = 0.20" in clean
