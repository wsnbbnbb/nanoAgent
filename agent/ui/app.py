"""
Agent TUI 应用 - 全屏交互式界面

类似 Claude Code 的交互体验：
- 全屏终端界面
- 实时对话显示
- 工具调用可视化
- 快捷命令支持
"""
import asyncio
from typing import Optional
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import (
    Input, RichLog, Static, Header, Footer,
    Button, Label, TabbedContent, TabPane
)
from textual.reactive import reactive
from textual.binding import Binding
from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax

from ..core.agent import AgentRunner
from ..core.config import Config, AgentState


class MessageDisplay(Static):
    """消息显示组件"""

    def __init__(self, content: str, role: str = "user", **kwargs):
        self.message_content = content
        self.role = role
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        # 根据角色设置不同样式
        if self.role == "user":
            yield Label(Text(f"👤 You:\n{self.message_content}", style="cyan"))
        elif self.role == "assistant":
            yield Label(Text(f"🤖 Assistant:\n{self.message_content}", style="green"))
        elif self.role == "system":
            yield Label(Text(f"ℹ️ System:\n{self.message_content}", style="dim"))

    def render(self) -> RenderableType:
        """渲染消息"""
        header = {
            "user": ("👤 You", "cyan"),
            "assistant": ("🤖 Assistant", "green"),
            "system": ("ℹ️ System", "dim"),
            "tool": ("🔧 Tool", "yellow")
        }.get(self.role, ("? Unknown", "white"))

        panel = Panel(
            self.message_content,
            title=Text(header[0], style=header[1]),
            border_style=header[1],
            padding=(0, 1)
        )
        return panel


class ToolCallDisplay(Static):
    """工具调用显示组件"""

    def __init__(self, tool_name: str, args: dict, result: str = None, **kwargs):
        self.tool_name = tool_name
        self.args = args
        self.result = result
        super().__init__(**kwargs)

    def render(self) -> RenderableType:
        """渲染工具调用"""
        # 简短显示参数
        args_str = ", ".join([f"{k}={repr(v)[:30]}" for k, v in self.args.items()])[:60]

        content = f"[bold]{self.tool_name}[/bold]({args_str}...)"

        if self.result:
            # 截断结果
            result_preview = str(self.result)[:200]
            if len(str(self.result)) > 200:
                result_preview += "..."
            content += f"\n[dim]→ {result_preview}[/dim]"

        panel = Panel(
            content,
            title=Text(f"🔧 {self.tool_name}", style="yellow"),
            border_style="yellow",
            padding=(0, 1),
            height=5
        )
        return panel


class AgentHeader(Header):
    """自定义 Header"""

    def render(self) -> RenderableType:
        title = Text("nanoAgent", style="bold cyan")
        subtitle = Text("按 Ctrl+C 退出 | /help 获取帮助", style="dim")

        return Panel(
            Horizontal(
                Static(title, classes="header-title"),
                Static(subtitle, classes="header-subtitle"),
                classes="header-content"
            ),
            style="on dark_blue"
        )


class AgentTUI(App[None]):
    """
    Agent TUI 主应用类

    提供类似 Claude Code 的全屏交互界面
    """

    TITLE = "nanoAgent"
    SUB_TITLE = "AI Agent 交互终端"

    CSS = """
    Screen { align: center middle; }

    #main-container {
        width: 100%;
        height: 100%;
        layout: vertical;
    }

    #chat-log {
        width: 100%;
        height: 85%;
        border: solid green;
        padding: 1;
        overflow-y: scroll;
    }

    #input-container {
        width: 100%;
        height: 15%;
        dock: bottom;
        border-top: solid $primary;
    }

    #input-box {
        width: 100%;
        height: auto;
    }

    #status-bar {
        width: 100%;
        height: 1;
        background: $primary-darken-2;
        color: $text;
        content-align: center middle;
    }

    .message-user {
        background: $surface-darken-1;
        border-left: solid cyan;
        padding: 1;
        margin: 1 0;
    }

    .message-assistant {
        background: $surface-darken-1;
        border-left: solid green;
        padding: 1;
        margin: 1 0;
    }

    .tool-call {
        background: $surface-darken-1;
        border-left: solid yellow;
        padding: 1;
        margin: 1 0;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", show=True),
        Binding("ctrl+l", "clear", "清屏", show=True),
        Binding("ctrl+h", "help", "帮助", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent: Optional[AgentRunner] = None
        self.messages = []  # 对话历史
        self.is_processing = False
        self.current_task = None

    def compose(self) -> ComposeResult:
        """构建 UI"""
        yield Static(
            Text("nanoAgent", style="bold cyan") + Text(" | 按 Ctrl+C 退出 | /help 获取帮助", style="dim"),
            id="status-bar"
        )

        with Vertical(id="main-container"):
            # 聊天记录区域
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)

            # 输入区域
            with Horizontal(id="input-container"):
                yield Input(
                    placeholder="输入消息... (按 Enter 发送, /help 查看命令)",
                    id="input-box"
                )

    async def on_mount(self) -> None:
        """应用加载时初始化"""
        self.agent = AgentRunner()

        # 显示欢迎信息
        log = self.query_one("#chat-log", RichLog)
        log.write(Panel.fit(
            Text.assemble(
                ("欢迎使用 nanoAgent!\n\n", "bold cyan"),
                ("可用命令:\n", "bold"),
                ("  /clear", "yellow"), (" - 清空屏幕\n", "dim"),
                ("  /help", "yellow"), (" - 显示帮助\n", "dim"),
                ("  /exit", "yellow"), (" - 退出程序\n", "dim"),
                ("\n快捷操作:\n", "bold"),
                ("  Ctrl+L", "yellow"), (" - 清屏\n", "dim"),
                ("  Ctrl+C", "yellow"), (" - 退出\n", "dim"),
            ),
            title="nanoAgent",
            border_style="cyan"
        ))

        self.query_one("#input-box", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理输入提交"""
        if self.is_processing:
            return

        user_input = event.value.strip()
        if not user_input:
            return

        # 清空输入框
        input_widget = self.query_one("#input-box", Input)
        input_widget.value = ""

        # 处理命令
        if user_input.startswith("/"):
            await self.handle_command(user_input)
            return

        # 处理普通消息
        await self.process_message(user_input)

    async def handle_command(self, command: str) -> None:
        """处理斜杠命令"""
        log = self.query_one("#chat-log", RichLog)
        status = self.query_one("#status-bar", Static)

        cmd = command.lower()

        if cmd == "/clear" or cmd == "/cls":
            log.clear()
            status.update(Text("屏幕已清空", style="dim"))

        elif cmd == "/help":
            help_text = self.get_help_text()
            log.write(Panel(help_text, title="帮助", border_style="cyan"))

        elif cmd == "/exit" or cmd == "/quit":
            await self.action_quit()

        elif cmd == "/status":
            status_text = self.get_status_text()
            log.write(Panel(status_text, title="状态", border_style="green"))

        elif cmd.startswith("/model"):
            # 可以切换模型
            parts = command.split(maxsplit=1)
            if len(parts) > 1:
                new_model = parts[1]
                Config.OPENAI_MODEL = new_model
                log.write(Panel(f"模型已切换为: {new_model}", style="green"))
            else:
                log.write(Panel(f"当前模型: {Config.OPENAI_MODEL}", style="dim"))

        else:
            log.write(Panel(f"未知命令: {command}\n输入 /help 查看可用命令", style="red"))

    async def process_message(self, message: str) -> None:
        """处理用户消息"""
        if not self.agent:
            return

        log = self.query_one("#chat-log", RichLog)
        status = self.query_one("#status-bar", Static)

        self.is_processing = True
        status.update(Text("处理中...", style="yellow"))

        # 显示用户消息
        log.write(Panel(
            message,
            title="👤 You",
            border_style="cyan",
            title_align="left"
        ))

        # 滚动到底部
        log.scroll_end()

        try:
            # 构建上下文并执行
            rules, skills, memory = self.agent._load_context()
            system_prompt = self.agent._build_system_prompt(rules, skills, memory)

            # 添加用户消息到历史
            self.messages.append({"role": "user", "content": message})
            all_messages = [{"role": "system", "content": system_prompt}] + self.messages

            # 执行步骤并显示工具调用
            result = await self.execute_with_tools(all_messages)

            # 显示助手回复
            if result:
                log.write(Panel(
                    result,
                    title="🤖 Assistant",
                    border_style="green",
                    title_align="left"
                ))

                # 更新历史
                self.messages.append({"role": "assistant", "content": result})

                # 保存到记忆
                self.agent.memory_manager.save(message, result)

            status.update(Text("就绪", style="green"))

        except Exception as e:
            log.write(Panel(f"错误: {str(e)}", title="❌ Error", border_style="red"))
            status.update(Text(f"错误: {str(e)}", style="red"))

        finally:
            self.is_processing = False
            log.scroll_end()

    async def execute_with_tools(self, messages: list) -> str:
        """执行 Agent 步骤并显示工具调用"""
        import json

        log = self.query_one("#chat-log", RichLog)

        for iteration in range(Config.MAX_ITERATIONS):
            # 调用 API
            response = self.agent.client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=messages,
                tools=self.agent.all_tools
            )

            message = response.choices[0].message

            # 如果没有工具调用，直接返回内容
            if not message.tool_calls:
                return message.content

            # 添加助手消息
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            })

            # 处理每个工具调用
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                raw_args = tool_call.function.arguments

                try:
                    args = json.loads(raw_args)
                except:
                    args = {}

                # 显示工具调用
                self.show_tool_call(func_name, args)

                # 执行工具
                result, _ = self.agent.executor.execute_tool(func_name, raw_args)

                # 显示工具结果
                self.show_tool_result(func_name, result)

                # 添加工具响应到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

                # 特殊处理 plan 工具
                if func_name == "plan" and AgentState.current_plan:
                    step_results = []
                    for step in AgentState.current_plan:
                        self.show_step_start(step)
                        messages.append({"role": "user", "content": step})
                        step_result = await self.execute_with_tools(messages)
                        step_results.append(step_result)
                        self.show_step_done(step, step_result)

                    AgentState.plan_mode = False
                    AgentState.current_plan = []
                    return "\n\n".join(step_results)

        return "达到最大迭代次数"

    def show_tool_call(self, name: str, args: dict) -> None:
        """显示工具调用提示"""
        log = self.query_one("#chat-log", RichLog)

        # 格式化参数
        args_str = ", ".join([f"{k}={repr(v)[:50]}" for k, v in args.items()])

        log.write(Panel(
            f"[bold blue]{name}[/bold blue]({args_str})",
            title="⏳ 正在执行",
            border_style="yellow",
            title_align="left"
        ))
        log.scroll_end()

    def show_tool_result(self, name: str, result: str) -> None:
        """显示工具执行结果"""
        log = self.query_one("#chat-log", RichLog)

        # 截断过长的结果
        preview = str(result)[:500]
        if len(str(result)) > 500:
            preview += "\n... (截断)"

        # 根据工具类型显示不同的样式
        if "Error" in str(result):
            border = "red"
            icon = "❌"
        else:
            border = "green"
            icon = "✓"

        log.write(Panel(
            preview,
            title=f"{icon} {name} 完成",
            border_style=border,
            title_align="left"
        ))
        log.scroll_end()

    def show_step_start(self, step: str) -> None:
        """显示步骤开始"""
        log = self.query_one("#chat-log", RichLog)
        log.write(Panel(
            f"[bold]{step}[/bold]",
            title="📋 执行步骤",
            border_style="blue",
            title_align="left"
        ))
        log.scroll_end()

    def show_step_done(self, step: str, result: str) -> None:
        """显示步骤完成"""
        log = self.query_one("#chat-log", RichLog)
        log.write(Panel(
            f"[dim]{str(result)[:300]}...[/dim]" if len(str(result)) > 300 else result,
            title="✓ 步骤完成",
            border_style="green",
            title_align="left"
        ))
        log.scroll_end()

    def get_help_text(self) -> Text:
        """获取帮助文本"""
        return Text.assemble(
            ("命令列表:\n\n", "bold underline"),
            ("/help", "yellow bold"), ("    - 显示此帮助信息\n", "dim"),
            ("/clear", "yellow bold"), ("   - 清空屏幕\n", "dim"),
            ("/cls", "yellow bold"), ("     - 清空屏幕（Windows风格）\n", "dim"),
            ("/status", "yellow bold"), ("  - 显示当前状态\n", "dim"),
            ("/exit", "yellow bold"), ("    - 退出程序\n", "dim"),
            ("/quit", "yellow bold"), ("    - 退出程序（同上）\n\n", "dim"),
            ("/model [name]", "yellow bold"), (" - 切换或查看模型\n\n", "dim"),
            ("快捷操作:\n", "bold underline"),
            ("Ctrl+L", "cyan"), (" - 清空屏幕\n", "dim"),
            ("Ctrl+C", "cyan"), (" - 退出程序\n", "dim"),
            ("Ctrl+H", "cyan"), (" - 显示帮助\n\n", "dim"),
            ("提示:\n", "bold underline"),
            ("• 直接输入消息与 Agent 对话\n", "dim"),
            ("• Agent 会记住对话历史\n", "dim"),
            ("• 支持文件读写、代码搜索、命令执行等操作\n", "dim"),
        )

    def get_status_text(self) -> Text:
        """获取状态文本"""
        return Text.assemble(
            ("当前状态:\n\n", "bold underline"),
            ("模型: ", "bold"), (f"{Config.OPENAI_MODEL}\n", "green"),
            ("API Key: ", "bold"), ("已配置\n" if Config.OPENAI_API_KEY else "未配置 ❌\n", "green" if Config.OPENAI_API_KEY else "red"),
            ("记忆文件: ", "bold"), (f"{Config.MEMORY_FILE}\n\n", "dim"),
            ("当前计划: ", "bold"), (f"{len(AgentState.current_plan)} 个步骤\n" if AgentState.current_plan else "无\n", "blue"),
            ("计划模式: ", "bold"), ("开启\n" if AgentState.plan_mode else "关闭\n", "green" if AgentState.plan_mode else "dim"),
        )

    async def action_clear(self) -> None:
        """清屏动作"""
        log = self.query_one("#chat-log", RichLog)
        log.clear()

    async def action_help(self) -> None:
        """帮助动作"""
        log = self.query_one("#chat-log", RichLog)
        log.write(Panel(self.get_help_text(), title="帮助", border_style="cyan"))


def run_tui() -> None:
    """启动 TUI 应用"""
    app = AgentTUI()
    app.run()


if __name__ == "__main__":
    run_tui()
