"""CodeAgent - ClaudeCode style Agent implementation

Core Design:
- No abstract base classes, CodeAgent itself is the Agent
- ReAct loop built-in
- Simple dict-based tool management, no ToolRegistry
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

from codeagent.core import Config, get_config, LLMClient, get_client
from codeagent.core.message import Message
from codeagent.tools import (
    BASE_TOOLS,
    AVAILABLE_FUNCTIONS,
    get_function,
    set_plan_function,
    get_all_tool_definitions,
    get_mcp_tools,
)
from codeagent.context import (
    load_memory,
    save_memory,
    load_rules,
    load_skills,
    format_skills_prompt,
    HistoryManager,
    truncate_observation,
)
from codeagent.utils.display import (
    print_info,
    print_success,
    print_error,
    print_tool_call,
    print_step,
    console,
)

logger = logging.getLogger(__name__)


class CodeAgent:
    """
    CodeAgent - ClaudeCode style Agent

    Built-in ReAct loop, simple dict-based tool management
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Optional[Config] = None,
        system_prompt: Optional[str] = None,
    ):
        self.config = config or get_config()
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        self.llm = LLMClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        self.tools = get_all_tool_definitions()
        self.mcp_tools = get_mcp_tools()
        self.all_tools = self.tools + self.mcp_tools

        set_plan_function(self._plan)

        self.history = HistoryManager(
            max_length=self.config.max_history_length,
            context_window=self.config.context_window,
            compression_threshold=self.config.compression_threshold,
        )

        self.messages: List[Dict[str, Any]] = []
        self._initialized = False

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt"""
        return """You are a helpful assistant that can interact with the system. Be concise.

IMPORTANT: Before using tools, think about what you're trying to accomplish.
Use tools only when necessary. Prefer direct answers when possible.

You have access to the following tools:
- Read: Read file with line numbers
- Write: Write content to a file
- Edit: Replace a string in a file (old_string must appear exactly once)
- Glob: Find files by pattern
- Grep: Search files for pattern
- Bash: Run shell commands
- Plan: Break down complex tasks into steps
- TodoWrite: Create and manage todo list

When working on files:
- Use Read first to see the current content
- Use Edit to make targeted changes
- Use Write only when creating new files or full replacements

Be concise and focused. Answer directly without unnecessary preamble."""

    def initialize(self) -> None:
        """Initialize Agent context"""
        if self._initialized:
            return

        print_info("Loading ClaudeCode features...")
        memory = load_memory(self.config.memory_file)
        rules = load_rules(self.config.rules_dir)
        skills = load_skills(self.config.skills_dir)

        context_parts = [self.system_prompt]

        if rules:
            context_parts.append(f"\n# Rules\n{rules}")
            rules_count = rules.count("# ")
            print_success(f"Loaded [yellow]{rules_count}[/yellow] rule files")

        if skills:
            skills_prompt = format_skills_prompt(skills)
            context_parts.append(f"\n# Skills\n{skills_prompt}")
            print_success(f"Loaded [yellow]{len(skills)}[/yellow] skills")

        if self.mcp_tools:
            print_success(f"Loaded [yellow]{len(self.mcp_tools)}[/yellow] MCP tools")

        if memory:
            context_parts.append(f"\n# Previous Context\n{memory}")
            print_success("Loaded previous context")

        self.messages = [{"role": "system", "content": "\n\n".join(context_parts)}]
        self._initialized = True

    def run(self, task: str, use_plan: bool = False, max_iterations: int = 100) -> str:
        """
        Run Agent to execute task

        Original flavor: direct ReAct loop
        """
        self.initialize()
        self.history.clear()

        if use_plan:
            return self._run_with_plan(task, max_iterations)
        return self._run_simple(task, max_iterations)

    def _run_simple(self, task: str, max_iterations: int = 100) -> str:
        """Simple mode execution without planning"""
        self.messages.append({"role": "user", "content": task})

        result, self.messages = self._react_loop(self.messages, max_iterations)

        save_memory(task, str(result)[:500], self.config.memory_file)
        return str(result)

    def _run_with_plan(self, task: str, max_iterations: int = 100) -> str:
        """Plan mode execution"""
        self.messages.append({"role": "user", "content": task})

        plan_result = self._plan(task)
        print_info(plan_result)

        if not hasattr(self, '_current_plan') or not self._current_plan:
            return self._run_simple(task, max_iterations)

        results = []
        for i, step in enumerate(self._current_plan, 1):
            print_step(i, len(self._current_plan), step)
            console.print()
            self.messages.append({"role": "user", "content": step})
            self.history.append_user(step)

            result, self.messages = self._react_loop(
                self.messages,
                max_iterations,
                exclude_tool="Plan"
            )
            results.append(str(result))
            console.print(f"\n{result}")

        final_result = "\n".join(results)
        save_memory(task, final_result[:500], self.config.memory_file)
        return final_result

    def _react_loop(
        self,
        messages: List[Dict[str, Any]],
        max_iterations: int = 100,
        exclude_tool: Optional[str] = None,
    ) -> tuple:
        """
        ReAct loop

        Original flavor: direct iterative tool calling
        """
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            available_tools = [
                t for t in self.all_tools
                if exclude_tool is None or t.get("name") != exclude_tool
            ]

            try:
                response = self.llm.chat(
                    messages,
                    tools=available_tools,
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                return f"Error: {e}", messages

            if not response.choices:
                return "No response from LLM", messages

            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                return message.content or "No content", messages

            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = {}

                if tool_call.function.arguments:
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        function_args = {"raw": tool_call.function.arguments}

                print_tool_call(function_name, function_args)

                if "_argument_error" in function_args:
                    result = function_args.get("_error_message", "Argument error")
                else:
                    func = get_function(function_name)
                    if func:
                        try:
                            result = func(**function_args)
                        except Exception as e:
                            result = f"Error: {e}"
                            logger.exception(f"Tool {function_name} failed")
                    else:
                        result = f"Unknown function: {function_name}"

                truncated = truncate_observation(function_name, str(result))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": truncated,
                })

                self.history.append_tool(tool_call_id=tool_call.id, tool_name=function_name, content=truncated)

            if iteration >= max_iterations:
                return f"Max iterations ({max_iterations}) reached", messages

        return "Max iterations reached", messages

    def _plan(self, task: str) -> str:
        """Plan tool implementation"""
        print_info(f"[bold]Breaking down task:[/bold] {task}")

        plan_messages = [
            {"role": "system", "content": "Break task into 3-5 steps. Return JSON with 'steps' array."},
            {"role": "user", "content": task}
        ]

        try:
            response = self.llm.chat(
                plan_messages,
                model=self.llm.model,
                response_format={"type": "json_object"}
            )
            plan_data = json.loads(response.choices[0].message.content)
            steps = plan_data.get("steps", [task])
            self._current_plan = steps

            print_success(f"[green]Created {len(steps)} steps[/green]")
            for i, step in enumerate(steps, 1):
                console.print(f"  [dim]{i}.[/dim] {step}")

            return f"Plan created with {len(steps)} steps. Executing now..."
        except Exception as e:
            logger.warning(f"Plan generation failed: {e}")
            self._current_plan = [task]
            return f"Plan: {task}"

    def _parse_tool_arguments(self, raw_arguments: str) -> Dict[str, Any]:
        """Parse tool arguments from string"""
        try:
            return json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {"raw": raw_arguments}
