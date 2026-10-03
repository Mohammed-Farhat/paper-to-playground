"""OpenRouter chat-completions client with hard per-case budget enforcement.

Assessment limits per case: 10 minutes, at most 10 API requests (including
retries) and 30,000 total completion tokens. The Budget object is the single
source of truth for these limits; every HTTP attempt is counted before it is
sent, and max_tokens is always capped by the remaining completion budget.

Responses are streamed so that the wall-clock deadline can be enforced even
while the server is still generating. Reasoning text is excluded from the
response and never stored or logged; only its token count is recorded.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MAX_REQUESTS = 10
MAX_COMPLETION_TOKENS = 30_000
MAX_SECONDS = 600.0
# Time kept in reserve after the last model call for checks, building and exit.
FINISH_RESERVE_SECONDS = 20.0

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}

# Provider routing (same model, MODEL_ID unchanged). Measured on this model:
# default price-based routing gave 35-115 tok/s, BaseTen 200-300 tok/s,
# Together about 160 tok/s. Fallbacks stay enabled, so if neither provider is
# available OpenRouter routes the request as usual.
PROVIDER_PREFERENCES = {"order": ["baseten", "together"], "allow_fallbacks": True}


class BudgetExceeded(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


@dataclass
class Budget:
    t0: float
    max_requests: int = MAX_REQUESTS
    max_completion_tokens: int = MAX_COMPLETION_TOKENS
    max_seconds: float = MAX_SECONDS
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    usage_estimated: bool = False

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def seconds_left(self) -> float:
        return self.max_seconds - FINISH_RESERVE_SECONDS - self.elapsed()

    def requests_left(self) -> int:
        return self.max_requests - self.requests

    def completion_left(self) -> int:
        return self.max_completion_tokens - self.completion_tokens

    def summary(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "usage_estimated": self.usage_estimated,
        }


@dataclass
class CallResult:
    text: str
    finish_reason: str | None
    usage: dict[str, Any] = field(default_factory=dict)
    generation_id: str | None = None
    provider: str | None = None
    seconds: float = 0.0
    attempts: int = 1


class OpenRouterClient:
    def __init__(
        self,
        model: str,
        api_key: str,
        budget: Budget,
        trace,
        reasoning: dict[str, Any] | None = None,
        temperature: float | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.budget = budget
        self.trace = trace
        self.reasoning = reasoning
        self.temperature = temperature
        self.session = requests.Session()

    # ------------------------------------------------------------------ public
    def chat(self, messages: list[dict[str, str]], max_tokens: int, stage: str, purpose: str,
             max_attempts: int = 3, min_tokens: int = 1500) -> CallResult:
        """Send one logical request (with bounded retries). Raises BudgetExceeded / LLMError."""
        last_error = "no attempt made"
        for attempt in range(1, max_attempts + 1):
            self._check_budget(min_tokens)
            cap = min(max_tokens, self.budget.completion_left())
            self.budget.requests += 1
            t_start = time.monotonic()
            try:
                result = self._stream_once(messages, cap)
            except _RetryableError as exc:
                last_error = str(exc)
                usage_fields = self._account(exc.usage, exc.partial_chars)
                self.trace.log(stage, "llm_call", "error", purpose=purpose, attempt=attempt,
                               model=self.model, error=last_error, retryable=True,
                               elapsed_s=round(time.monotonic() - t_start, 3), max_tokens=cap,
                               partial_output_chars=exc.partial_chars, **usage_fields)
                if attempt < max_attempts:
                    time.sleep(min(1.5 * attempt, max(0.0, self.budget.seconds_left() - 1)))
                continue
            except _FatalError as exc:
                self.trace.log(stage, "llm_call", "error", purpose=purpose, attempt=attempt,
                               model=self.model, error=str(exc), retryable=False,
                               elapsed_s=round(time.monotonic() - t_start, 3), max_tokens=cap)
                raise LLMError(str(exc)) from None
            result.seconds = round(time.monotonic() - t_start, 3)
            result.attempts = attempt
            usage_fields = self._account(result.usage, len(result.text))
            self.trace.log(stage, "llm_call", "ok", purpose=purpose, attempt=attempt,
                           model=self.model, provider=result.provider, generation_id=result.generation_id,
                           finish_reason=result.finish_reason, max_tokens=cap,
                           output_chars=len(result.text), elapsed_s=result.seconds,
                           **usage_fields)
            return result
        raise LLMError(f"model call failed after retries: {last_error}")

    # ----------------------------------------------------------------- helpers
    def _check_budget(self, min_tokens: int) -> None:
        b = self.budget
        if b.requests_left() <= 0:
            raise BudgetExceeded(f"request limit reached ({b.max_requests})")
        if b.completion_left() < min_tokens:
            raise BudgetExceeded(f"completion-token budget nearly exhausted ({b.completion_left()} left)")
        if b.seconds_left() < 15:
            raise BudgetExceeded(f"time budget nearly exhausted ({b.seconds_left():.0f}s left)")

    def _account(self, usage: dict[str, Any] | None, output_chars: int) -> dict[str, Any]:
        """Add one response's usage to the budget; returns the fields to log."""
        b = self.budget
        if usage:
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
            reasoning = int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
            cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
            estimated = False
        else:
            # Usage missing (stream aborted). Count a conservative estimate so
            # the completion budget is never overrun.
            prompt, reasoning, cached = 0, 0, 0
            completion = int(output_chars / 3) + 1 if output_chars else 0
            estimated = True
            b.usage_estimated = b.usage_estimated or bool(completion)
        b.prompt_tokens += prompt
        b.completion_tokens += completion
        b.reasoning_tokens += reasoning
        b.cached_tokens += cached
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "reasoning_tokens": reasoning,
            "cached_tokens": cached,
            "total_tokens": prompt + completion,
            "usage_estimated": estimated,
            "cumulative_completion_tokens": b.completion_tokens,
            "cumulative_requests": b.requests,
        }

    def _stream_once(self, messages: list[dict[str, str]], max_tokens: int) -> CallResult:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            "usage": {"include": True},
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.reasoning is not None:
            body["reasoning"] = self.reasoning
        if PROVIDER_PREFERENCES:
            body["provider"] = PROVIDER_PREFERENCES
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": "paper-to-playground",
        }
        deadline = time.monotonic() + max(5.0, self.budget.seconds_left())
        read_timeout = max(5.0, min(120.0, self.budget.seconds_left()))
        try:
            resp = self.session.post(OPENROUTER_URL, headers=headers, json=body, stream=True,
                                     timeout=(15, read_timeout))
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise _RetryableError(f"network error: {type(exc).__name__}") from None

        with resp:
            if resp.status_code != 200:
                detail = _error_detail(resp)
                if resp.status_code in RETRYABLE_STATUS:
                    raise _RetryableError(f"HTTP {resp.status_code}: {detail}")
                raise _FatalError(f"HTTP {resp.status_code}: {detail}")

            parts: list[str] = []
            usage: dict[str, Any] | None = None
            finish: str | None = None
            gen_id: str | None = None
            provider: str | None = None
            try:
                for raw in resp.iter_lines():
                    if time.monotonic() > deadline:
                        raise _RetryableError("deadline reached while streaming", usage,
                                              sum(map(len, parts)))
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace")
                    if line.startswith(":") or not line.startswith("data:"):
                        continue  # SSE comment / keep-alive
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if "error" in chunk:
                        err = chunk["error"]
                        msg = err.get("message") if isinstance(err, dict) else str(err)
                        raise _RetryableError(f"stream error: {msg}", chunk.get("usage"),
                                              sum(map(len, parts)))
                    gen_id = chunk.get("id") or gen_id
                    provider = chunk.get("provider") or provider
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            parts.append(delta["content"])
                        if choice.get("finish_reason"):
                            finish = choice["finish_reason"]
                    if chunk.get("usage"):
                        usage = chunk["usage"]
            except (requests.ConnectionError, requests.Timeout,
                    requests.exceptions.ChunkedEncodingError) as exc:
                raise _RetryableError(f"stream interrupted: {type(exc).__name__}", usage,
                                      sum(map(len, parts))) from None

        text = "".join(parts)
        if not text.strip():
            raise _RetryableError(f"empty response (finish_reason={finish})", usage, 0)
        return CallResult(text=text, finish_reason=finish, usage=usage or {}, generation_id=gen_id,
                          provider=provider)


class _RetryableError(Exception):
    def __init__(self, msg: str, usage: dict[str, Any] | None = None, partial_chars: int = 0):
        super().__init__(msg)
        self.usage = usage
        self.partial_chars = partial_chars


class _FatalError(Exception):
    pass


def _error_detail(resp: requests.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error", data)
        if isinstance(err, dict):
            return str(err.get("message") or err)[:300]
        return str(err)[:300]
    except ValueError:
        return resp.text[:300]
