"""Thin wrapper around the Anthropic API for research (web search) and plain reasoning calls."""

import anthropic

from app.config import settings

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _web_search_tool(max_uses: int = 8) -> dict:
    return {"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses}


def _extract_text(response: anthropic.types.Message) -> str:
    text = "\n".join(block.text for block in response.content if block.type == "text")
    if response.stop_reason == "max_tokens":
        # Silently returning partial text reads as a clean response with the tail quietly missing —
        # surfacing it as an error is more honest than serving cut-off content.
        raise RuntimeError("Response was cut off by the max_tokens limit before it finished.")
    return text


def research_call(
    system: str,
    user_prompt: str,
    max_tokens: int = 8000,
    effort: str = "medium",
    max_search_uses: int = 8,
) -> str:
    """One research request with the web search tool enabled. Resumes automatically on pause_turn
    (the server-side search loop hit its per-request iteration cap) and returns the final text."""
    client = get_client()
    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    response = client.messages.create(
        model=settings.research_model,
        max_tokens=max_tokens,
        system=system,
        tools=[_web_search_tool(max_search_uses)],
        output_config={"effort": effort},
        messages=messages,
    )
    while response.stop_reason == "pause_turn":
        messages = [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": response.content},
        ]
        response = client.messages.create(
            model=settings.research_model,
            max_tokens=max_tokens,
            system=system,
            tools=[_web_search_tool(max_search_uses)],
            output_config={"effort": effort},
            messages=messages,
        )
    return _extract_text(response)


def plain_call(system: str, user_prompt: str, max_tokens: int = 4000, effort: str = "medium") -> str:
    """A reasoning call with no tools — grading, method selection rationale, teaching turns, etc."""
    client = get_client()
    response = client.messages.create(
        model=settings.grading_model,
        max_tokens=max_tokens,
        system=system,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user_prompt}],
    )
    return _extract_text(response)


def structured_call(
    system: str,
    user_prompt: str,
    schema: dict,
    max_tokens: int = 4000,
    effort: str = "medium",
) -> dict:
    """A reasoning call constrained to a JSON schema. No tools — for structuring already-gathered
    research into a reliable shape (outlines, grading rubric scores, etc.)."""
    import json

    client = get_client()
    response = client.messages.create(
        model=settings.grading_model,
        max_tokens=max_tokens,
        system=system,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
