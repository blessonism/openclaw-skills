#!/usr/bin/env python3
"""
dependency-tracker: scan
Scans all installed skills and system dependencies, generates/updates manifest.
"""

import json
import os
import subprocess
import time
from pathlib import Path

from utils import (
    OPENCLAW_HOME, WORKSPACE, DATA_DIR, MANIFEST_PATH,
    SKILL_DIRS, LOCK_PATHS,
    sha256_file, git_hash_object, WarningCollector,
)

warnings = WarningCollector()

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")


def load_config():
    """Load user overrides from config.json."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def read_skill_frontmatter(skill_md_path):
    """Extract name, version, description from SKILL.md YAML frontmatter."""
    info = {}
    try:
        with open(skill_md_path, "r") as f:
            content = f.read(4096)  # frontmatter is always near the top
        if not content.startswith("---"):
            return info
        end = content.index("---", 3)
        fm = content[3:end]
        for line in fm.split("\n"):
            line = line.strip()
            if line.startswith("name:"):
                info["name"] = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("version:"):
                info["version"] = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
                if desc.startswith(">"):
                    desc = ""
                info["description"] = desc[:120]
    except Exception as e:
        warnings.add(skill_md_path, f"Failed to read frontmatter: {e}")
    return info


def read_lock_files():
    """Read all .skill-lock.json files and merge."""
    merged = {}
    for lp in LOCK_PATHS:
        if os.path.exists(lp):
            try:
                with open(lp) as f:
                    data = json.load(f)
                for name, info in data.get("skills", {}).items():
                    merged[name] = info
                    merged[name]["_lockFile"] = lp
            except Exception as e:
                warnings.add(lp, f"Failed to read lock file: {e}")
    return merged


def read_meta_files():
    """Read _meta.json files from skill directories."""
    metas = {}
    for category, base_dir in SKILL_DIRS.items():
        if not os.path.isdir(base_dir):
            continue
        for entry in os.listdir(base_dir):
            meta_path = os.path.join(base_dir, entry, "_meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path) as f:
                        metas[entry] = json.load(f)
                except Exception as e:
                    warnings.add(meta_path, f"Failed to read _meta.json: {e}")
    return metas


def get_openclaw_version():
    """Get current OpenClaw version."""
    try:
        result = subprocess.run(
            ["openclaw", "--version"], capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return None


def get_cli_versions():
    """Get versions of key CLI tools."""
    tools = {
        "codex": ["codex", "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "python3": ["python3", "--version"],
        "pip3": ["pip3", "--version"],
        "git": ["git", "--version"],
        "curl": ["curl", "--version"],
    }
    versions = {}
    for name, cmd in tools.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            # Some tools (python3) print to stderr
            ver = (result.stdout or result.stderr or "").strip().split("\n")[0]
            versions[name] = ver if ver else None
        except Exception:
            versions[name] = None
    return versions


def get_npm_global_outdated():
    """Get outdated npm global packages."""
    try:
        result = subprocess.run(
            ["npm", "outdated", "-g", "--json"],
            capture_output=True, text=True, timeout=30
        )
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception:
        return {}


def get_npm_app_outdated():
    """Get outdated npm packages in /app."""
    try:
        result = subprocess.run(
            ["npm", "outdated", "--json"],
            capture_output=True, text=True, timeout=30,
            cwd="/app"
        )
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception:
        return {}


def get_pip_outdated():
    """Get outdated pip packages."""
    try:
        result = subprocess.run(
            ["pip3", "list", "--outdated", "--format=json"],
            capture_output=True, text=True, timeout=30
        )
        return json.loads(result.stdout) if result.stdout.strip() else []
    except subprocess.TimeoutExpired:
        warnings.add("pip", "pip check timed out (30s), skipping")
        return []
    except Exception:
        return []


def find_skill_md(real_path):
    """Find SKILL.md in a skill directory (fast, safe)."""
    # 1. Direct root
    direct = os.path.join(real_path, "SKILL.md")
    if os.path.exists(direct):
        return direct

    # 2. Known nested paths
    candidates = [
        os.path.join(real_path, "integrations", "openclaw", "SKILL.md"),
        os.path.join(real_path, "integration", "openclaw", "SKILL.md"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    # 3. Shallow walk (max depth 4, skip heavy dirs)
    skip_dirs = {"node_modules", ".git", "data", "backups", "dist", "build", "__pycache__"}
    for root, dirs, files in os.walk(real_path):
        rel_depth = len(Path(root).relative_to(real_path).parts)
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        if rel_depth > 4:
            dirs[:] = []
            continue
        if "SKILL.md" in files:
            return os.path.join(root, "SKILL.md")

    return None


def scan_skills(openclaw_version=None):
    """Scan all skill directories and build inventory."""
    lock_data = read_lock_files()
    meta_data = read_meta_files()
    config = load_config()
    overrides = config.get("overrides", {})
    skills = {}

    for category, base_dir in SKILL_DIRS.items():
        if not os.path.isdir(base_dir):
            continue
        for entry in sorted(os.listdir(base_dir)):
            entry_path = os.path.join(base_dir, entry)

            if entry.startswith(".") or entry == "dependency-tracker":
                continue

            real_path = os.path.realpath(entry_path)
            is_symlink = os.path.islink(entry_path)

            skill_md = find_skill_md(real_path)
            if not skill_md:
                continue

            fm = read_skill_frontmatter(skill_md)
            skill_name = fm.get("name", entry)

            # Determine source
            source = {"type": "unknown"}
            lock_meta = None
            if category == "bundled":
                source = {"type": "bundled", "openclawVersion": openclaw_version}
            elif entry in lock_data:
                ld = lock_data[entry]
                lock_meta = ld
                source = {
                    "type": ld.get("sourceType", "github"),
                    "repo": ld.get("source", ""),
                    "repoUrl": ld.get("sourceUrl", ""),
                    "skillPath": ld.get("skillPath", ""),
                }
            elif entry in meta_data:
                md = meta_data[entry]
                source = {
                    "type": "clawhub",
                    "slug": md.get("slug", entry),
                    "owner": md.get("owner", ""),
                    "metaLatest": md.get("latest", {}),
                }
            elif category == "workspace":
                source = {"type": "local"}

            # Apply user overrides from config.json
            if entry in overrides:
                override = overrides[entry]
                source["type"] = override.get("type", source["type"])
                source["note"] = override.get("note", "")

            # Compute hashes (fast — SKILL.md only)
            content_hash = sha256_file(skill_md)
            skill_md_git_hash = git_hash_object(skill_md)

            # File modification time
            try:
                mtime = os.path.getmtime(skill_md)
                modified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
            except Exception:
                modified_at = None

            # Lock metadata
            installed_at = None
            folder_hash = None
            if lock_meta:
                installed_at = lock_meta.get("installedAt")
                folder_hash = lock_meta.get("skillFolderHash") or None

            skills[entry] = {
                "name": skill_name,
                "category": category,
                "source": source,
                "location": entry_path,
                "realPath": real_path,
                "isSymlink": is_symlink,
                "version": fm.get("version"),
                "description": fm.get("description", "")[:100],
                "contentHash": content_hash,
                "skillMdGitHash": skill_md_git_hash,
                "skillFolderHash": folder_hash,
                "installedAt": installed_at,
                "modifiedAt": modified_at,
            }

    return skills


def build_manifest():
    """Build the full dependency manifest."""
    print("🔍 Checking OpenClaw version...")
    openclaw_version = get_openclaw_version()

    print("🔍 Scanning skills...")
    skills = scan_skills(openclaw_version=openclaw_version)
    print(f"   Found {len(skills)} skills")

    print("🔍 Checking CLI tools...")
    cli_versions = get_cli_versions()

    print("🔍 Checking npm global outdated...")
    npm_global = get_npm_global_outdated()

    print("🔍 Checking OpenClaw npm dependencies...")
    npm_app = get_npm_app_outdated()

    print("🔍 Checking pip outdated...")
    pip_outdated = get_pip_outdated()

    manifest = {
        "version": "1.0.0",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "openclaw": {
            "version": openclaw_version,
        },
        "skills": skills,
        "cliTools": cli_versions,
        "npmGlobal": {
            "outdated": npm_global,
        },
        "npmApp": {
            "outdatedCount": len(npm_app),
            "outdated": {k: {"current": v.get("current"), "latest": v.get("latest")} for k, v in npm_app.items()},
        },
        "pipOutdated": {
            "count": len(pip_outdated),
            "packages": [{"name": p["name"], "current": p["version"], "latest": p["latest_version"]} for p in pip_outdated[:20]],
            "truncated": len(pip_outdated) > 20,
        },
        "warnings": warnings.to_list(),
    }

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Manifest written to {MANIFEST_PATH}")
    src_counts = {}
    for s in skills.values():
        t = s["source"]["type"]
        src_counts[t] = src_counts.get(t, 0) + 1
    parts = ", ".join(f"{v} {k}" for k, v in sorted(src_counts.items()))
    print(f"   Skills: {len(skills)} ({parts})")
    print(f"   npm app outdated: {len(npm_app)}")
    print(f"   pip outdated: {len(pip_outdated)}")
    if warnings.to_list():
        print(f"   ⚠️ Warnings: {len(warnings.to_list())}")

    return manifest


if __name__ == "__main__":
    build_manifest()
