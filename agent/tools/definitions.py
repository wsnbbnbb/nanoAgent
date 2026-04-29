"""
工具定义 - OpenAI Function Calling 格式
"""

from .todo import todo_create, todo_update, todo_list, todo_delete, todo_stats
from .multi_edit import multi_edit, apply_edits
from .interaction import ask_user, confirm


# 基础工具定义列表
BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "读取文件内容，支持行号显示、偏移量和限制行数",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径（相对于当前工作目录的相对路径）"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "起始行偏移量（从0开始）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大读取行数"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "写入内容到文件（覆盖写入）。路径应相对于当前工作目录，使用相对路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径（相对于当前工作目录的相对路径，或相对于项目根目录的路径）"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文件内容"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "在文件中进行字符串替换（old_string 必须唯一出现）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径（相对于当前工作目录的相对路径）"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "要替换的字符串（必须唯一）"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "替换后的新字符串"
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "按模式查找文件（支持递归通配符），结果按修改时间排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "文件匹配模式，如 '*.py' 或 'src/**/*.js'"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "递归搜索文件内容（使用 grep 命令）",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "搜索的正则表达式模式"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索路径，默认为当前目录",
                        "default": "."
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "执行 shell 命令，返回标准输出和错误输出",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plan",
            "description": "将复杂任务拆解为多个步骤并依次执行（仅在非 plan 模式中使用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "需要拆解执行的复杂任务"
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "todo_create",
            "description": "创建新任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "任务标题"
                    },
                    "description": {
                        "type": "string",
                        "description": "任务描述",
                        "default": ""
                    },
                    "priority": {
                        "type": "string",
                        "description": "优先级 (low/medium/high/urgent)",
                        "default": "medium"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "todo_list",
            "description": "列出所有任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "按状态过滤 (pending/in_progress/completed)",
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "todo_update",
            "description": "更新任务状态或优先级",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "任务 ID"
                    },
                    "status": {
                        "type": "string",
                        "description": "新状态 (pending/in_progress/completed/cancelled/blocked)"
                    },
                    "priority": {
                        "type": "string",
                        "description": "新优先级 (low/medium/high/urgent)"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "multi_edit",
            "description": "批量编辑多个文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "description": "编辑操作列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "old_string": {"type": "string"},
                                "new_string": {"type": "string"},
                                "index": {"type": "integer"}
                            }
                        }
                    }
                },
                "required": ["operations"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "向用户提问获取更多信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "问题内容"
                    },
                    "question_id": {
                        "type": "string",
                        "description": "问题 ID"
                    },
                    "options": {
                        "type": "array",
                        "description": "选项列表",
                        "items": {"type": "string"}
                    },
                    "default": {
                        "type": "string",
                        "description": "默认答案"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm",
            "description": "请求用户确认操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作描述"
                    },
                    "reason": {
                        "type": "string",
                        "description": "操作原因",
                        "default": ""
                    }
                },
                "required": ["action"]
            }
        }
    }
]
