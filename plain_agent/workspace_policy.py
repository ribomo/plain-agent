"""Shared policy for paths hidden from workspace tools and sandboxes."""

IGNORED_DIRS = {".agents", ".codex", ".git", ".sandbox", ".venv", "__pycache__"}
SENSITIVE_FILE_NAMES = {".env", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa"}
SENSITIVE_FILE_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
BLOCKED_PATH_NAMES = IGNORED_DIRS | SENSITIVE_FILE_NAMES
