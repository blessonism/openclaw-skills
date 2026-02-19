# Extraction heuristics (probe → fallback)

This file defines **when to accept web_fetch output** vs **when to fallback to MinerU** vs **when to use a specialized API**.

## Accept web_fetch when

- HTTP status is 200 and extracted markdown has meaningful body content.
- Content length is not trivially small (rule of thumb: > 2k chars for articles; adjust by site).
- Does NOT look like a captcha/interstitial page.

## GitHub fast path (skip probe AND MinerU)

If URL matches `github.com/{owner}/{repo}` pattern, **do NOT use web_fetch or MinerU**. GitHub repo pages are SPA (client-side rendered); web_fetch only gets the nav shell.

Instead, use GitHub API directly:

| Content | API Endpoint | Notes |
|---------|-------------|-------|
| README | `GET /repos/{owner}/{repo}/readme` with `Accept: application/vnd.github.v3.raw` | Returns raw markdown |
| Repo metadata | `GET /repos/{owner}/{repo}` | Stars, forks, license, description, etc. |
| File tree | `GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1` | Full file listing |
| File content | `GET /repos/{owner}/{repo}/contents/{path}` with `Accept: application/vnd.github.v3.raw` | Any specific file |
| Issues | `GET /repos/{owner}/{repo}/issues?state=all&sort=comments&per_page=10` | Top issues by engagement |
| Commits | `GET /repos/{owner}/{repo}/commits?per_page=10` | Recent activity |

Auth header: `Authorization: token {GITHUB_PAT}` (see TOOLS.md)

Detection regex: `^https?://github\.com/([^/]+)/([^/]+)(/.*)?$`

This also applies to subpages like `github.com/{owner}/{repo}/issues`, `github.com/{owner}/{repo}/blob/...`, etc. — always prefer API over web_fetch for github.com.

## Force fallback to MinerU (MinerU-HTML) when

### Domain whitelist (skip probe)

If URL host matches the whitelist in `domain-whitelist.md` (excluding GitHub, which has its own fast path), **skip probe** and go straight to MinerU.

See: `references/domain-whitelist.md`

### Obvious interstitial / anti-bot patterns

If web_fetch markdown contains any of:
- "环境异常"
- "完成验证"
- "拖动下方滑块"
- "验证码"
- "请在微信客户端打开"
- "访问过于频繁"

### Content too thin / nav-only

- Content length < 800 chars and URL is expected to be an article.
- Extracted text is mostly navigation items / footer.

### fetch failure

- web_fetch returns 401/403/429/5xx.
- web_fetch times out repeatedly.

## MinerU failure fallback (future)

If MinerU fails to fetch protected pages:
- Ask for a mirror URL, OR
- Use browser relay to export HTML, then add "upload HTML then parse" flow.

(Upload flow is not implemented yet in OpenClaw A-route.)
