# OpenClaw Skills

一组 [OpenClaw](https://github.com/openclaw/openclaw) Agent 技能（Skills），覆盖搜索、分析、内容提取、备份等场景。

按需安装，各 skill 独立运行，互不依赖（除非特别说明）。

## 技能一览

| Skill | 干什么 | 依赖 |
|-------|--------|------|
| **[search-layer](./search-layer/)** | 多源搜索引擎。Brave + Exa + Tavily 三源并行，意图感知评分，自动去重排序 | `requests` + API Keys |
| **[content-extract](./content-extract/)** | URL → 干净 Markdown。反爬站点（微信、知乎）自动降级到 MinerU | mineru-extract（可选） |
| **[mineru-extract](./mineru-extract/)** | [MinerU](https://mineru.net) API 封装。PDF/Office/HTML → Markdown | `requests` + MinerU Token |
| **[github-explorer](./github-explorer/)** | GitHub 项目深度分析。多源采集 + 结构化研判报告 | search-layer, content-extract |
| **[dependency-tracker](./dependency-tracker/)** | 依赖健康检查。扫描 skills/npm/pip/CLI 版本漂移，生成报告 | `requests` |
| **[gitclaw-backup](./gitclaw-backup/)** | GitHub 备份。将 OpenClaw 工作区同步到 GitHub 仓库 | git |

## 它们之间的关系

```
github-explorer（项目分析）
├── search-layer ──── 三源并行搜索 + 意图评分
├── content-extract ── 智能 URL → Markdown
│   └── mineru-extract ── MinerU API（反爬兜底）
└── OpenClaw 内置 ── web_search, web_fetch, browser

dependency-tracker（依赖检查）── 独立运行
gitclaw-backup（备份）── 独立运行
```

## 安装

### 方式一：让 OpenClaw 帮你装（推荐 🚀）

直接在对话里说：

> 帮我安装这个 skill：https://github.com/blessonism/openclaw-skills

OpenClaw 会自动 clone 并链接所有 skill。

### 方式二：手动安装（全部）

```bash
# 1. Clone
mkdir -p ~/.openclaw/workspace/_repos
git clone https://github.com/blessonism/openclaw-skills.git \
  ~/.openclaw/workspace/_repos/openclaw-skills

# 2. 链接所有 skill
cd ~/.openclaw/workspace/skills
for skill in search-layer content-extract mineru-extract github-explorer dependency-tracker gitclaw-backup; do
  ln -s ~/.openclaw/workspace/_repos/openclaw-skills/$skill $skill
done
```

### 方式三：只装你需要的

```bash
# Clone 一次
mkdir -p ~/.openclaw/workspace/_repos
git clone https://github.com/blessonism/openclaw-skills.git \
  ~/.openclaw/workspace/_repos/openclaw-skills

# 只链接你要的（比如只要搜索相关的）
cd ~/.openclaw/workspace/skills
ln -s ~/.openclaw/workspace/_repos/openclaw-skills/search-layer search-layer
ln -s ~/.openclaw/workspace/_repos/openclaw-skills/content-extract content-extract
```

> 💡 skills 目录因安装方式不同可能不同，常见的是 `~/.openclaw/workspace/skills/` 或 `~/.openclaw/skills/`。

## 配置

### 搜索 API Keys（search-layer 需要）

在 OpenClaw workspace 根目录的 `TOOLS.md` 中添加：

```markdown
### Search
- **Brave**: `your-brave-key`
- **Exa**: `your-exa-key`
- **Tavily**: `your-tavily-key`
```

或设置环境变量：

```bash
export EXA_API_KEY="your-exa-key"        # https://exa.ai
export TAVILY_API_KEY="your-tavily-key"  # https://tavily.com
```

Brave 由 OpenClaw 内置的 `web_search` 使用，在 OpenClaw 配置中设置。

### MinerU Token（可选）

抓取微信/知乎/小红书等反爬站点时需要：

```bash
cp mineru-extract/.env.example mineru-extract/.env
# 编辑 .env，填入 MinerU token（https://mineru.net/apiManage）
```

### Python 依赖

```bash
pip install requests  # 唯一的外部依赖
```

## 各 Skill 详情

每个 skill 目录下都有 `SKILL.md`，包含完整的使用说明和配置指南。点击上方表格中的链接查看。

### search-layer 亮点

- **意图感知**：7 种查询意图（factual / status / comparison / tutorial / exploratory / news / resource），自动调整搜索策略
- **三源并行**：Brave + Exa + Tavily，任一源故障自动降级
- **意图评分**：`score = w_keyword × keyword + w_freshness × freshness + w_authority × authority`
- **域名权威性**：内置四级评分表（60+ 域名）
- **多查询并行**：`--queries "q1" "q2" "q3"` 同时执行
- **完全向后兼容**：不带新参数时行为与 v1 一致

### github-explorer 亮点

- 自动定位 repo，抓 README、Stars、Forks 基础信息
- 翻 Issues 找高质量讨论（按评论数排序，挑 maintainer 参与的）
- 去知乎、微信公众号、V2EX、Twitter 搜社区评价
- 查 arXiv 关联论文、DeepWiki、zread 收录情况
- 找同赛道竞品做横向对比
- 输出结构化研判报告，附主观判断

## 环境要求

- [OpenClaw](https://github.com/openclaw/openclaw)（agent 运行时）
- Python 3.10+
- `requests`（pip install）
- API Keys：按需配置（见上方配置章节）

## 历史仓库

以下仓库的内容已合并到本仓库，不再单独维护：

- [openclaw-search-skills](https://github.com/blessonism/openclaw-search-skills) → search-layer + content-extract + mineru-extract
- [github-explorer-skill](https://github.com/blessonism/github-explorer-skill) → github-explorer

## License

MIT
