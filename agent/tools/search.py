"""
搜索工具 - 在文件内容中搜索
"""
import subprocess
from ..core.config import Config


def grep_search(pattern: str, path: str = ".") -> str:
    """
    递归搜索文件内容

    Args:
        pattern: 搜索的正则表达式模式
        path: 搜索路径，默认为当前目录

    Returns:
        匹配结果
    """
    try:
        # 使用 grep 命令进行递归搜索
        result = subprocess.run(
            f"grep -r '{pattern}' {path}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=Config.COMMAND_TIMEOUT
        )

        if result.stdout:
            return result.stdout
        elif result.stderr:
            return f"Grep error: {result.stderr}"
        else:
            return "No matches found"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {Config.COMMAND_TIMEOUT} seconds"
    except Exception as e:
        return f"Error: {str(e)}"
