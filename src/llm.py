"""Anthropic API wrapper for Haiku 4.5 calls.

Tracks cumulative token usage and cost across a single CLI run so that
batch mode can summarize spend at the end.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

import anthropic


MODEL = "claude-haiku-4-5-20251001"

# Public Haiku 4.5 pricing per the model card (USD per 1M tokens).
INPUT_PRICE_PER_MTOK = 1.00
OUTPUT_PRICE_PER_MTOK = 5.00


@dataclass
class UsageTracker:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * INPUT_PRICE_PER_MTOK
            + self.output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MTOK
        )

    def summary(self) -> str:
        return (
            f"{self.calls} call(s), "
            f"{self.input_tokens} in / {self.output_tokens} out tokens, "
            f"~${self.cost_usd:.4f}"
        )


# Module-level singleton — easy for the CLI to read at the end of a run.
usage = UsageTracker()


_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env "
                "and add your key, or export it in your shell."
            )
        _client = anthropic.Anthropic()
    return _client


def call_haiku(system: str, prompt: str, max_tokens: int = 2048) -> str:
    """Call Claude Haiku 4.5 and return the response text."""
    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        usage.add(response.usage.input_tokens, response.usage.output_tokens)
    except AttributeError:
        pass

    # Concatenate all text blocks (Haiku usually returns one).
    parts = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)
