"""
nanoAgent Plus - 增强版 AI Agent 实现（版本 2.0）
====================================================
基于 agent.py 的增强版本，新增以下特性：

【改进特性】
1. 任务规划系统 (--plan 参数): LLM 将复杂任务拆分为可执行步骤
2. 记忆系统: 自动保存任务历史到 agent_memory.md, 加载最近50行作为上下文
3. 健壮性增强: 完整的异常处理、30秒命令超时、JSON解析容错

【核心架构】
    任务输入 → [可选: 任务规划] → 依次执行步骤
                              ↓
                    ┌─────────────────┐
                    │  run_agent_step │
                    │  (带记忆上下文)  │
                    └────────┬────────┘
                             ↓
                      ReAct Loop (↻5)
                             ↓
                       保存到记忆

【文件说明】
- create_plan():     任务分解函数
- load_memory():     记忆加载函数（滑窗机制，最近50行）
- save_memory():     记忆保存函数
- parse_tool_arguments(): 容错型参数解析
- run_agent_step():  单步执行函数
- run_agent_plus():  主入口函数

许可证: MIT
"""

# ===================================================================
# Part 1: 环境配置与依赖导入
# ===================================================================

# === 标准库导入 ===
import os               # 环境变量读取、文件路径操作
import json             # JSON 数据解析（工具参数、API 响应）
import subprocess       # 执行 Shell 命令（核心工具实现）
import sys              # 命令行参数处理
from datetime import datetime  # 时间戳生成（记忆记录）
from typing import Any  # 类型注解支持

# === 第三方库 ===
from openai import OpenAI  # OpenAI API 客户端（支持任何兼容 API）

# ===================================================================
# Part 2: OpenAI 客户端初始化
# ===================================================================
# 创建 OpenAI 客户端实例
# - api_key: 从环境变量读取，支持 OpenAI 或第三方兼容服务
# - base_url: 可选，支持自定义 API 端点（如 OpenRouter、本地代理等）
# 若未设置 base_url，默认使用 OpenAI 官方端点
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)

# ===================================================================
# Part 3: 配置常量
# ===================================================================
# MEMORY_FILE: 记忆文件路径，存储历史任务和结果（Markdown 格式）
# 用于保持上下文连续性，支持Agent"记住"之前的任务
MEMORY_FILE = "agent_memory.md"

# ===================================================================
# Part 4: 工具定义（Tools Schema）
# ===================================================================
# OpenAI Function Calling 协议的 JSON Schema 描述
# 与 agent.py 相同的三工具设计，但增加了详细的 description

tools = [
    # --- 工具 1: execute_bash ---
    # 执行 Shell 命令，增加 timeout=30 防止无限挂起
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a bash command on the system",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    # --- 工具 2: read_file ---
    # 读取文件内容
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["path"]
            }
        }
    },
    # --- 工具 3: write_file ---
    # 写入文件内容
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    }
]

# ===================================================================
# Part 5: 工具实现（Tool Implementations）
# ===================================================================
# 工具函数增加了健壮性处理：try-except 包裹 + 30秒超时

def execute_bash(command):
    """
    执行 Shell 命令并返回输出。
    
    改进点: 增加 timeout=30 防止命令无限执行，完整异常捕获。

    参数:
        command: 要执行的 shell 命令字符串
    
    返回:
        str: 命令输出或错误信息
    """
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {str(e)}"


def read_file(path):
    """
    读取指定文件内容。
    
    改进点: 异常处理，文件不存在或读取失败返回错误信息而非崩溃。

    参数:
        path: 文件路径
    
    返回:
        str: 文件内容或错误信息
    """
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error: {str(e)}"


def write_file(path, content):
    """
    写入内容到指定文件。
    
    改进点: 异常处理，返回成功或失败的明确提示。

    参数:
        path: 目标文件路径
        content: 要写入的内容
    
    返回:
        str: 成功确认或错误信息
    """
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error: {str(e)}"


# ===================================================================
# Part 6: 工具注册表
# ===================================================================
# 将工具名称映射到实现函数，供动态分发使用
available_functions = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file
}

# ===================================================================
# Part 7: 参数解析（容错设计）
# ===================================================================
# 解析工具调用参数，确保即使输入无效也能返回错误信息而不是崩溃
# 这是 agent.py 没有的处理，增加了健壮性

def parse_tool_arguments(raw_arguments: str) -> dict[str, Any]:
    """
    容错型 JSON 参数解析。
    
    处理场景:
    1. 空参数 → 返回空字典
    2. 无效 JSON → 返回 {"_argument_error": "错误信息"}
    3. JSON 数组 → 降级为空字典
    4. 有效对象 → 正常返回
    
    返回的错误标记会被后续逻辑检测并返回给模型。

    参数:
        raw_arguments: 原始参数字符串（JSON 格式）
    
    返回:
        dict: 解析后的参数字典，可能包含 _argument_error 错误标记
    """
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}


# ===================================================================
# Part 8: 记忆系统（Memory System）
# ===================================================================
# 实现简单的基于文件的长期记忆，支持上下文连续性

def load_memory():
    """
    加载记忆文件的最后50行作为上下文。
    
    设计原理:
    - 滑窗机制: 只保留最近50行，避免上下文过长导致模型输入限制
    - 容错处理: 文件不存在或读取失败返回空字符串
    - 格式: Markdown，便于人工阅读和调试

    返回:
        str: 最近50行记忆内容，或空字符串
    """
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
    """
    保存任务和结果到记忆文件。
    
    格式:
        ## 2024-01-15 10:30:00
        **Task:** 用户输入的任务
        **Result:** 执行结果
    
    使用追加模式("a")保留历史记录。

    参数:
        task: 原始任务描述
        result: 任务执行结果
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {timestamp}\n**Task:** {task}\n**Result:** {result}\n"
    try:
        with open(MEMORY_FILE, 'a') as f:
            f.write(entry)
    except:
        pass


# ===================================================================
# Part 9: 任务规划系统（Planning）
# ===================================================================
# 使用 LLM 将复杂任务自动分解为可执行的子步骤

def create_plan(task):
    """
    使用模型将复杂任务分解为简单步骤，返回步骤列表供后续执行。
    
    实现逻辑:
    1. 单独调用 LLM（不带工具上下文），聚焦任务分解
    2. 强制 JSON 格式输出（response_format）
    3. 支持两种返回格式: {"steps": [...]} 或直接列表
    4. 降级策略: 解析失败返回原任务作为单一步骤
    
    工作流程:
        用户输入 → LLM分解 → 返回步骤列表 → 逐个执行

    参数:
        task: 用户输入的自然语言任务描述
    
    返回:
        list[str]: 步骤列表
    """
    print("[Planning] Breaking down task...")
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Break down the task into 3-5 simple, actionable steps. Return as JSON array of strings."},
            {"role": "user", "content": f"Task: {task}"}
        ],
        response_format={"type": "json_object"}
    )
    try:
        plan_data = json.loads(response.choices[0].message.content)
        # 支持两种格式: {"steps": [...]} 或返回的直接是列表 [...]
        if isinstance(plan_data, dict):
            steps = plan_data.get("steps", [task])
        elif isinstance(plan_data, list):
            steps = plan_data
        else:
            steps = [task]
        
        print(f"[Plan] {len(steps)} steps created")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
        return steps
    except:
        return [task]


# ===================================================================
# Part 10: 单步执行函数（Agent Step）
# ===================================================================
# 执行单个任务或步骤的核心逻辑，支持带记忆上下文的 ReAct 循环

def run_agent_step(task, messages, max_iterations=5):
    """
    运行代理步骤，处理单个任务或步骤的执行逻辑。
    
    包含：
    1. 与模型的交互（聊天补全）
    2. 工具调用和执行
    3. 结果处理和错误反馈
    4. 多轮迭代直到完成或达到最大次数

    支持错误处理：
    - 未知工具 → 返回错误信息给模型
    - 无效参数 → 返回解析错误
    - 工具执行异常 → 捕获并反馈
    
    参数:
        task: 当前步骤的任务描述
        messages: 当前对话消息列表（会被修改）
        max_iterations: 最大迭代次数，默认5
    
    返回:
        tuple: (结果内容, 动作列表, 更新后的消息列表)
    """
    messages.append({"role": "user", "content": task})
    actions = []
    
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
            return message.content, actions, messages
        
        # 处理工具调用
        for tool_call in message.tool_calls:
            # 安全检查：工具调用可能没有函数信息
            function_payload = getattr(tool_call, "function", None)
            if function_payload is None:
                continue
            
            function_name = str(getattr(function_payload, "name", ""))
            raw_arguments = str(getattr(function_payload, "arguments", ""))
            function_args = parse_tool_arguments(raw_arguments)
            
            print(f"[Tool] {function_name}({function_args})")
            
            # 工具分发
            function_impl = available_functions.get(function_name)
            if function_impl is None:
                function_response = f"Error: Unknown tool '{function_name}'"
            elif "_argument_error" in function_args:
                function_response = f"Error: {function_args['_argument_error']}"
            else:
                function_response = function_impl(**function_args)
            
            actions.append({"tool": function_name, "args": function_args})
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": function_response
            })
    
    return "Max iterations reached", actions, messages


# ===================================================================
# Part 11: 主入口函数（Agent Plus）
# ===================================================================
# 协调任务规划、记忆加载、步骤执行和结果保存

def run_agent_plus(task, use_plan=False):
    """
    Agent Plus 主函数，整合记忆、规划和执行功能。
    
    执行流程:
    1. 加载记忆 → 注入到 System Prompt
    2. [可选] 任务规划 → 分解成步骤
    3. 执行步骤 → 逐个调用 run_agent_step
    4. 保存结果 → 追加到记忆文件
    
    参数:
        task: 用户输入的任务描述
        use_plan: 是否启用任务规划，默认 False
    
    返回:
        str: 所有步骤的执行结果合并
    """
    # 加载记忆并构建系统提示
    memory = load_memory()
    system_prompt = "You are a helpful assistant that can interact with the system. Be concise."
    if memory:
        system_prompt += f"\n\nPrevious context:\n{memory}"
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # 任务规划
    if use_plan:
        steps = create_plan(task)
    else:
        steps = [task]
    
    # 逐个执行步骤
    all_results = []
    for i, step in enumerate(steps, 1):
        if len(steps) > 1:
            print(f"\n[Step {i}/{len(steps)}] {step}")
        result, actions, messages = run_agent_step(step, messages)
        all_results.append(result)
        print(f"\n{result}")
    
    # 保存结果到记忆
    final_result = "\n".join(all_results)
    save_memory(task, final_result)
    return final_result


# ===================================================================
# Part 12: 命令行入口
# ===================================================================

if __name__ == "__main__":
    # 检查是否启用规划模式
    use_plan = "--plan" in sys.argv
    if use_plan:
        sys.argv.remove("--plan")
    
    # 参数检查
    if len(sys.argv) < 2:
        print("Usage: python agent-plus.py [--plan] 'your task here'")
        print("  --plan: Enable task planning and decomposition")
        sys.exit(1)
    
    # 合并命令行参数作为任务
    task = " ".join(sys.argv[1:])
    run_agent_plus(task, use_plan=use_plan)
