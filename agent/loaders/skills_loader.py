"""
Skills 系统 - 支持 Markdown 和 JSON 格式的 Skill 定义
"""
import os
import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SkillMeta:
    """Skill 元数据"""
    name: str
    description: str
    path: str
    base_dir: str
    mtime: float
    content: str = ""


@dataclass
class SkillContext:
    """Skill 执行上下文"""
    cwd: str
    project_root: str
    args: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None


@dataclass
class SkillDefinition:
    """Skill 定义（用于 JSON 格式）"""
    name: str
    description: str
    content: str = ""
    tags: List[str] = field(default_factory=list)


class SkillLoader:
    """
    Skill 加载器

    从 .agent/skills 目录加载 Skill 定义。
    支持：
    - Markdown 格式的 Skill 文件（SKILL.md）
    - JSON 格式的 Skill 文件（*.json）
    - frontmatter 元数据解析
    - 自动扫描和缓存
    - Skill 列表格式化
    """

    SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def __init__(self, project_root: str = None, skills_dir: str = ".agent/skills"):
        """
        初始化 Skill 加载器

        Args:
            project_root: 项目根目录
            skills_dir: 技能目录路径
        """
        from ..core import config as config_module
        self._project_root = Path(project_root or config_module.PROJECT_ROOT or os.getcwd()).resolve()
        self._skills_dir = (self._project_root / skills_dir).resolve()
        self._skills: Dict[str, SkillMeta] = {}
        self._json_skills: Dict[str, SkillDefinition] = {}
        self._last_scan_mtime: float = 0.0
        self._last_scan_count: int = 0

    def load(self) -> List[SkillMeta]:
        """加载技能（兼容旧API）"""
        return self.scan()

    def scan(self) -> List[SkillMeta]:
        """扫描 skills 目录并刷新缓存"""
        skills: Dict[str, SkillMeta] = {}
        max_mtime = 0.0
        count = 0

        for path in self._iter_skill_files():
            count += 1
            try:
                stat = path.stat()
                max_mtime = max(max_mtime, stat.st_mtime)
            except OSError:
                continue

            parsed = self._parse_skill_file(path)
            if not parsed:
                continue

            meta = parsed
            if meta.name in skills:
                continue
            skills[meta.name] = meta

        self._skills = skills
        self._last_scan_mtime = max_mtime
        self._last_scan_count = count
        self._load_json_skills()
        return self.list_skills(refresh=False)

    def _load_json_skills(self):
        """加载 JSON 格式的 skills"""
        self._json_skills = {}
        if not self._skills_dir.exists():
            return

        json_dir = self._skills_dir / "json"
        if not json_dir.exists():
            json_dir = self._skills_dir

        for json_file in json_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "name" in data:
                        skill = SkillDefinition(
                            name=data.get("name", ""),
                            description=data.get("description", ""),
                            content=data.get("content", ""),
                            tags=data.get("tags", [])
                        )
                        self._json_skills[skill.name] = skill
            except (json.JSONDecodeError, OSError):
                continue

    def refresh_if_stale(self) -> List[SkillMeta]:
        """如果 skill 文件有变化则刷新缓存"""
        if not self._skills:
            return self.scan()

        current_max_mtime, current_count = self._get_skills_state()
        if current_max_mtime != self._last_scan_mtime or current_count != self._last_scan_count:
            return self.scan()
        return self.list_skills(refresh=False)

    def list_skills(self, refresh: bool = False) -> List[SkillMeta]:
        """列出所有可用的 skills"""
        if refresh:
            self.refresh_if_stale()
        return sorted(self._skills.values(), key=lambda s: s.name)

    def list_json_skills(self) -> List[SkillDefinition]:
        """列出所有 JSON 格式的 skills"""
        return sorted(self._json_skills.values(), key=lambda s: s.name)

    def get_skill(self, name: str, refresh: bool = False) -> Optional[SkillMeta]:
        """获取指定名称的 skill"""
        if refresh:
            self.refresh_if_stale()
        return self._skills.get(name)

    def get_skill_content(self, name: str, args: Optional[str] = None) -> Optional[str]:
        """获取 skill 的完整内容（带变量替换）"""
        meta = self.get_skill(name)
        if not meta:
            json_skill = self._json_skills.get(name)
            if json_skill:
                content = json_skill.content
                if args:
                    content = self._apply_args(content, args)
                return content
            return None

        content = meta.content

        if args:
            content = self._apply_args(content, args)

        return content

    def get_json_skill(self, name: str) -> Optional[SkillDefinition]:
        """获取 JSON 格式的 skill"""
        return self._json_skills.get(name)

    def format_skills_for_prompt(self, char_budget: int = 2000) -> str:
        """格式化 skill 列表用于 prompt"""
        skills = self.list_skills(refresh=False)
        if not skills:
            return "(none)"

        lines: List[str] = []
        used = 0

        for skill in skills:
            line = f"- {skill.name}: {skill.description}"
            line_len = len(line) + 1
            if used + line_len > char_budget and lines:
                break
            lines.append(line)
            used += line_len

        if not lines:
            return "(none)"

        return "\n".join(lines)

    def _iter_skill_files(self) -> List[Path]:
        """遍历所有 skill 文件"""
        if not self._skills_dir.exists():
            return []
        return sorted(self._skills_dir.rglob("SKILL.md"))

    def _get_skills_state(self) -> Tuple[float, int]:
        """获取当前 skills 目录状态"""
        max_mtime = 0.0
        count = 0
        for path in self._iter_skill_files():
            count += 1
            try:
                stat = path.stat()
                max_mtime = max(max_mtime, stat.st_mtime)
            except OSError:
                continue
        return max_mtime, count

    def _parse_skill_file(self, path: Path) -> Optional[SkillMeta]:
        """解析 skill 文件"""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None

        parsed = _parse_frontmatter(content)
        if not parsed:
            return None

        frontmatter, body = parsed
        name = (frontmatter.get("name") or "").strip()
        description = (frontmatter.get("description") or "").strip()

        if not name or not description:
            return None

        if not self.SKILL_NAME_PATTERN.match(name):
            return None

        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0

        try:
            base_dir = str(path.parent.relative_to(self._project_root)) or "."
        except ValueError:
            base_dir = str(path.parent)

        return SkillMeta(
            name=name,
            description=description,
            path=str(path),
            base_dir=base_dir,
            mtime=mtime,
            content=body.strip(),
        )

    def _apply_args(self, content: str, args: str) -> str:
        """应用参数到 skill 内容"""
        content = content.replace("{{args}}", args)
        content = content.replace("{{ARGS}}", args)

        args_parts = args.split()
        for i, part in enumerate(args_parts):
            content = content.replace(f"{{arg[{i}]}}", part)

        return content


def _parse_frontmatter(content: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """解析 Markdown frontmatter

    格式：
    ---
    name: my-skill
    description: This is my skill
    ---
    """
    lines = content.split("\n")

    if len(lines) < 3 or lines[0].strip() != "---":
        return None

    frontmatter_lines = []
    body_lines = []
    in_frontmatter = True

    for line in lines[1:]:
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
            else:
                frontmatter_lines.append(line)
        else:
            body_lines.append(line)

    frontmatter = {}
    for line in frontmatter_lines:
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    return frontmatter, "\n".join(body_lines)


def create_skill_template(name: str, description: str, content: str = "") -> str:
    """创建 skill 文件模板"""
    template = f"""---
name: {name}
description: {description}
---

{content or "Describe what this skill does..."}

## Usage

Explain how to use this skill...

## Examples

Provide usage examples...
"""
    return template


def load_skills(skills_dir: str = None) -> List[Dict[str, Any]]:
    """
    便捷函数：加载所有技能（JSON 格式）

    Args:
        skills_dir: 技能目录路径

    Returns:
        技能定义列表
    """
    loader = SkillLoader(skills_dir=skills_dir)
    loader.scan()
    json_skills = loader.list_json_skills()
    return [
        {
            "name": s.name,
            "description": s.description,
            "content": s.content,
            "tags": s.tags
        }
        for s in json_skills
    ]