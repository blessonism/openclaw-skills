---
name: dependency-tracker
description: "Track and check updates for all OpenClaw dependencies: managed skills (GitHub/ClewHub), bundled skills, workspace skills, npm packages, pip packages, and CLI tools. Use when user asks 'check for updates', 'dependency status', 'are my skills up to date', '什么需要更新', '检查依赖', '检查更新', or wants a dependency health report. Triggers on: dependency check, skill updates, outdated packages, version drift."
---

# Dependency Tracker

Track version drift across all OpenClaw dependencies. Detect updates, generate reports, notify Boss.

## Quick Start

```bash
# Full pipeline (run from skill directory)
SKILL_DIR=~/.openclaw/workspace/skills/dependency-tracker

# 1. Scan — build/refresh the local manifest
python3 $SKILL_DIR/scripts/scan.py

# 2. Check — compare local vs remote versions
python3 $SKILL_DIR/scripts/check.py

# 3. Report — generate human-readable Markdown report
python3 $SKILL_DIR/scripts/report.py
```

## What It Tracks

| Category | Source | Detection Method |
|----------|--------|-----------------|
| Managed skills (GitHub) | `.skill-lock.json` | GitHub Contents API (git hash compare) |
| Managed skills (ClewHub) | `_meta.json` | ClewHub API (version compare) |
| Bundled skills | `/app/skills/` | Tied to OpenClaw version |
| Workspace skills | `workspace/skills/` | Local git (self-managed) |
| OpenClaw version | npm registry + GitHub | `npm view` / GitHub Releases API |
| npm dependencies | `/app/node_modules/` | `npm outdated` |
| pip packages | system Python | `pip3 list --outdated` |
| CLI tools | PATH | Version commands |

## Workflow

### On-Demand Check

When user asks to check dependencies:

1. Run `scan.py` to refresh the manifest
   - **Validate**: verify `data/manifest.json` was created/updated (non-empty, valid JSON)
2. Run `check.py` to compare against remote sources
   - **Validate**: verify `data/check-results.json` exists and contains results
   - If script exits non-zero (e.g. GitHub API rate limit), report the error and skip remaining steps
3. Run `report.py` to generate the report
   - **Validate**: verify a new `data/reports/YYYY-MM-DD-report.md` was created
4. Send report summary to user (Telegram)
5. If unknown-source skills found, notify Boss

### Scheduled Check (Cron)

Weekly cron entry:

```bash
0 9 * * 1 cd ~/.openclaw/workspace/skills/dependency-tracker && python3 scripts/scan.py && python3 scripts/check.py && python3 scripts/report.py
```

- Only notify if updates are found or errors occur

### Error Handling

- **GitHub API rate limit (403)**: Wait and retry, or report rate limit status and skip GitHub-source checks
- **Network unavailable**: Report connectivity error, skip remote checks, still generate report from cached `check-results.json`
- **Script exits non-zero**: Report the error to user, do not proceed to subsequent scripts

## Data Files

All runtime data lives in `data/` (gitignored from backup):

```
data/
├── manifest.json        # Full dependency inventory
├── check-results.json   # Latest check results (see schema below)
└── reports/
    └── YYYY-MM-DD-report.md  # Generated reports
```

### check-results.json schema

```json
{
  "checked_at": "2026-04-16T09:00:00Z",
  "categories": {
    "managed_skills": [
      { "name": "skill-name", "local_hash": "abc123", "remote_hash": "def456", "has_update": true, "repo_url": "..." }
    ],
    "npm": [
      { "name": "package-name", "current": "1.0.0", "latest": "1.2.0", "has_update": true }
    ]
  }
}
```

## Key Design Decisions

- **No auto-update**: Only detect and report. User decides when to update.
- **GitHub hash comparison**: Uses `git hash-object` locally vs GitHub Contents API SHA — exact match, no false positives.
- **Lock file as source of truth**: `.skill-lock.json` (OpenClaw's managed skill registry) provides repo URLs and install metadata.
- **Changelog extraction**: For GitHub skills with updates, fetches recent commits for context.
- **Unknown source notification**: Skills without traceable source are flagged and reported to Boss.
