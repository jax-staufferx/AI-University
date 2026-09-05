"""The adaptive lesson: generated once, right after a learner first passes a module's quiz.
Goes over each concept the quiz covered with more examples and clearer explanation than the
raw digest, weighted by what the quiz showed — a missed easy question is a real gap and gets
heavy re-teaching; a missed hard question was expected to be hard and gets a lighter touch;
anything answered correctly gets brief reinforcement, not a repeat lecture. This is prep for
the 8 active-recall methods, not a replacement for them.
"""

import json

from sqlalchemy.orm import Session

from app.models import Module
from app.schemas import QuizSubmitResult, SlideshowOut, SlideshowSlideOut
from app.services import anthropic_client as ai
from app.services import budget
from app.services.research import _DEPTH_INSTRUCTIONS, read_digest

_SLIDESHOW_SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "difficulty": {"type": "integer"},
                    "emphasis": {"type": "string", "enum": ["light", "moderate", "heavy"]},
                    "content": {
                        "type": "string",
                        "description": (
                            "The teaching content for this slide — clearer and more "
                            "example-driven than the raw digest. Size it to the emphasis: "
                            "heavy means thorough with multiple examples and a plain-language "
                            "walkthrough; light means a brief reinforcement, a sentence or two."
                        ),
                    },
                    "examples": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["concept", "difficulty", "emphasis", "content", "examples"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["slides"],
    "additionalProperties": False,
}


def generate_slideshow(db: Session, module: Module, quiz_result: QuizSubmitResult) -> None:
    if module.slideshow_json:
        return  # already generated — a one-time lesson, not regenerated on every pass

    digest = read_digest(module.digest_path) or "(no digest available)"
    depth = module.topic.depth
    performance_summary = "\n".join(
        f"- {r.concept} (difficulty {r.difficulty}/10): "
        f"{'answered correctly' if r.correct else 'answered incorrectly'}"
        for r in quiz_result.results
    )

    budget.check_and_increment(db, module.topic_id)
    result = ai.structured_call(
        system=(
            "You build an adaptive teaching slideshow — the instructional step between reading "
            "a research digest and doing active-recall practice on it. One slide per concept the "
            "quiz covered. Weight emphasis by the quiz performance given: missing an EASY "
            "question (low difficulty) is the bigger red flag — it means a real gap — so give it "
            "heavy emphasis with multiple concrete examples and a clear walkthrough. Missing a "
            "HARD question was expected to be hard, so give it moderate emphasis at most. "
            "Anything answered correctly gets light treatment — brief reinforcement, not a "
            "repeat lecture, even if it was a hard question they got right. This slideshow "
            "prepares the learner for practice exercises afterward — it should make the "
            "material click, not just restate the digest in different words. Match the "
            "learner's chosen depth: " + _DEPTH_INSTRUCTIONS[depth]
        ),
        user_prompt=(
            f"Module: {module.title} — {module.one_liner}\n\nDigest:\n{digest}\n\n"
            f"Quiz performance by concept:\n{performance_summary}\n\n"
            "Build the slideshow now."
        ),
        schema=_SLIDESHOW_SCHEMA,
        max_tokens=6000,
        effort="medium",
    )

    module.slideshow_json = json.dumps({"slides": result.get("slides") or []})
    db.commit()


def get_slideshow_for_frontend(module: Module) -> SlideshowOut:
    stored = json.loads(module.slideshow_json or '{"slides": []}')
    slides = [
        SlideshowSlideOut(
            concept=s["concept"],
            difficulty=s["difficulty"],
            emphasis=s["emphasis"],
            content=s["content"],
            examples=s.get("examples") or [],
        )
        for s in stored["slides"]
    ]
    return SlideshowOut(module_id=module.id, slides=slides)
