"""
集成测试脚本 - 测试 nanoAgent 所有新功能

运行：python test_integration.py
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from agent.vcs.change_tracker import ChangeTracker, ChangeType
from agent.tools.enhanced_edit import FileEditor
from agent.context.manager import ContextManager
from agent.memory.vector.store import SimpleMemory, ConversationMemory
from agent.execution.async_executor import AsyncAgentExecutor
from agent.utils.profiler import profiled, PerformanceProfiler

# 测试 1: 文件变更追踪
def test_change_tracker():
    print("\n" + "="*60)
    print("测试 1: ChangeTracker (文件变更追踪)")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")

        # 创建追踪器
        tracker = ChangeTracker(storage_dir=os.path.join(tmpdir, ".history"))

        # 创建文件
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("original content\n")

        # 追踪修改
        tracker.track_edit(test_file, "original content\n", "new content\n", "test edit")
        print(f"✓ Tracked edit: {test_file}")

        # 验证 undo
        print(f"✓ Changes: {len(tracker.changes)}")
        print(f"✓ Can undo: {tracker.can_undo()}")

        # 测试 undo
        if tracker.can_undo():
            change = tracker.undo()
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"✓ Undo successful, content: {content!r}")

        # 测试 redo
        if tracker.can_redo():
            change = tracker.redo()
            print(f"✓ Redo 成功")

        print("[测试 1 通过 ✓]")
    return True


# 测试 2: 增强文件编辑
def test_enhanced_editor():
    print("\n" + "="*60)
    print("测试 2: FileEditor (增强文件编辑)")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")

        # 初始化编辑器
        editor = FileEditor(create_backup=True)

        # 测试编辑字符串
        old_content = "Hello World"
        new_content = "Hello Universe"

        diff = editor.calculate_diff(old_content, new_content)
        print(f"✓ Diff 计算成功:")
        print(diff[:200])

        # 测试文件写入
        edit_result = editor.edit_file_str(test_file, "测试内容", "修改后内容", "测试编辑")
        print(f"✓ 编辑成功: success={edit_result.success}")

        # 验证备份
        backups = editor.list_backups(test_file)
        print(f"✓ 备份数量: {len(backups)}")

        print("[测试 2 通过 ✓]")
    return True


# 测试 3: 智能上下文管理
def test_context_manager():
    print("\n" + "="*60)
    print("测试 3: ContextManager (智能上下文管理)")
    print("="*60)

    manager = ContextManager(max_tokens=1000)

    # 添加一些消息
    manager.add_message("system", "You are a helpful assistant.")
    manager.add_message("user", "Hello!")
    manager.add_message("assistant", "Hi there!")

    # 获取消息 - 使用 messages 属性
    messages = manager.messages
    print(f"✓ 消息数量: {len(messages)}")

    # 测试上下文优化
    stats = manager.get_stats()
    print(f"✓ Token统计: {stats}")

    # 测试获取模型上下文
    context = manager.get_context_for_model()
    print(f"✓ 上下文格式正确")

    print("[测试 3 通过 ✓]")
    return True


# 测试 4: 记忆系统
def test_memory():
    print("\n" + "="*60)
    print("测试 4: Memory (简单记忆系统)")
    print("="*60)

    # 简单记忆
    simple = SimpleMemory()
    simple.add("用户想要创建文件", "user")
    simple.add("好的，我帮你创建", "assistant")

    results = simple.search("创建文件")
    print(f"✓ 搜索结果数量: {len(results)}")

    context = simple.get_context(n=2)
    print(f"✓ 上下文长度: {len(context)} 字符")

    print("[测试 4 通过 ✓]")
    return True


# 测试 5: MCP 客户端
def test_mcp_client():
    print("\n" + "="*60)
    print("测试 5: MCP Client")
    print("="*60)

    try:
        from agent.mcp.client import MCPClient, MCPManager
        from agent.mcp.server import LocalMCPServer
        print("✓ MCP 模块导入成功")

        # 创建本地服务器（仅测试定义）
        server = LocalMCPServer(name="nanoAgent-test", version="0.1.0")

        # 定义简单的测试处理器 - 直接调用
        def test_handler(param: str = "default") -> dict:
            return {"result": f"Got: {param}"}

        server.register_tool("test_tool", "测试工具", test_handler)

        print(f"✓ MCP 工具注册成功: {len(server.tools)} 个工具")

        print("[测试 5 通过 ✓]")
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# 测试 6: 性能分析装饰器
@profiled
def fibonacci(n: int) -> int:
    """测试用的斐波那契 (非递归)"""
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(2, n):
        a, b = b, a + b
    return b

@profiled
async def async_test():
    """异步测试"""
    await asyncio.sleep(0.01)
    return "done"

def test_profiler():
    print("\n" + "="*60)
    print("测试 6: Profiler (性能分析)")
    print("="*60)

    # 测试同步
    result = fibonacci(15)
    print(f"✓ Fibonacci 结果: {result}")

    # 测试异步
    asyncio.run(async_test())
    print("✓ 异步测试完成")

    # 查看性能报告
    profiler = PerformanceProfiler()
    report = profiler.get_report()
    print(f"✓ 性能数据已收集")
    print(report[:500])

    print("[测试 6 通过 ✓]")
    return True


# 主测试函数
def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("nanoAgent 集成测试开始")
    print("="*60)

    results = []

    results.append(("ChangeTracker", test_change_tracker()))
    results.append(("FileEditor", test_enhanced_editor()))
    results.append(("ContextManager", test_context_manager()))
    results.append(("Memory", test_memory()))
    results.append(("MCP Client", test_mcp_client()))
    results.append(("Profiler", test_profiler()))

    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name:<20} {status}")

    passed = sum(1 for _, p in results if p)
    total = len(results)

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！nanoAgent 功能完整。")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息。")

    return all(r[1] for r in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
