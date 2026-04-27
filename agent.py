
# === 标准库导入 ===
import os        # 环境变量读取、文件操作辅助
import json      # 解析模型返回的 JSON 格式工具参数
import subprocess # 执行系统 Shell 命令（核心工具之一）

# === 第三方库 ===
from openai import OpenAI          # OpenAI API 客户端（兼容任何 OpenAI 格式 API）
from dotenv import load_dotenv    # 从 .env 文件自动加载环境变量

# === 初始化环境与客户端 ===
# 加载 .env 文件中的环境变量（如 OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL）
load_dotenv()

# 创建 OpenAI 客户端实例
# - api_key: 从环境变量读取 API 密钥
# - base_url: 可选的基础 URL，支持自定义 API 端点（如 OpenRouter、本地代理等）
#   若未设置 base_url，默认使用 OpenAI 官方端点
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)

# ===================================================================
# 工具定义（Tools Schema）
# ===================================================================
# 这是 OpenAI Function Calling 协议的核心——用 JSON Schema 向模型描述可用工具。
# 模型会根据这些描述自主决定：何时调用工具、调用哪个工具、传入什么参数。
#
# 三个工具的精心选择体现了"最小完备性"原则：
#   execute_bash → 执行任意系统命令（读/写/计算/网络 等一切操作的入口）
#   read_file    → 读取文件内容（获取信息的精确方式）
#   write_file   → 写入文件（产生持久化输出）
# 这三个工具的组合形成了 图灵完备 的操作能力。
# ===================================================================
tools = [
    # 工具 1: execute_bash —— 执行 Shell 命令
    # 这是能力最强大的工具，可以运行任意系统命令
    # 通过 shell=True 使得管道、重定向等复杂 shell 语法都能正常工作
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a bash command",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    # 工具 2: read_file —— 读取文件
    # 提供精确的文件读取能力，与 bash 的 cat 不同：
    # read_file 在 Python 层面处理，避免 shell 注入和转义问题
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    # 工具 3: write_file —— 写入文件
    # 将内容写入指定文件，是 Agent 产生持久化输出的主要方式
    # 注意：content 参数允许模型写入任意文本（代码、配置、报告等）
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
]


# ===================================================================
# 工具实现（Tool Implementations）
# ===================================================================
# 这些是工具定义对应的实际 Python 函数。
# 它们接收模型生成的参数，执行实际操作，并将结果以字符串形式返回给模型。
# 返回值的格式很重要：模型需要从文本中理解执行结果。
# ===================================================================

def execute_bash(command):
    """
    执行 Shell 命令并返回 stdout + stderr 的组合输出。
    
    关键设计决策：
    - shell=True: 允许管道 `|`、重定向 `>`、变量展开等 Shell 特性
    - capture_output=True: 捕获所有输出而非打印到终端
    - text=True: 返回字符串而非字节流，便于模型理解
    - 返回值合并 stdout 和 stderr: 确保错误信息也不会丢失
    
    安全注意：生产环境中应添加命令白名单或沙箱机制。
    """
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def read_file(path):
    """
    读取指定文件的全部内容并返回。
    
    使用 Python 原生文件操作而非 bash cat 命令：
    优势：避免 shell 注入、路径转义问题，编码处理更可靠。
    注意：对大文件没有分页机制，读取超大文件可能导致上下文溢出。
    """
    with open(path, "r") as f:
        return f.read()


def write_file(path, content):
    """
    将内容写入指定文件，覆盖已有内容。
    
    返回确认消息告知模型写入成功。
    content 参数由模型生成，可包含代码、文本、JSON、CSV 等任意格式。
    
    注意：使用 "w" 模式会覆盖已有文件，模型可通过 read_file 先读后写来避免误覆盖。
    """
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote to {path}"


# === 工具注册表 ===
# 将工具名称映射到实际函数，实现名字→执行的分发机制。
# 这是简单但有效的"服务定位"模式——通过字符串名称查找并调用对应函数。
functions = {"execute_bash": execute_bash, "read_file": read_file, "write_file": write_file}


# ===================================================================
# Agent 核心循环（Agent Loop）
# ===================================================================
# 这是整个 nanoAgent 的心脏——ReAct（Reasoning + Acting）模式的极简实现。
#
# 算法流程（ReAct Loop）：
#   1. 将用户任务 + 系统提示构建为初始消息列表
#   2. 发送消息给 LLM，让模型决策：是直接回复还是调用工具？
#   3. 如果模型直接回复 → 返回结果，循环结束
#   4. 如果模型调用工具 → 执行工具 → 将结果追加到消息列表 → 回到步骤 2
#   5. 达到最大迭代次数 → 安全退出，防止无限循环
#
# 这种"思考-行动-观察-思考"的循环是当前所有 Agent 框架的共同基础。
# ===================================================================

def run_agent(user_message, max_iterations=5):
    """
    Agent 主函数，执行 ReAct 循环直到任务完成或达到迭代上限。
    
    参数:
        user_message: 用户输入的自然语言任务描述
        max_iterations: 最大工具调用轮数，默认 5，防止无限循环或超长执行
    
    返回:
        str: 模型的最终回复内容
    
    迭代过程说明:
        每次迭代中，模型可能调用 0 个或多个工具。
        所有工具调用结果都会追加到 messages 中，模型据此调整下一步行为。
    """
    # --- 构建初始对话上下文 ---
    # system 消息定义 Agent 的角色和行为约束
    # user 消息包含具体的任务
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Be concise."},
        {"role": "user", "content": user_message},
    ]
    
    # --- ReAct 主循环 ---
    # 每次循环代表一次"思考→行动→观察"的完整周期
    for _ in range(max_iterations):
        # ===== 步骤 1: 调用 LLM 获取决策 =====
        # 将当前完整对话历史 + 可用工具列表发送给模型
        # 模型返回: (1) 纯文本回复 或 (2) 一个或多个 tool_calls
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "minimax/minimax-m2.5:free"),
            messages=messages,
            tools=tools,
        )
        message = response.choices[0].message
        
        # 将模型的回复加入对话历史（保持上下文完整性）
        messages.append(message)
        
        # ===== 步骤 2: 判断是否完成任务 =====
        # 如果模型没有请求工具调用（tool_calls 为 None 或空），
        # 说明模型认为任务已完成，直接返回文本回复
        if not message.tool_calls:
            return message.content
        
        # ===== 步骤 3: 执行工具调用（Acting） =====
        # 模型可能同时请求多个工具调用，逐个处理
        for tool_call in message.tool_calls:
            # 解析工具名称和参数
            name = tool_call.function.name       # 模型选择调用的工具名
            args = json.loads(tool_call.function.arguments)  # 模型生成的 JSON 参数
            
            # 打印执行日志，方便调试和观察 Agent 行为
            print(f"[Tool] {name}({args})")
            
            # --- 工具分发与执行 ---
            # 安全检查：如果模型请求了不存在的工具（可能是幻觉），返回错误而非崩溃
            if name not in functions:
                result = f"Error: Unknown tool '{name}'"
            else:
                # 通过 **args 解包参数字典，调用对应工具函数
                result = functions[name](**args)
            
            # ===== 步骤 4: 将工具结果反馈给模型（Observation） =====
            # 这是 ReAct 循环中关键的"观察"环节
            # tool_call_id 用于关联请求和响应，确保模型知道这条结果是哪个调用的返回值
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
    
    # --- 安全阀：达到最大迭代次数 ---
    # 如果循环耗尽 max_iterations 仍未完成，返回提示信息
    # 这种情况通常意味着：任务太复杂、模型陷入循环、或需要外部干预
    return "Max iterations reached"


# ===================================================================
# 命令行入口
# ===================================================================
# 允许从终端直接运行: python agent.py "列出所有 Python 文件"
# sys.argv[0] 是脚本名，sys.argv[1:] 是用户输入的任务（以空格连接）
# 若无参数则发送默认的 "Hello" 作为演示
# ===================================================================
if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello"
    print(run_agent(task))
