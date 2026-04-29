"""Tool output truncation"""
import os
import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


MAX_LINES = 2000
MAX_BYTES = 51200
OUTPUT_DIR = "tool-output"
RETENTION_DAYS = 7


def truncate_observation(tool_name: str, raw_result: str, project_root: Optional[str] = None) -> str:
    """
    Truncate tool output and save to disk
    Improved strategy from MyCodeAgent
    """
    lines = raw_result.split('\n')
    bytes_size = len(raw_result.encode('utf-8'))

    needs_truncation = len(lines) > MAX_LINES or bytes_size > MAX_BYTES

    if needs_truncation:
        output_dir = Path(project_root or ".") / OUTPUT_DIR
        output_dir.mkdir(exist_ok=True)

        timestamp = int(time.time() * 1000)
        filename = f"tool_{timestamp}_{tool_name}.json"
        filepath = output_dir / filename

        full_result = {
            "tool": tool_name,
            "timestamp": datetime.now().isoformat(),
            "truncated": True,
            "original_lines": len(lines),
            "original_bytes": bytes_size,
            "result": raw_result
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(full_result, f, ensure_ascii=False, indent=2)
            logger.info(f"Tool output saved to {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save tool output: {e}")

        truncated_lines = lines[:MAX_LINES]
        truncated_bytes = '\n'.join(truncated_lines)[:MAX_BYTES]

        return json.dumps({
            "truncated": True,
            "file": str(filepath),
            "summary": f"(Output truncated: {len(lines)} lines, {bytes_size} bytes -> saved to {filepath})",
            "preview": truncated_bytes[-1000:] if len(truncated_bytes) > 1000 else truncated_bytes
        }, ensure_ascii=False)

    return raw_result


def cleanup_old_outputs(project_root: Optional[str] = None, retention_days: int = RETENTION_DAYS) -> int:
    """Clean up old tool output files"""
    output_dir = Path(project_root or ".") / OUTPUT_DIR
    if not output_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0

    for file in output_dir.glob("tool_*.json"):
        try:
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            if mtime < cutoff:
                file.unlink()
                removed += 1
        except Exception:
            pass

    return removed
