
---

# MyCodeAgent 相对 agent-claudecode.py 的全面改进与差异分析

## 一、项目定位差异

| 维度 | agent-claudecode.py | MyCodeAgent |
|------|---------------------|-------------|
| **定位** | 轻量单文件Agent | 完整的多Agent协作框架 |
| **代码规模** | ~280行单文件 | 模块化分层架构，数十个模块 |
| **架构模式** | 函数式简单迭代 | 面向对象 + 事件驱动 + 团队协作 |

---

## 二、核心改进领域

### 1. LLM层抽象 (基础能力)

**agent-claudecode.py:**
```python
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)
```
- 硬编码OpenAI调用
- 单一模型支持

**MyCodeAgent:** [HelloAgentsLLM](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/llm.py#L1-L150)
- **多Provider自动检测**: openai, deepseek, qwen, modelscope, kimi, zhipu, siliconflow, ollama, vllm, local, auto
- **参数优先级机制**: 构造函数参数 > .env > 环境变量
- **流式响应默认支持**
- **重试与退避策略**: `max_retries`, `retry_backoff`
- **超时控制**: `timeout` (默认120s)
- **base_url自动归一化**: 自动处理 `/chat/completions` 后缀

### 2. 工具系统 (Tool System)

#### 2.1 工具基类与响应协议

**agent-claudecode.py:** 无结构化基类
```python
def read(path, offset=None, limit=None):  # 直接返回字符串
    # ...
    return f"Error: {str(e)}"  # 错误处理不统一
```

**MyCodeAgent:** [Tool基类](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/base.py#L1-L150)
- **标准响应协议** (遵循《通用工具响应协议》):
```python
class ToolStatus(str, Enum):
    SUCCESS = "success"    # 完全按预期
    PARTIAL = "partial"    # 有截断/回退
    ERROR = "error"        # 致命错误

class ErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"  # 沙箱越界
    TIMEOUT = "TIMEOUT"
    CONFLICT = "CONFLICT"  # 乐观锁冲突
    # ... 14种标准错误码
```

#### 2.2 工具注册表 (ToolRegistry)

**agent-claudecode.py:** 简单字典
```python
available_functions = {"read": read, "write": write, ...}
```

**MyCodeAgent:** [ToolRegistry](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/registry.py#L1-L150)
- **Circuit Breaker模式**: 工具连续失败3次后自动熔断，5分钟后恢复
- **乐观锁自动注入**: Read元信息缓存 (path_resolved, file_mtime_ms, file_size_bytes)
- **OpenAI格式Schema自动生成**: `_parameters_to_schema()`
- **熔断提示注入**: 临时禁用的工具会在prompt中标注

#### 2.3 Bash工具安全性

**agent-claudecode.py:**
```python
def bash(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr  # 无任何安全限制
```

**MyCodeAgent:** [BashTool](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/builtin/bash.py#L1-L100)
- **交互式命令黑名单**: vim, vi, nano, less, more, top, htop, tmux, screen, ssh...
- **破坏性命令黑名单**: mkfs, fdisk, dd, shutdown, reboot...
- **权限提升命令黑名单**: sudo, su, doas
- **读/搜/列命令重定向**: ls, cat, head, tail, grep, find, rg 应使用相应工具
- **沙箱限制**: 只能在 project_root 内执行
- **超时保护**: 默认120s，最大600s
- **网络控制**: `BASH_ALLOW_NETWORK` 环境变量

### 3. 上下文工程 (Context Engineering)

**agent-claudecode.py:** 无

**MyCodeAgent:** [完整上下文工程体系](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/)

| 组件 | 功能 |
|------|------|
| **[ContextBuilder](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/context_builder.py#L1-L200)** | Message List自然累积模式，L1系统提示/L2 CODE_LAW/L3历史/L4用户输入分层 |
| **[HistoryManager](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/history_manager.py#L1-L150)** | 轮次边界识别、消息压缩、Summary生成 |
| **[ObservationTruncator](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/observation_truncator.py#L1-L100)** | 统一截断策略 (2000行/50KB)，完整输出落盘7天保留 |
| **[SummaryCompressor](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/summary_compressor.py)** | 历史消息摘要压缩 |
| **[TraceLogger](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/trace_logger.py)** | 执行轨迹记录 |
| **[TraceSanitizer](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/trace_sanitizer.py)** | 敏感信息脱敏 |

**压缩触发条件** ([HistoryManager](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/context_engine/history_manager.py#L45)):
```python
#  estimated_total >= 0.8 * context_window 且消息数 >= 3
```

### 4. 多Agent协作 (Agent Teams)

**agent-claudecode.py:** 无

**MyCodeAgent:** [TeamEngine完整实现](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/)

#### 4.1 团队管理架构
| 组件 | 功能 |
|------|------|
| **[TeamManager](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/manager.py#L1-L150)** | 团队创建/删除/生命周期管理 |
| **[TaskBoard](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/task_board.py)** | 任务创建/认领/状态流转 |
| **[TaskBoardStore](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/task_board_store.py)** | 任务持久化存储 |
| **[MessageRouter](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/message_router.py)** | 团队成员间消息路由 |
| **[ApprovalService](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/approval.py)** | 计划审批流程 |

#### 4.2 执行引擎
| 组件 | 功能 |
|------|------|
| **[ExecutionService](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/execution.py)** | LLM并发控制 (Semaphore) |
| **[TurnExecutor](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/turn_executor.py)** | 单轮执行控制 |
| **[WorkerSupervisor](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/supervisor.py)** | Worker生命周期监管 |

#### 4.3 运行时模式
**[TmuxOrchestrator](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/tmux_orchestrator.py):**
- `in-process`: 进程内线程模拟 (开发模式)
- `tmux`: 真实tmux session隔离 (生产模式)

#### 4.4 并发控制
```python
self._llm_semaphore = threading.Semaphore(max(1, max_parallel))  # 默认4
```

### 5. MCP (Model Context Protocol) 支持

**agent-claudecode.py:**
```python
def load_mcp_tools():  # 简单JSON加载
    # ...
    for tool in server_config.get("tools", []):
        mcp_tools.append({"type": "function", "function": tool})
```

**MyCodeAgent:** [完整MCP实现](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/mcp/)
| 组件 | 功能 |
|------|------|
| **[protocol.py](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/mcp/protocol.py)** | MCP协议解析与错误转换 |
| **[adapter.py](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/mcp/adapter.py#L1-L100)** | MCP Tool → 本地Tool适配器 |
| **[loader.py](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/mcp/loader.py)** | MCP Server加载 |
| **[client.py](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/mcp/client.py)** | MCP Client实现 |

**MCP错误处理** (ErrorCode映射):
- `MCP_PARAM_ERROR`: 参数错误
- `MCP_PARSE_ERROR`: 解析错误
- `MCP_EXECUTION_ERROR`: 执行错误
- `MCP_NETWORK_ERROR`: 网络错误
- `MCP_TIMEOUT`: 超时
- `MCP_NOT_FOUND`: 工具不存在

### 6. Skill系统

**agent-claudecode.py:** JSON文件简单加载
```python
for skill_file in Path(SKILLS_DIR).glob("*.json"):
    skills.append(json.load(f))
```

**MyCodeAgent:** [SkillTool](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/builtin/skill.py)
- Skill注册与调用机制
- Prompt模板替换 (`{{available_skills}}`)
- 与ContextBuilder集成

---

## 三、ClaudeCode必要功能对照

以下是实现ClaudeCode相关功能的关键组件对照：

| ClaudeCode功能 | agent-claudecode.py | MyCodeAgent实现 |
|---------------|---------------------|----------------|
| **基础ReAct循环** | ✅ 简单迭代 | ✅ [Agent.run()](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/agent.py#L1-L46) |
| **Memory机制** | ✅ agent_memory.md | ✅ HistoryManager + Summary |
| **Rules加载** | ✅ .agent/rules | ✅ CODE_LAW.md + ContextBuilder |
| **Plan工具** | ✅ plan() | ⚠️ 需通过Task间接实现 |
| **Task子代理** | ❌ 无 | ✅ [TaskTool](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/builtin/task.py) |
| **Skill技能** | ⚠️ 简单加载 | ✅ [SkillTool](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/builtin/skill.py) |
| **MCP工具** | ⚠️ 简单加载 | ✅ [MCPToolAdapter](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/tools/mcp/adapter.py#L1-L100) |
| **多Agent协作** | ❌ 无 | ✅ [TeamManager](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/manager.py#L1-L150) |
| **任务看板** | ❌ 无 | ✅ [TaskBoard](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/task_board.py) |
| **CLI交互** | ❌ 无 | ✅ [CLICommands](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/cli_commands.py) |
| **进度显示** | ❌ 无 | ✅ [ProgressView](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/progress_view.py) |
| **Tmux支持** | ❌ 无 | ✅ [TmuxOrchestrator](file:///d:/A-Usually/1-ALL/Test/MyCodeAgent/core/team_engine/tmux_orchestrator.py) |

---

## 四、架构设计模式对比

### agent-claudecode.py: 线性过程式
```
main → run_agent_claudecode → run_agent_step (循环) → tool_calls → results
```

### MyCodeAgent: 分层事件驱动
```
┌─────────────────────────────────────────────────────────┐
│                    Agent (Abstract)                       │
├─────────────────────────────────────────────────────────┤
│  ContextBuilder.build_messages()                        │
│    ├── L1: System Prompt + Tools                        │
│    ├── L2: CODE_LAW                                      │
│    └── L3: History (HistoryManager)                      │
├─────────────────────────────────────────────────────────┤
│  HelloAgentsLLM (Multi-Provider)                        │
├─────────────────────────────────────────────────────────┤
│  ToolRegistry                                            │
│    ├── Builtin Tools (Bash, Read, Write, Task...)      │
│    ├── MCP Tools (Adapter)                              │
│    └── CircuitBreaker                                   │
├─────────────────────────────────────────────────────────┤
│  TeamEngine (Optional)                                  │
│    ├── TeamManager                                      │
│    ├── TaskBoard                                        │
│    └── WorkerSupervisor                                 │
└─────────────────────────────────────────────────────────┘
```

---

## 五、关键差异总结

| 维度 | agent-claudecode.py | MyCodeAgent |
|------|---------------------|-------------|
| **错误处理** | 字符串拼接 | 标准ErrorCode枚举 |
| **工具协议** | 无 | 通用工具响应协议 |
| **历史管理** | 追加写入 | 轮次感知+压缩+Summary |
| **上下文控制** | 无 | 0.8阈值触发压缩 |
| **工具熔断** | 无 | 3次失败熔断 |
| **多Agent** | 无 | 完整TeamEngine |
| **并发控制** | 无 | Semaphore限制 |
| **持久化** | 仅memory文件 | TeamStore+TaskBoardStore |
| **环境配置** | os.environ直接读 | Pydantic Config + .env |
| **Provider支持** | OpenAI only | 10+ Providers |
| **代码复用** | 复制粘贴 | 模块化继承 |

---

## 六、MyCodeAgent缺失的ClaudeCode功能

基于对比，以下是MyCodeAgent相对ClaudeCode还需要补充的功能：

1. **$code-review skill** - 需要新增专门的代码审查Skill
2. **@文件引用解析** - 系统提示中有提及但实现不完整
3. **Interactive码头 (vim/nano等)** - BashTool主动拒绝
4. **真正的PlanApprovalGate** - 现有ApprovalService是简化版
5. **Claude Code CLI兼容模式** - 无 `--model` `-p` 等CLI参数

---

如需深入了解某个具体模块的实现细节，我可以进一步展开说明。