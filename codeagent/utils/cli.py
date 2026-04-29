"""Interactive CLI interface"""
import sys
import os
from typing import Optional
from rich.console import Console

import codeagent
from .display import (
    console,
    print_info,
    print_success,
    print_warning,
    print_error,
    print_agent_intro,
    print_header,
    print_footer,
    print_tool_call,
    print_step,
    confirm,
    input_text,
)

console = Console()


class CLI:
    """Interactive command line interface"""

    def __init__(self, agent):
        self.agent = agent
        self.running = False
        self.history: list = []
        self.history_file = ".cli_history"

    def run(self) -> None:
        """Run interactive CLI"""
        self.running = True
        self._load_history()

        print_agent_intro("")
        print_info("Type 'help' for available commands, 'quit' to exit\n")

        while self.running:
            try:
                user_input = console.input("[bold green]>[/bold green] ").strip()

                if not user_input:
                    continue

                self.history.append(user_input)
                self._save_history()

                if user_input.lower() in ("q", "quit", "exit"):
                    self._quit()
                elif user_input.lower() == "clear":
                    self._clear()
                elif user_input.lower() == "help":
                    self._help()
                elif user_input.lower() == "history":
                    self._show_history()
                elif user_input.lower() == "agent":
                    self._show_agent_info()
                elif user_input.lower() == "tools":
                    self._show_tools()
                else:
                    self._process_input(user_input)

            except KeyboardInterrupt:
                print("\n")
                if confirm("Exit?"):
                    self._quit()
            except EOFError:
                self._quit()

    def _process_input(self, user_input: str) -> None:
        """Process user input"""
        result = self.agent.run(user_input)
        console.print(result)

    def _quit(self) -> None:
        """Quit CLI"""
        print_success("Goodbye!")
        self.running = False

    def _clear(self) -> None:
        """Clear screen"""
        console.clear()
        print_agent_intro("")

    def _help(self) -> None:
        """Show help"""
        help_text = """
[bold]Available Commands:[/bold]

  [cyan]Basic[/cyan]
    quit, q, exit     - Exit the CLI
    clear             - Clear the screen
    help              - Show this help message
    history           - Show command history

  [cyan]Agent[/cyan]
    agent             - Show agent information
    tools             - List available tools
    memory            - Show current memory

  [cyan]Examples[/cyan]
    Hello, how are you?
    Read the file at @README.md
    Build a web server with Flask
"""
        console.print(help_text)

    def _show_history(self) -> None:
        """Show history"""
        if not self.history:
            print_warning("No history yet")
            return

        for i, cmd in enumerate(self.history, 1):
            console.print(f"[dim]{i}[/dim]  {cmd}")

    def _show_agent_info(self) -> None:
        """Show agent info"""
        from .display import print_table

        info = [
            ["Property", "Value"],
            ["Model", self.agent.llm.model],
            ["Provider", self.agent.llm.provider],
            ["Temperature", str(self.agent.llm.temperature)],
            ["Tools", str(len(self.agent.all_tools))],
            ["MCP Tools", str(len(self.agent.mcp_tools))],
            ["Memory File", self.agent.config.memory_file],
        ]

        table = console.table("Agent Information", show_header=False, box=None)
        for row in info:
            table.add_row(f"[bold]{row[0]}[/bold]", row[1])
        console.print(table)

    def _show_tools(self) -> None:
        """Show tools list"""
        from .display import print_table

        rows = []
        for tool in self.agent.all_tools:
            name = tool["function"]["name"]
            desc = tool["function"].get("description", "")[:50]
            rows.append([name, desc + "..." if len(desc) == 50 else desc])

        print_table("Available Tools", ["Tool", "Description"], rows)

    def _load_history(self) -> None:
        """Load history"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    self.history = [line.strip() for line in f if line.strip()]
            except Exception:
                pass

    def _save_history(self) -> None:
        """Save history"""
        try:
            with open(self.history_file, "w") as f:
                f.write("\n".join(self.history[-1000:]))
        except Exception:
            pass


def run_cli(agent) -> None:
    """Run CLI"""
    cli = CLI(agent)
    cli.run()
