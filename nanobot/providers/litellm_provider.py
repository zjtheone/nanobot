"""LiteLLM provider implementation for multi-provider support."""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import litellm
from litellm import acompletion

from nanobot.providers.base import LLMProvider, LLMResponse, LLMStreamChunk, ToolCallRequest
from nanobot.providers.registry import find_by_model, find_gateway


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.

    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}

        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)

        # Configure environment variables
        if api_key:
            self._setup_env(api_key, api_base, default_model)

        if api_base:
            litellm.api_base = api_base

        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True

    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return

        # Gateway/local overrides existing env; standard provider doesn't
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        # Resolve env_extras placeholders:
        #   {api_key}  → user's API key
        #   {api_base} → user's api_base, falling back to spec.default_api_base
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model

        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            prefix = spec.litellm_prefix
            for skip in spec.skip_prefixes:
                if model.startswith(skip):
                    if skip.endswith("/"):
                        model_name = model[len(skip) :]
                        return f"{prefix}/{model_name}"
                    return model
            return f"{prefix}/{model}"

        return model

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    def _apply_prompt_caching(self, kwargs: dict[str, Any]) -> None:
        """Add cache_control to system messages for Anthropic prompt caching."""
        messages = kwargs.get("messages", [])
        if not messages:
            return
        # Mark system message for caching (saves ~90% input tokens on long sessions)
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 1000:
                    msg["cache_control"] = {"type": "ephemeral"}
                break

    def _build_kwargs(
        self,
        model: str,
        messages: list,
        tools: list | None,
        max_tokens: int,
        temperature: float,
        frequency_penalty: float,
        stream: bool = False,
        thinking_budget: int = 0,
    ) -> dict[str, Any]:
        """Build common kwargs for chat/stream_chat."""
        # Debug: Log full prompt to file
        try:
            debug_data = {
                "model": model or self.default_model,
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            with open("/tmp/nanobot_debug_prompt.json", "w") as f:
                json.dump(debug_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Debug log failed: {e}")

        model = self._resolve_model(model or self.default_model)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if frequency_penalty:
            kwargs["frequency_penalty"] = frequency_penalty

        self._apply_model_overrides(model, kwargs)

        # Extended thinking (Anthropic Claude)
        if thinking_budget and thinking_budget > 0:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

        # Prompt caching for Anthropic Claude models (Phase 5A)
        if "claude" in model.lower() and messages:
            self._apply_prompt_caching(kwargs)

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if stream:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}

        return kwargs

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        frequency_penalty: float = 0.0,
        thinking_budget: int = 0,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        # Debug: Log full prompt to file
        try:
            debug_data = {
                "model": model or self.default_model,
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            with open("/tmp/nanobot_debug_prompt.json", "w") as f:
                json.dump(debug_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Debug log failed: {e}")

        kwargs = self._build_kwargs(
            model or self.default_model,
            messages,
            tools,
            max_tokens,
            temperature,
            frequency_penalty,
            thinking_budget=thinking_budget,
        )

        try:
            response = await acompletion(**kwargs, num_retries=3)
            return self._parse_response(response)
        except Exception as e:
            # Return error as content for graceful handling
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        frequency_penalty: float = 0.0,
        thinking_budget: int = 0,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream a chat completion, yielding chunks as they arrive."""
        kwargs = self._build_kwargs(
            model or self.default_model,
            messages,
            tools,
            max_tokens,
            temperature,
            frequency_penalty,
            stream=True,
            thinking_budget=thinking_budget,
        )

        try:
            response = await acompletion(**kwargs, num_retries=3)
            async for chunk in response:
                if not chunk.choices:
                    # Usage-only chunk (final)
                    if hasattr(chunk, "usage") and chunk.usage:
                        yield LLMStreamChunk(
                            usage={
                                "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                                "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                                "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                            }
                        )
                    continue

                delta = chunk.choices[0].delta
                finish = chunk.choices[0].finish_reason

                sc = LLMStreamChunk(finish_reason=finish)

                # Text content
                if hasattr(delta, "content") and delta.content:
                    sc.delta_content = delta.content

                # Tool call deltas — iterate ALL entries, not just [0]
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_chunk = LLMStreamChunk(finish_reason=finish)
                        tc_chunk.tool_call_index = tc.index if hasattr(tc, "index") else 0
                        if hasattr(tc, "id") and tc.id:
                            tc_chunk.tool_call_id = tc.id
                        if hasattr(tc, "function"):
                            if hasattr(tc.function, "name") and tc.function.name:
                                tc_chunk.tool_call_name = tc.function.name
                            if hasattr(tc.function, "arguments") and tc.function.arguments:
                                tc_chunk.tool_call_arguments_delta = tc.function.arguments
                        # Carry text content only on the first tool call chunk
                        if tc == delta.tool_calls[0] and hasattr(delta, "content") and delta.content:
                            tc_chunk.delta_content = sc.delta_content
                        yield tc_chunk
                    # Usage in the final chunk
                    if hasattr(chunk, "usage") and chunk.usage:
                        yield LLMStreamChunk(
                            usage={
                                "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                                "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                                "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                            }
                        )
                    continue

                # Usage in the final chunk
                if hasattr(chunk, "usage") and chunk.usage:
                    sc.usage = {
                        "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                        "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                    }

                yield sc
        except Exception as e:
            yield LLMStreamChunk(
                delta_content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None)

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
