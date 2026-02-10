#!/usr/bin/env python3
"""
dependency-tracker: report
Generates a detailed, human-readable Markdown report from check results.
"""

import json
import os
import sys
import time

from utils import (
    MANIFEST_PATH, RESULTS_PATH, REPORT_DIR,
    redact_path,
)


def generate_report():
    """Generate Markdown report from check results."""
    if not os.path.exists(RESULTS_PATH):
        print("❌ No check results found. Run check.py first.")
        sys.exit(1)

    with open(RESULTS_PATH) as f:
        results = json.load(f)

    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

    checked_at = results.get("checkedAt", "unknown")
    summary = results.get("summary", {})

    lines = []
    lines.append("# 🔍 Dependency Tracker Report")
    lines.append(f"\n> Generated: {checked_at}")
    lines.append("")

    # ── Quick Summary ──────────────────────────────────────────
    update_count = summary.get("updateAvailable", 0)
    npm_count = results.get("npmApp", {}).get("outdatedCount", 0)
    pip_count = results.get("pipOutdated", {}).get("count", 0)
    unknown_count = sum(1 for r in results.get("skills", {}).values() if r.get("status") == "unknown-source")

    lines.append("## 📋 一句话总结")
    lines.append("")
    parts = []
    if update_count:
        parts.append(f"**{update_count} 个 skill 有更新**")
    if npm_count:
        parts.append(f"{npm_count} 个 npm 包可更新")
    if pip_count:
        parts.append(f"{pip_count} 个 pip 包可更新")
    if unknown_count:
        parts.append(f"{unknown_count} 个 skill 来源不明")
    if not parts:
        lines.append("✅ 一切正常，所有依赖均为最新。")
    else:
        lines.append("、".join(parts) + "。")
    lines.append("")

    # ── OpenClaw ───────────────────────────────────────────────
    oc = results.get("openclaw", {})
    oc_status = "✅ 最新" if oc.get("status") == "up-to-date" else "⬆️ 可更新" if oc.get("status") == "update-available" else "❓"
    lines.append("## OpenClaw")
    lines.append("")
    lines.append(f"| 当前 | npm latest | GitHub latest | 状态 |")
    lines.append(f"|------|-----------|--------------|------|")
    lines.append(f"| {oc.get('current', '?')} | {oc.get('npmLatest', '?')} | {oc.get('githubLatest', '?')} | {oc_status} |")
    lines.append("")

    # Release notes if update available
    release_notes = oc.get("releaseNotes", [])
    if release_notes:
        lines.append(f"### 📝 更新内容 ({oc.get('current', '?')} → {oc.get('githubLatest') or oc.get('npmLatest', '?')})")
        lines.append("")
        for rel in release_notes:
            ver = rel.get("version", "?")
            date = rel.get("date", "?")
            pre = " (prerelease)" if rel.get("prerelease") else ""
            lines.append(f"#### v{ver} ({date}){pre}")
            lines.append("")
            body = rel.get("body", "").strip()
            if body:
                # Indent the release body
                for bline in body.split("\n"):
                    lines.append(bline)
            lines.append("")

    # ── Skills with Updates ────────────────────────────────────
    updates = {n: r for n, r in results.get("skills", {}).items() if r.get("status") == "update-available"}
    if updates:
        lines.append("## ⬆️ 可更新的 Skills")
        lines.append("")
        for name, r in sorted(updates.items()):
            skill_info = manifest.get("skills", {}).get(name, {})
            source = skill_info.get("source", {})
            source_type = source.get("type", "unknown")
            desc = skill_info.get("description", "")

            lines.append(f"### {name}")
            if desc:
                lines.append(f"> {desc}")
            lines.append("")

            if source_type == "clawhub":
                slug = r.get("slug") or source.get("slug") or name
                owner = r.get("owner") or source.get("owner")
                lines.append(f"- **来源**: ClawHub — [{owner}/{slug}](https://clawhub.ai/skills/{slug})")
                lines.append(f"- **版本变化**: `{r.get('localVersion', '?')}` → `{r.get('remoteVersion', '?')}`")
                if r.get("changelog"):
                    lines.append(f"- **Changelog**:")
                    lines.append(f"  ```")
                    lines.append(f"  {r['changelog'][:400]}")
                    lines.append(f"  ```")
            else:
                repo = source.get("repo", "")
                repo_url = (source.get("repoUrl", "") or "").rstrip(".git")
                lines.append(f"- **来源**: GitHub — [{repo}]({repo_url})" if repo_url else f"- **来源**: {repo}")
                lines.append(f"- **Hash 变化**: `{r.get('localHash', '?')}` → `{r.get('remoteHash', '?')}`")

                # Diff summary
                diff = r.get("diff")
                if diff:
                    lines.append(f"- **变更规模**: +{diff['added']} 行 / -{diff['removed']} 行 (本地 {diff['localLines']} 行 → 远程 {diff['remoteLines']} 行)")

                    added_sample = diff.get("addedSample", [])
                    removed_sample = diff.get("removedSample", [])
                    if added_sample or removed_sample:
                        lines.append(f"- **具体变更**:")
                        if added_sample:
                            lines.append(f"  - 新增:")
                            lines.append(f"    ```")
                            for al in added_sample[:8]:
                                lines.append(f"    + {al[:120]}")
                            lines.append(f"    ```")
                        if removed_sample:
                            lines.append(f"  - 删除:")
                            lines.append(f"    ```")
                            for rl in removed_sample[:8]:
                                lines.append(f"    - {rl[:120]}")
                            lines.append(f"    ```")

                # Changelog with commits
                if r.get("changelog") and isinstance(r["changelog"], list):
                    lines.append(f"- **最近提交** ({len(r['changelog'])} 条):")
                    for c in r["changelog"][:5]:
                        lines.append(f"  - `{c['sha']}` ({c['date']}) {c['message']}")

            lines.append("")

    # ── Skills Up to Date ──────────────────────────────────────
    up_to_date = {n: r for n, r in results.get("skills", {}).items() if r.get("status") == "up-to-date"}
    if up_to_date:
        lines.append("## ✅ 已是最新的 Skills")
        lines.append("")
        lines.append("| Skill | 来源 | 本地标识 |")
        lines.append("|-------|------|----------|")
        for name, r in sorted(up_to_date.items()):
            skill_info = manifest.get("skills", {}).get(name, {})
            source = skill_info.get("source", {})
            st = source.get("type")
            if st == "clawhub":
                slug = r.get("slug") or source.get("slug") or name
                owner = r.get("owner") or source.get("owner")
                local_id = r.get("localVersion") or (source.get("metaLatest") or {}).get("version") or "?"
                lines.append(f"| {name} | ClawHub ({owner or '?'}/{slug}) | v{local_id} |")
            else:
                repo = source.get("repo", "")
                lines.append(f"| {name} | {repo} | `{(r.get('localHash') or '?')[:12]}` |")
        lines.append("")

    # ── Unknown Source Skills ──────────────────────────────────
    unknowns = {n: r for n, r in results.get("skills", {}).items() if r.get("status") == "unknown-source"}
    if unknowns:
        lines.append("## ⚠️ 来源不明的 Skills")
        lines.append("")
        lines.append("以下 skills 无法追踪更新。需要 Boss 确认来源后标注到 `config.json`。")
        lines.append("")
        for name in sorted(unknowns.keys()):
            r = unknowns[name]
            skill_info = manifest.get("skills", {}).get(name, {})
            location = redact_path(skill_info.get("location", "?"))
            desc = skill_info.get("description", "无描述")
            installed_at = r.get("installedAt") or skill_info.get("installedAt") or "未知"
            modified_at = r.get("modifiedAt") or skill_info.get("modifiedAt") or "未知"

            lines.append(f"### {name}")
            lines.append(f"> {desc}")
            lines.append("")
            lines.append(f"- **位置**: `{location}`")
            lines.append(f"- **安装时间**: {installed_at}")
            lines.append(f"- **最后修改**: {modified_at}")
            lines.append("")

    # ── Bundled / Local (compact) ──────────────────────────────
    bundled = {n: r for n, r in results.get("skills", {}).items() if r.get("status") in ("bundled", "local")}
    if bundled:
        bundled_count = sum(1 for r in bundled.values() if r.get("status") == "bundled")
        local_items = [(n, r) for n, r in sorted(bundled.items()) if r.get("status") == "local"]

        lines.append("## 📦 内置 / 本地 Skills")
        lines.append("")
        lines.append(f"- **内置 (bundled)**: {bundled_count} 个 — 随 OpenClaw 版本更新")
        if local_items:
            lines.append(f"- **本地 (workspace)**: {len(local_items)} 个")
            for name, r in local_items:
                note = r.get("note", "")
                if note and note != "Self-managed via git":
                    lines.append(f"  - `{name}` — {note}")
                else:
                    lines.append(f"  - `{name}`")
        lines.append("")

    # ── npm Dependencies ───────────────────────────────────────
    npm_app = results.get("npmApp", {})
    if npm_app.get("outdatedCount", 0) > 0:
        lines.append(f"## npm 依赖 — {npm_app['outdatedCount']} 个可更新")
        lines.append("")

        enriched = npm_app.get("enriched", [])
        if enriched:
            lines.append("| 包名 | 当前 | 最新 | 说明 |")
            lines.append("|------|------|------|------|")
            for e in enriched:
                ctx = e.get("context", "")
                lines.append(f"| {e['name']} | {e['current']} | {e['latest']} | {ctx} |")
        else:
            lines.append("| 包名 | 当前 | 最新 |")
            lines.append("|------|------|------|")
            for item in npm_app.get("topOutdated", []):
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    name, info = item
                    lines.append(f"| {name} | {info.get('current', '?')} | {info.get('latest', '?')} |")
        lines.append("")

    # ── pip Dependencies ───────────────────────────────────────
    pip_count = results.get("pipOutdated", {}).get("count", 0)
    if pip_count > 0:
        lines.append(f"## pip 依赖 — {pip_count} 个可更新")
        lines.append("")
        pip_pkgs = manifest.get("pipOutdated", {}).get("packages", [])
        if pip_pkgs:
            # Highlight important ones
            important = {"anthropic", "openai", "aiohttp", "beautifulsoup4", "google-generativeai"}
            important_pkgs = [p for p in pip_pkgs if p["name"].lower() in important]
            other_pkgs = [p for p in pip_pkgs if p["name"].lower() not in important]

            if important_pkgs:
                lines.append("**关键包：**")
                lines.append("")
                lines.append("| 包名 | 当前 | 最新 | 说明 |")
                lines.append("|------|------|------|------|")
                pip_context = {
                    "anthropic": "Claude API SDK",
                    "openai": "OpenAI API SDK",
                    "aiohttp": "异步 HTTP 客户端",
                    "beautifulsoup4": "HTML 解析",
                    "google-generativeai": "Gemini API SDK",
                }
                for p in important_pkgs:
                    ctx = pip_context.get(p["name"].lower(), "")
                    lines.append(f"| {p['name']} | {p['current']} | {p['latest']} | {ctx} |")
                lines.append("")

            if other_pkgs:
                lines.append(f"**其他 {len(other_pkgs)} 个包**（随 Docker 镜像更新）：")
                names = ", ".join(f"`{p['name']}`" for p in other_pkgs[:15])
                if len(other_pkgs) > 15:
                    names += f" ... 等 {len(other_pkgs)} 个"
                lines.append(names)
                lines.append("")

    # ── Scan Warnings ──────────────────────────────────────────
    scan_warnings = manifest.get("warnings", [])
    if scan_warnings:
        lines.append("## ⚠️ 扫描警告")
        lines.append("")
        for w in scan_warnings:
            lines.append(f"- [{redact_path(w.get('source', '?'))}] {w.get('message', '')}")
        lines.append("")

    # ── Footer ─────────────────────────────────────────────────
    lines.append("---")
    lines.append(f"*Generated by dependency-tracker | {checked_at}*")

    report = "\n".join(lines)

    # Write report
    os.makedirs(REPORT_DIR, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d", time.gmtime())
    report_path = os.path.join(REPORT_DIR, f"{date_str}-report.md")
    with open(report_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\n📄 Report saved to {report_path}")
    return report_path


if __name__ == "__main__":
    generate_report()
