"""
AI Service Layers
Abstracts different LLM providers behind a single interface.
Supports: Anthropic Claude, OpenAI GPT, Mock (for testing).
"""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

from core.exceptions.handlers import AIServiceException, AITimeoutException

logger = logging.getLogger("apps.ai_service")

@dataclass
class AIMessage:
    """A single message in a conversation."""
    role: str           # "user" | "assistant"
    content: str

@dataclass
class AIResponse:
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    raw: Optional[dict] = field(default=None, repr=False)

class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""
    @abstractmethod
    def complete(
        self,
        messages: list[AIMessage],
        system_prompt: str,
        max_tokens: int,
    ) -> AIResponse:
        ...


# Anthropic Provider
class AnthropicProvider(BaseAIProvider):
    """Claude via the Anthropic SDK."""
    def __init__(self):
        try:
            import anthropic  # type: ignore
        except ImportError:
            raise ImportError("anthropic package is required: pip install anthropic")

        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")

        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=settings.AI_TIMEOUT_SECONDS,
        )
        self._model = settings.AI_MODEL

    def complete(self, messages: list[AIMessage], system_prompt: str, max_tokens: int) -> AIResponse:
        import anthropic  # type: ignore

        start = time.monotonic()
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            )
        except anthropic.APITimeoutError as exc:
            logger.warning("Anthropic timeout: %s", exc)
            raise AITimeoutException() from exc
        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic rate limit: %s", exc)
            raise AIServiceException("AI rate limit reached. Please wait a moment.") from exc
        except anthropic.APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            raise AIServiceException() from exc

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        content = response.content[0].text if response.content else ""

        logger.info(
            "Anthropic response received",
            extra={
                "model": self._model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "duration_ms": duration_ms,
            },
        )

        return AIResponse(
            content=content,
            model=self._model,
            provider="anthropic",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration_ms,
            raw=response.model_dump(),
        )


# OpenAI Provider 
class OpenAIProvider(BaseAIProvider):
    """GPT via the OpenAI SDK."""
    def __init__(self):
        try:
            import openai  # type: ignore
        except ImportError:
            raise ImportError("openai package is required: pip install openai")

        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        self._client = openai.OpenAI(api_key=api_key, timeout=settings.AI_TIMEOUT_SECONDS)
        self._model = settings.AI_MODEL or "gpt-4o-mini"

    def complete(self, messages: list[AIMessage], system_prompt: str, max_tokens: int) -> AIResponse:
        import openai  # type: ignore

        start = time.monotonic()
        chat_messages = [{"role": "system", "content": system_prompt}]
        chat_messages += [{"role": m.role, "content": m.content} for m in messages]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=chat_messages,
            )
        except openai.APITimeoutError as exc:
            raise AITimeoutException() from exc
        except openai.RateLimitError as exc:
            raise AIServiceException("AI rate limit reached. Please wait a moment.") from exc
        except openai.APIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise AIServiceException() from exc

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        choice = response.choices[0]
        content = choice.message.content or ""

        return AIResponse(
            content=content,
            model=self._model,
            provider="openai",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            duration_ms=duration_ms,
        )

# Gemini Provider (new google-genai SDK)
class GeminiProvider(BaseAIProvider):
    """Google Gemini via the new google-genai SDK."""

    def __init__(self):
        try:
            from google import genai
        except ImportError:
            raise ImportError("google-genai package is required: pip install google-genai")

        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        self._client = genai.Client(api_key=api_key)
        self._model_name = getattr(settings, "AI_MODEL", "gemini-2.0-flash")

    def complete(self, messages: list[AIMessage], system_prompt: str, max_tokens: int) -> AIResponse:
        from google import genai
        from google.genai import types

        start = time.monotonic()

        try:
            # Build conversation history
            contents = []
            for m in messages:
                role = "user" if m.role == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=m.content)]
                    )
                )

            response = self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                ),
            )

        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise AIServiceException(str(exc)) from exc

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        content = response.text or ""

        logger.info(
            "Gemini response received",
            extra={"model": self._model_name, "duration_ms": duration_ms},
        )

        return AIResponse(
            content=content,
            model=self._model_name,
            provider="gemini",
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
            duration_ms=duration_ms,
        )

# Mock Provider (testing / no API key)
class MockProvider(BaseAIProvider):
    """Returns deterministic canned responses. Useful for testing."""

    RESPONSES = [
        "I'm a mock AI assistant. Your message has been received!",
        "That's an interesting question. In a real deployment, an LLM would answer here.",
        "Mock response: I understand your query and would normally provide a detailed answer.",
        "This is a test response from the mock AI provider.",
    ]
    _counter = 0

    def complete(self, messages: list[AIMessage], system_prompt: str, max_tokens: int) -> AIResponse:
        last_user_msg = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        content = self.RESPONSES[MockProvider._counter % len(self.RESPONSES)]
        MockProvider._counter += 1
        logger.debug("MockProvider returning response #%d", MockProvider._counter)
        return AIResponse(
            content=content,
            model="mock-model",
            provider="mock",
            input_tokens=len(last_user_msg.split()),
            output_tokens=len(content.split()),
            duration_ms=50.0,
        )


# Factory 
def get_ai_provider() -> BaseAIProvider:
    """Return the configured AI provider instance."""
    provider_name = getattr(settings, "AI_PROVIDER", "mock").lower()
    providers = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "mock": MockProvider,
    }
    cls = providers.get(provider_name)
    if cls is None:
        logger.warning("Unknown AI_PROVIDER '%s', falling back to mock.", provider_name)
        cls = MockProvider

    try:
        return cls()
    except Exception as exc:
        logger.error("Failed to initialise %s provider: %s — falling back to mock.", provider_name, exc)
        return MockProvider()


# Module-level singleton (lazily initialised)
_provider_instance: Optional[BaseAIProvider] = None

def get_provider() -> BaseAIProvider:
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = get_ai_provider()
        logger.info("Using AI provider: %s", type(_provider_instance).__name__)
    return _provider_instance
