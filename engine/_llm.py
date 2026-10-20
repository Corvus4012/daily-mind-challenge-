"""Thin wrapper around the Anthropic API for the review pipeline.

Each call_* function takes a system prompt and an input dict, sends the dict as JSON,
and returns the model's reply parsed as a JSON object (dict). Every successful API
response is logged to logs/cost.jsonl, even if its JSON later fails to parse.
"""
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COST_LOG = ROOT / "logs" / "cost.jsonl"

MODELS = {
    "opus": "claude-opus-5-5",
    "sonnet": "claude-sonnet-5-5",
    "haiku": "claude-haiku-5-5",
}
# USD per 1M tokens (input, output), Anthropic first-party rates.
PRICING = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
# Claude Haiku 5.5 is billed at a higher rate once the prompt exceeds 100K tokens.
HAIKU_LONG_PROMPT = (100_000, (0.50, 2.50))

MAX_ATTEMPTS = 3
BASE_DELAY = 2.0
MAX_TOKENS = 16000
JSON_INSTRUCTION = "\n\nRespond with a single JSON object and nothing else."


class LLMError(RuntimeError):
    """The API call failed, was refused, or returned unusable output."""


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set; the review pipeline cannot call the API.")
        # Retries are handled in _call so attempts and backoff are explicit.
        _client = anthropic.Anthropic(api_key=api_key, max_retries=0)
    return _client


def _create_message(model, system, user_content, agent):
    """Single network round trip. Kept separate so tests can replace it."""
    return _get_client().messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )


def _is_retryable(exc):
    import anthropic

    if isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError)):
        return True  # APIConnectionError also covers timeouts
    return isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500


def _cost_usd(model, tokens_in, tokens_out):
    price_in, price_out = PRICING[model]
    if model == MODELS["haiku"] and tokens_in > HAIKU_LONG_PROMPT[0]:
        price_in, price_out = HAIKU_LONG_PROMPT[1]
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 6)


def _log_cost(model, usage, agent):
    tokens_in = usage.input_tokens
    tokens_out = usage.output_tokens
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": _cost_usd(model, tokens_in, tokens_out),
        "agent": agent,
    }
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def parse_json(text):
    """json.loads first; fall back to the outermost {...} span; else raise LLMError."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise LLMError(f"No JSON object in model output: {text[:300]!r}")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"Unparseable JSON in model output ({exc}): {text[:300]!r}") from exc
    if not isinstance(data, dict):
        raise LLMError(f"Expected a JSON object, got {type(data).__name__}: {text[:300]!r}")
    return data


def _call(model_key, prompt, input_dict, agent):
    model = MODELS[model_key]
    user_content = json.dumps(input_dict, ensure_ascii=False, indent=2)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = _create_message(model, prompt + JSON_INSTRUCTION, user_content, agent)
            break
        except Exception as exc:
            if attempt == MAX_ATTEMPTS or not _is_retryable(exc):
                raise LLMError(f"[{agent}] {model} failed after {attempt} attempt(s): {exc}") from exc
            time.sleep(BASE_DELAY * 2 ** (attempt - 1) + random.uniform(0, 1))

    _log_cost(model, response.usage, agent)
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None)
        raise LLMError(f"[{agent}] {model} refused the request (category={category}).")
    if response.stop_reason == "max_tokens":
        raise LLMError(f"[{agent}] {model} hit max_tokens={MAX_TOKENS}; output is truncated.")
    # Responses can carry thinking blocks; only text blocks hold the answer.
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return parse_json(text)
    except LLMError as exc:
        raise LLMError(f"[{agent}] {exc}") from exc


def call_opus(prompt, input_dict, agent="unknown"):
    return _call("opus", prompt, input_dict, agent)


def call_sonnet(prompt, input_dict, agent="unknown"):
    return _call("sonnet", prompt, input_dict, agent)


def call_haiku(prompt, input_dict, agent="unknown"):
    return _call("haiku", prompt, input_dict, agent)
