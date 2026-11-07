"""Model access with a per-project cost ceiling.

Two backends:
- AnthropicLLM: real calls through the official SDK (needs ANTHROPIC_API_KEY
  or another credential the SDK can resolve).
- MockLLM: deterministic offline output, used for tests, demos and when no
  key is configured. Agents fall back to their own template logic.

Keys live only in environment variables, never in prompts.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# USD per 1M tokens (input, output). Keep in sync with Anthropic pricing.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

DEFAULT_MODEL = "claude-opus-5-5"


class BudgetExceeded(RuntimeError):
    pass


class ModelRefused(RuntimeError):
    pass


@dataclass
class CostTracker:
    budget_usd: float
    spent_usd: float = 0.0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_agent: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def check(self) -> None:
        if self.spent_usd >= self.budget_usd:
            raise BudgetExceeded(
                f"Đã tiêu ${self.spent_usd:.4f} / trần ${self.budget_usd:.2f}"
            )

    def add(self, agent: str, model: str, input_tokens: int, output_tokens: int) -> None:
        pin, pout = PRICING.get(model, PRICING[DEFAULT_MODEL])
        cost = input_tokens / 1e6 * pin + output_tokens / 1e6 * pout
        with self._lock:
            self.calls += 1
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.spent_usd += cost
            self.by_agent[agent] = self.by_agent.get(agent, 0.0) + cost

    def to_dict(self) -> dict:
        return {
            "budget_usd": self.budget_usd,
            "spent_usd": round(self.spent_usd, 6),
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "by_agent": {k: round(v, 6) for k, v in self.by_agent.items()},
        }


class LLM:
    """Interface every agent uses."""

    name = "base"
    is_mock = False

    def __init__(self, cost: CostTracker):
        self.cost = cost

    def structured(self, agent: str, system: str, user: str, schema: type[T]) -> T | None:
        raise NotImplementedError


class MockLLM(LLM):
    """Returns None so each agent uses its deterministic fallback."""

    name = "mock"
    is_mock = True

    def structured(self, agent, system, user, schema):
        self.cost.check()
        self.cost.add(agent, DEFAULT_MODEL, 0, 0)
        return None


class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(self, cost: CostTracker, model: str | None = None, effort: str | None = None):
        super().__init__(cost)
        import anthropic  # imported lazily so mock mode needs no SDK

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("VTD_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("VTD_EFFORT", "medium")

    def structured(self, agent, system, user, schema):
        self.cost.check()
        with self.client.messages.stream(
            model=self.model,
            max_tokens=32000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort},
            output_format=schema,
        ) as stream:
            response = stream.get_final_message()
        self.cost.add(agent, self.model, response.usage.input_tokens, response.usage.output_tokens)
        if response.stop_reason == "refusal":
            raise ModelRefused(f"{agent}: model declined the request")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"{agent}: output was cut off at max_tokens")
        return response.parsed_output


def make_llm(cost: CostTracker) -> LLM:
    mode = os.environ.get("VTD_LLM", "auto")
    if mode == "mock":
        return MockLLM(cost)
    if mode == "anthropic" or os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicLLM(cost)
    return MockLLM(cost)
