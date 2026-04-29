"""CodeAgent - ClaudeCode style Agent framework with original flavor

Usage:
    python main.py [--plan] "your task"
    python main.py --interactive
    python main.py --chat

--plan: Enable task planning mode, decompose complex tasks into steps
--interactive, --chat: Start interactive CLI interface
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from dotenv import load_dotenv

load_dotenv()

from codeagent.agent import CodeAgent
from codeagent.utils.display import (
    print_header,
    print_footer,
    print_info,
    print_error,
    print_result,
    console,
)


def main():
    parser = argparse.ArgumentParser(
        description="CodeAgent - ClaudeCode style Agent framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py "Hello, what is 2+2?"
    python main.py --plan "Build a web server with Flask"
    python main.py --interactive
    python main.py --chat

Features:
    * Memory: Remember previous conversations
    * Rules: Load .agent/rules/*.md rule files
    * Skills: Load .agent/skills/*.json skill files
    * MCP: Support Model Context Protocol external tools
    * Plan: Decompose complex tasks into steps
    * Rich TUI: Colored output and progress display
        """
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Enable task planning mode"
    )
    parser.add_argument(
        "--interactive",
        "--chat",
        "-i",
        action="store_true",
        dest="interactive",
        help="Start interactive CLI mode"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (default: from OPENAI_MODEL env)"
    )
    parser.add_argument(
        "--memory-file",
        type=str,
        default=None,
        help="Memory file path (default: agent_memory.md)"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="Task to execute"
    )

    args = parser.parse_args()

    if args.no_color:
        os.environ["NO_COLOR"] = "1"

    agent = CodeAgent(
        model=args.model,
    )

    if args.memory_file:
        agent.config.memory_file = args.memory_file

    if args.interactive:
        from codeagent.utils.cli import run_cli
        run_cli(agent)
        return

    if not args.task:
        print_error("Task is required")
        console.print("\n[dim]Usage:[/dim] python main.py [--plan] 'your task'")
        console.print("[dim]Or use:[/dim] python main.py --interactive [yellow]for interactive mode[/yellow]")
        sys.exit(1)

    task = " ".join(args.task)

    print_header("CodeAgent")
    print_info(f"[yellow]Task:[/yellow] {task}")
    if args.plan:
        print_info("[yellow]Plan mode:[/yellow] enabled")
        console.print()

    try:
        result = agent.run(task, use_plan=args.plan)

        print_footer()
        print_result(result)

    except KeyboardInterrupt:
        console.print("\n")
        print_error("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Error: {e}")
        if os.getenv("DEBUG"):
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
