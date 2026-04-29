"""TUI display module - Based on Rich"""
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.tree import Tree
from rich import box
from typing import Optional, List, Dict, Any
import sys


console = Console()


def print_info(message: str) -> None:
    """Print info message"""
    console.print(f"[bold blue]i[/bold blue] {message}")


def print_success(message: str) -> None:
    """Print success message"""
    console.print(f"[bold green]+[/bold green] {message}")


def print_warning(message: str) -> None:
    """Print warning message"""
    console.print(f"[bold yellow]![/bold yellow] {message}")


def print_error(message: str) -> None:
    """Print error message"""
    console.print(f"[bold red]x[/bold red] {message}")


def print_tool_call(tool_name: str, args: Dict[str, Any]) -> None:
    """Print tool call"""
    console.print(f"[bold cyan]Tool[/bold cyan] [yellow]{tool_name}[/yellow]({args})")


def print_step(step: int, total: int, message: str) -> None:
    """Print step info"""
    console.print(f"\n[bold magenta]Step {step}/{total}[/bold magenta] {message}")


def print_result(content: str, max_lines: int = 50) -> None:
    """Print result content"""
    lines = content.split('\n')
    if len(lines) > max_lines:
        content = '\n'.join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
    console.print(Panel(content, title="Result", expand=False))


def print_markdown(content: str) -> None:
    """Print markdown content"""
    console.print(Markdown(content))


def print_syntax(code: str, language: str = "python") -> None:
    """Print syntax highlighted code"""
    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
    console.print(syntax)


def print_table(headers: List[str], rows: List[List[str]], title: Optional[str] = None) -> None:
    """Print table"""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def print_tree(root: Any, **kwargs) -> None:
    """Print tree structure"""
    if isinstance(root, dict):
        items = list(root.items())
    elif isinstance(root, list):
        items = [(str(i), v) for i, v in enumerate(root)]
    else:
        items = [("root", root)]

    tree = Tree("Tree")
    for key, value in items:
        if isinstance(value, (dict, list)):
            branch = tree.add(f"[bold]{key}[/bold]")
            print_tree(value, parent=branch)
        else:
            tree.add(f"[bold]{key}[/bold]: {value}")
    console.print(tree)


def print_panel(content: str, title: Optional[str] = None, **kwargs) -> None:
    """Print panel"""
    console.print(Panel(content, title=title, **kwargs))


def print_header(message: str) -> None:
    """Print header"""
    console.print(f"\n[bold cyan]==== {message} ====[/bold cyan]\n")


def print_footer(message: str) -> None:
    """Print footer"""
    console.print(f"\n[bold cyan]==== {message} ====[/bold cyan]\n")


def create_progress() -> Progress:
    """Create progress bar"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    )


class Spinner:
    """Spinner context manager"""

    def __init__(self, message: str = "Loading..."):
        self.message = message
        self.progress = None
        self.task = None

    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
        )
        self.progress.__enter__()
        self.task = self.progress.add_task(self.message, total=None)
        return self

    def __exit__(self, *args):
        if self.progress:
            self.progress.__exit__(*args)


class StatusDisplay:
    """Status display context manager"""

    def __init__(self, message: str):
        self.message = message
        self.console = Console()

    def __enter__(self):
        self.console.print(f"[bold blue]...[/bold blue] {self.message}")
        return self

    def __exit__(self, *args):
        pass

    def update(self, message: str):
        """Update status message"""
        self.console.print(f"[bold blue]...[/bold blue] {message}")


def confirm(message: str) -> bool:
    """Ask for confirmation"""
    console.print(f"[bold yellow]?[/bold yellow] {message} (y/n)")
    answer = input().strip().lower()
    return answer in ('y', 'yes')


def input_text(message: str) -> str:
    """Get text input"""
    console.print(f"[bold blue]>[/bold blue] {message}")
    return input().strip()


def print_agent_intro(version: str = "") -> None:
    """Print agent intro"""
    if version:
        intro = f"[bold cyan]CodeAgent[/bold cyan] v{version}\n\nType your task and press Enter."
    else:
        intro = "Type your task and press Enter."
    console.print(Panel(intro, title="CodeAgent", expand=False))
