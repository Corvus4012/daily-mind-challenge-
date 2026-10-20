"""Thin wrapper around the Anthropic API for the review pipeline.

Prompts are templates: every {{name}} is replaced with input_dict[name] (strings as-is, anything
else as JSON). A prompt with no placeholders gets the whole input_dict appended as JSON.
Each call_* returns the model's reply parsed as a JSON object (dict). Every API response is
logged to logs/cost.jsonl, even if its JSON later fails to parse.
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
PROMPTS = ROOT / "prompts"

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
WEB_SEARCH_USD = 10.00 / 1000
# Server-side web search; the _20260209 version runs on Opus 5.5 and Sonnet 5.5 (not Haiku).
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}

MAX_ATTEMPTS = 3
BASE_DELAY = 2.0
MAX_TOKENS = 16000
MAX_CONTINUATIONS = 3  # pause_turn resumes for long server-side search loops
SYSTEM = "Respond with a single JSON object and nothing else: no markdown, no text outside the JSON."
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


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
        # Retries are handled in _create_with_retry so attempts and backoff are explicit.
        _client = anthropic.Anthropic(api_key=api_key, max_retries=0)
    return _client


def _create_message(model, system, messages, agent, tools):
    """Single network round trip. Kept separate so tests can replace it."""
    kwargs = {"tools": tools} if tools else {}
    return _get_client().messages.create(
        model=model, max_tokens=MAX_TOKENS, system=system, messages=messages, **kwargs
    )


def _is_retryable(exc):
    import anthropic

    if isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError)):
        return True  # APIConnectionError also covers timeouts
    return isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500


def _create_with_retry(model, messages, agent, tools):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _create_message(model, SYSTEM, messages, agent, tools)
        except Exception as exc:
            if attempt == MAX_ATTEMPTS or not _is_retryable(exc):
                raise LLMError(f"[{agent}] {model} failed after {attempt} attempt(s): {exc}") from exc
            time.sleep(BASE_DELAY * 2 ** (attempt - 1) + random.uniform(0, 1))


def _cost_usd(model, tokens_in, tokens_out, searches=0):
    price_in, price_out = PRICING[model]
    if model == MODELS["haiku"] and tokens_in > HAIKU_LONG_PROMPT[0]:
        price_in, price_out = HAIKU_LONG_PROMPT[1]
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000 + searches * WEB_SEARCH_USD, 6)


def _log_cost(model, usage, agent):
    tokens_in = usage.input_tokens
    tokens_out = usage.output_tokens
    server = getattr(usage, "server_tool_use", None)
    searches = getattr(server, "web_search_requests", 0) or 0
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": _cost_usd(model, tokens_in, tokens_out, searches),
        "agent": agent,
    }
    if searches:
        entry["web_searches"] = searches
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_prompt(name):
    """Read prompts/{name}.md; refuse placeholder files that hold only an HTML comment."""
    path = PROMPTS / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    if not re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip():
        raise LLMError(f"{path} has no prompt content yet.")
    return text


def render(prompt, input_dict):
    """Fill {{name}} placeholders from input_dict; raise if one has no value."""
    names = PLACEHOLDER.findall(prompt)
    if not names:
        return prompt + "\n\n" + json.dumps(input_dict, ensure_ascii=False, indent=2)
    missing = sorted(set(names) - input_dict.keys())
    if missing:
        raise LLMError(f"Prompt placeholders without values: {missing}")

    def value(match):
        v = input_dict[match.group(1)]
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2)

    return PLACEHOLDER.sub(value, prompt)


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


def _final_text(content):
    """Text after the last non-text block, so search narration before the answer is dropped."""
    last_other = max((i for i, b in enumerate(content) if b.type not in ("text", "thinking")), default=-1)
    tail = "".join(b.text for b in content[last_other + 1:] if b.type == "text")
    return tail or "".join(b.text for b in content if b.type == "text")


def _call(model_key, prompt, input_dict, agent, web_search):
    model = MODELS[model_key]
    if web_search and model_key == "haiku":
        raise LLMError(f"[{agent}] web search is not wired up for {model}.")
    tools = [WEB_SEARCH_TOOL] if web_search else None
    user_turn = {"role": "user", "content": render(prompt, input_dict)}
    messages = [user_turn]
    paused_blocks = []

    for _ in range(MAX_CONTINUATIONS + 1):
        response = _create_with_retry(model, messages, agent, tools)
        _log_cost(model, response.usage, agent)
        if response.stop_reason != "pause_turn":
            break
        # Resume the server-side tool loop: resend the paused turn so far, no extra user message.
        paused_blocks += list(response.content)
        messages = [user_turn, {"role": "assistant", "content": paused_blocks}]
    else:
        raise LLMError(f"[{agent}] {model} still paused after {MAX_CONTINUATIONS} continuations.")

    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None)
        raise LLMError(f"[{agent}] {model} refused the request (category={category}).")
    if response.stop_reason == "max_tokens":
        raise LLMError(f"[{agent}] {model} hit max_tokens={MAX_TOKENS}; output is truncated.")
    try:
        return parse_json(_final_text(paused_blocks + list(response.content)))
    except LLMError as exc:
        raise LLMError(f"[{agent}] {exc}") from exc


def call_opus(prompt, input_dict, agent="unknown", web_search=False):
    return _call("opus", prompt, input_dict, agent, web_search)


def call_sonnet(prompt, input_dict, agent="unknown", web_search=False):
    return _call("sonnet", prompt, input_dict, agent, web_search)


def call_haiku(prompt, input_dict, agent="unknown"):
    return _call("haiku", prompt, input_dict, agent, False)
