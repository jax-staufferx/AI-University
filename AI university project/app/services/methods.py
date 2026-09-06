"""The 8 active-learning methods: default selection by content type, weighted by what the
monitor agent has learned works for this user, and prompt generation for each."""

import random

from sqlalchemy.orm import Session

from app.models import ContentType, LearnerProfile, LearningMethod, Module
from app.services import anthropic_client as ai
from app.services.research import _DEPTH_INSTRUCTIONS, read_digest

# Methods that involve a genuine back-and-forth before grading (poke holes / defend / argue).
INTERACTIVE_METHODS = {LearningMethod.sparring, LearningMethod.teach_it_back}
MAX_INTERACTIVE_ROUNDS = 2

_METHOD_LABELS = {
    LearningMethod.teach_it_back: "Teach-it-back",
    LearningMethod.sparring: "Sparring",
    LearningMethod.ship_it: "Ship-it",
    LearningMethod.analogy_builder: "Analogy Builder",
    LearningMethod.error_hunt: "Error Hunt",
    LearningMethod.eli5: "ELI5",
    LearningMethod.scenario_application: "Scenario Application",
    LearningMethod.rapid_recall: "Rapid Recall",
}

# Default candidate methods by content type, per the spec: skill-based topics lean
# ship-it/error-hunt, conceptual/nuanced topics lean sparring/scenario-application.
_DEFAULTS_BY_CONTENT_TYPE: dict[ContentType, list[LearningMethod]] = {
    ContentType.skill: [
        LearningMethod.ship_it,
        LearningMethod.error_hunt,
        LearningMethod.rapid_recall,
        LearningMethod.scenario_application,
    ],
    ContentType.conceptual: [
        LearningMethod.sparring,
        LearningMethod.scenario_application,
        LearningMethod.analogy_builder,
        LearningMethod.teach_it_back,
    ],
    ContentType.mixed: [
        LearningMethod.teach_it_back,
        LearningMethod.scenario_application,
        LearningMethod.error_hunt,
        LearningMethod.eli5,
        LearningMethod.rapid_recall,
        LearningMethod.analogy_builder,
    ],
}


def select_method(db: Session, module: Module) -> LearningMethod:
    """Weighted-random pick among the content type's candidate methods. Weights start at 1.0
    and are nudged over time by monitor-agent-approved proposals — this is what gives the
    rotation its "nudged by what works for this user" behavior instead of pure round-robin."""
    candidates = _DEFAULTS_BY_CONTENT_TYPE[module.content_type]
    profiles = {
        p.method: p
        for p in db.query(LearnerProfile).filter(
            LearnerProfile.content_type == module.content_type,
            LearnerProfile.method.in_(candidates),
        )
    }
    weights = [profiles[m].weight if m in profiles else 1.0 for m in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def _digest_text(module: Module) -> str:
    return read_digest(module.digest_path) or "(no digest available)"


def opening_prompt(module: Module, method: LearningMethod) -> str:
    """Generates the agent's first message for a session, grounded in the module's digest."""
    digest = _digest_text(module)
    instructions = {
        LearningMethod.teach_it_back: (
            "Ask the learner to explain this module's core concept to you in their own words. "
            "Tell them you'll play dumb and poke holes in whatever they say — don't grade yet, "
            "just set up the exercise and ask them to begin."
        ),
        LearningMethod.sparring: (
            "Pick one substantive, arguable claim from this module. State a wrong or contrarian "
            "position on it confidently, as if you believe it, and challenge the learner to argue "
            "you out of it. Don't reveal you're wrong — commit to the position."
        ),
        LearningMethod.ship_it: (
            "Give the learner a concrete task to produce a real artifact demonstrating this "
            "module's skill (for code: something you can actually run and check the output of). "
            "State the exact requirements and what a correct result looks like."
        ),
        LearningMethod.analogy_builder: (
            "Ask the learner to explain this module's core concept using an analogy to something "
            "unrelated and familiar. Ask them to be specific about how the analogy maps to the "
            "real concept, part by part."
        ),
        LearningMethod.error_hunt: (
            "Write a short explanation or solution related to this module that contains one "
            "clear, meaningful factual or logical error. Present it as if it were correct and "
            "ask the learner to find the mistake."
        ),
        LearningMethod.eli5: (
            "Ask the learner to explain this module's core concept in the simplest possible terms, "
            "as if to a five-year-old — no jargon."
        ),
        LearningMethod.scenario_application: (
            "Invent a novel, concrete scenario (not from the digest) where this module's concept "
            "applies. Ask the learner to work through how they'd apply it in that scenario."
        ),
        LearningMethod.rapid_recall: (
            "Ask one quick, specific retrieval-practice question about a key fact or definition "
            "from this module. Keep it short — this is a low-stakes rep, not an essay prompt."
        ),
    }
    system = (
        "You are a learning coach running an active-learning exercise. Ground everything in the "
        "reference digest below — don't invent facts that contradict it. Be direct and concise; "
        "this is the opening prompt for the exercise, not a lecture. Keep the exercise itself "
        "tightly scoped: state one clear task in a few sentences. Do not turn it into a multi-part "
        "checklist, a numbered list of mandatory requirements, or a formal rubric with named "
        "constraints — grading happens separately, after the fact; the learner should be able to "
        "give a genuine first-pass answer in a paragraph or two, not write an audit response."
    )
    prompt = (
        f"Module: {module.title} — {module.one_liner}\n\n"
        f"Reference digest:\n{digest}\n\n"
        f"Learner's chosen depth: {_DEPTH_INSTRUCTIONS[module.topic.depth]}\n\n"
        f"Exercise: {_METHOD_LABELS[method]}. {instructions[method]}\n\n"
        "Write only the message the learner will see — no meta-commentary."
    )
    return ai.plain_call(system=system, user_prompt=prompt, max_tokens=1500, effort="medium")


def followup_prompt(module: Module, method: LearningMethod, transcript: list[tuple[str, str]]) -> str:
    """Generates the agent's next turn in an interactive (sparring / teach-it-back) exchange."""
    digest = _digest_text(module)
    convo = "\n\n".join(f"{role.upper()}: {content}" for role, content in transcript)
    stance = {
        LearningMethod.sparring: (
            "Stay in character as the contrarian position — push back on their argument with your "
            "next-strongest counter-point, or if they've genuinely dismantled your position, concede "
            "clearly and say what convinced you."
        ),
        LearningMethod.teach_it_back: (
            "Play dumb: poke a real hole in their explanation, or ask a clarifying question that "
            "exposes a gap, based on the reference digest."
        ),
    }[method]
    system = (
        "You are continuing an active-learning exercise. Ground everything in the reference digest — "
        "don't invent facts that contradict it."
    )
    prompt = (
        f"Module: {module.title} — {module.one_liner}\n\nReference digest:\n{digest}\n\n"
        f"Exercise: {_METHOD_LABELS[method]}.\n\nTranscript so far:\n{convo}\n\n"
        f"{stance}\n\nWrite only the message the learner will see."
    )
    return ai.plain_call(system=system, user_prompt=prompt, max_tokens=1200, effort="medium")


def method_label(method: LearningMethod) -> str:
    return _METHOD_LABELS[method]
