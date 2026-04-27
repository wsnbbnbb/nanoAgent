"""
nanoAgent 测试套件 - 详细注释版
==============================
测试三个版本的 Agent 功能：
- AgentRegressionTests: agent.py (基础版)
- AgentPlusRegressionTests: agent-plus.py (增强版)  
- AgentClaudeCodeRegressionTests: agent-claudecode.py (高级版)

测试策略:
1. 通过 mock OpenAI 客户端避免真实 API 调用
2. 测试错误处理：未知工具、无效参数
3. 测试消息流：验证模型接收的消息格式正确
4. 测试回归：确保功能不被破坏

"""

# ===================================================================
# Part 1: 导入与工具函数
# ===================================================================

import importlib.util      # 动态模块加载
import sys                 # 模块路径操作
import types               # 创建模拟模块
import unittest            # 单元测试框架
from importlib.machinery import ModuleSpec  # 模块规格
from pathlib import Path   # 路径操作
from types import SimpleNamespace  # 简单命名空间
from typing import cast

# 项目根目录
REPO_ROOT = Path(__file__).resolve().parents[1]


def load_agent_module(relative_path: str, module_name: str):
    """
    动态加载 Agent 模块并注入模拟的 OpenAI 客户端。
    
    这是测试的关键：避免真实 API 调用，通过 mock 控制模型行为。
    
    实现步骤:
    1. 创建一个假的 openai 模块
    2. 创建一个假的 OpenAI 类（只初始化，不实际连接）
    3. 将假模块注入 sys.modules，覆盖真实导入
    4. 使用 importlib 从文件加载目标模块
    5. 恢复原始 openai 模块（如有）
    
    参数:
        relative_path: 相对于项目根目录的模块路径
        module_name: 模块名称（用于 __name__）
    
    返回:
        module: 加载的模块对象
    """
    # 创建假 openai 模块
    fake_openai = types.ModuleType("openai")
    
    # 创建假 OpenAI 类
    class FakeOpenAI:
        def __init__(self, *args, **kwargs):
            # 模拟客户端结构，但不实际连接
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=None))
    
    # 将假类注入假模块
    setattr(fake_openai, "OpenAI", FakeOpenAI)
    
    # 保存原始 openai 模块（如有）
    previous_openai = sys.modules.get("openai")
    
    # 注入假模块
    sys.modules["openai"] = fake_openai
    
    try:
        # 从文件加载目标模块
        spec = importlib.util.spec_from_file_location(
            module_name,
            REPO_ROOT / relative_path,
        )
        assert spec is not None
        module = importlib.util.module_from_spec(cast(ModuleSpec, spec))
        loader = spec.loader
        assert loader is not None
        loader.exec_module(module)
        return module
    finally:
        # 恢复原始模块或清理
        if previous_openai is None:
            sys.modules.pop("openai", None)
        else:
            sys.modules["openai"] = previous_openai


def make_response(message):
    """
    创建模拟的 OpenAI API 响应对象。
    
    参数:
        message: 模拟的消息对象
    
    返回:
        SimpleNamespace: 模拟的 API 响应
    """
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# ===================================================================
# Part 2: 基础版 Agent 测试
# ===================================================================

class AgentRegressionTests(unittest.TestCase):
    """
    测试 agent.py 的功能和错误处理。
    """
    
    def setUp(self):
        """测试准备：加载 agent 模块。"""
        self.agent = load_agent_module("agent.py", "nanoagent_agent")
    
    def test_parse_tool_arguments_reports_invalid_json(self):
        """
        测试：无效 JSON 参数应返回错误标记。
        
        验证 parse_tool_arguments 能正确处理截断的 JSON。
        """
        parsed = self.agent.parse_tool_arguments('{"command":')
        self.assertIn("_argument_error", parsed)
        self.assertIn("Invalid JSON arguments", parsed["_argument_error"])
    
    def test_parse_tool_arguments_ignores_non_object_payloads(self):
        """
        测试：非对象类型（如数组）应降级为空字典。
        """
        self.assertEqual(self.agent.parse_tool_arguments('["ls"]'), {})
    
    def test_run_agent_returns_unknown_tool_error_to_model_loop(self):
        """
        测试：未知工具应返回错误信息给模型。
        
        验证当模型调用不存在的工具时，错误能被正确传递回模型，
        模型根据错误信息调整策略，最终完成任务。
        """
        captured_messages = []
        
        def fake_create(*, model, messages, tools):
            """模拟 OpenAI API 调用。"""
            captured_messages.append(messages)
            
            if len(captured_messages) == 1:
                # 第一次调用：模拟模型调用不存在的工具
                return make_response(
                    SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id="tc-1",
                                function=SimpleNamespace(
                                    name="missing_tool",
                                    arguments="{}"
                                ),
                            )
                        ],
                    )
                )
            # 第二次调用：模拟模型直接回复（无工具调用）
            return make_response(SimpleNamespace(content="done", tool_calls=[]))
        
        # 注入模拟客户端
        setattr(
            self.agent, "client",
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
        )
        
        # 执行测试
        result = self.agent.run_agent("test unknown tool", max_iterations=2)
        
        # 验证结果
        self.assertEqual(result, "done")
        
        # 验证错误消息被正确传递给模型
        tool_messages = [
            m for m in captured_messages[1]
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Unknown tool 'missing_tool'", tool_messages[0]["content"])
    
    def test_run_agent_returns_argument_errors_to_model_loop(self):
        """
        测试：无效参数 JSON 应返回错误信息给模型。
        """
        captured_messages = []
        
        def fake_create(*, model, messages, tools):
            captured_messages.append(messages)
            
            if len(captured_messages) == 1:
                # 模拟模型生成无效的 JSON 参数
                return make_response(
                    SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id="tc-1",
                                function=SimpleNamespace(
                                    name="read_file",
                                    arguments='{"path":',  # 截断的 JSON
                                ),
                            )
                        ],
                    )
                )
            return make_response(SimpleNamespace(content="done", tool_calls=[]))
        
        setattr(
            self.agent, "client",
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
        )
        
        result = self.agent.run_agent("test invalid args", max_iterations=2)
        self.assertEqual(result, "done")
        
        # 验证错误传递
        tool_messages = [
            m for m in captured_messages[1]
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Invalid JSON arguments", tool_messages[0]["content"])


# ===================================================================
# Part 3: 增强版 Agent 测试
# ===================================================================

class AgentPlusRegressionTests(unittest.TestCase):
    """
    测试 agent-plus.py 的功能和错误处理。
    """
    
    def setUp(self):
        """加载 agent-plus 模块。"""
        self.agent = load_agent_module("agent-plus.py", "nanoagent_agent_plus")
    
    def test_run_agent_step_returns_unknown_tool_error(self):
        """
        测试：run_agent_step 应正确处理未知工具。
        """
        captured_messages = []
        
        def fake_create(*, model, messages, tools):
            captured_messages.append(messages)
            
            if len(captured_messages) == 1:
                return make_response(
                    SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id="tc-1",
                                function=SimpleNamespace(
                                    name="missing_tool",
                                    arguments="{}"
                                ),
                            )
                        ],
                    )
                )
            return make_response(SimpleNamespace(content="done", tool_calls=[]))
        
        setattr(
            self.agent, "client",
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
        )
        
        result, actions, _messages = self.agent.run_agent_step(
            "test unknown tool",
            [{"role": "system", "content": "hi"}],
            max_iterations=2,
        )
        
        self.assertEqual(result, "done")
        self.assertEqual(actions, [])  # 未知工具不记录到 actions
        
        # 验证错误传递
        tool_messages = [
            m for m in captured_messages[1]
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Unknown tool 'missing_tool'", tool_messages[0]["content"])
    
    def test_run_agent_step_returns_argument_errors(self):
        """
        测试：run_agent_step 应处理无效参数。
        """
        captured_messages = []
        
        def fake_create(*, model, messages, tools):
            captured_messages.append(messages)
            
            if len(captured_messages) == 1:
                return make_response(
                    SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id="tc-1",
                                function=SimpleNamespace(
                                    name="read_file",
                                    arguments='{"path":',  # 无效 JSON
                                ),
                            )
                        ],
                    )
                )
            return make_response(SimpleNamespace(content="done", tool_calls=[]))
        
        setattr(
            self.agent, "client",
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
        )
        
        result, actions, _messages = self.agent.run_agent_step(
            "test invalid args",
            [{"role": "system", "content": "hi"}],
            max_iterations=2,
        )
        
        self.assertEqual(result, "done")
        self.assertEqual(actions, [])
        
        # 验证错误传递
        tool_messages = [
            m for m in captured_messages[1]
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Invalid JSON arguments", tool_messages[0]["content"])


# ===================================================================
# Part 4: 高级版 Agent 测试
# ===================================================================

class AgentClaudeCodeRegressionTests(unittest.TestCase):
    """
    测试 agent-claudecode.py 的功能。
    """
    
    def setUp(self):
        """加载 agent-claudecode 模块。"""
        self.agent = load_agent_module(
            "agent-claudecode.py", "nanoagent_agent_claudecode"
        )
    
    def test_run_agent_step_returns_unknown_tool_error(self):
        """
        测试：高级版也能正确处理未知工具。
        
        验证工具分发机制工作正常。
        """
        captured_messages = []
        
        def fake_create(*, model, messages, tools):
            captured_messages.append(messages)
            
            if len(captured_messages) == 1:
                return make_response(
                    SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id="tc-1",
                                function=SimpleNamespace(
                                    name="missing_tool",
                                    arguments="{}"
                                ),
                            )
                        ],
                    )
                )
            return make_response(SimpleNamespace(content="done", tool_calls=[]))
        
        setattr(
            self.agent, "client",
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
        )
        
        result, _messages = self.agent.run_agent_step(
            [{"role": "system", "content": "hi"}, {"role": "user", "content": "test"}],
            self.agent.base_tools,
            max_iterations=2,
        )
        
        self.assertEqual(result, "done")
        
        # 验证
        tool_messages = [
            m for m in captured_messages[1]
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Unknown tool 'missing_tool'", tool_messages[0]["content"])
    
    def test_run_agent_step_returns_argument_errors(self):
        """
        测试：高级版参数错误处理。
        """
        captured_messages = []
        
        def fake_create(*, model, messages, tools):
            captured_messages.append(messages)
            
            if len(captured_messages) == 1:
                return make_response(
                    SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                id="tc-1",
                                function=SimpleNamespace(
                                    name="read",
                                    arguments='{"path":',  # 无效 JSON
                                ),
                            )
                        ],
                    )
                )
            return make_response(SimpleNamespace(content="done", tool_calls=[]))
        
        setattr(
            self.agent, "client",
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
        )
        
        result, _messages = self.agent.run_agent_step(
            [{"role": "system", "content": "hi"}],
            self.agent.base_tools,
            max_iterations=2,
        )
        
        self.assertEqual(result, "done")


# ===================================================================
# Part 5: 测试运行入口
# ===================================================================

if __name__ == "__main__":
    # 使用 unittest 运行所有测试
    unittest.main()
