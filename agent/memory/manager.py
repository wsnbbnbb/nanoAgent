"""
内存管理器 - 持久化存储对话历史和任务结果
"""
import os
from datetime import datetime
from ..core.config import Config


class MemoryManager:
    """管理 Agent 的记忆存储"""

    def __init__(self, memory_file: str = None):
        """
        初始化内存管理器

        Args:
            memory_file: 记忆文件路径，默认使用 Config.MEMORY_FILE
        """
        self.memory_file = memory_file or Config.MEMORY_FILE

    def load(self, max_lines: int = None) -> str:
        """
        加载最近的记忆内容

        Args:
            max_lines: 最大返回行数，默认使用 Config.MAX_MEMORY_LINES

        Returns:
            记忆内容字符串
        """
        if not os.path.exists(self.memory_file):
            return ""

        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            max_lines = max_lines or Config.MAX_MEMORY_LINES

            # 返回最近的行
            if len(lines) > max_lines:
                return '\n'.join(lines[-max_lines:])
            return content

        except Exception as e:
            print(f"Warning: Failed to load memory: {e}")
            return ""

    def save(self, task: str, result: str) -> None:
        """
        保存任务和结果到记忆文件

        Args:
            task: 任务描述
            result: 任务结果
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n## {timestamp}\n**Task:** {task}\n**Result:** {result}\n"

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.memory_file) or '.', exist_ok=True)

            with open(self.memory_file, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception as e:
            print(f"Warning: Failed to save memory: {e}")

    def clear(self) -> None:
        """清空记忆文件"""
        if os.path.exists(self.memory_file):
            try:
                os.remove(self.memory_file)
            except Exception as e:
                print(f"Warning: Failed to clear memory: {e}")

    def get_stats(self) -> dict:
        """
        获取记忆文件统计信息

        Returns:
            包含文件大小、条目数等信息的字典
        """
        if not os.path.exists(self.memory_file):
            return {"exists": False, "size": 0, "entries": 0}

        try:
            size = os.path.getsize(self.memory_file)
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                content = f.read()
            entries = content.count("## ")
            return {"exists": True, "size": size, "entries": entries}
        except Exception as e:
            return {"exists": True, "error": str(e)}
