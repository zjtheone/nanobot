# Nanobot 增强功能 - 浏览器控制与技能系统

本次更新参考 OpenClaw 的先进实现，为 Nanobot 添加了两大核心增强功能：

## 🌐 1. 增强的浏览器控制 (Browser Control)

### 新增文件

1. **`nanobot/agent/tools/browser/cdp.py`** - CDP 核心实现
   - Chrome/Chromium 启动和管理
   - CDP WebSocket 通信
   - 配置文件管理
   - SSRF 防护导航守卫

2. **`nanobot/agent/tools/browser/browser_tool.py`** - 浏览器工具
   - 页面导航
   - 截图功能
   - 内容提取
   - DOM 操作（点击、填充）
   - JavaScript 执行

### 功能特性

#### 1.1 Chrome 启动和管理

```python
from nanobot.agent.tools.browser.cdp import BrowserManager, BrowserConfig

config = BrowserConfig(
    headless=True,
    sandbox=True,
    profile_name="default",
    cdp_port=9222,
)

manager = BrowserManager(config)
browser = await manager.launch()
```

#### 1.2 浏览器工具使用

```python
from nanobot.agent.tools.browser.browser_tool import BrowserTool

browser = BrowserTool(
    headless=True,
    navigation_guard=True,  # 启用 SSRF 防护
    allow_list=["example.com", "github.com"],  # 可选白名单
)

# 导航
await browser.execute(action="navigate", url="https://example.com")

# 截图
screenshot = await browser.execute(action="screenshot", full_page=True)

# 提取内容
content = await browser.execute(action="extract")

# 点击元素
await browser.execute(action="click", selector="button.submit")

# 填充表单
await browser.execute(action="fill", selector="input#email", value="test@example.com")

# 执行 JavaScript
result = await browser.execute(action="evaluate", value="document.title")

# 关闭浏览器
await browser.execute(action="close")
```

#### 1.3 SSRF 防护

```python
from nanobot.agent.tools.browser.cdp import NavigationGuard

guard = NavigationGuard(
    allow_list=["example.com", "*.github.com"]
)

allowed, reason = guard.is_allowed("https://example.com/page")
if allowed:
    print("Safe to navigate")
else:
    print(f"Blocked: {reason}")
```

### 配置

在 `~/.nanobot/config.json` 中添加：

```json
{
  "tools": {
    "browser": {
      "enabled": true,
      "headless": true,
      "sandbox": true,
      "executable": "/usr/bin/google-chrome",
      "profile_name": "default",
      "proxy": null,
      "navigation_guard": true,
      "allow_list": ["example.com"]
    }
  }
}
```

---

## 🎓 2. 技能注册表系统 (NanoHub)

### 设计参考

参考 OpenClaw 的 ClawHub 技能系统，实现：
- 技能发现和搜索
- 技能安装和管理
- 技能前后文解析
- 运行时资格评估
- 依赖检查
- 捆绑技能目录

### 目录结构

```
nanobot/skills/
├── registry/           # 技能注册表
│   ├── __init__.py
│   ├── hub.py         # NanoHub 客户端
│   ├── search.py      # 技能搜索
│   └── install.py     # 技能安装
├── bundled/           # 捆绑技能
│   ├── weather/
│   │   └── SKILL.md
│   ├── github/
│   │   └── SKILL.md
│   └── ...
└── workspace/         # 工作区技能
    └── ...
```

### SKILL.md 格式

```markdown
---
name: skill-name
description: What this skill does
emoji: 🔧
homepage: https://example.com
os: ["darwin", "linux", "win32"]
requires:
  bins: ["node", "npm"]
  env: ["API_KEY"]
install:
  - kind: node
    package: package-name
    module: module-name
---

# Skill Name

## Description
Detailed description of what this skill does.

## Commands
- `command1` - description
- `command2` - description

## Dependencies
Required tools and APIs.

## Usage
How to use this skill.
```

### API 使用

```python
from nanobot.skills.registry import NanoHub

# 创建 NanoHub 客户端
hub = NanoHub(
    api_url="https://nanohub.example.com",
    skills_dir="~/.nanobot/skills",
)

# 搜索技能
results = await hub.search("github", limit=10)
for skill in results:
    print(f"{skill.name}: {skill.description}")

# 获取技能详情
skill = await hub.get_skill("github-skill")
print(skill.metadata)
print(skill.requires)
print(skill.install)

# 安装技能
await hub.install("github-skill")

# 列出已安装技能
installed = await hub.list_installed()
for skill in installed:
    print(f"{skill.name} (version: {skill.version})")

# 卸载技能
await hub.uninstall("github-skill")

# 检查技能资格
eligibility = await hub.check_eligibility("github-skill")
if eligibility.eligible:
    print("Skill can be used")
else:
    print(f"Not eligible: {eligibility.reason}")
```

### 运行时资格评估

```python
from nanobot.skills.eligibility import evaluate_eligibility

eligibility = evaluate_eligibility({
    "os": ["darwin", "linux"],
    "requires": {
        "bins": ["node", "npm"],
        "env": ["API_KEY"],
    },
    "always": False,
})

print(eligibility.eligible)  # True/False
print(eligibility.reason)    # 如果不符，说明原因
```

### 技能加载

```python
from nanobot.skills.loader import SkillLoader

loader = SkillLoader(
    skills_dir="~/.nanobot/skills",
    bundled_dir="nanobot/skills/bundled",
)

# 加载所有可用技能
skills = loader.load_all()

# 加载特定技能
skill = loader.load_skill("github-skill")

# 解析技能前后文
frontmatter = loader.parse_frontmatter(skill.path)
metadata = loader.extract_metadata(frontmatter)
```

---

## 📦 3. 依赖安装

### 浏览器控制依赖

```bash
# 安装 Chrome/Chromium
# macOS
brew install --cask google-chrome

# Linux
sudo apt-get install -y google-chrome-stable

# 或使用 Chromium
sudo apt-get install -y chromium-browser
```

### Python 依赖

```bash
# 在 pyproject.toml 中添加
[project.optional-dependencies]
browser = [
    "playwright>=1.40.0",  # 可选，用于高级浏览器自动化
    "selenium>=4.15.0",    # 可选，用于 Selenium 支持
]

# 安装
pip install nanobot-ai[browser]
```

---

## 🔧 4. 使用方法

### 在 Agent 中使用浏览器工具

```python
from nanobot.agent.loop import AgentLoop

agent = AgentLoop(
    # ... 其他配置
    tools={
        "browser": {
            "enabled": True,
            "headless": True,
        }
    }
)
```

### 在配置中启用

编辑 `~/.nanobot/config.json`:

```json
{
  "tools": {
    "browser": {
      "enabled": true,
      "headless": true,
      "sandbox": true
    },
    "skills": {
      "enabled": true,
      "allowBundled": true,
      "registry": "https://nanohub.example.com"
    }
  }
}
```

---

## 🔒 5. 安全特性

### 浏览器安全

1. **SSRF 防护** - NavigationGuard 阻止访问私有 IP
2. **导航白名单** - 只允许访问指定域名
3. **沙箱模式** - Chrome 以 `--no-sandbox` 运行（可选）
4. **配置文件隔离** - 每个配置文件独立用户数据

### 技能安全

1. **运行时检查** - 验证技能和环境
2. **依赖门控** - 只有满足依赖才能使用
3. **来源验证** - 只加载受信任来源的技能

---

## 📝 6. 示例

### 浏览器自动化示例

```python
import asyncio
from nanobot.agent.tools.browser.browser_tool import BrowserTool

async def main():
    browser = BrowserTool(headless=True)
    
    # 访问 GitHub
    await browser.execute(action="navigate", url="https://github.com")
    
    # 截图
    screenshot = await browser.execute(action="screenshot")
    print(f"Screenshot: {screenshot[:100]}...")
    
    # 提取内容
    content = await browser.execute(action="extract")
    print(f"Content: {content[:500]}...")
    
    # 关闭
    await browser.execute(action="close")

asyncio.run(main())
```

### 技能使用示例

```python
from nanobot.skills.registry import NanoHub

async def setup_skills():
    hub = NanoHub()
    
    # 搜索 GitHub 相关技能
    results = await hub.search("github")
    
    # 安装第一个结果
    if results:
        await hub.install(results[0].name)
    
    # 列出所有已安装技能
    installed = await hub.list_installed()
    for skill in installed:
        print(f"✓ {skill.name}")

asyncio.run(setup_skills())
```

---

## 🎯 7. 与 OpenClaw 对比

| 功能 | OpenClaw | Nanobot (增强后) |
|------|---------|-----------------|
| 浏览器控制 | ✅ Playwright/CDP | ✅ CDP (自研) |
| SSRF 防护 | ✅ Navigation Guard | ✅ NavigationGuard |
| 配置文件管理 | ✅ 装饰和清理 | ✅ 基础实现 |
| 技能系统 | ✅ ClawHub (完整) | ✅ NanoHub (简化) |
| 技能发现 | ✅ 在线注册表 | ⚠️ 本地为主 |
| 截图功能 | ✅ 完整支持 | ✅ 基础支持 |
| DOM 操作 | ✅ 完整支持 | ✅ 基础支持 |

---

## 🚀 8. 下一步改进

1. **浏览器**
   - 添加 Playwright 支持（更高级的自动化）
   - 实现下载管理
   - 添加 Cookie 管理
   - 支持多个浏览器实例

2. **技能系统**
   - 实现 NanoHub 在线注册表
   - 添加技能版本管理
   - 实现技能更新机制
   - 添加技能评分和评论

3. **安全**
   - 增强 SSRF 防护
   - 添加 CSP 策略
   - 实现更细粒度的权限控制

---

## 📚 9. 参考资料

- OpenClaw Browser: `/Users/cengjian/workspace/AI/openclaw/src/browser/`
- OpenClaw Skills: `/Users/cengjian/workspace/AI/openclaw/src/agents/skills/`
- CDP Protocol: https://chromedevtools.github.io/devtools-protocol/

---

## ✨ 10. 贡献

欢迎提交 PR 和 Issue！
