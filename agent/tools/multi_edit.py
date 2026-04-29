"""
批量编辑工具 - MultiEdit

支持一次调用执行多个编辑操作
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def _resolve_path(path: str) -> str:
    """解析路径：相对路径基于项目根目录，绝对路径保持不变"""
    p = Path(path)
    if p.is_absolute():
        return path
    return str(PROJECT_ROOT / p)


@dataclass
class EditOperation:
    """单个编辑操作"""
    path: str
    old_string: str
    new_string: str
    index: int


@dataclass
class EditResult:
    """编辑结果"""
    path: str
    success: bool
    applied: bool
    message: str
    new_content: Optional[str] = None


def multi_edit(operations: List[Dict[str, Any]]) -> str:
    """
    批量编辑多个文件

    Args:
        operations: 编辑操作列表，每项包含:
            - path: 文件路径
            - old_string: 要替换的字符串
            - new_string: 新字符串
            - index: 操作序号（用于排序）

    Returns:
        JSON 格式的编辑结果
    """
    if not operations:
        return json.dumps({
            "success": False,
            "error": "没有提供编辑操作",
        }, ensure_ascii=False)

    sorted_ops = sorted(operations, key=lambda x: x.get("index", 0))

    results: List[EditResult] = []
    file_contents: Dict[str, str] = {}

    for i, op in enumerate(sorted_ops):
        path = op.get("path", "")
        old_string = op.get("old_string", "")
        new_string = op.get("new_string", "")

        if not path:
            results.append(EditResult(
                path="",
                success=False,
                applied=False,
                message="文件路径为空",
            ))
            continue

        try:
            resolved_path = _resolve_path(path)
            file_path = Path(resolved_path)
            if not file_path.exists():
                results.append(EditResult(
                    path=path,
                    success=False,
                    applied=False,
                    message=f"文件不存在: {resolved_path}",
                ))
                continue

            if path not in file_contents:
                file_contents[path] = file_path.read_text(encoding="utf-8")

            content = file_contents[path]

            if old_string not in content:
                results.append(EditResult(
                    path=path,
                    success=False,
                    applied=False,
                    message=f"old_string 在文件中未找到（精确匹配）",
                ))
                continue

            new_content = content.replace(old_string, new_string, 1)
            file_contents[path] = new_content

            results.append(EditResult(
                path=path,
                success=True,
                applied=True,
                message=f"编辑 {i + 1} 成功",
            ))

        except Exception as e:
            results.append(EditResult(
                path=path,
                success=False,
                applied=False,
                message=f"编辑失败: {str(e)}",
            ))

    applied_count = sum(1 for r in results if r.applied)
    failed_count = len(results) - applied_count

    for path, content in file_contents.items():
        try:
            resolved = _resolve_path(path)
            Path(resolved).write_text(content, encoding="utf-8")
        except Exception as e:
            for result in results:
                if result.path == path:
                    result.message += f" (保存失败: {str(e)})"

    return json.dumps({
        "success": failed_count == 0,
        "total": len(operations),
        "applied": applied_count,
        "failed": failed_count,
        "results": [
            {
                "path": r.path,
                "success": r.success,
                "applied": r.applied,
                "message": r.message,
            }
            for r in results
        ],
    }, ensure_ascii=False, indent=2)


def apply_edits(edits: List[Dict[str, Any]]) -> str:
    """
    简化的批量编辑接口

    Args:
        edits: [{"path": "file.py", "old": "...", "new": "..."}, ...]

    Returns:
        简要结果
    """
    operations = [
        {
            "path": e.get("path", ""),
            "old_string": e.get("old", ""),
            "new_string": e.get("new", ""),
            "index": i,
        }
        for i, e in enumerate(edits)
    ]

    return multi_edit(operations)
