# CodeAgent

A ClaudeCode-style agent framework that maintains the original flavor while incorporating best practices from modern agent frameworks.

## 核心设计原则

1. **保持原始风味**: 不使用复杂的抽象基类，CodeAgent本身就是Agent
2. **简单工具管理**: 使用字典管理工具，而非ToolRegistry
3. **ReAct循环内置**: 直接在Agent中实现，而非通过继承

## 项目结构

```
codeagent/
├── agent/             # Agent实现
│   └── code_agent.py # CodeAgent (保持原始风味)
├── core/              # 核心模块
│   ├── config.py      # 配置管理
│   ├── llm.py         # LLM客户端
│   └── message.py     # 消息类
├── tools/             # 工具模块
│   ├── definitions.py # 工具定义
│   ├── functions.py   # 工具函数
│   └── mcp_loader.py  # MCP加载器
├── context/           # 上下文管理
│   ├── memory.py      # 记忆
│   ├── rules.py       # 规则加载
│   ├── skills.py      # 技能加载
│   ├── history.py     # 历史管理
│   └── truncation.py  # 输出截断
├── utils/             # 工具类
│   ├── display.py     # Rich TUI显示
│   └── cli.py         # 交互式CLI
└── main.py            # 入口点
```

## 运行

```bash
cd codeagent
python main.py "Hello, what is 2+2?"

# 计划模式（分解任务）
python main.py --plan "Build a web server"

# 交互式CLI模式
python main.py --interactive
python main.py --chat
```

## 环境变量

```bash
# LLM配置
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Agent配置
MEMORY_FILE=agent_memory.md
RULES_DIR=.agent/rules
SKILLS_DIR=.agent/skills
MCP_CONFIG=.agent/mcp.json

# TUI配置
NO_COLOR=1  # 禁用彩色输出
```

## 功能特性

### 核心功能
- **Memory**: 自动加载和保存对话记忆
- **Rules**: 从`.agent/rules/`目录加载规则文件
- **Skills**: 从`.agent/skills/`目录加载技能配置
- **MCP**: 支持Model Context Protocol外部工具
- **Plan**: 将复杂任务分解为步骤执行

### 上下文管理
- **HistoryManager**: 智能历史记录管理和压缩
- **ObservationTruncator**: 工具输出统一截断 + 落盘

### TUI显示 (Rich)
- 彩色输出 (Info, Success, Warning, Error)
- 工具调用显示
- 步骤进度显示
- Markdown渲染
- 语法高亮
- 交互式CLI模式

## 工具列表

| 工具 | 描述 |
|------|------|
| Read | 读取文件（带行号） |
| Write | 写入文件 |
| Edit | 编辑文件（精确替换） |
| Glob | 查找文件 |
| Grep | 搜索内容 |
| Bash | 执行Shell命令 |
| Plan | 任务规划 |
| TodoWrite | 任务列表管理 |

## 设计对比

| 原始风味 | CodeAgent实现 |
|---------|----------------|
| 简单字典管理 | ✅ BASE_TOOLS字典列表 |
| 函数直接调用 | ✅ AVAILABLE_FUNCTIONS |
| 无抽象基类 | ✅ CodeAgent就是Agent |
| 简单MCP加载 | ✅ JSON直接加载 |
| 无TUI | ✅ Rich TUI支持 |

## 许可证

MIT
