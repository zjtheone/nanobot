# Nanobot 配置指南 - 增强功能

## 浏览器控制配置

在 `~/.nanobot/config.json` 中添加浏览器配置：

```json
{
  "agents": {
    "defaults": {
      "browser": {
        "enabled": true,
        "headless": true,
        "sandbox": true,
        "allow_list": ["github.com", "example.com"]
      }
    }
  }
}
```

### 配置选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | boolean | false | 是否启用浏览器工具 |
| `headless` | boolean | true | 无头模式运行 |
| `sandbox` | boolean | true | Chrome 沙箱模式 |
| `allow_list` | string[] | [] | 允许访问的域名白名单 |

### 使用示例

```python
from nanobot.agent.loop import AgentLoop

agent = AgentLoop(
    # ... 其他配置
    browser_enabled=True,
    browser_headless=True,
    browser_sandbox=True,
    browser_allow_list=["github.com", "stackoverflow.com"],
)
```

## 技能系统配置

### 启用技能系统

```json
{
  "skills": {
    "enabled": true,
    "bundled_dir": "/path/to/bundled/skills",
    "workspace_dir": ".nanobot/skills",
    "allow_bundled": true
  }
}
```

### 技能目录结构

```
~/.nanobot/
└── skills/
    ├── bundled/      # 捆绑技能（只读）
    │   ├── github/
    │   │   └── SKILL.md
    │   └── weather/
    │       └── SKILL.md
    ├── workspace/    # 工作区技能
    │   └── custom/
    │       └── SKILL.md
    └── managed/      # 已安装技能
        └── ...
```

### 技能文件格式

```markdown
---
name: skill-name
description: Skill description
emoji: 🔧
os: ["darwin", "linux"]
requires:
  env: ["API_KEY"]
  bins: ["node", "npm"]
---

# Skill Name

## Commands
- `command` - description
```

## 环境变量

### 浏览器相关

```bash
# Chrome 可执行文件路径
export CHROME_EXECUTABLE=/usr/bin/google-chrome

# CDP 端口
export CDP_PORT=9222
```

### 技能相关

```bash
# 捆绑技能目录
export NANOBOT_BUNDLED_SKILLS_DIR=/path/to/skills

# 技能注册表 URL
export NANOHUB_API_URL=https://nanohub.example.com
```

## 完整配置示例

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "browser": {
        "enabled": true,
        "headless": true,
        "sandbox": true,
        "allow_list": ["github.com"]
      }
    }
  },
  "skills": {
    "enabled": true,
    "allow_bundled": true
  },
  "tools": {
    "browser": {
      "enabled": true,
      "headless": true
    }
  }
}
```

## 测试配置

### 测试浏览器

```bash
python -c "
from nanobot.agent.tools.browser.browser_tool import BrowserTool
import asyncio

async def test():
    browser = BrowserTool(headless=True)
    result = await browser.execute(action='navigate', url='https://example.com')
    print(result)
    await browser.execute(action='close')

asyncio.run(test())
"
```

### 测试技能系统

```bash
python -c "
from nanobot.skills.loader import SkillLoader

loader = SkillLoader()
skills = loader.load_all()

for skill in skills:
    print(f'{skill.name}: {skill.metadata.description}')
"
```

## 故障排除

### 浏览器无法启动

1. 检查 Chrome 是否安装：
   ```bash
   which google-chrome
   which chromium
   ```

2. 设置可执行文件路径：
   ```bash
   export CHROME_EXECUTABLE=/path/to/chrome
   ```

3. 禁用沙箱（不推荐）：
   ```json
   {"browser": {"sandbox": false}}
   ```

### 技能无法加载

1. 检查技能目录是否存在
2. 验证 SKILL.md 格式是否正确
3. 检查依赖是否满足：
   ```bash
   python -c "from nanobot.skills.eligibility import evaluate_eligibility; print(evaluate_eligibility(requires_bins=['node']))"
   ```

## 性能优化

### 浏览器优化

- 使用无头模式减少资源占用
- 启用配置文件缓存
- 限制允许访问的域名

### 技能优化

- 只加载需要的技能
- 使用技能白名单
- 定期清理已安装技能
