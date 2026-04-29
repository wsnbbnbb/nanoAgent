"""Rules module - Original flavor"""
import os
from pathlib import Path
from typing import Optional


RULES_DIR = ".agent/rules"


def load_rules(rules_dir: Optional[str] = None) -> str:
    """
    Load rules files

    Original flavor: load all .md files from .rules directory
    """
    rules_path = rules_dir or os.getenv("RULES_DIR", RULES_DIR)
    if not os.path.exists(rules_path):
        return ""

    try:
        rules = []
        for rule_file in Path(rules_path).glob("*.md"):
            with open(rule_file, 'r', encoding='utf-8') as f:
                rules.append(f"# {rule_file.stem}\n{f.read()}")
        return "\n\n".join(rules) if rules else ""
    except Exception:
        return ""


def get_rules_count(rules_dir: Optional[str] = None) -> int:
    """Get rules file count"""
    rules_path = rules_dir or os.getenv("RULES_DIR", RULES_DIR)
    if not os.path.exists(rules_path):
        return 0
    return len(list(Path(rules_path).glob("*.md")))
