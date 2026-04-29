"""
Agent 执行器 - 处理单个 Agent 步骤的执行
"""
import json
import os
from typing import Any, Dict, List, Tuple


class ToolArgumentParser:
    """工具参数解析器"""

    @staticmethod
    def parse(raw_arguments: str) -> Dict[str, Any]:
        """
        解析工具参数的 JSON 字符串

        Args:
            raw_arguments: 原始参数字符串

        Returns:
            解析后的参数字典
        """
        if not raw_arguments:
            return {}

        try:
            parsed = json.loads(raw_arguments)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError as error:
            return {"_argument_error": f"Invalid JSON arguments: {error}"}


SYSTEM_PROMPT = """你是一个智能 CLI 助手，帮助用户完成软件开发任务。通过"思考→工具调用→观察→再思考"的迭代循环完成任务。

## 核心能力
- 读写和编辑文件
- 执行 Shell 命令
- 代码搜索和浏览
- 任务规划和拆解

## 工作流程
1. 理解用户任务
2. 使用 TodoWrite 规划任务步骤（如需要）
3. 使用并行工具调用提高效率（如多个独立操作）
4. 根据工具结果调整下一步行动
5. 完成后标记 Todo 为已完成

## 工具调用规则
- 使用 OpenAI function calling 格式调用工具
- 多个独立操作可并行调用
- 相同文件的多个编辑优先用 multi_edit 或 apply_edits
- 参数必须使用工具定义中的参数名

## 输出要求
- 简洁直接，不废话
- 非 trivial 命令执行时简单说明原因
- 回复保持在 4 行以内（不含工具调用）
- 不需要前言或结语，直接回答

## 路径说明
- 所有文件路径相对于当前工作目录
- 工具会自动处理路径解析

## 任务管理
- 复杂任务用 TodoWrite 拆解步骤
- 每个步骤完成后标记完成
- 这样用户能清楚看到进度

## 错误处理
- 工具调用失败看错误信息，调整参数重试
- Windows 上避免使用 Linux 命令（pwd, find, ls 等 Linux 专有命令）
- Windows 上使用 dir, type, copy 等对应命令

## 约束
- 不写恶意代码
- 不泄露密钥或敏感信息
- 不擅自提交代码（除非用户明确要求）"""


class AgentExecutor:
    """Agent 执行器，负责执行单个步骤的工具调用"""

    def __init__(self, available_functions: Dict[str, callable]):
        """
        初始化执行器

        Args:
            available_functions: 可用函数映射表
        """
        self.available_functions = available_functions
        self.parser = ToolArgumentParser()

    def execute_tool(
        self,
        function_name: str,
        raw_arguments: str,
        cwd: str = None
    ) -> Tuple[str, bool]:
        """
        执行单个工具

        Args:
            function_name: 函数名
            raw_arguments: 原始参数
            cwd: 当前工作目录

        Returns:
            (执行结果, 是否为特殊plan工具)
        """
        function_args = self.parser.parse(raw_arguments)

        if "_argument_error" in function_args:
            return function_args["_argument_error"], False

        function_impl = self.available_functions.get(function_name)

        if function_name == "plan" and function_impl:
            return function_impl(**function_args), True

        if function_impl:
            context = {"cwd": cwd} if cwd else {"cwd": os.getcwd()}
            return function_impl(**function_args, context=context), False

        return f"Error: Unknown tool '{function_name}'", False

    def build_context(
        self,
        rules: str = "",
        skills: List[Dict] = None,
        memory: str = "",
        cwd: str = None
    ) -> str:
        """
        构建系统上下文

        Args:
            rules: 规则内容
            skills: 技能列表
            memory: 记忆内容
            cwd: 当前工作目录

        Returns:
            系统提示词
        """
        parts = [SYSTEM_PROMPT]

        if cwd:
            parts.append(f"\n# 当前工作目录\n{cwd}")

        if rules:
            parts.append(f"\n# 规则\n{rules}")

        if skills:
            skill_descriptions = "\n".join([
                f"- {s.get('name', 'unknown')}: {s.get('description', '')}"
                for s in skills
            ])
            parts.append(f"\n# 技能\n{skill_descriptions}")

        if memory:
            parts.append(f"\n# 历史记录\n{memory}")

        return "\n".join(parts)
