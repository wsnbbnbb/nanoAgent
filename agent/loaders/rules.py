"""
规则加载器 - 从 .agent/rules 目录加载规则文件
"""
import os
from pathlib import Path
from ..core.config import Config


class RuleLoader:
    """规则加载器，负责加载 Markdown 格式的规则文件"""

    def __init__(self, rules_dir: str = None):
        """
        初始化规则加载器

        Args:
            rules_dir: 规则目录路径，默认使用 Config.RULES_DIR
        """
        self.rules_dir = rules_dir or Config.RULES_DIR

    def load(self) -> str:
        """
        加载所有规则文件

        Returns:
            拼接后的规则内容
        """
        if not os.path.exists(self.rules_dir):
            return ""

        rules = []
        try:
            rules_path = Path(self.rules_dir)
            if not rules_path.exists():
                return ""

            for rule_file in rules_path.glob("*.md"):
                try:
                    with open(rule_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        rules.append(f"# {rule_file.stem}\n{content}")
                except Exception as e:
                    print(f"Warning: Failed to load rule {rule_file}: {e}")

            return "\n\n".join(rules) if rules else ""

        except Exception as e:
            print(f"Warning: Failed to load rules: {e}")
            return ""

    def list_rules(self) -> list:
        """
        列出所有可用的规则文件

        Returns:
            规则文件名列表
        """
        if not os.path.exists(self.rules_dir):
            return []

        try:
            rules_path = Path(self.rules_dir)
            return [f.stem for f in rules_path.glob("*.md")]
        except Exception:
            return []


def load_rules(rules_dir: str = None) -> str:
    """
    便捷函数：加载所有规则

    Args:
        rules_dir: 规则目录路径

    Returns:
        拼接后的规则内容
    """
    loader = RuleLoader(rules_dir)
    return loader.load()
