"""
任务管理工具 - TodoWrite, TodoList, TaskStatus

提供任务创建、追踪和管理能力
"""

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: TaskStatus
    priority: Priority
    created_at: str
    updated_at: str
    tags: List[str]
    subtasks: List[str]
    parent_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TodoManager:
    """
    Todo Manager - 任务列表管理器

    管理任务，支持：
    - 创建、更新、删除任务
    - 任务状态流转
    - 优先级和标签
    - 子任务管理
    """

    DEFAULT_STORAGE = ".nano_tasks.json"

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or self.DEFAULT_STORAGE
        self._tasks: Dict[str, Task] = {}
        self._load()

    def _load(self) -> None:
        """从文件加载任务"""
        path = Path(self.storage_path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._tasks = {
                    k: Task(**v) for k, v in data.get("tasks", {}).items()
                }
            except (json.JSONDecodeError, TypeError):
                self._tasks = {}

    def _save(self) -> None:
        """保存任务到文件"""
        path = Path(self.storage_path)
        data = {
            "tasks": {k: v.to_dict() for k, v in self._tasks.items()},
            "saved_at": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        tags: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
    ) -> Task:
        """创建新任务"""
        now = datetime.now().isoformat()
        task = Task(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now,
            updated_at=now,
            tags=tags or [],
            subtasks=[],
            parent_id=parent_id,
        )
        self._tasks[task.id] = task

        if parent_id and parent_id in self._tasks:
            self._tasks[parent_id].subtasks.append(task.id)

        self._save()
        return task

    def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[Priority] = None,
    ) -> Optional[Task]:
        """更新任务"""
        if task_id not in self._tasks:
            return None

        task = self._tasks[task_id]
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        task.updated_at = datetime.now().isoformat()

        self._save()
        return task

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]

        if task.parent_id and task.parent_id in self._tasks:
            parent = self._tasks[task.parent_id]
            if task_id in parent.subtasks:
                parent.subtasks.remove(task_id)

        for subtask_id in task.subtasks:
            if subtask_id in self._tasks:
                del self._tasks[subtask_id]

        del self._tasks[task_id]
        self._save()
        return True

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[Priority] = None,
        tag: Optional[str] = None,
    ) -> List[Task]:
        """列出任务"""
        result = list(self._tasks.values())

        if status is not None:
            result = [t for t in result if t.status == status]
        if priority is not None:
            result = [t for t in result if t.priority == priority]
        if tag is not None:
            result = [t for t in result if tag in t.tags]

        return sorted(result, key=lambda t: (t.priority.value, t.created_at))

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        tasks = list(self._tasks.values())
        return {
            "total": len(tasks),
            "by_status": {
                "pending": len([t for t in tasks if t.status == TaskStatus.PENDING]),
                "in_progress": len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS]),
                "completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                "cancelled": len([t for t in tasks if t.status == TaskStatus.CANCELLED]),
                "blocked": len([t for t in tasks if t.status == TaskStatus.BLOCKED]),
            },
            "by_priority": {
                "high": len([t for t in tasks if t.priority == Priority.HIGH]),
                "urgent": len([t for t in tasks if t.priority == Priority.URGENT]),
            },
        }


_todo_manager: Optional[TodoManager] = None


def get_todo_manager() -> TodoManager:
    """获取全局 TodoManager 实例"""
    global _todo_manager
    if _todo_manager is None:
        _todo_manager = TodoManager()
    return _todo_manager


def todo_create(title: str, description: str = "", priority: str = "medium") -> str:
    """
    创建任务

    Args:
        title: 任务标题
        description: 任务描述
        priority: 优先级 (low/medium/high/urgent)

    Returns:
        任务 ID 和信息
    """
    manager = get_todo_manager()
    priority_enum = Priority(priority.lower())
    task = manager.create_task(title, description, priority_enum)

    return json.dumps({
        "success": True,
        "task_id": task.id,
        "message": f"任务已创建: {task.title}",
        "task": task.to_dict(),
    }, ensure_ascii=False)


def todo_update(
    task_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """
    更新任务状态/优先级

    Args:
        task_id: 任务 ID
        status: 新状态 (pending/in_progress/completed/cancelled/blocked)
        priority: 新优先级 (low/medium/high/urgent)

    Returns:
        更新结果
    """
    manager = get_todo_manager()

    status_enum = TaskStatus(status.lower()) if status else None
    priority_enum = Priority(priority.lower()) if priority else None

    task = manager.update_task(task_id, status=status_enum, priority=priority_enum, title=title)

    if task:
        return json.dumps({
            "success": True,
            "task": task.to_dict(),
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": f"任务 {task_id} 不存在",
        }, ensure_ascii=False)


def todo_list(status: Optional[str] = None) -> str:
    """
    列出任务

    Args:
        status: 按状态过滤 (pending/in_progress/completed)

    Returns:
        任务列表
    """
    manager = get_todo_manager()

    status_enum = TaskStatus(status.lower()) if status else None
    tasks = manager.list_tasks(status=status_enum)

    return json.dumps({
        "count": len(tasks),
        "tasks": [t.to_dict() for t in tasks],
        "stats": manager.get_stats(),
    }, ensure_ascii=False, indent=2)


def todo_delete(task_id: str) -> str:
    """删除任务"""
    manager = get_todo_manager()
    success = manager.delete_task(task_id)

    return json.dumps({
        "success": success,
        "task_id": task_id,
    }, ensure_ascii=False)


def todo_stats() -> str:
    """获取任务统计"""
    manager = get_todo_manager()
    return json.dumps(manager.get_stats(), ensure_ascii=False, indent=2)
