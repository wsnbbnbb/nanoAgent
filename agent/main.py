#!/usr/bin/env python3
"""
nanoAgent - 轻量级 AI Agent 框架

使用方法:
    python main.py "你的任务"           # 单任务执行模式
    python main.py --plan "复杂任务"    # 计划模式
    python main.py --interactive        # 交互式 REPL 模式
    python main.py --tui               # 全屏 TUI 模式（实验性）
    python main.py --help

功能特性:
    - 文件读写与编辑
    - 代码搜索与全局查找
    - 命令行执行
    - 任务规划与拆解
    - 记忆持久化
    - 规则与技能系统
    - MCP 协议扩展
    - 交互式对话
"""
import sys
from pathlib import Path

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from agent.core import run_agent_claudecode
from agent.ui import run_repl


def print_banner():
    """打印启动横幅"""
    print("=" * 50)
    print(" nanoAgent - 轻量级 AI Agent 框架 ")
    print("=" * 50)


def print_help():
    """打印帮助信息"""
    print(f"""
{sys.argv[0]} - AI Agent 执行器

用法:
    python main.py [选项] "任务描述"

选项:
    --plan, -p      启用计划模式，将任务拆解为多个步骤
    --help, -h      显示帮助信息

示例:
    # 简单任务
    python main.py "创建一个 Hello World 程序"

    # 复杂任务（使用计划模式）
    python main.py --plan "创建一个完整的 TODO 应用，包含增删改查功能"

    # 文件操作
    python main.py "读取 ./README.md 文件内容"

    # 代码搜索
    python main.py "在所有 Python 文件中搜索 'class' 定义"

交互式模式:
    python main.py --interactive
    python main.py -i

    交互式模式特点：
    - 持续对话，记住上下文
    - 支持 /help、/clear、/exit 等命令
    - 实时显示工具调用过程

TUI 模式（全屏界面）:
    python main.py --tui
    python main.py -t

    TUI 模式特点：
    - 全屏界面，类似 Claude Code
    - 实时显示对话和工具调用
    - 支持快捷键：Ctrl+L 清屏，Ctrl+C 退出

环境变量:
    OPENAI_API_KEY      - OpenAI API 密钥
    OPENAI_BASE_URL     - OpenAI API 基础地址（可选）
    OPENAI_MODEL        - 使用的模型（默认: gpt-4o-mini）
    """)


def main():
    """主函数"""
    if "--help" in sys.argv or "-h" in sys.argv:
        print_help()
        sys.exit(0)

    if "--interactive" in sys.argv or "-i" in sys.argv:
        run_repl()
        return

    if "--tui" in sys.argv or "-t" in sys.argv:
        try:
            from agent.ui import run_tui
            run_tui()
        except Exception as e:
            print(f"TUI 模式启动失败: {e}")
            print("切换为 REPL 模式...")
            run_repl()
        return

    use_plan = "--plan" in sys.argv or "-p" in sys.argv

    for opt in ["--plan", "-p"]:
        if opt in sys.argv:
            sys.argv.remove(opt)

    if len(sys.argv) < 2:
        print("错误: 请提供任务描述")
        print("\n用法:")
        print(f'  python main.py "你的任务描述"')
        print(f'  python main.py --plan "复杂任务描述"')
        print(f'  python main.py --interactive      # 交互式对话')
        print(f'  python main.py --tui            # 全屏界面')
        print("\n使用 --help 查看更多信息")
        sys.exit(1)

    task = " ".join(sys.argv[1:])

    print_banner()
    print(f"\n任务: {task}")
    if use_plan:
        print("模式: 计划模式（任务将被拆解执行）")
    print("-" * 50)

    try:
        result = run_agent_claudecode(task, use_plan=use_plan)
        print("\n" + "=" * 50)
        print("任务执行完成")
        print("=" * 50)
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n执行错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()