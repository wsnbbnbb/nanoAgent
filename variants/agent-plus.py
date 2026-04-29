# =============================================================================
# Part 1: 环境配置与依赖导入
# =============================================================================

import os               # 环境变量读取、文件路径操作
import json             # JSON 数据解析（工具参数、API 响应）
import subprocess       # 执行 Shell 命令（核心工具实现）
import sys              # 命令行参数处理
from datetime import datetime  # 时间戳生成（记忆记录）
from typing import Any  # 类型注解支持
from openai import OpenAI  # OpenAI API 客户端（支持任何兼容 API）

# =============================================================================
# Part 2: OpenAI 客户端初始化
# =============================================================================
# 创建 OpenAI 客户端实例
# - api_key: 从环境变量读取，支持 OpenAI 或第三方兼容服务
# - base_url: 可选，支持自定义 API 端点（如 OpenRouter、本地代理等）

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)

# =============================================================================
# Part 3: 配置常量
# =============================================================================
# MEMORY_FILE: 记忆文件路径，存储历史任务和结果（Markdown 格式）
# 用于保持上下文连续性，支持Agent"记住"之前的任务
MEMORY_FILE = "agent_memory.md"

tools = [
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

def execute_bash(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {str(e)}"

def read_file(path):
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error: {str(e)}"

def write_file(path, content):
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error: {str(e)}"

available_functions = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file
}
#解析工具调用参数，确保即使输入无效也能返回错误信息而不是崩溃
def parse_tool_arguments(raw_arguments: str) -> dict[str, Any]: 
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}
# 读取记忆文件的最后50行作为上下文，避免过长导致模型输入限制问题，同时保留最近的交互历史
def load_memory():
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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {timestamp}\n**Task:** {task}\n**Result:** {result}\n"
    try:
        with open(MEMORY_FILE, 'a') as f:
            f.write(entry)
    except:
        pass
# 创建计划函数，使用模型将复杂任务分解为简单步骤，返回步骤列表供后续执行
def create_plan(task):
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
        if isinstance(plan_data, dict): 
            #支持两种格式：{"steps": [...]} 或直接是步骤列表 [...]
            steps = plan_data.get("steps", [task])
        elif isinstance(plan_data, list):#如果直接返回列表格式，也能正确解析
            steps = plan_data
        else:
            steps = [task]
        print(f"[Plan] {len(steps)} steps created")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
        return steps
    except:
        return [task]
# 运行代理步骤函数，处理单个任务或步骤的执行逻辑，
# 包括与模型的交互、工具调用和结果处理，支持多轮迭代直到完成或达到最大迭代次数
def run_agent_step(task, messages, max_iterations=5):
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
        if not message.tool_calls:
            return message.content, actions, messages
        #处理工具调用，解析函数名称和参数，执行对应函数并将结果反馈给模型，
        # 支持错误处理以防止崩溃
        for tool_call in message.tool_calls:
            #工具调用可能没有函数信息，添加安全检查避免AttributeError
            function_payload = getattr(tool_call, "function", None)
            
            if function_payload is None:
                continue
            function_name = str(getattr(function_payload, "name", ""))
            raw_arguments = str(getattr(function_payload, "arguments", ""))
            function_args = parse_tool_arguments(raw_arguments)
            print(f"[Tool] {function_name}({function_args})")
            function_impl = available_functions.get(function_name)
            if function_impl is None:
                function_response = f"Error: Unknown tool '{function_name}'"
            elif "_argument_error" in function_args:
                function_response = f"Error: {function_args['_argument_error']}"
            else:
                function_response = function_impl(**function_args)
                actions.append({"tool": function_name, "args": function_args})
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": function_response})
    return "Max iterations reached", actions, messages

def run_agent_plus(task, use_plan=False):
    memory = load_memory()
    system_prompt = "You are a helpful assistant that can interact with the system. Be concise."
    if memory:
        system_prompt += f"\n\nPrevious context:\n{memory}"
    messages = [{"role": "system", "content": system_prompt}]
    if use_plan:
        steps = create_plan(task)
    else:
        steps = [task]
    all_results = []
    for i, step in enumerate(steps, 1):
        if len(steps) > 1:
            print(f"\n[Step {i}/{len(steps)}] {step}")
        result, actions, messages = run_agent_step(step, messages)
        all_results.append(result)
        print(f"\n{result}")
    final_result = "\n".join(all_results)
    save_memory(task, final_result)
    return final_result

if __name__ == "__main__":
    use_plan = "--plan" in sys.argv
    if use_plan:
        sys.argv.remove("--plan")
    if len(sys.argv) < 2:
        print("Usage: python agent-plus.py [--plan] 'your task here'")
        print("  --plan: Enable task planning and decomposition")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    run_agent_plus(task, use_plan=use_plan)
