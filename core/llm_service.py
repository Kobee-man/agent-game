import os
import httpx
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    mode: str = field(default_factory=lambda: os.getenv("LLM_MODE", "external"))
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen3.5:4b"))
    api_url: str = field(default_factory=lambda: os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")))
    api_model: str = field(default_factory=lambda: os.getenv("LLM_API_MODEL", "deepseek-chat"))
    temperature: float = 0.5
    max_tokens: int = 1000
    timeout: float = 30.0


class LLMError(Exception):
    pass


class LLMService:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()

    @property
    def mode(self) -> str:
        return self.config.mode

    def is_available(self) -> bool:
        if self.config.mode == "local":
            return True
        return bool(self.config.api_key)

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        t = temperature if temperature is not None else self.config.temperature
        m = max_tokens if max_tokens is not None else self.config.max_tokens

        if self.config.mode == "local":
            return await self._call_ollama(prompt, system_prompt, t, m)
        elif self.config.mode == "external":
            return await self._call_external(prompt, system_prompt, t, m)
        raise LLMError(f"不支持的模式: {self.config.mode}")

    async def _call_ollama(self, prompt: str, system: str, temp: float, max_tok: int) -> str:
        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temp, "num_predict": max_tok},
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(f"{self.config.ollama_host}/api/generate", json=payload)
                if resp.status_code != 200:
                    raise LLMError(f"Ollama错误 (HTTP {resp.status_code})")
                text = resp.json().get("response", "").strip()
                if not text:
                    raise LLMError("Ollama返回空内容")
                return text
        except httpx.ConnectError:
            raise LLMError("无法连接Ollama，请确认 ollama serve 已启动")
        except httpx.TimeoutException:
            raise LLMError(f"Ollama超时 ({self.config.timeout}s)")
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Ollama调用失败: {e}")

    async def _call_external(self, prompt: str, system: str, temp: float, max_tok: int) -> str:
        if not self.config.api_key:
            raise LLMError("需要设置 LLM_API_KEY")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.config.api_model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tok,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(self.config.api_url, headers=headers, json=payload)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                elif resp.status_code == 401:
                    raise LLMError("API密钥无效")
                elif resp.status_code == 429:
                    raise LLMError("请求频率超限")
                else:
                    raise LLMError(f"API错误 (HTTP {resp.status_code})")
        except LLMError:
            raise
        except httpx.ConnectError:
            raise LLMError(f"无法连接: {self.config.api_url}")
        except httpx.TimeoutException:
            raise LLMError(f"请求超时 ({self.config.timeout}s)")
        except Exception as e:
            raise LLMError(f"调用失败: {e}")


llm_service = LLMService()
