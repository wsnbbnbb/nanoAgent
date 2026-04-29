"""Skills module - Original flavor"""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any


SKILLS_DIR = ".agent/skills"


def load_skills(skills_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load skills config
    Original flavor: load all .json files from .skills directory
    """
    skills_path = skills_dir or os.getenv("SKILLS_DIR", SKILLS_DIR)
    if not os.path.exists(skills_path):
        return []

    try:
        skills = []
        for skill_file in Path(skills_path).glob("*.json"):
            with open(skill_file, 'r', encoding='utf-8') as f:
                skills.append(json.load(f))
        return skills
    except Exception:
        return []


def format_skills_prompt(skills: List[Dict[str, Any]]) -> str:
    """Format skills as prompt string"""
    if not skills:
        return ""
    return "\n".join([f"- {s['name']}: {s.get('description', '')}" for s in skills])


def get_skill_by_name(name: str, skills_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get skill by name"""
    skills = load_skills(skills_dir)
    for skill in skills:
        if skill.get("name") == name:
            return skill
    return None
