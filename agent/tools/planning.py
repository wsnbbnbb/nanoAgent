"""
任务规划工具 - 将复杂任务拆解为多个步骤
"""
import json
from openai import OpenAI
from ..core.config import Config, AgentState


def create_plan(task: str, client: OpenAI = None) -> str:
    """
    使用 LLM 将复杂任务拆解为多个小步骤

    Args:
        task: 需要拆解的复杂任务
        client: OpenAI 客户端实例

    Returns:
        包含步骤列表的 JSON 字符串，或错误消息
    """
    if AgentState.plan_mode:
        return "Error: Cannot plan within a plan"

    if client is None:
        client = OpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )

    try:
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个任务规划助手。将用户的任务拆解为3-5个具体的执行步骤。"
                            "每个步骤应该是明确可操作的。返回严格的JSON格式："
                            '{"steps": ["步骤1", "步骤2", "步骤3"]}'
                },
                {"role": "user", "content": f"请规划任务：{task}"}
            ],
            response_format={"type": "json_object"}
        )

        plan_data = json.loads(response.choices[0].message.content)
        steps = plan_data.get("steps", [task])

        # 存储到全局状态
        AgentState.current_plan = steps
        AgentState.plan_mode = True

        return json.dumps(plan_data, ensure_ascii=False)

    except json.JSONDecodeError:
        return 'Error: Invalid JSON response from model'
    except Exception as e:
        return f"Error: Failed to create plan - {str(e)}"
