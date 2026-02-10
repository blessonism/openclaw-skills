#!/usr/bin/env python3
"""
dependency-tracker: shared utilities
Centralized path resolution, HTTP helpers, and constants.
"""

import json
import os
import hashlib
import subprocess
import urllib.request
import urllib.error

# ─── Path Resolution ───────────────────────────────────────────────

OPENCLAW_HOME = os.environ.get("OPENCLAW_HOME", os.path.expanduser("~/.openclaw"))
WORKSPACE = os.environ.get("WORKSPACE", os.path.join(OPENCLAW_HOME, "workspace"))
DATA_DIR = os.path.join(WORKSPACE, "skills/dependency-tracker/data")
MANIFEST_PATH = os.path.join(DATA_DIR, "manifest.json")
RESULTS_PATH = os.path.join(DATA_DIR, "check-results.json")
REPORT_DIR = os.path.join(DATA_DIR, "reports")

SKILL_DIRS = {
    "bundled": "/app/skills",
    "managed": os.path.join(OPENCLAW_HOME, "skills"),
    "workspace": os.path.join(WORKSPACE, "skills"),
}

LOCK_PATHS = [
    os.path.join(os.path.expanduser("~/.agents"), ".skill-lock.json"),
    os.path.join(WORKSPACE, ".agents/.skill-lock.json"),
]

GITHUB_API = "https://api.github.com"
CLAWHUB_API = "https://clawhub.ai/api/v1"


# ─── GitHub Token ──────────────────────────────────────────────────

def get_github_token():
    """Try to find a GitHub token from environment or git credentials."""
    # 1. Environment variable
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token

    # 2. Git credential store
    cred_path = os.path.expanduser("~/.git-credentials")
    if os.path.exists(cred_path):
        try:
            with open(cred_path) as f:
                for line in f:
                    if "github.com" in line:
                        # Format: https://user:token@github.com
                        parts = line.strip().split(":")
                        if len(parts) >= 3:
                            token_part = parts[2].split("@")[0]
                            if token_part:
                                return token_part
        except Exception:
            pass

    return None


# ─── HTTP Helpers ──────────────────────────────────────────────────

def api_get(url, timeout=15):
    """GET JSON from URL with optional GitHub auth."""
    headers = {"User-Agent": "dependency-tracker/1.0"}

    # Add GitHub auth if available and it's a GitHub API call
    if "api.github.com" in url:
        token = get_github_token()
        if token:
            headers["Authorization"] = f"token {token}"

    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "_url": url}
    except Exception as e:
        return {"_error": str(e), "_url": url}


# ─── Hashing ──────────────────────────────────────────────────────

def sha256_file(path):
    """Compute SHA-256 of a file (first 16 hex chars)."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return None


def git_hash_object(path):
    """Get git blob hash of a file (same as GitHub API sha)."""
    try:
        result = subprocess.run(
            ["git", "hash-object", path],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


# ─── Path Redaction ────────────────────────────────────────────────

def redact_path(path):
    """Redact absolute paths to workspace-relative for external reports."""
    if not path:
        return "?"
    path = str(path)
    # Try multiple known prefixes
    for prefix, label in [
        (WORKSPACE + "/", "workspace/"),
        (OPENCLAW_HOME + "/", "~openclaw/"),
        (os.path.expanduser("~") + "/", "~/"),
        ("/app/", "bundled/"),
    ]:
        if path.startswith(prefix):
            return label + path[len(prefix):]
    return path


# ─── Warnings Collector ───────────────────────────────────────────

class WarningCollector:
    """Collect non-fatal warnings during scan/check."""

    def __init__(self):
        self.warnings = []

    def add(self, source, message):
        self.warnings.append({"source": source, "message": message})
        print(f"   ⚠️ [{source}] {message}")

    def to_list(self):
        return self.warnings
