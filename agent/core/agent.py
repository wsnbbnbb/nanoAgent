"""
Agent 主逻辑 - 包含同步和流式执行接口
"""
import json
import os
from typing import List, Dict, Any, Iterator
from openai import OpenAI

from .config import Config, AgentState
from ..tools.definitions import BASE_TOOLS
from ..tools.filesystem import read_file, write_file, edit_file, glob_files
from ..tools.search import grep_search
from ..tools.command import run_bash
from ..tools.planning import create_plan
from ..tools.todo import todo_create, todo_update, todo_list, todo_delete, todo_stats
from ..tools.multi_edit import multi_edit, apply_edits
from ..tools.interaction import ask_user, confirm
from ..memory.manager import MemoryManager
from ..loaders.rules import RuleLoader
from ..loaders.skills_loader import SkillLoader
from ..loaders.mcp import McpLoader
from .executor import AgentExecutor
from .llm import AgentsLLM  

class AgentRunner:
    """Agent 运行器，执行完整的任务流程"""

    def __init__(self):
        """初始化 Agent"""
        self.client = AgentsLLM()

        self.memory_manager = MemoryManager()
        self.rule_loader = RuleLoader()
        self.skill_loader = SkillLoader()
        self.mcp_loader = McpLoader()

        self.available_functions = {
            "read": read_file,
            "write": write_file,
            "edit": edit_file,
            "glob": glob_files,
            "grep": grep_search,
            "bash": run_bash,
            "plan": lambda task: self._execute_plan(task),
            "todo_create": todo_create,
            "todo_update": todo_update,
            "todo_list": todo_list,
            "todo_delete": todo_delete,
            "todo_stats": todo_stats,
            "multi_edit": multi_edit,
            "apply_edits": apply_edits,
            "ask_user": ask_user,
            "confirm": confirm,
        }

        self.executor = AgentExecutor(self.available_functions)
        self.all_tools = BASE_TOOLS.copy()

    def _execute_plan(self, task: str) -> str:
        """内部 plan 执行器，用于延迟执行"""
        return create_plan(task, self.client)

    def _load_context(self) -> tuple:
        """
        加载所有上下文数据

        Returns:
            (规则内容, 技能列表, 记忆内容)
        """
        memory = self.memory_manager.load()
        rules = self.rule_loader.load()
        skills = self.skill_loader.load()
        mcp_tools = self.mcp_loader.load()

        # 扩展工具列表
        if mcp_tools:
            self.all_tools = BASE_TOOLS.copy() + mcp_tools
            print(f"[MCP] 已加载 {len(mcp_tools)} 个 MCP 工具")

        # 打印加载信息
        if rules:
            rule_files = self.rule_loader.list_rules()
            print(f"[规则] 已加载 {len(rule_files)} 个规则文件")

        if skills:
            print(f"[技能] 已加载 {len(skills)} 个技能")

        if memory:
            print(f"[记忆] 已加载历史记录")

        return rules, skills, memory

    def _build_system_prompt(self, rules: str, skills: List[Dict], memory: str) -> str:
        """构建系统提示词"""
        return self.executor.build_context(rules, skills, memory, cwd=os.getcwd())

    def run_step(self, messages: List[Dict], tools: List[Dict], max_iterations: int = None) -> tuple:
        """
        执行单步对话（可能包含多个工具调用）

        Args:
            messages: 消息历史
            tools: 可用工具列表
            max_iterations: 最大迭代次数

        Returns:
            (最终结果, 更新后的消息历史)
        """
        max_iterations = max_iterations or Config.MAX_ITERATIONS
        for iteration in range(max_iterations):
            # 调用模型 - 使用 generate_raw 获取原始响应对象
            response = self.client.generate_raw(
                messages=messages,
                tools=tools
            )
            message = response.choices[0].message
            messages.append(message)
            # 如果没有工具调用，直接返回结果
            if not message.tool_calls:
                return message.content, messages
            # 处理工具调用
            for tool_call in message.tool_calls:
                func_data = getattr(tool_call, "function", None)
                if not func_data:
                    continue
                func_name = str(getattr(func_data, "name", ""))
                raw_args = str(getattr(func_data, "arguments", ""))
                print(f"[调用] {func_name}({raw_args})")
                # 执行工具
                result, is_plan = self.executor.execute_tool(func_name, raw_args)
                # 如果是 plan 工具，处理返回的计划
                if is_plan and AgentState.current_plan:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
                    # 依次执行计划中的步骤
                    step_results = []
                    for step in AgentState.current_plan:
                        messages.append({"role": "user", "content": step})
                        step_result, messages = self.run_step(messages, [t for t in tools if t["function"]["name"] != "plan"])
                        step_results.append(step_result)
                    AgentState.plan_mode = False
                    AgentState.current_plan = []
                    return "\n".join(step_results), messages
                # 添加工具响应
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        return "达到最大迭代次数", messages

    def run(
        self,
        task: str,
        use_plan: bool = False
    ) -> str:
        """
        运行 Agent（同步模式）

        Args:
            task: 任务描述
            use_plan: 是否使用计划模式

        Returns:
            执行结果
        """
        print("[初始化] 加载配置和资源...")
        rules, skills, memory = self._load_context()

        # 构建系统提示
        system_prompt = self._build_system_prompt(rules, skills, memory)
        messages = [{"role": "system", "content": system_prompt}]

        # 计划模式
        if use_plan:
            print(f"\n[计划模式] 任务: {task}")
            AgentState.plan_mode = True

            # 生成计划
            plan_result = create_plan(task, self.client)

            if "Error" in plan_result:
                print(f"[警告] 计划生成失败: {plan_result}")
                AgentState.plan_mode = False
            else:
                try:
                    plan_data = json.loads(plan_result)
                    steps = plan_data.get("steps", [task])
                    AgentState.current_plan = steps

                    print(f"[计划] 已拆解为 {len(steps)} 个步骤")
                    for i, step in enumerate(steps, 1):
                        print(f"  {i}. {step}")

                    # 依次执行步骤
                    results = []
                    for i, step in enumerate(steps):
                        print(f"\n[步骤 {i+1}/{len(steps)}] {step}")
                        messages.append({"role": "user", "content": step})
                        result, messages = self.run_step(messages, [t for t in self.all_tools if t["function"]["name"] != "plan"])
                        results.append(result)
                        print(f"结果:\n{result}")

                    final_result = "\n".join(results)
                    AgentState.plan_mode = False
                    AgentState.current_plan = []

                    # 保存记忆
                    self.memory_manager.save(task, final_result)
                    return final_result

                except Exception as e:
                    print(f"[警告] 计划执行失败: {e}")
                    AgentState.plan_mode = False
                    AgentState.current_plan = []

        # 标准模式
        messages.append({"role": "user", "content": task})
        final_result, _ = self.run_step(messages, self.all_tools)

        print(f"\n{final_result}")

        # 保存记忆
        self.memory_manager.save(task, final_result)
        return final_result

    def run_stream(
        self,
        task: str,
        use_plan: bool = False
    ) -> Iterator[Dict[str, Any]]:
        """
        运行 Agent（流式模式，用于 UI）

        Args:
            task: 任务描述
            use_plan: 是否使用计划模式

        Yields:
            状态事件字典 {type, ...}
        """
        rules, skills, memory = self._load_context()

        system_prompt = self._build_system_prompt(rules, skills, memory)
        messages = [{"role": "system", "content": system_prompt}]

        # 计划模式
        if use_plan:
            # 生成计划
            try:
                response = self.client.chat.completions.create(
                    model=Config.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "将任务拆解为3-5个可执行的步骤。返回严格的JSON格式：{'steps': ['步骤1', '步骤2']}"
                        },
                        {"role": "user", "content": task}
                    ],
                    response_format={"type": "json_object"}
                )

                plan_data = json.loads(response.choices[0].message.content)
                steps = plan_data.get("steps", [task])
            except:
                steps = [task]

            yield {"type": "plan", "steps": steps}
            AgentState.current_plan = steps
            AgentState.plan_mode = True

            # 执行步骤
            for i, step in enumerate(steps):
                yield {"type": "step_start", "step": step, "index": i}

                messages.append({"role": "user", "content": step})
                result, messages = self._run_step_stream(messages)

                yield {"type": "step_done", "step": step, "index": i}
                yield {"type": "step_result", "content": result}

            AgentState.plan_mode = False
            AgentState.current_plan = []

            final = "计划执行完成"
            yield {"type": "final", "content": final}

            self.memory_manager.save(task, final)

        else:
            # 标准模式
            messages.append({"role": "user", "content": task})
            result, _ = self._run_step_stream(messages)

            yield {"type": "final", "content": result}
            self.memory_manager.save(task, result)

    def _run_step_stream(self, messages: List[Dict], max_iterations: int = None) -> tuple:
        """流式单步执行"""
        max_iterations = max_iterations or Config.MAX_ITERATIONS

        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=messages,
                tools=self.all_tools
            )

            message = response.choices[0].message
            messages.append(message)

            if not message.tool_calls:
                return message.content, messages

            for tool_call in message.tool_calls:
                func_data = getattr(tool_call, "function", None)
                if not func_data:
                    continue

                func_name = str(getattr(func_data, "name", ""))
                raw_args = str(getattr(func_data, "arguments", ""))

                # 发送工具调用事件
                parsed_args = json.loads(raw_args) if raw_args else {}
                yield {"type": "tool_call", "name": func_name, "args": parsed_args}

                # 执行工具
                result, _ = self.executor.execute_tool(func_name, raw_args)

                yield {"type": "tool_result", "content": result}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

        return "达到最大迭代次数", messages


# 便捷函数

def run_agent_claudecode(task: str, use_plan: bool = False) -> str:
    """
    便捷函数：运行 Agent（同步模式）

    Args:
        task: 任务描述
        use_plan: 是否使用计划模式

    Returns:
        执行结果
    """
    agent = AgentRunner()
    return agent.run(task, use_plan=use_plan)


def run_agent_stream(task: str, use_plan: bool = False) -> Iterator[Dict[str, Any]]:
    """
    便捷函数：运行 Agent（流式模式）

    Args:
        task: 任务描述
        use_plan: 是否使用计划模式

    Yields:
        状态事件字典
    """
    agent = AgentRunner()
    yield from agent.run_stream(task, use_plan=use_plan)
