""" 文件系统工具 - 读写、编辑、查找文件 遵循《通用工具响应协议》，返回标准化JSON结构 """
import os
import glob as glob_module
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()



def _resolve_path(path: str) -> str:
    """解析路径：相对路径基于项目根目录，绝对路径保持不变"""
    p = Path(path)
    if p.is_absolute():
        return path
    return str(PROJECT_ROOT / p)


def _validate_path(path: str, must_exist: bool = False) -> tuple[Optional[str], Optional[str]]:
    """
    验证路径
    
    Returns:
        (resolved_path, error_message)
    """
    try:
        resolved = _resolve_path(path)
        abs_path = Path(resolved).resolve()
        
        # 安全检查：确保路径在项目根目录内
        try:
            abs_path.relative_to(PROJECT_ROOT)
        except ValueError:
            return None, f"路径超出项目根目录: {path}"
            
        if must_exist and not abs_path.exists():
            return None, f"文件不存在: {path}"
            
        return str(resolved), None
        
    except Exception as e:
        return None, f"路径解析失败: {str(e)}"


def read_file(
    path: str,
    offset: int = None,
    limit: int = None,
    context: Dict[str, Any] = None
) -> str:
    """
    读取文件内容，支持行号显示和分页
    
    Args:
        path: 文件路径（必填）
        offset: 起始行偏移量（从1开始，可选）
        limit: 最大读取行数（可选，默认500，最大2000）
        context: 调用上下文（如 cwd）
        
    Returns:
        JSON 格式的 ToolResponse
    """
    start_time = datetime.now()
    
    # 参数校验
    if not path:
        return error_response(
            ErrorCode.MISSING_PARAM,
            "参数 'path' 是必需的",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
        
    # 校验 offset
    if offset is not None and (not isinstance(offset, int) or offset < 1):
        return error_response(
            ErrorCode.INVALID_PARAM,
            "offset 必须是正整数（>=1）",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
        
    # 校验 limit
    if limit is not None:
        if not isinstance(limit, int) or limit < 1:
            return error_response(
                ErrorCode.INVALID_PARAM,
                "limit 必须是正整数",
                context={"cwd": context.get("cwd", ".") if context else "."}
            )
        if limit > 2000:
            limit = 2000  # 硬上限
    else:
        limit = 500  # 默认值
    
    # 路径验证
    resolved_path, error = _validate_path(path, must_exist=True)
    if error:
        return error_response(
            ErrorCode.NOT_FOUND if "不存在" in error else ErrorCode.ACCESS_DENIED,
            error,
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    try:
        # 读取文件
        with open(resolved_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 处理 offset
        start_idx = 0
        if offset is not None:
            start_idx = max(0, offset - 1)  # 转换为 0-based
        
        # 处理 limit
        end_idx = min(start_idx + limit, len(lines))
        
        # 提取需要的行
        selected_lines = lines[start_idx:end_idx]
        
        # 添加行号（显示实际行号）
        numbered = [f"{start_idx + i + 1:4d} {line.rstrip()}" for i, line in enumerate(selected_lines)]
        content = '\n'.join(numbered)
        
        # 检查是否需要截断
        output_manager = _get_output_manager()
        was_truncated = ((end_idx - start_idx) < total_lines) or output_manager.should_truncate(content)
        
        # 构建数据
        data = {
            "content": content,
            "total_lines": total_lines,
            "start_line": start_idx + 1,
            "end_line": end_idx,
            "lines_read": end_idx - start_idx,
            "path": path,
            "path_resolved": resolved_path
        }
        
        # 添加截断标记（如果发生）
        if was_truncated:
            data["truncated"] = True
            data["full_output_path"] = None  # 只有超长才落盘
            
        # 计算耗时
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 构建文本摘要
        text = f"已读取 {data['lines_read']} 行（第 {data['start_line']}-{data['end_line']} 行，共 {total_lines} 行）"
        if was_truncated:
            text += f"\n⚠️ 输出截断，仅显示前 {limit} 行。使用 offset={end_idx+1} 读取更多内容。"
        text += f"\n文件: {path}"
        
        # 构建响应
        if was_truncated:
            return partial_response(
                data=data,
                text=text,
                reason="output_truncated",
                context={
                    "cwd": context.get("cwd", ".") if context else ".",
                    "params_input": {"path": path, "offset": offset, "limit": limit}
                },
                stats={
                    "time_ms": elapsed_ms,
                    "total_lines": total_lines,
                    "lines_read": data['lines_read'],
                    "bytes_read": len(content.encode('utf-8'))
                }
            )
        else:
            return success_response(
                data=data,
                text=text,
                context={
                    "cwd": context.get("cwd", ".") if context else ".",
                    "params_input": {"path": path, "offset": offset, "limit": limit},
                    "path_resolved": resolved_path
                },
                stats={
                    "time_ms": elapsed_ms,
                    "total_lines": total_lines,
                    "lines_read": data['lines_read'],
                    "bytes_read": len(content.encode('utf-8'))
                }
            )
            
    except UnicodeDecodeError:
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"文件编码错误（非 UTF-8）: {path}",
            context={"cwd": context.get("cwd", ".") if context else ".", "path": path}
        )
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"读取文件失败: {str(e)}",
            context={"cwd": context.get("cwd", ".") if context else ".", "path": path}
        )


def write_file(
    path: str,
    content: str,
    context: Dict[str, Any] = None
) -> str:
    """
    写入内容到文件（覆盖写入）
    
    Args:
        path: 文件路径
        content: 要写入的内容
        context: 调用上下文
        
    Returns:
        JSON 格式的 ToolResponse
    """
    start_time = datetime.now()
    
    if not path:
        return error_response(
            ErrorCode.MISSING_PARAM,
            "参数 'path' 是必需的",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
        
    if content is None:
        return error_response(
            ErrorCode.MISSING_PARAM,
            "参数 'content' 是必需的",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    # 路径验证
    resolved_path, error = _validate_path(path, must_exist=False)
    if error:
        return error_response(
            ErrorCode.ACCESS_DENIED,
            error,
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    try:
        # 确保目录存在
        dir_path = Path(resolved_path).parent
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # 检查文件是否已存在
        file_existed = Path(resolved_path).exists()
        
        # 写入文件
        with open(resolved_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        data = {
            "path": path,
            "path_resolved": resolved_path,
            "bytes_written": len(content.encode('utf-8')),
            "lines_written": content.count('\n') + (1 if content and not content.endswith('\n') else 0),
            "existed": file_existed
        }
        
        return success_response(
            data=data,
            text=f"成功写入 {data['lines_written']} 行到 {path}" + ("（覆盖）" if file_existed else ""),
            context={
                "cwd": context.get("cwd", ".") if context else ".",
                "params_input": {"path": path}
            },
            stats={
                "time_ms": elapsed_ms,
                "bytes_written": data["bytes_written"],
                "lines_written": data["lines_written"]
            }
        )
        
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"写入文件失败: {str(e)}",
            context={"cwd": context.get("cwd", ".") if context else ".", "path": path}
        )


def edit_file(
    path: str,
    old_string: str,
    new_string: str,
    context: Dict[str, Any] = None
) -> str:
    """
    在文件中进行字符串替换（old_string 必须唯一出现）
    
    Args:
        path: 文件路径
        old_string: 要替换的字符串
        new_string: 替换后的字符串
        context: 调用上下文
        
    Returns:
        JSON 格式的 ToolResponse
    """
    start_time = datetime.now()
    
    # 参数校验
    if not path or not old_string:
        missing = "'path'" if not path else "'old_string'"
        return error_response(
            ErrorCode.MISSING_PARAM,
            f"参数 {missing} 是必需的",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    # 路径验证
    resolved_path, error = _validate_path(path, must_exist=True)
    if error:
        return error_response(
            ErrorCode.NOT_FOUND if "不存在" in error else ErrorCode.ACCESS_DENIED,
            error,
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    try:
        with open(resolved_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查 old_string 出现次数
        count = content.count(old_string)
        if count == 0:
            # 返回匹配失败，但提供相似内容建议
            similar = _find_similar_snippet(content, old_string)
            data = {
                "path": path,
                "applied": False,
                "reason": "old_string 不存在",
                "similar_suggestion": similar
            }
            return error_response(
                ErrorCode.NOT_FOUND,
                f"old_string 未在文件中找到。{('相似内容: ' + similar if similar else '')}",
                data=data,
                context={"cwd": context.get("cwd", ".") if context else ".", "path": path}
            )
        elif count > 1:
            data = {
                "path": path,
                "applied": False,
                "reason": f"old_string 出现 {count} 次（必须唯一）",
                "occurrences": count
            }
            return error_response(
                ErrorCode.INVALID_PARAM,
                f"old_string 出现 {count} 次，必须唯一出现",
                data=data,
                context={"cwd": context.get("cwd", ".") if context else ".", "path": path}
            )
        
        # 执行替换
        new_content = content.replace(old_string, new_string)
        
        with open(resolved_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 计算变化行数
        old_lines = old_string.count('\n') + 1
        new_lines = new_string.count('\n') + 1
        
        data = {
            "path": path,
            "path_resolved": resolved_path,
            "applied": True,
            "old_string_preview": old_string[:100] if len(old_string) > 100 else old_string,
            "new_string_preview": new_string[:100] if len(new_string) > 100 else new_string,
            "lines_changed": {
                "before": old_lines,
                "after": new_lines,
                "net": new_lines - old_lines
            }
        }
        
        return success_response(
            data=data,
            text=f"成功修改 {path}\n" +
                 f"第 {content.find(old_string)} 字符处: {data['old_string_preview']!r} → {data['new_string_preview']!r}",
            context={
                "cwd": context.get("cwd", ".") if context else ".",
                "params_input": {"path": path, "old_string": old_string[:100], "new_string": new_string[:100]},
                "path_resolved": resolved_path
            },
            stats={
                "time_ms": elapsed_ms,
                "old_lines": old_lines,
                "new_lines": new_lines
            }
        )
        
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"编辑文件失败: {str(e)}",
            context={"cwd": context.get("cwd", ".") if context else ".", "path": path}
        )


def _find_similar_snippet(content: str, target: str, window: int = 200) -> Optional[str]:
    """在内容中查找与目标字符串相似的部分"""
    if len(target) < 10:
        return None
    
    # 简单启发式：找包含 target 前 20 个字符的段落
    prefix = target[:min(20, len(target) // 2)]
    idx = content.find(prefix)
    if idx >= 0:
        start = max(0, idx - 50)
        end = min(len(content), idx + window)
        snippet = content[start:end].replace('\n', ' ')
        if len(snippet) > 100:
            snippet = snippet[:97] + "..."
        return snippet
    return None


def glob_files(
    pattern: str,
    path: str = None,
    context: Dict[str, Any] = None
) -> str:
    """
    按模式查找文件
    
    Args:
        pattern: 文件匹配模式，如 '*.py'
        path: 搜索路径（可选）
        context: 调用上下文
        
    Returns:
        JSON 格式的 ToolResponse
    """
    start_time = datetime.now()
    
    if not pattern:
        return error_response(
            ErrorCode.MISSING_PARAM,
            "参数 'pattern' 是必需的",
            context={"cwd": context.get("cwd", ".") if context else "."}
        )
    
    search_path = path or "."
    try:
        # 构建完整 pattern
        if path and not pattern.startswith("/"):
            full_pattern = _resolve_path(f"{path}/{pattern}")
        else:
            full_pattern = _resolve_path(pattern)
        
        # 搜索文件
        files = glob_module.glob(full_pattern, recursive=True)
        
        # 按修改时间排序（最近优先）
        files.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        
        # 转换为相对路径
        relative_files = []
        for f in files:
            abs_path = Path(f).resolve()
            try:
                rel_path = abs_path.relative_to(PROJECT_ROOT)
                relative_files.append(str(rel_path))
            except ValueError:
                # 文件在项目根目录外，跳过
                pass
        
        # 检查是否需要截断
        total_matches = len(relative_files)
        was_truncated = False
        MAX_RESULTS = 500
        
        if len(relative_files) > MAX_RESULTS:
            was_truncated = True
            displayed_files = relative_files[:MAX_RESULTS]
        else:
            displayed_files = relative_files
        
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 构建条目列表
        entries = [{"path": f, "type": "file" if Path(f).is_file() else "dir"} for f in displayed_files]
        
        data = {
            "pattern": pattern,
            "path": search_path,
            "entries": entries,
            "total_matches": total_matches,
            "showing": len(displayed_files)
        }
        
        if was_truncated:
            data["truncated"] = True
            text = f"找到 {total_matches} 个匹配项，显示前 {MAX_RESULTS} 个（按修改时间排序）"
            return partial_response(
                data=data,
                text=text,
                reason="results_truncated",
                context={
                    "cwd": context.get("cwd", ".") if context else ".",
                    "params_input": {"pattern": pattern, "path": path}
                },
                stats={
                    "time_ms": elapsed_ms,
                    "total_matches": total_matches,
                    "showing": len(displayed_files)
                }
            )
        else:
            text = f"找到 {total_matches} 个匹配项"
            if total_matches == 0:
                text += "\n提示: 尝试使用不同的模式，如 '**/*.py' 进行递归搜索"
            
            return success_response(
                data=data,
                text=text,
                context={
                    "cwd": context.get("cwd", ".") if context else ".",
                    "params_input": {"pattern": pattern, "path": path}
                },
                stats={
                    "time_ms": elapsed_ms,
                    "total_matches": total_matches,
                    "showing": len(displayed_files)
                }
            )
            
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"搜索失败: {str(e)}",
            context={"cwd": context.get("cwd", ".") if context else "."
, "pattern": pattern}
        )
