"""命令执行工具 - Shell/Bash 命令执行

遵循《通用工具响应协议》，返回标准化 JSON 结构。
支持超时、输出截断、安全白名单。
"""
import os
import subprocess
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


from .filesystem import PROJECT_ROOT




# 危险命令黑名单（不可执行）
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "> /dev/sda",
    "dd if=/dev/zero",
    "mkfs.",
    ":(){ :|:& };:",  # Fork bomb
    "format C:",
    "del /f /s /q",
    "rmdir /s /q C:",
]

# 需要警告的高危命令
CAUTION_PATTERNS = [
    "rm ",
    "rmdir",
    "del",
    "format",
    "mkfs",
    "fdisk",
    "parted",
]


def _check_dangerous(command: str) -> Optional[str]:
    """检查命令是否在危险列表中"""
    lower = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in lower:
            return pattern
    return None


def run_bash(
    command: str,
    timeout: int = None,
    cwd: str = None,
    context: Dict[str, Any] = None
) -> str:
    """
    执行 shell 命令
    
    Args:
        command: 要执行的 shell 命令
        timeout: 超时秒数（默认 120）
        cwd: 工作目录
        context: 调用上下文
        
    Returns:
        JSON 格式的 ToolResponse
    """
    start_time = datetime.now()
    
    if not command:
        return error_response(
            ErrorCode.MISSING_PARAM,
            "参数 'command' 是必需的",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    # 安全检查
    dangerous_pattern = _check_dangerous(command)
    if dangerous_pattern:
        return error_response(
            ErrorCode.ACCESS_DENIED,
            f"命令包含危险操作: {dangerous_pattern}",
            context={"cwd": context.get("cwd", ".") if context else ".", "command": command[:100]}
        )
    
    # 获取超时
    command_timeout = timeout or 120
    if command_timeout > 600:
        command_timeout = 600  # 最大 10 分钟
    
    # 获取工作目录
    work_dir = cwd or (context.get("cwd") if context else None) or str(PROJECT_ROOT)
    
    try:
        # 执行命令
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=command_timeout,
            cwd=work_dir
        )
        
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 组合输出
        output = result.stdout or ""
        if result.stderr:
            if output:
                output += "\n"
            output += f"[STDERR]\n{result.stderr}"
        
        return_code = result.returncode
        
        # 检查是否需要截断
        output_manager = _get_output_manager()
        
        if output_manager.should_truncate(output):
            # 需要截断
            from .output_manager import TruncationInfo
            
            lines = output.split('\n')
            truncation_info = TruncationInfo(
                original_lines=len(lines),
                kept_lines=2000,
                original_size=len(output.encode('utf-8')),
                kept_size=50000,
                truncated=True
            )
            
            # 保存完整输出
            full_path = output_manager.save_output(output, "bash")
            preview = output[:500] if len(output) > 500 else output
            
            data = {
                "command": command,
                "returncode": return_code,
                "output_preview": preview,
                "full_output_path": full_path,
                "truncated": True
            }
            
            return partial_response(
                data=data,
                text=f"命令执行完成（返回码 {return_code}）\n" +
                     f"输出已截断保存到: {full_path}\n" +
                     f"预览:\n{preview[:200]}...",
                reason="output_truncated",
                context={
                    "cwd": context.get("cwd", ".") if context else ".",
                    "params_input": {"command": command, "timeout": command_timeout}
                },
                stats={
                    "time_ms": elapsed_ms,
                    "returncode": return_code,
                    "output_lines": len(lines),
                    "output_bytes": len(output.encode('utf-8'))
                }
            )
        
        # 正常输出
        data = {
            "command": command,
            "returncode": return_code,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "output": output if output else "（无输出）"
        }
        
        if return_code != 0:
            # 非零返回码 - 部分成功
            return partial_response(
                data=data,
                text=f"命令执行完成但返回非零状态码: {return_code}\n{output[:500]}",
                reason="non_zero_exit",
                context={
                    "cwd": context.get("cwd", ".") if context else ".",
                    "params_input": {"command": command}
                },
                stats={"time_ms": elapsed_ms, "returncode": return_code}
            )
        
        # 完全成功
        return success_response(
            data=data,
            text=output if output else "命令执行成功（无输出）",
            context={
                "cwd": context.get("cwd", ".") if context else ".",
                "params_input": {"command": command, "timeout": command_timeout}
            },
            stats={
                "time_ms": elapsed_ms,
                "returncode": return_code,
                "output_lines": output.count('\n') + (1 if output else 0),
                "stdout_lines": (result.stdout or "").count('\n') + (1 if result.stdout else 0),
                "stderr_lines": (result.stderr or "").count('\n') + (1 if result.stderr else 0)
            }
        )
        
    except subprocess.TimeoutExpired:
        return error_response(
            ErrorCode.TIMEOUT,
            f"命令执行超时（{command_timeout}秒）",
            context={"cwd": context.get("cwd", ".") if context else ".", "command": command}
        )
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"命令执行失败: {str(e)}",
            context={"cwd": context.get("cwd", ".") if context else ".", "command": command}
        )


def run_bash_safe(
    command: str,
    context: Dict[str, Any] = None
) -> str:
    """
    安全模式执行 bash - 只允许白名单命令
    
    Args:
        command: 命令
        context: 调用上下文
        
    Returns:
        JSON 格式的 ToolResponse
    """
    # 允许的命令白名单
    ALLOWED_COMMANDS = [
        "ls", "dir", "cat", "type",
        "grep", "find", "echo", "pwd",
        "git --version", "python --version", "node --version",
        "head", "tail", "wc",
    ]
    
    lower_cmd = command.lower().strip()
    
    # 检查是否在白名单
    allowed = any(lower_cmd.startswith(cmd) for cmd in ALLOWED_COMMANDS)
    
    if not allowed:
        return error_response(
            ErrorCode.ACCESS_DENIED,
            f"命令不在安全白名单中: {command}\n允许的命令: {', '.join(ALLOWED_COMMANDS)}",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    return run_bash(command, timeout=30, context=context)
