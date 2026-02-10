#!/usr/bin/env python3
"""
dependency-tracker: check
Checks for updates by comparing local state against remote sources.
Reads manifest.json, queries GitHub API / ClewHub API / npm registry.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

from utils import (
    MANIFEST_PATH, RESULTS_PATH, DATA_DIR,
    GITHUB_API, CLAWHUB_API,
    api_get,
)


def check_github_skill(skill_info):
    """Check a GitHub-sourced skill for updates."""
    source = skill_info["source"]
    repo = source.get("repo", "")
    skill_path = source.get("skillPath", "")
    local_git_hash = skill_info.get("skillMdGitHash", "")

    if not repo or not skill_path:
        return {"status": "error", "reason": "missing repo or skillPath"}

    encoded_path = urllib.parse.quote(skill_path, safe="/")
    url = f"{GITHUB_API}/repos/{repo}/contents/{encoded_path}"
    data = api_get(url)

    if "_error" in data:
        return {"status": "error", "reason": data["_error"]}

    # Guard: GitHub may return a list (directory)
    if isinstance(data, list):
        skill_entry = next((e for e in data if e.get("name") == "SKILL.md"), None)
        if skill_entry:
            data = skill_entry
        else:
            return {"status": "error", "reason": f"skillPath is a directory without SKILL.md: {skill_path}"}

    remote_hash = data.get("sha", "")
    remote_size = data.get("size", 0)

    if local_git_hash and remote_hash:
        if local_git_hash == remote_hash:
            return {"status": "up-to-date", "localHash": local_git_hash[:12], "remoteHash": remote_hash[:12]}
        else:
            # Get recent commits for changelog
            dir_path = skill_path.rsplit("/SKILL.md", 1)[0] if "/SKILL.md" in skill_path else skill_path
            encoded_dir = urllib.parse.quote(dir_path, safe="/")
            commits_url = f"{GITHUB_API}/repos/{repo}/commits?path={encoded_dir}&per_page=5"
            commits_data = api_get(commits_url)
            changelog = []
            if isinstance(commits_data, list):
                for c in commits_data:
                    changelog.append({
                        "sha": c["sha"][:7],
                        "date": c["commit"]["committer"]["date"][:10],
                        "message": c["commit"]["message"].split("\n")[0][:120],
                    })

            # Fetch remote SKILL.md content for diff summary
            diff_summary = None
            try:
                raw_url = data.get("download_url", "")
                if raw_url:
                    req = urllib.request.Request(raw_url, headers={"User-Agent": "dependency-tracker/1.0"})
                    resp = urllib.request.urlopen(req, timeout=10)
                    remote_content = resp.read().decode("utf-8", errors="replace")

                    # Find local SKILL.md
                    local_md = None
                    for loc_key in ("realPath", "location"):
                        loc = skill_info.get(loc_key, "")
                        if loc:
                            candidate = os.path.join(os.path.realpath(loc), "SKILL.md")
                            if os.path.exists(candidate):
                                local_md = candidate
                                break

                    if local_md:
                        with open(local_md, "r") as f:
                            local_content = f.read()
                        local_lines = set(local_content.splitlines())
                        remote_lines = set(remote_content.splitlines())
                        added = len(remote_lines - local_lines)
                        removed = len(local_lines - remote_lines)

                        # Generate meaningful diff: show actual added/removed lines
                        added_lines = [l.strip() for l in remote_content.splitlines() if l.strip() and l not in local_content.splitlines()]
                        removed_lines = [l.strip() for l in local_content.splitlines() if l.strip() and l not in remote_content.splitlines()]

                        diff_summary = {
                            "added": added,
                            "removed": removed,
                            "localLines": len(local_content.splitlines()),
                            "remoteLines": len(remote_content.splitlines()),
                            "addedSample": added_lines[:10],
                            "removedSample": removed_lines[:10],
                        }
            except Exception:
                pass

            return {
                "status": "update-available",
                "localHash": local_git_hash[:12],
                "remoteHash": remote_hash[:12],
                "remoteSize": remote_size,
                "changelog": changelog,
                "diff": diff_summary,
            }

    return {"status": "unknown", "reason": "could not compare hashes"}


def check_clawhub_skill(skill_info):
    """Check a ClewHub-sourced skill for updates."""
    source = skill_info["source"]
    slug = source.get("slug", skill_info.get("name", ""))

    url = f"{CLAWHUB_API}/skills/{slug}"
    data = api_get(url)

    if "_error" in data:
        return {"status": "error", "reason": data["_error"]}

    latest_ver = data.get("latestVersion", {})
    remote_version = latest_ver.get("version", "")

    local_version = skill_info.get("version")
    if not local_version:
        local_version = (source.get("metaLatest") or {}).get("version")

    result = {
        "slug": slug,
        "remoteVersion": remote_version,
        "localVersion": local_version,
        "owner": data.get("owner", {}).get("handle"),
        "changelog": (latest_ver.get("changelog", "") or "")[:400],
    }

    if local_version and remote_version and local_version == remote_version:
        result["status"] = "up-to-date"
    elif remote_version and local_version:
        result["status"] = "update-available"
    elif remote_version and not local_version:
        result["status"] = "unknown-local-version"
    else:
        result["status"] = "unknown"

    return result


def check_openclaw_version(manifest):
    """Check if OpenClaw has a newer version, including release notes."""
    current = manifest.get("openclaw", {}).get("version", "")

    url = "https://registry.npmjs.org/openclaw/latest"
    data = api_get(url)
    npm_latest = data.get("version", "")

    gh_data = api_get(f"{GITHUB_API}/repos/openclaw/openclaw/releases/latest")
    gh_latest = gh_data.get("tag_name", "").lstrip("v")

    result = {
        "current": current,
        "npmLatest": npm_latest,
        "githubLatest": gh_latest,
    }

    if current and (npm_latest or gh_latest):
        latest = npm_latest or gh_latest
        if current == latest or current == gh_latest:
            result["status"] = "up-to-date"
        else:
            result["status"] = "update-available"
            # Fetch release notes for all versions between current and latest
            releases_data = api_get(f"{GITHUB_API}/repos/openclaw/openclaw/releases?per_page=10")
            release_notes = []
            if isinstance(releases_data, list):
                for rel in releases_data:
                    tag = rel.get("tag_name", "").lstrip("v")
                    if tag == current:
                        break  # Stop at current version
                    body = rel.get("body", "")
                    release_notes.append({
                        "version": tag,
                        "date": (rel.get("published_at") or "")[:10],
                        "name": rel.get("name", ""),
                        "body": body[:2000],  # Cap per release
                        "prerelease": rel.get("prerelease", False),
                    })
            result["releaseNotes"] = release_notes
    else:
        result["status"] = "unknown"

    return result


def enrich_npm_outdated(npm_outdated):
    """Add context about what key npm packages do."""
    known_packages = {
        "grammy": "Telegram Bot 框架 — 我们的 Telegram 通道核心依赖",
        "hono": "Web 框架 — Gateway HTTP 服务",
        "@buape/carbon": "Discord Bot 框架",
        "@homebridge/ciao": "mDNS/DNS-SD 服务发现",
        "@mariozechner/pi-agent-core": "Pi Coding Agent 核心",
        "@mariozechner/pi-ai": "Pi AI 接口层",
        "@mariozechner/pi-coding-agent": "Pi Coding Agent CLI",
        "@mariozechner/pi-tui": "Pi 终端 UI",
        "@napi-rs/canvas": "Node.js Canvas 图像处理",
        "playwright-core": "浏览器自动化引擎",
        "openai": "OpenAI API SDK",
    }
    enriched = []
    for item in npm_outdated:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            name, info = item
            entry = {
                "name": name,
                "current": info.get("current", "?"),
                "latest": info.get("latest", "?"),
                "context": known_packages.get(name, ""),
            }
            enriched.append(entry)
    return enriched


def check_all():
    """Run all checks and generate results."""
    if not os.path.exists(MANIFEST_PATH):
        print("❌ No manifest found. Run scan.py first.")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    results = {
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "openclaw": {},
        "skills": {},
        "summary": {"total": 0, "upToDate": 0, "updateAvailable": 0, "errors": 0, "skipped": 0},
    }

    print("🔍 Checking OpenClaw version...")
    results["openclaw"] = check_openclaw_version(manifest)
    print(f"   OpenClaw: {results['openclaw'].get('current', '?')} → {results['openclaw'].get('status', '?')}")

    skills = manifest.get("skills", {})
    print(f"\n🔍 Checking {len(skills)} skills...")

    for name, info in sorted(skills.items()):
        source_type = info.get("source", {}).get("type", "unknown")
        results["summary"]["total"] += 1

        if source_type == "github":
            print(f"   [{name}] checking GitHub ({info['source'].get('repo', '')})...")
            check = check_github_skill(info)
        elif source_type == "clawhub":
            print(f"   [{name}] checking ClewHub ({info['source'].get('slug', '')})...")
            check = check_clawhub_skill(info)
        elif source_type == "bundled":
            check = {"status": "bundled", "note": "Updates with OpenClaw version"}
            results["summary"]["skipped"] += 1
        elif source_type == "local":
            note = info.get("source", {}).get("note", "Self-managed via git")
            check = {"status": "local", "note": note or "Self-managed via git"}
            results["summary"]["skipped"] += 1
        else:
            check = {
                "status": "unknown-source",
                "note": "Source not tracked",
                "description": info.get("description", ""),
                "installedAt": info.get("installedAt"),
                "modifiedAt": info.get("modifiedAt"),
            }
            results["summary"]["skipped"] += 1

        status = check.get("status", "")
        if status == "up-to-date":
            results["summary"]["upToDate"] += 1
        elif status == "update-available":
            results["summary"]["updateAvailable"] += 1
        elif status == "error":
            results["summary"]["errors"] += 1

        results["skills"][name] = check

    # Enrich npm data
    raw_npm = list(manifest.get("npmApp", {}).get("outdated", {}).items())[:10]
    results["npmApp"] = {
        "outdatedCount": manifest.get("npmApp", {}).get("outdatedCount", 0),
        "topOutdated": raw_npm,
        "enriched": enrich_npm_outdated(raw_npm),
    }
    results["pipOutdated"] = {
        "count": manifest.get("pipOutdated", {}).get("count", 0),
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    s = results["summary"]
    print(f"\n{'='*60}")
    print(f"📊 Check Results Summary")
    print(f"{'='*60}")
    print(f"   Total skills:      {s['total']}")
    print(f"   ✅ Up to date:     {s['upToDate']}")
    print(f"   ⬆️  Update avail:  {s['updateAvailable']}")
    print(f"   ❌ Errors:         {s['errors']}")
    print(f"   ⏭️  Skipped:       {s['skipped']}")
    print(f"   npm outdated:      {results['npmApp']['outdatedCount']}")
    print(f"   pip outdated:      {results['pipOutdated']['count']}")

    if results["openclaw"].get("status") == "update-available":
        oc = results["openclaw"]
        print(f"\n   🔔 OpenClaw update: {oc['current']} → {oc.get('npmLatest') or oc.get('githubLatest')}")

    updates = [(n, r) for n, r in results["skills"].items() if r.get("status") == "update-available"]
    if updates:
        print(f"\n   🔔 Skills with updates:")
        for name, r in updates:
            print(f"      • {name}")
            if r.get("changelog"):
                if isinstance(r["changelog"], list):
                    for c in r["changelog"][:3]:
                        print(f"        {c['sha']} ({c['date']}) {c['message']}")
                else:
                    print(f"        {r['changelog'][:100]}")

    unknowns = [(n, r) for n, r in results["skills"].items() if r.get("status") == "unknown-source"]
    if unknowns:
        print(f"\n   ⚠️  Skills with unknown source ({len(unknowns)}):")
        for name, _ in unknowns:
            print(f"      • {name}")

    print(f"\n✅ Results written to {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    check_all()
