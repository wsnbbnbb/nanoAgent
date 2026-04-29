"""
REPL 模式 - 简单的命令行交互（不需要全屏 TUI）

适用于：
- 不支持全屏终端的环境
- 简单的交互需求
- 较小屏幕的窗口
"""
import os
import sys
import json
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.spinner import Spinner
from rich.prompt import Prompt

from ..core.agent import AgentRunner
from ..core.config import Config, AgentState


console = Console()


class AgentREPL():
    """
    Agent REPL - 简单的命令行交互模式

    不需要全屏，直接在终端中交互
    """

    def __init__(self):
        self.agent: Optional[AgentRunner] = None
        self.messages = []
        self.command_handlers = {
            "/help": self.show_help,
            "/clear": self.clear_screen,
            "/exit": self.exit_app,
            "/quit": self.exit_app,
            "/status": self.show_status,
            "/reset": self.reset_session,
        }

    def print_banner(self):
        """打印启动横幅"""
        console.print()
        console.print(Panel.fit(
            Text.assemble(
                ("nanoAgent", "bold cyan"),
                (" - 命令行 AI 助手\n", "dim"),
                ("\n输入 ", "dim"),
                ("/help", "yellow"),
                (" 查看帮助，", "dim"),
                ("/exit", "yellow"),
                (" 退出", "dim"),
            ),
            border_style="cyan"
        ))
        console.print()

    def show_help(self, args=None):
        """显示帮助"""
        help_text = """
[bold cyan]nanoAgent[/bold cyan] - 命令行交互模式

[bold]可用命令:[/bold]
  [yellow]/help[/yellow]     显示此帮助
  [yellow]/clear[/yellow]    清空屏幕
  [yellow]/status[/yellow]   显示当前状态
  [yellow]/reset[/yellow]    重置会话（清除历史）
  [yellow]/exit[/yellow]     退出程序
  [yellow]/quit[/yellow]     同上

[bold]使用方法:[/bold]
  直接输入问题或任务，Agent 会处理并回复。
  支持文件操作、代码搜索、命令执行等。

[bold]示例:[/bold]
  "帮我创建一个 Python Flask 项目"
  "在 src 目录下搜索包含 TODO 的文件"
  "读取 README.md 文件内容"
"""
        console.print(Panel(help_text, title="帮助", border_style="cyan"))

    def clear_screen(self, args=None):
        """清屏"""
        console.clear()
        self.print_banner()

    def exit_app(self, args=None):
        """退出"""
        console.print("\n[dim]Goodbye! 👋[/dim]\n")
        sys.exit(0)

    def show_status(self, args=None):
        """显示状态"""
        status_text = Text.assemble(
            ("模型: ", "bold"), (f"{Config.OPENAI_MODEL}\n", "green"),
            ("API Key: ", "bold"), ("✓ 已配置\n" if Config.OPENAI_API_KEY else "✗ 未配置\n", "green" if Config.OPENAI_API_KEY else "red"),
            ("当前会话消息: ", "bold"), (f"{len(self.messages)} 条\n", "blue"),
            ("当前计划: ", "bold"), (f"{len(AgentState.current_plan)} 个步骤" if AgentState.current_plan else "无", "blue"),
        )
        console.print(Panel(status_text, title="状态", border_style="green"))

    def reset_session(self, args=None):
        """重置会话"""
        self.messages = []
        AgentState.current_plan = []
        AgentState.plan_mode = False
        console.print("[green]✓[/green] 会话已重置")

    def run(self):
        """运行 REPL 循环"""
        self.print_banner()

        # 初始化 Agent
        with console.status("[cyan]正在初始化...") as status:
            self.agent = AgentRunner()
            # 预热加载
            _ = self.agent._load_context()

        console.print("[green]✓[/green] 已就绪")
        console.print()

        while True:
            try:
                # 获取输入
                user_input = console.input("[cyan]❯[/cyan] ").strip()

                if not user_input:
                    continue
                
                # 处理命令
                if user_input.startswith("/"):
                    cmd_parts = user_input.split(maxsplit=1)
                    cmd = cmd_parts[0].lower()
                    args = cmd_parts[1] if len(cmd_parts) > 1 else None

                    handler = self.command_handlers.get(cmd)
                    if handler:
                        handler(args)
                    else:
                        console.print(f"[red]未知命令:[/red] {cmd}")
                        console.print("[dim]输入 /help 查看可用命令[/dim]")
                    continue

                # 处理消息
                self.process_message(user_input)

            except KeyboardInterrupt:
                console.print("\n[dim]使用 /exit 退出[/dim]")
                continue
            except EOFError:
                self.exit_app()

    def process_message(self, message: str):
        """处理用户消息"""
        console.print()
        console.print(Panel(
            message,
            title="👤 User",
            border_style="cyan",
            title_align="left"
        ))

        rules, skills, memory = self.agent._load_context()
        system_prompt = self.agent._build_system_prompt(rules, skills, memory)

        self.messages.append({"role": "user", "content": message})
        all_messages = [{"role": "system", "content": system_prompt}] + self.messages

        with console.status("[cyan]思考中..."):
            result, all_messages = self.agent.run_step(all_messages, self.agent.all_tools)

        if result:
            console.print(Panel(
                result,
                title="🤖 Assistant",
                border_style="green",
                title_align="left"
            ))
            self.messages.append({"role": "assistant", "content": result})
            self.agent.memory_manager.save(message, result)

        console.print()


def run_repl():
    """启动 REPL 模式"""
    try:
        repl = AgentREPL()
        repl.run()
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye! 👋[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    run_repl()
