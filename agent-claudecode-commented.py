"""
nanoAgent ClaudeCode - 高级版 AI Agent 实现（版本 3.0）
======================================================
基于 agent-plus.py 的企业级增强版本，参考 Claude Code 设计理念。

【主要特性】

1. 【扩展工具集】(3个 → 7个专业工具)
   - read:  增强文件读取（支持 offset/limit 分页、行号显示）
   - write: 文件写入
   - edit:  精准文本替换（old_string → new_string）
   - glob:  文件搜索（通配符模式、按修改时间排序）
   - grep:  内容搜索（全文检索）
   - bash:  Shell 命令执行（30秒超时）
   - plan:  内置规划工具（支持执行规划但不允许嵌套规划）

2. 【规则系统】(.agent/rules/*.md)
   - 从指定目录加载 Markdown 规则文件
   - 自动注入到 System Prompt 作为行为准则
   - 支持编码规范、项目约定等

3. 【技能系统】(.agent/skills/*.json)
   - 从指定目录加载 JSON 技能定义
   - 包含名称、描述、模板等元信息
   - 支持预定义任务模板

4. 【MCP协议支持】(.agent/mcp.json)
   - Model Context Protocol 集成
   - 支持从外部 MCP 服务器加载工具
   - 扩展 Agent 功能边界

【核心架构】
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  Rules   │   │  Skills  │   │   MCP    │
    │ (.md)    │   │ (.json)  │   │ (.json)  │
    └────┬─────┘   └────┬─────┘   └────┬─────┘
         │              │              │
         └──────────────┼──────────────┘
                        ↓
               ┌─────────────────┐
               │  System Context │  ← 动态组装
               │  (记忆+规则+技能) │
               └────────┬────────┘
                        ↓
          ┌─────────────────────────────┐
          │      Base Tools (7个)        │
          │ read/write/edit/glob/grep/  │
          │ bash/plan                   │
          └─────────────┬───────────────┘
                        ↓
               ┌─────────────────┐
               │   Plan Mode     │  ← 支持任务规划但不嵌套
               │  (防止无限递归) │
               └────────┬────────┘
                        ↓
                [执行并保存记忆]

【配置常量】
- MEMORY_FILE = "agent_memory.md"
- RULES_DIR = ".agent/rules"
- SKILLS_DIR = ".agent/skills"  
- MCP_CONFIG = ".agent/mcp.json"

【关键函数】
- load_rules():     加载规则文件
- load_skills():    加载技能定义
- load_mcp_tools(): 加载 MCP 工具
- glob():           文件搜索（按时间排序）
- grep():           内容检索
- edit():           精准文本替换
- run_agent_step(): 支持规划模式的核心执行
- run_agent_claudecode(): 主入口

"""

# ===================================================================
# Part 1: 环境配置与依赖导入
# ===================================================================

import os               # 文件系统操作、环境变量
import json             # JSON 数据处理
import subprocess       # Shell 命令执行
import sys              # 命令行参数
import glob as glob_module  # 文件通配符搜索（重命名避免冲突）
from datetime import datetime  # 时间戳
from pathlib import Path  # 面向对象路径操作
from typing import Any  # 类型注解

from openai import OpenAI  # OpenAI API 客户端

# ===================================================================
# Part 2: OpenAI 客户端初始化
# ===================================================================

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)

# ===================================================================
# Part 3: 配置常量
# ===================================================================

MEMORY_FILE = "agent_memory.md"      # 记忆文件路径
RULES_DIR = ".agent/rules"             # 规则文件目录
SKILLS_DIR = ".agent/skills"         # 技能文件目录  
MCP_CONFIG = ".agent/mcp.json"        # MCP 配置文件

# 全局状态变量（用于规划模式）
current_plan = []   # 当前规划步骤列表
plan_mode = False   # 是否处于规划模式（防止嵌套规划）

# ===================================================================
# Part 4: 基础工具定义（7个专业工具）
# ===================================================================

base_tools = [
    # --- 工具 1: read ---
    # 读取文件，支持 offset/limit 分页，显示行号
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read file with line numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},           # 文件路径
                    "offset": {"type": "integer"},        # 起始行号（可选）
                    "limit": {"type": "integer"}          # 读取行数（可选）
                },
                "required": ["path"]
            }
        }
    },
    # --- 工具 2: write ---
    # 写入文件
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write content to file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        }
    },
    # --- 工具 3: edit ---
    # 精准的文本替换，要求 old_string 必须出现且仅出现一次
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Replace string in file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"}
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    # --- 工具 4: glob ---
    # 文件搜索，支持通配符，按修改时间排序
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files by pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"}  # 通配符模式，如 "*.py"
                },
                "required": ["pattern"]
            }
        }
    },
    # --- 工具 5: grep ---
    # 内容搜索，支持递归查找
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search files for pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},  # 搜索模式
                    "path": {"type": "string"}      # 搜索路径（可选）
                },
                "required": ["pattern"]
            }
        }
    },
    # --- 工具 6: bash ---
    # 执行 Shell 命令
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"}
                },
                "required": ["command"]
            }
        }
    },
    # --- 工具 7: plan ---
    # 任务规划工具（特殊：会触发嵌套执行）
    {
        "type": "function",
        "function": {
            "name": "plan",
            "description": "Break down complex task into steps and execute sequentially",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"}
                },
                "required": ["task"]
            }
        }
    }
]

# ===================================================================
# Part 5: 基础工具实现
# ===================================================================

def read(path, offset=None, limit=None):
    """
    读取文件，支持分页和行号显示。
    
    特点:
    - 支持 offset/limit 参数，适合读取大文件的特定部分
    - 自动添加行号，便于定位和编辑
    - 使用 readlines() 保持行尾换行符
    
    参数:
        path: 文件路径
        offset: 起始行号（0-based）
        limit: 读取行数
    
    返回:
        str: 带行号的文件内容，或错误信息
    """
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
        
        # 计算起始和结束行
        start = offset if offset else 0
        end = start + limit if limit else len(lines)
        
        # 添加行号（4位宽度，右对齐）
        numbered = [f"{i+1:4d} {line}" for i, line in enumerate(lines[start:end], start)]
        return ''.join(numbered)
    except Exception as e:
        return f"Error: {str(e)}"


def write(path, content):
    """
    写入内容到文件。
    
    参数:
        path: 目标路径
        content: 写入内容
    
    返回:
        str: 成功确认或错误信息
    """
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error: {str(e)}"


def edit(path, old_string, new_string):
    """
    精准文本替换工具。
    
    关键约束:
    - old_string 必须在文件中**出现且仅出现一次**
    - 这是编辑安全性的关键设计
    
    使用场景:
    - 精准修改代码中的特定片段
    - 避免模糊匹配导致的错误修改
    
    参数:
        path: 文件路径
        old_string: 要替换的原始字符串
        new_string: 新字符串
    
    返回:
        str: 成功确认或错误信息
    """
    try:
        with open(path, 'r') as f:
            content = f.read()
        
        # 安全检查：old_string 必须出现且仅出现一次
        if content.count(old_string) != 1:
            return f"Error: old_string must appear exactly once"
        
        new_content = content.replace(old_string, new_string)
        with open(path, 'w') as f:
            f.write(new_content)
        return f"Successfully edited {path}"
    except Exception as e:
        return f"Error: {str(e)}"


def glob(pattern):
    """
    文件搜索工具，按最后修改时间排序。
    
    特点:
    - 支持通配符模式，如 "*.py", "**/*.json"
    - 递归搜索（recursive=True）
    - 按修改时间倒序排列（最新的在前）
    
    参数:
        pattern: 通配符模式
    
    返回:
        str: 文件路径列表（每行一个），或提示信息
    """
    try:
        files = glob_module.glob(pattern, recursive=True)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return '\n'.join(files) if files else "No files found"
    except Exception as e:
        return f"Error: {str(e)}"


def grep(pattern, path="."):
    """
    内容搜索工具。
    
    特点:
    - 使用系统 grep 命令（递归搜索）
    - 适合在大型代码库中快速定位
    
    参数:
        pattern: 搜索模式
        path: 搜索路径，默认为当前目录
    
    返回:
        str: 匹配结果或提示信息
    """
    try:
        result = subprocess.run(
            f"grep -r '{pattern}' {path}",
            shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout if result.stdout else "No matches found"
    except Exception as e:
        return f"Error: {str(e)}"


def bash(command):
    """
    执行 Shell 命令。
    
    参数:
        command: Shell 命令
    
    返回:
        str: 命令输出（stdout + stderr）或错误信息
    """
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {str(e)}"


def plan(task):
    """
    任务规划工具。
    
    特殊处理:
    - 检查 plan_mode，防止嵌套规划（避免无限递归）
    - 调用 LLM 生成步骤列表
    - 将步骤存入全局 current_plan
    - 在 run_agent_step 中处理嵌套执行
    
    参数:
        task: 要分解的任务
    
    返回:
        str: 规划结果或错误信息
    """
    global current_plan, plan_mode
    
    # 防止嵌套规划
    if plan_mode:
        return "Error: Cannot plan within a plan"
    
    print(f"[Plan] Breaking down: {task}")
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Break task into 3-5 steps. Return JSON with 'steps' array."},
            {"role": "user", "content": task}
        ],
        response_format={"type": "json_object"}
    )
    
    try:
        plan_data = json.loads(response.choices[0].message.content)
        steps = plan_data.get("steps", [task])
        current_plan = steps  # 存储到全局变量
        
        print(f"[Plan] Created {len(steps)} steps")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
        
        return f"Plan created with {len(steps)} steps. Executing now..."
    except:
        return "Error: Failed to create plan"


# ===================================================================
# Part 6: 工具注册表
# ===================================================================

available_functions = {
    "read": read,
    "write": write,
    "edit": edit,
    "glob": glob,
    "grep": grep,
    "bash": bash,
    "plan": plan
}

# ===================================================================
# Part 7: 参数解析（与 agent-plus.py 相同）
# ===================================================================

def parse_tool_arguments(raw_arguments: str) -> dict[str, Any]:
    """
    容错型 JSON 参数解析。
    
    参数:
        raw_arguments: 原始参数字符串
    
    返回:
        dict: 解析后的参数字典
    """
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}


# ===================================================================
# Part 8: 基础功能（记忆系统，与 agent-plus.py 相同）
# ===================================================================

def load_memory():
    """加载记忆文件的最后50行。"""
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE, 'r') as f:
            content = f.read()
        lines = content.split('\n')
        return '\n'.join(lines[-50:]) if len(lines) > 50 else content
    except:
        return ""


def save_memory(task, result):
    """保存任务和结果到记忆文件。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {timestamp}\n**Task:** {task}\n**Result:** {result}\n"
    try:
        with open(MEMORY_FILE, 'a') as f:
            f.write(entry)
    except:
        pass


# ===================================================================
# Part 9: 规则系统（Rules）
# ===================================================================

def load_rules():
    """
    加载规则文件。
    
    从 RULES_DIR 目录加载所有 .md 文件，作为行为规则。
    规则内容会追加到 System Prompt，影响模型行为。
    
    返回:
        str: 所有规则文件内容合并
    """
    rules = []
    if not os.path.exists(RULES_DIR):
        return ""
    
    try:
        for rule_file in Path(RULES_DIR).glob("*.md"):
            with open(rule_file, 'r') as f:
                # 使用文件名作为标题
                rules.append(f"# {rule_file.stem}\n{f.read()}")
        return "\n\n".join(rules) if rules else ""
    except:
        return ""


# ===================================================================
# Part 10: 技能系统（Skills）
# ===================================================================

def load_skills():
    """
    加载技能定义。
    
    从 SKILLS_DIR 目录加载所有 .json 文件。
    技能定义包含名称、描述、模板等。
    
    返回:
        list: 技能定义列表
    """
    skills = []
    if not os.path.exists(SKILLS_DIR):
        return []
    
    try:
        for skill_file in Path(SKILLS_DIR).glob("*.json"):
            with open(skill_file, 'r') as f:
                skills.append(json.load(f))
        return skills
    except:
        return []


# ===================================================================
# Part 11: MCP 工具系统（Model Context Protocol）
# ===================================================================

def load_mcp_tools():
    """
    加载 MCP 工具。
    
    从 MCP_CONFIG 文件加载外部 MCP 服务器定义的工具。
    支持多服务器配置，可禁用特定服务器。
    
    配置格式:
        {
            "mcpServers": {
                "server_name": {
                    "disabled": false,
                    "tools": [{"name": "...", "description": "..."}]
                }
            }
        }
    
    返回:
        list: MCP 工具列表（OpenAI 函数格式）
    """
    if not os.path.exists(MCP_CONFIG):
        return []
    
    try:
        with open(MCP_CONFIG, 'r') as f:
            config = json.load(f)
        
        mcp_tools = []
        for server_name, server_config in config.get("mcpServers", {}).items():
            if server_config.get("disabled", False):
                continue  # 跳过禁用的服务器
            
            for tool in server_config.get("tools", []):
                mcp_tools.append({"type": "function", "function": tool})
        
        return mcp_tools
    except:
        return []


# ===================================================================
# Part 12: 核心执行函数（带规划模式处理）
# ===================================================================

def run_agent_step(messages, tools, max_iterations=5):
    """
    执行 Agent 步骤，支持规划模式。
    
    与 agent-plus.py 的主要区别:
    1. 支持 plan 工具的特殊处理（嵌套执行）
    2. 支持 MCP 工具（通过 all_tools 传入）
    3. 使用 getattr 安全检查避免 AttributeError
    
    plan 工具处理流程:
    - 调用 plan() 生成步骤列表 → 存入 current_plan
    - 递归调用 run_agent_step 执行每个步骤
    - 使用不包含 plan 工具的工具列表（防止嵌套规划）
    - 收集所有步骤结果并返回
    
    参数:
        messages: 对话消息列表
        tools: 可用的工具列表
        max_iterations: 最大迭代次数
    
    返回:
        tuple: (结果, 更新后的消息列表)
    """
    global current_plan, plan_mode
    
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            tools=tools
        )
        message = response.choices[0].message
        messages.append(message)
        
        # 检查是否完成任务
        if not message.tool_calls:
            return message.content, messages
        
        # 处理工具调用
        for tool_call in message.tool_calls:
            # 安全检查：避免 AttributeError
            function_payload = getattr(tool_call, "function", None)
            if function_payload is None:
                continue
            
            function_name = str(getattr(function_payload, "name", ""))
            raw_arguments = str(getattr(function_payload, "arguments", ""))
            function_args = parse_tool_arguments(raw_arguments)
            
            print(f"[Tool] {function_name}({function_args})")
            
            # 获取工具实现
            function_impl = available_functions.get(function_name)
            
            # 处理参数错误
            if "_argument_error" in function_args:
                function_response = f"Error: {function_args['_argument_error']}"
            
            # 特殊处理：plan 工具
            elif function_name == "plan" and function_impl is not None:
                plan_mode = True
                function_response = function_impl(**function_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": function_response
                })
                
                # 执行规划中的步骤
                if current_plan:
                    results = []
                    for i, step in enumerate(current_plan, 1):
                        print(f"\n[Step {i}/{len(current_plan)}] {step}")
                        messages.append({"role": "user", "content": step})
                        
                        # 递归调用，但移除 plan 工具防止嵌套
                        result, messages = run_agent_step(
                            messages,
                            [t for t in tools if t["function"]["name"] != "plan"]
                        )
                        results.append(result)
                        print(f"\n{result}")
                    
                    plan_mode = False
                    current_plan = []
                    return "\n".join(results), messages
            
            # 普通工具执行
            elif function_impl is not None:
                function_response = function_impl(**function_args)
            
            # 未知工具
            else:
                function_response = f"Error: Unknown tool '{function_name}'"
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": function_response
            })
    
    return "Max iterations reached", messages


# ===================================================================
# Part 13: 主入口函数
# ===================================================================

def run_agent_claudecode(task, use_plan=False):
    """
    ClaudeCode 版 Agent 主函数。
    
    执行流程:
    1. 加载记忆/规则/技能/MCP
    2. 动态构建 System Prompt
    3. [可选] 任务规划
    4. 执行步骤
    5. 保存结果
    
    参数:
        task: 用户任务
        use_plan: 是否使用规划模式
    
    返回:
        str: 执行结果
    """
    global plan_mode, current_plan
    
    print("[Init] Loading ClaudeCode features...")
    
    # 加载所有上下文
    memory = load_memory()
    rules = load_rules()
    skills = load_skills()
    mcp_tools = load_mcp_tools()
    
    # 合并工具：基础工具 + MCP 工具
    all_tools = base_tools + mcp_tools
    
    # 构建 System Prompt
    context_parts = ["You are a helpful assistant that can interact with the system. Be concise."]
    
    if rules:
        context_parts.append(f"\n# Rules\n{rules}")
        print(f"[Rules] Loaded {len(rules.split('# '))-1} rule files")
    
    if skills:
        skills_desc = "\n".join([f"- {s['name']}: {s.get('description', '')}" for s in skills])
        context_parts.append(f"\n# Skills\n{skills_desc}")
        print(f"[Skills] Loaded {len(skills)} skills")
    
    if mcp_tools:
        print(f"[MCP] Loaded {len(mcp_tools)} MCP tools")
    
    if memory:
        context_parts.append(f"\n# Previous Context\n{memory}")
    
    messages = [{"role": "system", "content": "\n".join(context_parts)}]
    
    # 任务规划或单科执行
    if use_plan:
        plan_mode = True
        plan(task)
        
        if current_plan:
            results = []
            for i, step in enumerate(current_plan, 1):
                print(f"\n[Step {i}/{len(current_plan)}] {step}")
                messages.append({"role": "user", "content": step})
                
                result, messages = run_agent_step(
                    messages,
                    [t for t in all_tools if t["function"]["name"] != "plan"]
                )
                results.append(result)
                print(f"\n{result}")
            
            plan_mode = False
            current_plan = []
            final_result = "\n".join(results)
        else:
            final_result = "No plan created"
    else:
        messages.append({"role": "user", "content": task})
        final_result, messages = run_agent_step(messages, all_tools)
        print(f"\n{final_result}")
    
    # 保存记忆
    save_memory(task, final_result)
    return final_result


# ===================================================================
# Part 14: 命令行入口
# ===================================================================

if __name__ == "__main__":
    # 检查规划模式
    use_plan = "--plan" in sys.argv
    if use_plan:
        sys.argv.remove("--plan")
    
    # 参数检查
    if len(sys.argv) < 2:
        print("Usage: python agent-claudecode.py [--plan] 'your task'")
        print("  --plan: Enable task planning")
        print("\nFeatures: Memory, Rules, Skills, MCP, Plan tool")
        sys.exit(1)
    
    # 执行任务
    task = " ".join(sys.argv[1:])
    run_agent_claudecode(task, use_plan=use_plan)
