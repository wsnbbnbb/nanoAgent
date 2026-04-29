"""LLM Client - Multi-provider support"""
import os
import time
import logging
from typing import Optional, Dict, Any, Iterator, Literal
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = Literal[
    "openai", "deepseek", "qwen", "modelscope",
    "kimi", "zhipu", "siliconflow", "ollama", "vllm", "nvidia", "local", "auto"
]


class LLMClient:
    """
    Unified LLM client with multi-provider auto-detection
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[SUPPORTED_PROVIDERS] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: int = 120,
        **kwargs
    ):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.kwargs = kwargs

        self._dotenv_values: Dict[str, str] = {}
        self._load_dotenv()

        self.provider = self._resolve_provider(provider, api_key, base_url)
        self.api_key, resolved_base_url = self._resolve_credentials(api_key, base_url)
        self.base_url = self._normalize_base_url(resolved_base_url)

        if not self.api_key or not self.base_url:
            raise ValueError("API key and base URL must be provided or configured in .env file")

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=2,
        )

    def _load_dotenv(self) -> None:
        """Load .env configuration"""
        try:
            from dotenv import load_dotenv, find_dotenv, dotenv_values
            dotenv_path = find_dotenv(usecwd=True)
            if dotenv_path:
                values = dotenv_values(dotenv_path)
                self._dotenv_values = {k: v for k, v in values.items() if v is not None and str(v).strip()}
                load_dotenv(dotenv_path, override=False)
        except ImportError:
            pass

    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable"""
        if key in self._dotenv_values:
            return self._dotenv_values.get(key)
        return os.getenv(key, default)

    def _resolve_provider(self, provider: Optional[str], api_key: Optional[str], base_url: Optional[str]) -> str:
        """Resolve provider"""
        if provider:
            return provider.strip().lower()
        env_provider = self._get_env("OPENAI_PROVIDER")
        if env_provider:
            return env_provider.strip().lower()
        return self._auto_detect_provider(api_key, base_url)

    def _auto_detect_provider(self, api_key: Optional[str], base_url: Optional[str]) -> str:
        """Auto-detect provider from URL or API key"""
        url = (base_url or self._get_env("OPENAI_BASE_URL") or "").lower()
        if "deepseek" in url:
            return "deepseek"
        elif "qwen" in url or "dashscope" in url:
            return "qwen"
        elif "modelscope" in url or "modelscope" in (api_key or "").lower():
            return "modelscope"
        elif "kimi" in url or "moonshot" in url:
            return "kimi"
        elif "zhipu" in url:
            return "zhipu"
        elif "siliconflow" in url:
            return "siliconflow"
        elif "ollama" in url:
            return "ollama"
        elif "vllm" in url:
            return "vllm"
        elif "nvidia" in url or "nvapi" in url:
            return "nvidia"
        return "openai"

    def _resolve_credentials(self, api_key: Optional[str], base_url: Optional[str]):
        """Resolve credentials"""
        resolved_key = api_key or self._get_env("OPENAI_API_KEY")
        resolved_url = base_url or self._get_env("OPENAI_BASE_URL")
        return resolved_key, resolved_url

    def _normalize_base_url(self, base_url: Optional[str]) -> Optional[str]:
        """Normalize base URL"""
        if not base_url:
            return base_url
        normalized = base_url.strip().rstrip("/")
        for suffix in ("/chat/completions", "/completions"):
            if normalized.lower().endswith(suffix):
                normalized = normalized[: -len(suffix)]
        return normalized

    def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Any:
        """Send chat request"""
        return self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            stream=stream,
            **kwargs
        )

    def chat_with_retry(
        self,
        messages: list,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """Chat with retry"""
        last_error = None
        for attempt in range(max_retries):
            try:
                return self.chat(messages, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"LLM request failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise last_error


_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    """Get global LLM client singleton"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def set_client(client: LLMClient) -> None:
    """Set global LLM client"""
    global _client
    _client = client
