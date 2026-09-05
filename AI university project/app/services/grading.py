"""Grading: brutally honest, tied to the module's actual research digest. No padding, no
participation trophies, no progression gate — a bad result gets flagged and logged, and the
learner moves on regardless."""

from app.models import LearningMethod, Module
from app.services import anthropic_client as ai
from app.services import sandbox
from app.services.research import read_digest

_GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "description": "0-100. Be honest — most first attempts land in the 40-75 range. Reserve 90+ for genuinely excellent responses.",
        },
        "feedback": {
            "type": "string",
            "description": (
                "Direct, specific feedback. Say exactly what was wrong and why, citing the "
                "reference digest. No padding, no 'good effort', no participation trophies."
            ),
        },
    },
    "required": ["score", "feedback"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a strict, honest grader for a self-directed learner. Grade against the reference "
    "digest, not against effort or intent. Be specific about what's wrong and why. Do not soften "
    "the feedback or add encouragement filler — the learner wants to know exactly where they "
    "stand. A low score is fine; say so plainly."
)


def grade_session(
    module: Module,
    method: LearningMethod,
    transcript: list[tuple[str, str]],
    final_response: str,
) -> tuple[int, str, sandbox.SandboxResult | None]:
    digest = read_digest(module.digest_path) or "(no digest available)"
    execution_note = ""
    execution_result: sandbox.SandboxResult | None = None

    if method == LearningMethod.ship_it and _looks_like_code(final_response):
        execution_result = sandbox.run_python(final_response)
        status = "TIMED OUT" if execution_result.timed_out else f"exit code {execution_result.return_code}"
        network_note = (
            "network was sandboxed (isolated namespace)"
            if execution_result.network_sandboxed
            else "network isolation unavailable on this host — ran without a network sandbox"
        )
        execution_note = (
            f"\n\nActual execution result ({status}, {network_note}):\n"
            f"stdout:\n{execution_result.stdout}\n\nstderr:\n{execution_result.stderr}\n\n"
            "Grade based on whether it actually ran correctly and produced the right result — "
            "do not just eyeball-review the code."
        )

    convo = "\n\n".join(f"{role.upper()}: {content}" for role, content in transcript)
    prompt = (
        f"Module: {module.title} — {module.one_liner}\n\nReference digest:\n{digest}\n\n"
        f"Exercise transcript:\n{convo}\n\nFinal learner response:\n{final_response}"
        f"{execution_note}\n\nGrade this."
    )
    result = ai.structured_call(system=_SYSTEM, user_prompt=prompt, schema=_GRADE_SCHEMA, max_tokens=1500)
    score = max(0, min(100, int(result.get("score", 0))))
    feedback = result.get("feedback", "")
    return score, feedback, execution_result


def _looks_like_code(text: str) -> bool:
    markers = ("def ", "import ", "class ", "print(", "```")
    return any(m in text for m in markers)
