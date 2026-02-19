# Domain whitelist → force MinerU

When `source_url` matches any domain in this list (exact host match or subdomain), **skip probe** and go directly to **MinerU-HTML**.

Rationale: these sites frequently block automated fetches, render dynamically, or return interstitial/captcha pages.

## Default whitelist

### 反爬/动态渲染 → MinerU-HTML
- mp.weixin.qq.com
- mmbiz.qpic.cn (WeChat images; usually appears as assets)
- zhuanlan.zhihu.com
- www.zhihu.com
- zhihu.com
- xhslink.com
- xiaohongshu.com

### SPA/客户端渲染 → 专用 API 快速路径（不走 MinerU）
- github.com → GitHub API（README 等内容由客户端渲染，web_fetch 只能拿到导航栏壳子）

## Notes

- Matching rule: `host == domain` OR `host.endsWith('.' + domain)`
- GitHub 域名不走 MinerU，走 GitHub API 快速路径（见 SKILL.md Phase 0.5）
- You can add/remove domains here based on real failures.
